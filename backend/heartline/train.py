"""Trains and evaluates the detection models, then writes the scores table.

Four methods are compared, named by what they use:

- DLCN: the standard clinical score, using only family history written in the chart.
- DLCN with linked family: the same score, with family history taken from relatives' own records.
- Heart Line, own record: a model that sees one patient's record.
- Heart Line, linked family: the same model plus what first-degree relatives' records show.

Comparing the first pair and the second pair separates "more data" from "better method".

Five-fold GroupKFold by clan_id keeps families on one side of each split. Scores are
calibrated inside the folds (isotonic regression on inner out-of-fold predictions), so the
calibrated figure for a person never saw that person. All numbers are on synthetic data.

Run: python -m heartline.train
"""
from __future__ import annotations

import json
import sqlite3
import time
import warnings
from datetime import datetime, timezone

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score,
                             roc_curve)
from sklearn.model_selection import GroupKFold

from . import dlcn, features, reference
from pathlib import Path

from .config import DB_PATH, EVAL_PATH, SEED
from .scoring import BANDS, MODEL_VERSION, NOT_FLAGGED, band_for

warnings.filterwarnings("ignore", message="X does not have valid feature names")

PARAMS = dict(n_estimators=300, learning_rate=0.04, num_leaves=15, min_child_samples=25, subsample=0.8,
              subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1)
TARGET_SENS = 0.80
N_BOOT = 200
SMALL_GROUP = 20  # fewer people with FH than this: show the row as too small to read

METHODS = {
    "dlcn": "DLCN score",
    "dlcn_linked": "DLCN with linked family records",
    "own": "Heart Line, own record only",
    "linked": "Heart Line, with linked family records",
}

# Published results, for the Model page. Sources are listed in docs/research/05-evidence-and-judging.md.
PUBLISHED = {
    "note": "Published figures come from real populations at a prevalence of about 1 in 250 unless stated. "
            "Heart Line's figures come from a synthetic population at about 1 in 114 with complete family links "
            "and few FH lookalikes, so they are higher than a real deployment would see.",
    "rows": [
        {"method": "DLCN 6 or more", "source": "Qureshi 2021", "sensitivity": 0.375, "ppv": 0.330},
        {"method": "FAMCAT 1", "source": "Akyea 2020", "sensitivity": 0.775, "ppv": 0.0068},
        {"method": "FAMCAT 2", "source": "Akyea 2020", "sensitivity": 0.694, "ppv": 0.0158},
        {"method": "Gradient boosting", "source": "Akyea 2020", "sensitivity": 0.583, "ppv": 0.053},
        {"method": "FIND FH, against genetic testing", "source": "Gidding 2023", "sensitivity": 0.121, "ppv": 0.059},
    ],
    "review": "Osei et al., JACC: Advances 2024, a scoping review of 14 algorithms across 27 studies.",
}


def model() -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(**PARAMS)


def dlcn_for(row: pd.Series, linked: bool = False) -> dict:
    """DLCN from the chart. With linked=True, family history also comes from relatives' own records."""
    return dlcn.score(
        ldl_untreated=row["max_ldl_corr"], premature_cad=bool(row["early_cad"]), xanthoma=bool(row["xanthoma"]),
        arcus_under_45=bool(row["arcus_u45"]),
        fhx_premature_cad=bool(row["fhx_cad"]) or (linked and bool(row["rel_early_cad"])),
        fhx_high_ldl=bool(row["fhx_ldl"]) or (linked and row["rel_n_high_ldl"] > 0))


def rates(y: np.ndarray, flag: np.ndarray) -> dict:
    tp = int((y & flag).sum())
    n = int(flag.sum())
    return {"flagged": n, "found": tp, "sensitivity": tp / max(int(y.sum()), 1), "ppv": tp / max(n, 1)}


def top_k(s: np.ndarray, k: int) -> np.ndarray:
    flag = np.zeros(len(s), dtype=bool)
    flag[np.argsort(-s, kind="stable")[:k]] = True
    return flag


def interval(fn, n: int, rng: np.random.Generator) -> list[float]:
    """95% bootstrap interval for fn(sample indexes)."""
    vals = []
    for _ in range(N_BOOT):
        v = fn(rng.integers(0, n, n))
        if v is not None and not np.isnan(v):
            vals.append(v)
    if not vals:
        return [0.0, 0.0]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def with_intervals(y: np.ndarray, flag: np.ndarray, rng) -> dict:
    out = rates(y, flag)
    out["sensitivity_ci"] = interval(lambda i: (y[i] & flag[i]).sum() / max(y[i].sum(), 1), len(y), rng)
    out["ppv_ci"] = interval(lambda i: (y[i] & flag[i]).sum() / max(flag[i].sum(), 1), len(y), rng)
    return out


def age_band(a: float) -> str:
    if a < 18:
        return "Under 18"
    if a < 40:
        return "18 to 39"
    if a < 60:
        return "40 to 59"
    return "60 and over"


def cross_validate(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, cols: list[str], folds: int = 5,
                   progress=None, label: str = ""):
    """Outer folds give honest raw scores. Inner folds give the calibrator its training data."""
    raw, cal, fold_of = np.zeros(len(X)), np.zeros(len(X)), np.zeros(len(X), dtype=int)
    contrib = np.zeros((len(X), len(cols) + 1))
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=folds).split(X, y, groups)):
        t0 = time.perf_counter()
        Xtr, ytr = X.iloc[tr][cols], y[tr]
        inner = np.zeros(len(tr))
        for itr, ite in GroupKFold(n_splits=3).split(Xtr, ytr, groups[tr]):
            inner[ite] = model().fit(Xtr.iloc[itr], ytr[itr]).predict_proba(Xtr.iloc[ite])[:, 1]
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(inner, ytr)
        m = model().fit(Xtr, ytr)
        raw[te] = m.predict_proba(X.iloc[te][cols])[:, 1]
        cal[te] = iso.predict(raw[te])
        contrib[te] = m.booster_.predict(X.iloc[te][cols].to_numpy(), pred_contrib=True)
        fold_of[te] = fold
        if progress:
            yt = y[te]
            progress({"kind": "fold", "model": label, "fold": fold + 1, "folds": folds, "people": int(len(te)),
                      "with_fh": int(yt.sum()),
                      "auroc": float(roc_auc_score(yt, raw[te])) if 0 < yt.sum() < len(yt) else None,
                      "auprc": float(average_precision_score(yt, raw[te])) if yt.sum() else None,
                      "seconds": round(time.perf_counter() - t0, 2)})
    return raw, cal, contrib, fold_of


def curve_points(y: np.ndarray, s: np.ndarray, n: int = 120) -> dict:
    """ROC and precision-recall curves, thinned to about n points each for drawing."""
    fpr, tpr, _ = roc_curve(y, s)
    prec, rec, _ = precision_recall_curve(y, s)

    def thin(a, b):
        idx = np.unique(np.linspace(0, len(a) - 1, min(n, len(a))).astype(int))
        return [[round(float(a[i]), 4), round(float(b[i]), 4)] for i in idx]
    return {"roc": thin(fpr, tpr), "pr": thin(rec, prec)}


def train(db_path=None, out_dir: Path | None = None, table: str = "scores", folds: int = 5,
          sample: float | None = None, progress=None) -> dict:
    """Train, evaluate and score. Writes model.joblib and evaluation.json to out_dir and the scores to
    `table`. A quick run (sample < 1) uses a share of families and is labelled as such."""
    started = time.perf_counter()
    out_dir = Path(out_dir or EVAL_PATH.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    say = progress or (lambda e: print(e.get("text") or e))
    rng = np.random.default_rng(SEED)
    con = sqlite3.connect(db_path or DB_PATH)
    say({"kind": "stage", "text": "Building features from the records"})
    X = features.build(con, history_only=True)
    if sample and sample < 1:
        clans = X["clan_id"].unique()
        keep = set(np.random.default_rng(SEED).choice(clans, int(len(clans) * sample), replace=False))
        X = X[X["clan_id"].isin(keep)]
    truth = pd.read_sql("SELECT person_id, fh FROM truth", con).set_index("person_id")["fh"]
    y = (np.asarray(X.index.map(truth)) > 0).astype(int)
    groups = X["clan_id"].to_numpy()
    n = len(X)
    say({"kind": "stage", "text": f"{n} people with a cholesterol result, {int(y.sum())} with FH (synthetic)"})

    raw_own, cal_own, _, _ = cross_validate(X, y, groups, features.FEATURES_A, folds, progress, "own")
    raw, cal, contrib, fold_of = cross_validate(X, y, groups, features.FEATURES_B, folds, progress, "linked")
    say({"kind": "stage", "text": "Comparing methods and checking fairness"})

    d = [dlcn_for(r) for _, r in X.iterrows()]
    d_linked = [dlcn_for(r, linked=True) for _, r in X.iterrows()]
    dl = np.array([x["total"] for x in d])
    dl_linked = np.array([x["total"] for x in d_linked])
    score_of = {"dlcn": dl.astype(float), "dlcn_linked": dl_linked.astype(float), "own": raw_own, "linked": raw}

    metrics = {}
    for key, s in score_of.items():
        fold_auc = [float(roc_auc_score(y[fold_of == f], s[fold_of == f])) for f in range(folds)
                    if 0 < y[fold_of == f].sum() < (fold_of == f).sum()]
        metrics[key] = {
            "name": METHODS[key],
            "auroc": float(roc_auc_score(y, s)), "auprc": float(average_precision_score(y, s)),
            "auroc_ci": interval(lambda i: roc_auc_score(y[i], s[i]) if 0 < y[i].sum() < len(i) else None, n, rng),
            "auprc_ci": interval(lambda i: average_precision_score(y[i], s[i]) if y[i].sum() else None, n, rng),
            "auroc_folds": [min(fold_auc), max(fold_auc)] if fold_auc else [0.0, 0.0],
        }

    # Same workload for every method: as many people as DLCN 6 or more flags.
    k = int((dl >= 6).sum())
    matched = {"flag_count": k, "methods": {
        "dlcn": {"name": METHODS["dlcn"], **with_intervals(y, dl >= 6, rng)},
        **{key: {"name": METHODS[key], **with_intervals(y, top_k(score_of[key], k), rng)}
           for key in ("dlcn_linked", "own", "linked")}}}

    thresholds = []
    for t in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7):
        thresholds.append({"threshold": t, **rates(y, raw >= t)})
    ok = [r for r in thresholds if r["sensitivity"] >= TARGET_SENS]
    chosen = max(ok, key=lambda r: r["threshold"]) if ok else thresholds[0]
    threshold = chosen["threshold"]
    flagged = raw >= threshold
    ok_own = [t for t in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.15, 0.2) if rates(y, raw_own >= t)["sensitivity"] >= TARGET_SENS]
    threshold_own = max(ok_own) if ok_own else 0.02

    curves = {key: curve_points(y, s) for key, s in score_of.items() if key != "dlcn_linked"}
    for key in curves:  # where each method sits at the shared workload
        flag = (dl >= 6) if key == "dlcn" else top_k(score_of[key], k)
        tp = int((y & flag).sum())
        fp = int(flag.sum()) - tp
        curves[key]["point"] = {"fpr": fp / max(int((y == 0).sum()), 1), "tpr": tp / max(int(y.sum()), 1),
                                "precision": tp / max(int(flag.sum()), 1)}

    bands = np.array([band_for(bool(f), float(c)) for f, c in zip(flagged, cal)])
    band_table = []
    for name in [b[0] for b in BANDS] + [NOT_FLAGGED]:
        m = bands == name
        band_table.append({"band": name, "people": int(m.sum()), "with_fh": int(y[m].sum()),
                           "observed_rate": float(y[m].mean()) if m.any() else 0.0})

    edges = [0, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0001]
    curve = []
    for lo, hi in zip(edges, edges[1:]):
        m = (cal >= lo) & (cal < hi)
        if m.sum():
            curve.append({"from": lo, "to": min(hi, 1.0), "people": int(m.sum()), "predicted": float(cal[m].mean()),
                          "observed": float(y[m].mean())})
    calibration = {"method": "Isotonic regression fitted inside each training fold",
                   "brier_raw": float(brier_score_loss(y, raw)), "brier_calibrated": float(brier_score_loss(y, cal)),
                   "curve": curve}

    def fair(col: pd.Series) -> list[dict]:
        rows = []
        for g in sorted(col.unique()):
            m = (col == g).to_numpy()
            yb, fb = y[m], flagged[m]
            pos = int(yb.sum())
            rows.append({
                "group": g, "people": int(m.sum()), "with_fh": pos, "small": pos < SMALL_GROUP,
                "sensitivity": rates(yb, fb)["sensitivity"], "ppv": rates(yb, fb)["ppv"],
                "sensitivity_ci": interval(lambda i: (yb[i] & fb[i]).sum() / yb[i].sum() if yb[i].sum() else None,
                                           len(yb), rng),
                "dlcn_sensitivity": rates(yb, dl[m] >= 6)["sensitivity"]})
        return rows

    fairness = {
        "Sex": fair(X["sex"].map({"M": "Male", "F": "Female"})),
        "Nationality group": fair(X["group"]),
        "Age band": fair(X["age"].map(age_band)),
    }

    # Where it misses: people with FH below the cut-off.
    miss = (y == 1) & ~flagged
    found = (y == 1) & flagged

    def share(mask, cond):
        return float(cond[mask].mean()) if mask.any() else 0.0

    conds = {
        "On a statin": (X["statin_ever"] == 1).to_numpy(),
        "Only one cholesterol result": (X["n_panels"] == 1).to_numpy(),
        "No relatives in the system": (X["rel_n"] == 0).to_numpy(),
        "Highest LDL below 4.9 mmol/L after statin correction": (X["max_ldl_corr"] < 4.9).to_numpy(),
    }
    misses = {"missed": int(miss.sum()), "found": int(found.sum()),
              "rows": [{"what": k_, "among_missed": share(miss, c), "among_found": share(found, c)}
                       for k_, c in conds.items()]}

    n_people = pd.read_sql("SELECT COUNT(*) n FROM people", con)["n"][0]
    evaluation = {
        "synthetic": True,
        "label": "On synthetic data",
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": {"folds": folds, "sample": sample or 1.0, "quick": bool(sample and sample < 1)},
        "realism": reference.realism(con, dl, n),
        "curves": curves,
        "population": {"people": int(n_people), "with_labs": int(n), "with_fh_with_labs": int(y.sum()),
                       "with_fh_total": int((truth > 0).sum())},
        "methods": METHODS,
        "metrics": metrics,
        "matched_workload": matched,
        "thresholds": thresholds,
        "worklist_threshold": {"threshold": threshold, **with_intervals(y, flagged, rng),
                               "why": f"Highest cut-off that still finds at least {int(TARGET_SENS * 100)}% of people "
                                      "with FH among those with a cholesterol result."},
        "bands": band_table,
        "calibration": calibration,
        "fairness": fairness,
        "misses": misses,
        "published": PUBLISHED,
        "model_card": {
            "intended_use": "Flag adults and children with routine lipid results who may have familial "
                            "hypercholesterolaemia, for review by a clinician. It does not diagnose. A clinician "
                            "reviews every flag, and a genetic or clinical test confirms it.",
            "data": "A synthetic population of about 80,000 people shaped like Abu Dhabi: multi-generation Emirati "
                    "families, expatriate households and single workers. No real patient data was used.",
            "features": {"own": features.FEATURES_A, "linked": features.FEATURES_B},
            "family_data_governance": "The linked-family model reads relatives' records. In production the family "
                                      "book could supply these links, but using a relative's data to score someone "
                                      "else needs a legal basis, governance approval and clear patient information.",
            "validation": f"{folds}-fold cross-validation grouped by extended family, so relatives never sit on both "
                          "sides of a split. Scores are calibrated inside the folds. Intervals are 95% bootstrap "
                          f"intervals over {N_BOOT} resamples.",
            "limits": [
                "Synthetic data only. Real-world accuracy will be lower; published models report a PPV of 1% to 15%.",
                "The synthetic world has few people with high cholesterol from other causes, which flatters every "
                "method here.",
                "Family links are complete in this synthetic world; real links will be patchier.",
                "People with no lipid results cannot be flagged at all.",
                "Statin correction uses standard factors and does not know about adherence.",
                "The claim to test on real data is the relative one: linked family records beat one record alone.",
            ],
        },
    }
    # Final models on all data, each with a calibrator fitted on its out-of-fold scores, for live scoring.
    # The own-record model scores numbers typed in by hand, where there are no relatives to link.
    say({"kind": "stage", "text": "Fitting the final models on everyone"})
    final = model().fit(X[features.FEATURES_B], y)
    calibrator = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(raw, y)
    final_own = model().fit(X[features.FEATURES_A], y)
    calibrator_own = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(raw_own, y)
    joblib.dump({"model": final, "features": features.FEATURES_B, "threshold": threshold, "calibrator": calibrator,
                 "version": MODEL_VERSION,
                 "own": {"model": final_own, "features": features.FEATURES_A, "threshold": threshold_own,
                         "calibrator": calibrator_own}}, out_dir / "model.joblib")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for i, (pid, r) in enumerate(X.iterrows()):
        reasons = features.top_reasons(r, contrib[i], features.FEATURES_B)
        rows.append((int(pid), d[i]["total"], d[i]["band"], json.dumps(d[i]["items"]), int(dl_linked[i]),
                     float(raw_own[i]), float(raw[i]), float(cal[i]), bands[i], json.dumps(reasons),
                     int(flagged[i]), MODEL_VERSION, now))
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(SCORES_SCHEMA.replace("TABLE scores", f"TABLE {table}"))
    con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * 13)})", rows)
    con.commit()
    con.close()
    evaluation["train_seconds"] = round(time.perf_counter() - started, 1)
    (out_dir / "evaluation.json").write_text(json.dumps(evaluation, indent=2))
    say({"kind": "done", "seconds": evaluation["train_seconds"], "metrics": metrics})
    return evaluation


def main():
    e = train()
    m = e["matched_workload"]["methods"]
    print(json.dumps({"matched": {k_: (v["found"], round(v["ppv"], 2)) for k_, v in m.items()},
                      "threshold": e["worklist_threshold"]["threshold"], "seconds": e["train_seconds"]}, indent=1))


SCORES_SCHEMA = (
    "CREATE TABLE scores (person_id INTEGER PRIMARY KEY, dlcn_total INTEGER, dlcn_band TEXT, dlcn_items TEXT, "
    "dlcn_linked_total INTEGER, prob_a REAL, prob_b REAL, prob_cal REAL, band TEXT, reasons TEXT, flagged INTEGER, "
    "model_version TEXT, scored_at TEXT)")


if __name__ == "__main__":
    main()
