"""Twelve-month pilot projection, run in memory on the synthetic population.

Clinicians work through the flagged list at a fixed number of reviews per week. Confirmed
patients consent at the same rate as in the demo, relatives book and test at the same rate,
and each positive relative starts their own cascade. Fixed seeds, so the result is stable.
This is a projection on synthetic data, not a forecast.
"""
from __future__ import annotations

import random
import sqlite3
from collections import defaultdict
from datetime import date

from .cascade import BOOK_RATE, CONSENT_RATE, DETECTION_SENSITIVITY, WELLCHILD_RATE
from .config import DB_PATH, LDL_P95_ADULT, LDL_P95_CHILD, REF_DATE, SEED

WEEKS = 52
REVIEWS_PER_WEEK = 20
TEST_WEEKS = 2       # genetic test turnaround
RESPOND_WEEKS = 2    # invitation to test
WELLCHILD_RETRY = 13


def _roll(*key) -> float:
    return random.Random(f"{SEED}:pilot:" + ":".join(map(str, key))).random()


def run(path=DB_PATH, reviews_per_week: int = REVIEWS_PER_WEEK) -> dict:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    people = {r["id"]: r for r in con.execute(
        "SELECT id, birth_date, death_date, mother_id, father_id, relatives_abroad FROM people")}
    truth = {r[0]: (r[1], r[2], r[3]) for r in con.execute("SELECT person_id, fh, variant, true_ldl FROM truth")}
    scores = list(con.execute("SELECT person_id, dlcn_total, flagged, prob_b FROM scores WHERE flagged=1 "
                              "AND prob_a IS NOT NULL ORDER BY prob_b DESC"))
    screened = con.execute("SELECT COUNT(*) FROM scores WHERE prob_a IS NOT NULL").fetchone()[0]
    con.close()

    kids = defaultdict(list)
    for p in people.values():
        for par in (p["mother_id"], p["father_id"]):
            if par:
                kids[par].append(p["id"])

    def age_at(pid, week):
        d = REF_DATE.toordinal() + week * 7
        return (d - date.fromisoformat(people[pid]["birth_date"]).toordinal()) / 365.25

    def relatives(pid):
        p = people[pid]
        rel = [x for x in (p["mother_id"], p["father_id"]) if x] + kids[pid]
        if p["mother_id"] and p["father_id"]:
            rel += [s for s in kids[p["mother_id"]] if s != pid and people[s]["father_id"] == p["father_id"]]
        return [r for r in dict.fromkeys(rel) if people[r]["death_date"] is None]

    def positive(pid, fam_variant, child):
        fh, variant, ldl = truth[pid]
        if fam_variant:
            return variant == fam_variant
        return ldl >= (LDL_P95_CHILD if child else LDL_P95_ADULT)

    queue = [r["person_id"] for r in scores]
    dlcn = {r["person_id"]: r["dlcn_total"] for r in scores}
    touched: set[int] = set()
    events = defaultdict(list)  # week -> list of (kind, payload)
    months = [defaultdict(int) for _ in range(12)]
    abroad = 0

    def month(w):
        return min(11, int(w * 12 / WEEKS))

    def confirm(pid, w, variant, source):
        m = months[month(w)]
        m[{"detection": "confirmed_detection", "cascade": "relatives_positive", "wellchild": "children_positive"}[source]] += 1
        if source != "wellchild" and _roll(pid, "consent") < CONSENT_RATE:
            events[w + 1].append(("cascade", (pid, variant)))

    for w in range(WEEKS):
        m = months[month(w)]
        # Clinician reviews.
        n = 0
        while queue and n < reviews_per_week:
            pid = queue.pop(0)
            if pid in touched:
                continue
            touched.add(pid)
            n += 1
            m["reviewed"] += 1
            events[w + TEST_WEEKS].append(("result", pid))
        for kind, payload in events.pop(w, []):
            if kind == "result":
                pid = payload
                fh, variant, _ = truth[pid]
                if fh > 0 and _roll(pid, "detect") < DETECTION_SENSITIVITY:
                    confirm(pid, w, variant, "detection")
                elif dlcn.get(pid, 0) >= 6:
                    confirm(pid, w, None, "detection")
            elif kind == "cascade":
                pid, variant = payload
                abroad += people[pid]["relatives_abroad"] or 0
                for r in relatives(pid):
                    if r in touched:
                        continue
                    touched.add(r)
                    if age_at(r, w) < 18:
                        due = max(w + 2, int((2 - age_at(r, w)) * 52) + w)
                        if due < WEEKS:
                            m["children_flagged"] += 1
                            events[due].append(("wellchild", (r, variant, 0)))
                    else:
                        m["invited"] += 1
                        if _roll(r, "book") < BOOK_RATE:
                            events[w + RESPOND_WEEKS].append(("test", (r, variant)))
            elif kind == "test":
                r, variant = payload
                m["tested"] += 1
                if positive(r, variant, False):
                    confirm(r, w, variant, "cascade")
            elif kind == "wellchild":
                r, variant, tries = payload
                if _roll(r, "wellchild", tries) < WELLCHILD_RATE:
                    m["children_tested"] += 1
                    if positive(r, variant, True):
                        confirm(r, w, variant, "wellchild")
                elif w + WELLCHILD_RETRY < WEEKS:
                    events[w + WELLCHILD_RETRY].append(("wellchild", (r, variant, tries + 1)))

    keys = ["reviewed", "confirmed_detection", "invited", "tested", "relatives_positive", "children_flagged",
            "children_tested", "children_positive"]
    series = []
    cum_det = cum_all = 0
    for i, m in enumerate(months):
        cum_det += m["confirmed_detection"]
        cum_all += m["confirmed_detection"] + m["relatives_positive"] + m["children_positive"]
        series.append({"month": i + 1, **{k: m[k] for k in keys}, "cumulative_detection_only": cum_det,
                       "cumulative_with_cascade": cum_all})
    tot = {k: sum(m[k] for m in months) for k in keys}
    found = tot["confirmed_detection"] + tot["relatives_positive"] + tot["children_positive"]
    return {
        "label": "Projection on synthetic data",
        "assumptions": {
            "weeks": WEEKS, "reviews_per_week": reviews_per_week, "detection_test_sensitivity": DETECTION_SENSITIVITY,
            "consent_rate": CONSENT_RATE, "relative_uptake": BOOK_RATE, "wellchild_uptake": WELLCHILD_RATE,
            "test_turnaround_weeks": TEST_WEEKS,
        },
        "totals": {
            "screened": screened, "flagged": len(scores), **tot,
            "uptake": tot["tested"] / tot["invited"] if tot["invited"] else 0.0,
            "found_detection_only": tot["confirmed_detection"],
            "found_with_cascade": found,
            "people_per_detection_case": found / tot["confirmed_detection"] if tot["confirmed_detection"] else 0.0,
            "relatives_abroad_reached_by_letter": abroad,
        },
        "series": series,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run()["totals"], indent=2))
