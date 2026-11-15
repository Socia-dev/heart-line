"""Is the synthetic population realistic? Published figures, each with its source, and the same figures
computed from the synthetic population, so the Model page can show where they agree and where they do not.

Only figures that could be read from the cited source are here. Where no comparable published figure was
found (LDL by age and sex for the UAE, statin use in the general UAE population), the page says so.

This runs at training time, because the FH prevalence needs the `truth` table, which the API never reads.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from .config import REF_DATE

MG = 38.67  # mg/dL per mmol/L for cholesterol
MG_TG = 88.57

SOURCES = {
    "nhanes": {
        "short": "US NHANES 2017 to 2018",
        "cite": "Gao Y, Shah LM, Ding J, Martin SS. US Trends in Cholesterol Screening, Lipid Levels, and "
                "Lipid-Lowering Medication Use in US Adults, 1999 to 2018. J Am Heart Assoc. 2023. "
                "doi:10.1161/JAHA.122.028205",
    },
    "gulf_fh": {
        "short": "Gulf FH Registry",
        "cite": "Alhabib KF, et al. Familial Hypercholesterolemia in the Arabian Gulf Region: Clinical results of the "
                "Gulf FH Registry. PLoS One. 2021. doi:10.1371/journal.pone.0251560",
    },
    "hu_2020": {
        "short": "Global meta-analysis",
        "cite": "Hu P, et al. Prevalence of Familial Hypercholesterolemia Among the General Population and Patients With "
                "Atherosclerotic Cardiovascular Disease: A Systematic Review and Meta-Analysis. Circulation. 2020. "
                "doi:10.1161/CIRCULATIONAHA.119.044795",
    },
}

# Published values. Means in mmol/L, converted from the mg/dL in the source and kept beside it.
PUBLISHED = {
    "ldl_mean": {"value": round(111.7 / MG, 2), "as_published": "111.7 mg/dL", "source": "nhanes",
                 "what": "Mean LDL cholesterol, US adults"},
    "tc_mean": {"value": round(188.4 / MG, 2), "as_published": "188.4 mg/dL", "source": "nhanes",
                "what": "Mean total cholesterol, US adults"},
    "tg_mean": {"value": round(91.4 / MG_TG, 2), "as_published": "91.4 mg/dL", "source": "nhanes",
                "what": "Mean triglycerides, US adults"},
    "clinical_fh": {"value": 112, "as_published": "0.9% (1 in 112) met DLCN probable or definite", "source": "gulf_fh",
                    "what": "Adults screened in Gulf clinics meeting clinical FH criteria"},
    "fh_prevalence": {"value": 311, "as_published": "1 in 311 (95% CI 1 in 250 to 1 in 397)", "source": "hu_2020",
                      "what": "FH in the general population, worldwide"},
}


def synthetic_figures(con: sqlite3.Connection, dlcn_totals: np.ndarray, with_labs: int) -> dict:
    """The same measures, from the synthetic population. Adults are 20 and over, each person's latest
    result from the recorded history (results added live in a demo are left out)."""
    people = pd.read_sql("SELECT id, sex, birth_date FROM people", con).set_index("id")
    labs = pd.read_sql("SELECT person_id, date, ldl, tc, tg, on_statin FROM labs WHERE source IS NULL OR source<>'live' "
                       "ORDER BY date", con)
    latest = labs.groupby("person_id").last()
    latest = latest.join(people)
    age = (pd.Timestamp(REF_DATE) - pd.to_datetime(latest["birth_date"])).dt.days / 365.25
    adults = latest[age >= 20].copy()
    adults["age"] = age[age >= 20]

    def band(a):
        return "20 to 39" if a < 40 else "40 to 59" if a < 60 else "60 and over"
    adults["band"] = adults["age"].map(band)
    by = (adults.groupby(["band", "sex"])["ldl"].agg(["mean", "count"]).round(2).reset_index()
          .rename(columns={"mean": "ldl_mean", "count": "people"}))
    hist_edges = np.arange(0, 10.5, 0.5)
    hist, _ = np.histogram(adults["ldl"].clip(upper=10.0), bins=hist_edges)

    truth = pd.read_sql("SELECT fh FROM truth", con)["fh"]
    n_people = len(truth)
    n_fh = int((truth > 0).sum())
    clinical = int((dlcn_totals >= 6).sum())
    return {
        "ldl_mean": round(float(adults["ldl"].mean()), 2),
        "tc_mean": round(float(adults["tc"].mean()), 2),
        "tg_mean": round(float(adults["tg"].mean()), 2),
        "clinical_fh": round(with_labs / max(clinical, 1)),
        "fh_prevalence": round(n_people / max(n_fh, 1)),
        "adults": int(len(adults)),
        "on_statin_at_latest": round(float(adults["on_statin"].mean()), 3),
        "ldl_by_age_sex": by.to_dict(orient="records"),
        "ldl_histogram": {"edges": hist_edges.tolist(), "counts": hist.tolist()},
    }


def realism(con, dlcn_totals, with_labs) -> dict:
    syn = synthetic_figures(con, dlcn_totals, with_labs)
    rows = []
    for key, pub in PUBLISHED.items():
        s = syn[key]
        if key in ("clinical_fh", "fh_prevalence"):  # "1 in N": smaller N means more common
            ratio = pub["value"] / s
            verdict = "close" if 0.75 <= ratio <= 1.33 else ("more common here" if ratio > 1 else "less common here")
        else:
            ratio = s / pub["value"]
            verdict = "close" if 0.9 <= ratio <= 1.1 else ("higher here" if ratio > 1 else "lower here")
        rows.append({"key": key, "what": pub["what"], "published": pub["value"], "as_published": pub["as_published"],
                     "synthetic": s, "verdict": verdict, "source": pub["source"],
                     "unit": "1 in" if key in ("clinical_fh", "fh_prevalence") else "mmol/L"})
    return {"rows": rows, "sources": SOURCES, "synthetic": syn,
            "notes": [
                "The published lipid means are for US adults. No citable mean LDL for UAE adults by age and sex was found "
                "in this pass, so the age and sex breakdown below has nothing published to compare against.",
                "No comparable published figure for statin use across all UAE adults was found.",
                "FH is more common in this synthetic population than the worldwide estimate on purpose: Emirati founders "
                "are seeded at 1 in 100, following the Gulf registry. The registry figure is clinical criteria among "
                "people screened in clinics, not a genetic prevalence, so it is an upper bound.",
            ]}
