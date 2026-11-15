"""Per-person feature table for the detection models.

Model A uses only what one patient's own record shows. Model B adds what the records of
linked first-degree relatives show (parents, children, full siblings). Ground truth is never
read here.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from .config import LDL_P95_ADULT, PREMATURE_AGE, REF_DATE
from .dlcn import STATIN_FACTOR

FEATURES_A = [
    "max_ldl_corr", "latest_ldl_corr", "max_ldl_raw", "max_tc", "mean_hdl", "median_tg", "n_panels",
    "age", "male", "statin_ever", "statin_high", "early_cad", "any_cad", "xanthoma", "arcus_u45",
    "fhx_cad", "fhx_ldl",
]
FEATURES_FAMILY = ["rel_n", "rel_max_ldl_corr", "rel_n_high_ldl", "rel_early_cad", "rel_statin_u40"]
FEATURES_B = FEATURES_A + FEATURES_FAMILY

REF = pd.Timestamp(REF_DATE)


def load(con: sqlite3.Connection, history_only: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """history_only leaves out results added live during a demo, so training never learns from them."""
    people = pd.read_sql("SELECT * FROM people", con)
    where = " WHERE source IS NULL OR source<>'live'" if history_only else ""
    labs = pd.read_sql(f"SELECT person_id, date, ldl, tc, hdl, tg, on_statin FROM labs{where}", con)
    return people, labs


def first_degree_edges(people: pd.DataFrame) -> pd.DataFrame:
    """All (person, relative) pairs for parents, children and full siblings."""
    pairs = []
    for col in ("mother_id", "father_id"):
        m = people[people[col].notna()][["id", col]].astype({col: int})
        pairs.append(pd.DataFrame({"pid": m["id"].values, "rid": m[col].values}))  # parent
        pairs.append(pd.DataFrame({"pid": m[col].values, "rid": m["id"].values}))  # child
    both = people[people["mother_id"].notna() & people["father_id"].notna()][["id", "mother_id", "father_id"]]
    sib = both.merge(both, on=["mother_id", "father_id"])
    sib = sib[sib["id_x"] != sib["id_y"]]
    pairs.append(pd.DataFrame({"pid": sib["id_x"].values, "rid": sib["id_y"].values}))
    return pd.concat(pairs, ignore_index=True).drop_duplicates()


def _lab_summary(people: pd.DataFrame, labs: pd.DataFrame) -> pd.DataFrame:
    intensity = people.set_index("id")["statin_intensity"]
    l = labs.copy()
    fac = l["person_id"].map(intensity).map(STATIN_FACTOR).fillna(0.7)
    l["ldl_corr"] = np.where(l["on_statin"] == 1, l["ldl"] / fac, l["ldl"])
    l = l.sort_values(["person_id", "date"])
    g = l.groupby("person_id")
    return pd.DataFrame({
        "max_ldl_corr": g["ldl_corr"].max(),
        "latest_ldl_corr": g["ldl_corr"].last(),
        "max_ldl_raw": g["ldl"].max(),
        "max_tc": g["tc"].max(),
        "mean_hdl": g["hdl"].mean(),
        "median_tg": g["tg"].median(),
        "n_panels": g.size(),
    })


def build(con: sqlite3.Connection, only_with_labs: bool = True, history_only: bool = False) -> pd.DataFrame:
    """Feature table indexed by person id. Includes clan_id, sex and group for splitting and fairness."""
    people, labs = load(con, history_only)
    return build_from(people, labs, only_with_labs)


def build_from(people: pd.DataFrame, labs: pd.DataFrame, only_with_labs: bool = True) -> pd.DataFrame:
    p = people.set_index("id")
    birth = pd.to_datetime(p["birth_date"])
    end = pd.to_datetime(p["death_date"]).fillna(REF)
    age = (end - birth).dt.days / 365.25
    prem = p["sex"].map(PREMATURE_AGE)
    statin_start = pd.to_datetime(p["statin_start"])

    df = pd.DataFrame(index=p.index)
    df["age"] = age.round(1)
    df["male"] = (p["sex"] == "M").astype(int)
    df["statin_ever"] = statin_start.notna().astype(int)
    df["statin_high"] = (p["statin_intensity"] == "high").astype(int)
    df["early_cad"] = (p["cad_age"].notna() & (p["cad_age"] < prem)).astype(int)
    df["any_cad"] = p["cad_age"].notna().astype(int)
    df["xanthoma"] = p["xanthoma"].fillna(0).astype(int)
    df["arcus_u45"] = ((p["arcus"] == 1) & (age < 45)).astype(int)
    df["fhx_cad"] = p["fhx_recorded_cad"].fillna(0).astype(int)
    df["fhx_ldl"] = p["fhx_recorded_ldl"].fillna(0).astype(int)

    lab = _lab_summary(people, labs)
    df = df.join(lab)
    df["n_panels"] = df["n_panels"].fillna(0).astype(int)

    # What linked relatives' records show.
    edges = first_degree_edges(people)
    rel = edges.merge(df[["max_ldl_corr", "early_cad", "age"]], left_on="rid", right_index=True, how="left")
    rel_birth = edges["rid"].map(birth)
    rel["statin_u40"] = ((edges["rid"].map(statin_start) - rel_birth).dt.days / 365.25 < 40).astype(int)
    rel["high"] = (rel["max_ldl_corr"] >= LDL_P95_ADULT).astype(int)
    g = rel.groupby("pid")
    fam = pd.DataFrame({
        "rel_n": g.size(),
        "rel_max_ldl_corr": g["max_ldl_corr"].max(),
        "rel_n_high_ldl": g["high"].sum(),
        "rel_early_cad": g["early_cad"].max(),
        "rel_statin_u40": g["statin_u40"].max(),
    })
    df = df.join(fam)
    for c in ("rel_n", "rel_n_high_ldl", "rel_early_cad", "rel_statin_u40"):
        df[c] = df[c].fillna(0).astype(int)

    df["clan_id"] = p["clan_id"]
    df["sex"] = p["sex"]
    df["group"] = p["nationality_group"]
    if only_with_labs:
        df = df[df["n_panels"] > 0]
    return df


# Plain-language sentences for model reasons. Features that carry no clinical meaning on
# their own (age, sex, number of panels) are left out of the reasons.
def _count_words(n: int) -> str:
    return {1: "One", 2: "Two", 3: "Three", 4: "Four"}.get(n, str(n))


def reason_text(feature: str, v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if feature in ("max_ldl_corr", "latest_ldl_corr", "max_ldl_raw", "rel_max_ldl_corr") and v < 4.0:
        return None
    if feature == "max_tc" and v < 6.5:
        return None
    if feature == "max_ldl_corr":
        return f"Highest LDL about {v:.1f} mmol/L after allowing for statins"
    if feature == "latest_ldl_corr":
        return f"Latest LDL about {v:.1f} mmol/L after allowing for statins"
    if feature == "max_ldl_raw":
        return f"Highest measured LDL {v:.1f} mmol/L"
    if feature == "max_tc":
        return f"Highest total cholesterol {v:.1f} mmol/L"
    if feature == "statin_high" and v:
        return "Already on a high-intensity statin"
    if feature == "statin_ever" and v:
        return "Has been prescribed a statin"
    if feature == "early_cad" and v:
        return "Coronary heart disease at a young age"
    if feature == "any_cad" and v:
        return "Coronary heart disease on record"
    if feature == "xanthoma" and v:
        return "Tendon xanthomas recorded"
    if feature == "arcus_u45" and v:
        return "Corneal arcus before age 45"
    if feature == "fhx_cad" and v:
        return "Family history of early heart disease in the chart"
    if feature == "fhx_ldl" and v:
        return "Family history of high cholesterol in the chart"
    if feature == "rel_n_high_ldl" and v:
        n = int(v)
        return f"{_count_words(n)} close relative{'s' if n > 1 else ''} with very high LDL"
    if feature == "rel_max_ldl_corr":
        return f"A parent, sibling or child has LDL about {v:.1f} mmol/L"
    if feature == "rel_early_cad" and v:
        return "A parent, sibling or child had early heart disease"
    if feature == "rel_statin_u40" and v:
        return "A parent, sibling or child started a statin before 40"
    return None


OWN_LDL = ("max_ldl_corr", "latest_ldl_corr", "max_ldl_raw")


def against_text(feature: str, v) -> str | None:
    """Sentence for something in the record that lowers the score. Missing data is never
    turned into evidence against: unknown is not the same as no."""
    missing = v is None or (isinstance(v, float) and np.isnan(v))
    if feature == "rel_max_ldl_corr":
        return None if missing or v >= 4.9 else f"Highest LDL among close relatives is {v:.1f} mmol/L"
    if missing:
        return None
    if feature in ("max_ldl_corr", "latest_ldl_corr") and v < 4.9:
        which = "Highest" if feature == "max_ldl_corr" else "Latest"
        return f"{which} LDL is {v:.1f} mmol/L, below the usual range for FH"
    if feature == "rel_n_high_ldl" and v == 0:
        return "No close relative with very high LDL on record"
    if feature == "n_panels" and v >= 3:
        return f"{int(v)} cholesterol results on record, so the picture is fairly complete"
    if feature == "age" and v >= 60:
        return "No early heart disease by this age"
    return None


def top_reasons(row: pd.Series, contrib: np.ndarray, features: list[str], k: int = 3, k_against: int = 2) -> list[dict]:
    """Signed reasons from SHAP contributions: up to k for the flag and k_against against it."""
    c = contrib[: len(features)]
    out: list[dict] = []
    for direction, order, limit, text in (("for", np.argsort(-c), k, reason_text),
                                          ("against", np.argsort(c), k_against, against_text)):
        n, own_ldl = 0, False  # the three own-LDL features say much the same thing; keep one
        for i in order:
            if (direction == "for" and c[i] <= 0) or (direction == "against" and c[i] >= 0) or n == limit:
                break
            f = features[i]
            if f in OWN_LDL:
                if own_ldl:
                    continue
                own_ldl = True
            t = text(f, row[f])
            if t and all(t != r["text"] for r in out):
                out.append({"text": t, "direction": direction, "weight": round(float(abs(c[i])), 3), "feature": f})
                n += 1
    return out


def reason_texts(reasons: list, direction: str = "for") -> list[str]:
    return [r["text"] for r in reasons if isinstance(r, dict) and r["direction"] == direction]
