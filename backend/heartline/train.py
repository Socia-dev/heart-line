"""Trains and evaluates the detection models, then writes the scores table.

- Model A: one patient's own record.
- Model B: model A plus linked first-degree relatives' records.
- DLCN: the classic clinical score, using only family history recorded in the chart.

Five-fold GroupKFold by clan_id keeps families on one side of each split. Out-of-fold
predictions are everyone's scores. All numbers are on synthetic data.

Run: python -m heartline.train
"""
from __future__ import annotations

import json
import sqlite3
import warnings

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from . import dlcn, features
from .config import DB_PATH, EVAL_PATH, MODEL_PATH, SEED

warnings.filterwarnings("ignore", message="X does not have valid feature names")

PARAMS = dict(n_estimators=300, learning_rate=0.04, num_leaves=15, min_child_samples=25, subsample=0.8,
              subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1)
TARGET_SENS = 0.80


def model() -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(**PARAMS)


def dlcn_for(row: pd.Series) -> dict:
    return dlcn.score(
        ldl_untreated=row["max_ldl_corr"], premature_cad=bool(row["early_cad"]), xanthoma=bool(row["xanthoma"]),
        arcus_under_45=bool(row["arcus_u45"]), fhx_premature_cad=bool(row["fhx_cad"]),
        fhx_high_ldl=bool(row["fhx_ldl"]))


def at_k(y: np.ndarray, s: np.ndarray, k: int) -> dict:
    idx = np.argsort(-s, kind="stable")[:k]
    tp = int(y[idx].sum())
    return {"flagged": k, "found": tp, "sensitivity": tp / max(int(y.sum()), 1), "ppv": tp / max(k, 1)}


def at_threshold(y: np.ndarray, flag: np.ndarray) -> dict:
    tp = int((y & flag).sum())
    n = int(flag.sum())
    return {"flagged": n, "found": tp, "sensitivity": tp / max(int(y.sum()), 1), "ppv": tp / max(n, 1)}


def age_band(a: float) -> str:
    if a < 18:
        return "Under 18"
    if a < 40:
        return "18 to 39"
    if a < 60:
        return "40 to 59"
    return "60 and over"


def main():
    con = sqlite3.connect(DB_PATH)
    X = features.build(con)
    truth = pd.read_sql("SELECT person_id, fh FROM truth", con).set_index("person_id")["fh"]
    y = (np.asarray(X.index.map(truth)) > 0).astype(int)
    groups = X["clan_id"].to_numpy()
    print(f"{len(X)} people with at least one lipid panel, {y.sum()} with FH (synthetic)")

    oof = {"A": np.zeros(len(X)), "B": np.zeros(len(X))}
    contrib_b = np.zeros((len(X), len(features.FEATURES_B) + 1))
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=5).split(X, y, groups)):
        for name, cols in (("A", features.FEATURES_A), ("B", features.FEATURES_B)):
            m = model().fit(X.iloc[tr][cols], y[tr])
            oof[name][te] = m.predict_proba(X.iloc[te][cols])[:, 1]
            if name == "B":
                contrib_b[te] = m.booster_.predict(X.iloc[te][cols].to_numpy(), pred_contrib=True)
        print(f"fold {fold + 1} done")

    # DLCN, classic version with recorded family history only.
    d = [dlcn_for(r) for _, r in X.iterrows()]
    dl_total = np.array([x["total"] for x in d])

    metrics = {}
    for name, s in (("DLCN", dl_total.astype(float)), ("Model A", oof["A"]), ("Model B", oof["B"])):
        metrics[name] = {"auroc": float(roc_auc_score(y, s)), "auprc": float(average_precision_score(y, s))}

    k = int((dl_total >= 6).sum())
    matched = {
        "flag_count": k,
        "note": "Each method flags the same number of people as DLCN 6 or higher.",
        "DLCN": at_threshold(y, dl_total >= 6),
        "Model A": at_k(y, oof["A"], k),
        "Model B": at_k(y, oof["B"], k),
    }

    thresholds = []
    for t in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7):
        r = at_threshold(y, oof["B"] >= t)
        thresholds.append({"threshold": t, **r})
    ok = [r for r in thresholds if r["sensitivity"] >= TARGET_SENS]
    chosen = max(ok, key=lambda r: r["threshold"]) if ok else thresholds[0]
    threshold = chosen["threshold"]
    flagged = oof["B"] >= threshold

    def fair(col: pd.Series) -> list[dict]:
        rows = []
        for g in sorted(col.unique()):
            m = (col == g).to_numpy()
            yb = y[m]
            rows.append({"group": g, "people": int(m.sum()), "with_fh": int(yb.sum()),
                         "model_b": at_threshold(yb, flagged[m]), "dlcn6": at_threshold(yb, dl_total[m] >= 6)})
        return rows

    fairness = {
        "Sex": fair(X["sex"].map({"M": "Male", "F": "Female"})),
        "Nationality group": fair(X["group"]),
        "Age band": fair(X["age"].map(age_band)),
    }

    n_people = pd.read_sql("SELECT COUNT(*) n FROM people", con)["n"][0]
    n_fh_all = int((truth > 0).sum())
    evaluation = {
        "synthetic": True,
        "label": "On synthetic data",
        "population": {"people": int(n_people), "with_labs": int(len(X)), "with_fh_with_labs": int(y.sum()),
                       "with_fh_total": n_fh_all},
        "metrics": metrics,
        "matched_workload": matched,
        "thresholds": thresholds,
        "worklist_threshold": {"threshold": threshold, **chosen,
                               "why": f"Highest model B cut-off that still finds at least {int(TARGET_SENS * 100)}% "
                                      "of people with FH among those with lipid results."},
        "fairness": fairness,
        "model_card": {
            "intended_use": "Flag adults and children with routine lipid results who may have familial "
                            "hypercholesterolaemia, for review by a clinician. It does not diagnose. A clinician "
                            "reviews every flag, and a genetic or clinical test confirms it.",
            "data": "A synthetic population of about 80,000 people shaped like Abu Dhabi: multi-generation Emirati "
                    "families, expatriate households and single workers. No real patient data was used.",
            "features": {"Model A": features.FEATURES_A, "Model B": features.FEATURES_B},
            "family_data_governance": "Model B reads linked relatives' records. In production the family book could "
                                      "supply these links, but using a relative's data to score someone else needs "
                                      "a legal basis, governance approval and clear patient information first.",
            "validation": "Five-fold cross-validation grouped by extended family, so relatives never sit on both "
                          "sides of a split. Scores shown in the app are out-of-fold.",
            "limits": [
                "Synthetic data only. Performance on real records will differ and must be measured before any use.",
                "People with no lipid results cannot be flagged at all.",
                "Statin correction uses standard factors and does not know about adherence.",
                "Family links are complete in this synthetic world; real links will be patchier.",
                "Recorded family history is sparse, which is realistic but makes DLCN look weaker.",
            ],
        },
    }
    EVAL_PATH.write_text(json.dumps(evaluation, indent=2))

    # Final model on all data, for live scoring of new results.
    final = model().fit(X[features.FEATURES_B], y)
    joblib.dump({"model": final, "features": features.FEATURES_B, "threshold": threshold}, MODEL_PATH)

    rows = []
    for i, (pid, r) in enumerate(X.iterrows()):
        reasons = features.top_reasons(r, contrib_b[i], features.FEATURES_B)
        rows.append((int(pid), d[i]["total"], d[i]["band"], json.dumps(d[i]["items"]), float(oof["A"][i]),
                     float(oof["B"][i]), json.dumps(reasons), int(flagged[i])))
    con.execute("DROP TABLE IF EXISTS scores")
    con.execute("CREATE TABLE scores (person_id INTEGER PRIMARY KEY, dlcn_total INTEGER, dlcn_band TEXT, "
                "dlcn_items TEXT, prob_a REAL, prob_b REAL, reasons TEXT, flagged INTEGER)")
    con.executemany("INSERT INTO scores VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()

    print(json.dumps({"metrics": metrics, "matched_workload": matched,
                      "worklist_threshold": evaluation["worklist_threshold"]}, indent=2))


if __name__ == "__main__":
    main()
