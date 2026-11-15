"""Live scoring, shown step by step.

Every call returns the real output of each stage of the pipeline and how long it took, so the
interface can show the work instead of only the answer:

    received -> record -> features -> model -> clinical -> threshold -> worklist

Two entry points:

- `score_input`: numbers typed in by hand (or one CSV row). There are no relatives to link, so
  this uses the own-record model. Nothing is stored.
- `score_record`: a person in the synthetic population, scored with the linked-family model,
  optionally with some values changed ("what if"). Nothing is stored unless the caller does it.

Neither reads the `truth` table.
"""
from __future__ import annotations

import math
import time

import joblib
import numpy as np
import pandas as pd

from . import dlcn, features, store
from .config import MODEL_PATH, PREMATURE_AGE
from .scoring import band_for

MG_PER_MMOL = {"ldl": 38.67, "tc": 38.67, "hdl": 38.67, "tg": 88.57}
LIMITS = {"ldl": (0.3, 25.0), "tc": (1.0, 30.0), "hdl": (0.1, 5.0), "tg": (0.1, 30.0)}
NAMES = {"ldl": "LDL cholesterol", "tc": "Total cholesterol", "hdl": "HDL cholesterol", "tg": "Triglycerides"}

_MODEL: dict | None = None


def model() -> dict:
    global _MODEL
    if _MODEL is None:
        _MODEL = joblib.load(MODEL_PATH)
    return _MODEL


def reload_model():
    global _MODEL
    _MODEL = None


def warm():
    """Load the model and run one prediction, so the first timed score measures the work, not start-up."""
    try:
        score_input({"ldl": 3.0})
    except Exception:  # warming is a convenience
        pass


class BadInput(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field, self.message = field, message


# ------------------------------------------------------------------ plain labels for the why-chart

def label(feature: str, v) -> str:
    """One feature and its value in words."""
    missing = v is None or (isinstance(v, float) and math.isnan(v))
    yes = bool(v) and not missing
    return {
        "max_ldl_corr": f"Highest LDL {v:.1f} mmol/L, allowing for statins" if not missing else "No LDL result",
        "latest_ldl_corr": f"Latest LDL {v:.1f} mmol/L, allowing for statins" if not missing else "No LDL result",
        "max_ldl_raw": f"Highest measured LDL {v:.1f} mmol/L" if not missing else "No LDL result",
        "max_tc": f"Highest total cholesterol {v:.1f} mmol/L" if not missing else "No total cholesterol",
        "mean_hdl": f"HDL {v:.1f} mmol/L" if not missing else "No HDL result",
        "median_tg": f"Triglycerides {v:.1f} mmol/L" if not missing else "No triglycerides",
        "n_panels": f"{int(v)} cholesterol result{'s' if v != 1 else ''} on record" if not missing else "No results",
        "age": f"Age {int(v)}" if not missing else "Age unknown",
        "male": "Male" if yes else "Female",
        "statin_ever": "Has been on a statin" if yes else "Never on a statin",
        "statin_high": "High-intensity statin" if yes else "No high-intensity statin",
        "early_cad": "Early heart disease" if yes else "No early heart disease",
        "any_cad": "Heart disease on record" if yes else "No heart disease on record",
        "xanthoma": "Tendon xanthomas" if yes else "No tendon xanthomas recorded",
        "arcus_u45": "Corneal arcus before 45" if yes else "No corneal arcus before 45",
        "fhx_cad": "Family history of early heart disease" if yes else "No family history of early heart disease noted",
        "fhx_ldl": "Family history of high cholesterol" if yes else "No family history of high cholesterol noted",
        "rel_n": f"{int(v)} close relatives linked" if not missing else "No relatives linked",
        "rel_max_ldl_corr": f"Highest LDL among close relatives {v:.1f} mmol/L" if not missing else "No relative has a result",
        "rel_n_high_ldl": f"{int(v)} close relative{'s' if v != 1 else ''} with very high LDL" if not missing else "",
        "rel_early_cad": "A close relative had early heart disease" if yes else "No close relative with early heart disease",
        "rel_statin_u40": "A close relative started a statin before 40" if yes else "No relative on a statin before 40",
    }.get(feature, feature)


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def waterfall(row: pd.Series, contrib: np.ndarray, feats: list[str], top: int = 6) -> dict:
    """From the starting point (the average person), add each feature's push, end at this person.
    Values are in the model's own log-odds units; the start and end are also given as probabilities."""
    c = contrib[: len(feats)]
    base = float(contrib[-1])
    # The three measures of a person's own LDL say one thing; show them as one step.
    groups: dict[str, float] = {}
    for f, v in zip(feats, c):
        k = "max_ldl_corr" if f in features.OWN_LDL else f
        groups[k] = groups.get(k, 0.0) + float(v)
    order = sorted(groups, key=lambda k: -abs(groups[k]))
    steps = []
    for k in order[:top]:
        steps.append({"feature": k, "label": label(k, row[k]), "value": round(groups[k], 4), "raises": groups[k] > 0})
    rest = sum(groups[k] for k in order[top:])
    if abs(rest) > 1e-6:
        steps.append({"feature": "other", "label": f"{len(order) - top} other factors together", "value": round(rest, 4),
                      "raises": rest > 0})
    end = base + float(c.sum())
    return {"base": round(base, 4), "base_prob": sigmoid(base), "end": round(end, 4), "end_prob": sigmoid(end),
            "steps": steps}


# ------------------------------------------------------------------ the pipeline

class Clock:
    """Times each stage and keeps what it produced."""

    def __init__(self):
        self.stages: list[dict] = []
        self.t = time.perf_counter()

    def done(self, key: str, title: str, output: str, detail=None):
        now = time.perf_counter()
        self.stages.append({"key": key, "title": title, "output": output, "detail": detail,
                            "ms": round((now - self.t) * 1000, 1)})
        self.t = now


def _finish(clk: Clock, row: pd.Series, m: dict, kind: str, worklist_text: str | None) -> dict:
    feats = m["features"]
    x = row[feats].to_numpy(dtype=float).reshape(1, -1)
    clk.done("features", "Features computed", f"{len(feats)} features",
             [{"feature": f, "label": label(f, row[f]), "value": None if pd.isna(row[f]) else float(row[f])} for f in feats])

    prob = float(m["model"].predict_proba(x)[0, 1])
    cal = float(m["calibrator"].predict([prob])[0])
    contrib = np.asarray(m["model"].booster_.predict(x, pred_contrib=True)[0])
    clk.done("model", "Model scored", f"Score {prob:.2f}",
             {"model": "Own-record model" if kind == "own" else "Linked-family model", "raw": prob, "calibrated": cal})

    d = dlcn.score(ldl_untreated=None if pd.isna(row["max_ldl_corr"]) else float(row["max_ldl_corr"]),
                   premature_cad=bool(row["early_cad"]), xanthoma=bool(row["xanthoma"]),
                   arcus_under_45=bool(row["arcus_u45"]), fhx_premature_cad=bool(row["fhx_cad"]),
                   fhx_high_ldl=bool(row["fhx_ldl"]))
    clk.done("clinical", "Clinical score", f"DLCN {d['total']}, {d['band'].lower()}", d)

    flagged = prob >= m["threshold"]
    band = band_for(flagged, cal)
    clk.done("threshold", "Threshold check",
             f"{'Above' if flagged else 'Below'} the {m['threshold']:.2f} cut-off", {"threshold": m["threshold"]})

    clk.done("worklist", "Added to worklist" if worklist_text is None else "Worklist",
             worklist_text or ("Flagged for clinical review" if flagged else "Not flagged"))
    return {"model": kind, "prob": prob, "calibrated": cal, "band": band, "flagged": bool(flagged),
            "threshold": m["threshold"], "dlcn": d, "reasons": features.top_reasons(row, contrib, feats),
            "why": waterfall(row, contrib, feats), "stages": clk.stages,
            "total_ms": round(sum(s["ms"] for s in clk.stages), 1)}


def _num(v, field: str, required=False):
    if v in (None, ""):
        if required:
            raise BadInput(field, f"{NAMES.get(field, field)} is needed.")
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise BadInput(field, f"{NAMES.get(field, field)} must be a number.")


def clean_panel(panel: dict) -> dict:
    """Validate one lipid panel and convert it to mmol/L."""
    unit = (panel.get("unit") or "mmol").lower()
    if unit not in ("mmol", "mgdl"):
        raise BadInput("unit", "Units must be mmol/L or mg/dL.")
    out = {}
    for f in ("ldl", "tc", "hdl", "tg"):
        v = _num(panel.get(f), f, required=f == "ldl")
        if v is None:
            continue
        if unit == "mgdl":
            v = v / MG_PER_MMOL[f]
        lo, hi = LIMITS[f]
        if not lo <= v <= hi:
            shown = f"{lo * MG_PER_MMOL[f]:.0f} and {hi * MG_PER_MMOL[f]:.0f} mg/dL" if unit == "mgdl" else f"{lo} and {hi} mmol/L"
            raise BadInput(f, f"{NAMES[f]} should be between {shown}.")
        out[f] = round(v, 2)
    return out


def score_input(panel: dict, context: dict | None = None) -> dict:
    """Score one panel typed in by hand. Uses the own-record model; stores nothing."""
    m = model().get("own")
    if m is None:
        raise BadInput("model", "The own-record model is missing. Run python -m heartline.train.")
    clk = Clock()
    p = clean_panel(panel)
    c = context or {}
    age = _num(c.get("age"), "age")
    if age is not None and not 2 <= age <= 100:
        raise BadInput("age", "Age should be between 2 and 100.")
    clk.done("received", "Result received", f"LDL {p['ldl']:.1f} mmol/L", p)

    statin = c.get("statin") or "none"
    if statin not in ("none", "moderate", "high"):
        raise BadInput("statin", "Statin must be none, moderate or high.")
    on = statin != "none"
    ldl_u = dlcn.untreated(p["ldl"], on, statin if on else None)
    sex = (c.get("sex") or "F").upper()[:1]
    age = age if age is not None else 40.0
    early = bool(c.get("early_cad"))
    row = pd.Series({
        "max_ldl_corr": ldl_u, "latest_ldl_corr": ldl_u, "max_ldl_raw": p["ldl"],
        "max_tc": p.get("tc", np.nan), "mean_hdl": p.get("hdl", np.nan), "median_tg": p.get("tg", np.nan),
        "n_panels": 1, "age": age, "male": int(sex == "M"), "statin_ever": int(on), "statin_high": int(statin == "high"),
        "early_cad": int(early), "any_cad": int(early or bool(c.get("any_cad"))), "xanthoma": int(bool(c.get("xanthoma"))),
        "arcus_u45": int(bool(c.get("arcus")) and age < 45), "fhx_cad": int(bool(c.get("fhx_cad"))),
        "fhx_ldl": int(bool(c.get("fhx_ldl"))),
    }, dtype=float)
    clk.done("record", "Record pulled", "Typed in, no linked relatives",
             {"age": age, "sex": sex, "statin": statin, "note": "Nothing typed in is stored."})
    return _finish(clk, row, m, "own", "Not stored. A real result above the cut-off would join the worklist.")


OVERRIDES = {"ldl", "age", "statin", "early_cad", "xanthoma", "arcus", "fhx_cad", "fhx_ldl"}


def score_record(con, pid: int, overrides: dict | None = None, worklist_text: str | None = None) -> tuple[dict, pd.Series]:
    """Score a person in the population with the linked-family model, optionally changing some values.
    Returns the result and the feature row (so the caller can store it)."""
    m = model()
    clk = Clock()
    p = store.person(con, pid)
    if p is None:
        raise BadInput("person", "No such person.")
    last = con.execute("SELECT ldl, date FROM labs WHERE person_id=? ORDER BY date DESC LIMIT 1", (pid,)).fetchone()
    clk.done("received", "Result received", f"LDL {last['ldl']:.1f} mmol/L on {last['date']}" if last else "No result yet")

    ids = [pid] + [r["id"] for r, _ in store.first_degree(con, pid, include_deceased=True)]
    q = ",".join("?" * len(ids))
    people = pd.read_sql(f"SELECT * FROM people WHERE id IN ({q})", con, params=ids)
    labs = pd.read_sql(f"SELECT person_id, date, ldl, tc, hdl, tg, on_statin FROM labs WHERE person_id IN ({q})", con,
                       params=ids)
    with_results = labs["person_id"].nunique() - int(pid in set(labs["person_id"]))
    clk.done("record", "Record pulled", f"{len(ids) - 1} close relatives linked, {with_results} with results",
             {"relatives": len(ids) - 1, "relatives_with_results": int(with_results), "panels": int((labs["person_id"] == pid).sum())})

    row = features.build_from(people, labs, only_with_labs=False).loc[pid].copy()
    o = {k: v for k, v in (overrides or {}).items() if k in OVERRIDES and v is not None}
    if o:
        if "statin" in o:
            row["statin_ever"] = int(o["statin"] != "none")
            row["statin_high"] = int(o["statin"] == "high")
        if "ldl" in o:  # the slider sets the untreated LDL
            row["max_ldl_corr"] = row["latest_ldl_corr"] = float(o["ldl"])
            factor = dlcn.STATIN_FACTOR.get("high" if row["statin_high"] else "moderate", 0.7) if row["statin_ever"] else 1
            row["max_ldl_raw"] = float(o["ldl"]) * factor
        if "age" in o:
            row["age"] = float(o["age"])
        for k in ("early_cad", "xanthoma", "fhx_cad", "fhx_ldl"):
            if k in o:
                row[k] = int(bool(o[k]))
        if "early_cad" in o and o["early_cad"]:
            row["any_cad"] = 1
        if "arcus" in o:
            row["arcus_u45"] = int(bool(o["arcus"]) and row["age"] < 45)
    return _finish(clk, row, m, "linked", worklist_text), row


def record_inputs(con, pid: int) -> dict:
    """The person's real values in the shape the what-if panel uses, so it can start from (and reset to) them."""
    p = store.person(con, pid)
    _, row = score_record(con, pid)
    return {"ldl": None if pd.isna(row["max_ldl_corr"]) else round(float(row["max_ldl_corr"]), 1),
            "age": int(row["age"]), "statin": "high" if row["statin_high"] else ("moderate" if row["statin_ever"] else "none"),
            "early_cad": bool(row["early_cad"]), "xanthoma": bool(row["xanthoma"]),
            "arcus": bool(p["arcus"]), "fhx_cad": bool(row["fhx_cad"]), "fhx_ldl": bool(row["fhx_ldl"]),
            "premature_age": PREMATURE_AGE[p["sex"]]}
