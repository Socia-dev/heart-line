"""The demo's stand-in for the outside world: lab results, relatives' replies, time passing.

In a pilot this file is what gets replaced. It reads the `truth` table to decide what a
test would find, then tells the engine through the same door staff use (cascade.act), as
the lab. It never records a person's decision for them: a relative who tests positive
becomes a case waiting for a clinician to ask about their own family.

Random outcomes are keyed on person ids with a fixed seed, so the demo is repeatable.
"""
from __future__ import annotations

import json
import random
import time
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import numpy as np

from . import cascade, dlcn, live, machine, store
from .config import DB_PATH, LDL_P95_ADULT, LDL_P95_CHILD, SEED
from .machine import Refusal
from .store import audit, today

DETECTION_SENSITIVITY = 0.95   # a genetic test finds the variant this often when one is there
BOOK_RATE = 0.60               # invited relatives who book and attend
CONSENT_RATE = 0.85            # used by the pilot projection only
WELLCHILD_RATE = 0.70          # children tested at the visit they were flagged for
NO_RESPONSE_AFTER = 28         # days


def roll(*key) -> float:
    return random.Random(f"{SEED}:" + ":".join(map(str, key))).random()


def _truth(con, pid: int):
    return con.execute("SELECT fh, variant, true_ldl FROM truth WHERE person_id=?", (pid,)).fetchone()


def _family_variant(con, case_id: int) -> str | None:
    c = cascade.get_case(con, case_id)
    return c["found_variant"] if c["status"] == "confirmed_genetic" else None


def _relative_positive(con, pid: int, family_variant: str | None, child: bool) -> bool:
    t = _truth(con, pid)
    if family_variant:  # targeted test for the family's known variant
        return t["variant"] == family_variant
    return t["true_ldl"] >= (LDL_P95_CHILD if child else LDL_P95_ADULT)  # no known variant: LDL cut-off


def _open_family_case(con, pid: int, index_case: int, source: str) -> int:
    fv = _family_variant(con, index_case)
    return cascade.new_case(con, pid, source, "confirmed_genetic" if fv else "clinical_fh", index_of=index_case,
                            variant=fv, role=machine.LAB, event="Confirmed through family testing",
                            detail={"basis": "Family variant found" if fv else "LDL above the cut-off"})


def advance(con, weeks: int = 2) -> dict:
    start = today(con)
    end = start + timedelta(days=7 * max(1, int(weeks)))
    store.set_day(con, end)
    s, e = start.isoformat(), end.isoformat()
    out = {"from": s, "to": e, "test_results": 0, "variants_found": 0, "booked": 0, "tested": 0,
           "relatives_positive": 0, "no_response": 0, "wellchild_tested": 0, "children_positive": 0}

    # Ordered genetic tests come back. The lab reports through the same door as everyone else.
    for c in list(con.execute("SELECT * FROM cases WHERE status='test_ordered' AND test_due<=?", (e,))):
        t = _truth(con, c["person_id"])
        if t["fh"] > 0 and roll(c["person_id"], "detect") < DETECTION_SENSITIVITY:
            cascade.act(con, c["person_id"], machine.LAB, "result_variant", {"variant": t["variant"]}, commit=False)
            out["variants_found"] += 1
        else:
            cascade.act(con, c["person_id"], machine.LAB, "result_none", commit=False)
        out["test_results"] += 1

    # Invitations sent before this step: some relatives book and attend; silence becomes no response.
    invs = list(con.execute("SELECT * FROM invitations WHERE (status='booked' AND booked_at<=?) OR "
                            "(status IN ('sent','call_requested') AND sent_at<=?) ORDER BY id", (s, s)))
    for inv in invs:
        pid = inv["person_id"]
        if inv["status"] != "booked":
            if roll(pid, "book") < BOOK_RATE or inv["status"] == "call_requested":
                con.execute("UPDATE invitations SET status='booked', slot='Booked by phone', booked_at=? WHERE id=?",
                            (s, inv["id"]))
                audit(con, "relative", "relative_book", "Relative booked a check", person_id=pid,
                      actor="Invited relative", detail={"slot": "By phone"})
                out["booked"] += 1
            else:
                if (end - date.fromisoformat(inv["sent_at"])).days >= NO_RESPONSE_AFTER:
                    con.execute("UPDATE invitations SET status='no_response' WHERE id=?", (inv["id"],))
                    audit(con, machine.SYSTEM, "no_response", "No reply to the invitation after 28 days", person_id=pid)
                    out["no_response"] += 1
                continue
        positive = _relative_positive(con, pid, _family_variant(con, inv["case_id"]), child=False)
        con.execute("UPDATE invitations SET status=?, tested_at=? WHERE id=?",
                    ("positive" if positive else "negative", e, inv["id"]))
        audit(con, machine.LAB, "relative_tested", "Relative tested", person_id=pid,
              detail={"result": "positive" if positive else "clear"})
        out["tested"] += 1
        if positive:
            out["relatives_positive"] += 1
            _open_family_case(con, pid, inv["case_id"], "cascade")

    # Well-Child visits that fall due.
    for w in list(con.execute("SELECT * FROM wellchild WHERE status='due' AND due_date<=? AND flagged_at<=?", (e, s))):
        pid = w["person_id"]
        if roll(pid, "wellchild", w["due_date"]) < WELLCHILD_RATE:
            positive = _relative_positive(con, pid, _family_variant(con, w["case_id"]), child=True)
            con.execute("UPDATE wellchild SET status=?, tested_at=? WHERE id=?",
                        ("tested_positive" if positive else "tested_negative", e, w["id"]))
            audit(con, "nurse", "child_tested", "Child tested at Well-Child", person_id=pid,
                  actor="Well-Child clinic (mock)", detail={"result": "positive" if positive else "clear"})
            out["wellchild_tested"] += 1
            if positive:
                out["children_positive"] += 1
                _open_family_case(con, pid, w["case_id"], "wellchild")
        else:
            nxt = (date.fromisoformat(w["due_date"]) + timedelta(days=91)).isoformat()
            con.execute("UPDATE wellchild SET due_date=? WHERE id=?", (nxt, w["id"]))
            audit(con, "nurse", "visit_missed", "Well-Child visit missed, rebooked", person_id=pid,
                  actor="Well-Child clinic (mock)", detail={"due": nxt})

    audit(con, "demo", "time_advanced", f"Demo: {weeks} weeks passed", actor="Demo", detail=out)
    con.commit()
    return out


# ------------------------------------------------------------------ a new result arrives

@lru_cache(maxsize=4)
def _demo_order(db: str) -> tuple[int, ...]:
    """Synthetic carriers who make a good demo patient, best first. Chosen once per database.

    This reads ground truth on purpose: the demo needs a patient whose result will flag, whose
    test will find the variant, and whose family shows a chain. It is a scripted demo choice,
    not part of the product.
    """
    con = store.connect(db, schema=False)
    rows = list(con.execute(
        "SELECT p.id, p.birth_date FROM people p JOIN truth t ON t.person_id=p.id "
        "WHERE t.fh=1 AND t.true_ldl>=7 AND p.death_date IS NULL AND p.mother_id IS NOT NULL "
        "AND p.father_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM labs l WHERE l.person_id=p.id AND l.source<>'live') "
        "ORDER BY p.id"))
    now = store.today(con)
    ranked = []
    for r in rows:
        a = store.age(r["birth_date"], now)
        if not 25 <= a <= 55 or roll(r["id"], "detect") >= DETECTION_SENSITIVITY:
            continue
        rel = store.first_degree(con, r["id"])
        if not rel:
            continue
        variant = _truth(con, r["id"])["variant"]
        score = 1
        for x, kind in rel:
            if kind in ("sister", "brother") and _truth(con, x["id"])["variant"] == variant \
                    and roll(x["id"], "book") < BOOK_RATE \
                    and any(2 <= store.age(k["birth_date"], now) < 12 for k in store.children_of(con, x["id"])):
                score = max(score, 3 if kind == "sister" else 2)
        ranked.append((-score, r["id"]))
    con.close()
    return tuple(pid for _, pid in sorted(ranked))


def warm():
    try:
        _demo_order(str(DB_PATH))
    except Exception:  # warming is a convenience; the first click will do the work if this fails
        pass


def _candidate(con) -> int:
    for pid in _demo_order(str(DB_PATH)):
        if con.execute("SELECT 1 FROM labs WHERE person_id=?", (pid,)).fetchone():
            continue
        if cascade.case_for_person(con, pid) or con.execute("SELECT 1 FROM invitations WHERE person_id=?", (pid,)).fetchone():
            continue
        if any(cascade.case_for_person(con, x["id"]) for x, _ in store.first_degree(con, pid)):
            continue
        return pid
    raise Refusal("business", "no_demo_patient", "No suitable synthetic patient is left. Reset the demo.")


def score_person(con, pid: int) -> dict:
    """Score one person live with the final linked-family model, and store the result."""
    res, row = live.score_record(con, pid, worklist_text="pending")
    linked = dlcn.score(
        ldl_untreated=row["max_ldl_corr"], premature_cad=bool(row["early_cad"]), xanthoma=bool(row["xanthoma"]),
        arcus_under_45=bool(row["arcus_u45"]), fhx_premature_cad=bool(row["fhx_cad"]) or bool(row["rel_early_cad"]),
        fhx_high_ldl=bool(row["fhx_ldl"]) or row["rel_n_high_ldl"] > 0)
    d = res["dlcn"]
    con.execute(f"INSERT OR REPLACE INTO scores VALUES ({','.join('?' * 13)})",
                (pid, d["total"], d["band"], json.dumps(d["items"]), linked["total"], None, res["prob"], res["calibrated"],
                 res["band"], json.dumps(res["reasons"]), int(res["flagged"]), live.model()["version"],
                 datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return res


def ingest_new_result(con) -> dict:
    """The demo's opening moment: a first cholesterol result arrives for someone with family in the system."""
    pid = _candidate(con)
    p = store.person(con, pid)
    t = _truth(con, pid)
    now = today(con)
    on = p["statin_start"] is not None and p["statin_start"] <= now.isoformat()
    factor = (1 - (0.5 if p["statin_intensity"] == "high" else 0.3)) if on else 1.0
    r = random.Random(f"{SEED}:lab:{pid}")
    ldl = round(t["true_ldl"] * factor * float(np.exp(r.gauss(0, 0.05))), 2)
    hdl = round(max(0.6, r.gauss(1.35 if p["sex"] == "F" else 1.15, 0.2)), 2)
    tg = round(float(np.exp(r.gauss(np.log(1.3), 0.3))), 2)
    t0 = time.perf_counter()
    con.execute("INSERT INTO labs (person_id, date, ldl, tc, hdl, tg, on_statin, source) VALUES (?,?,?,?,?,?,?,'live')",
                (pid, now.isoformat(), ldl, round(ldl + hdl + tg / 2.2, 2), hdl, tg, int(on)))
    received_ms = round((time.perf_counter() - t0) * 1000, 1)
    audit(con, machine.LAB, "lab_result", "New cholesterol result received", person_id=pid,
          actor="Lab interface (mock)", detail={"ldl_mmol_l": ldl})
    s = score_person(con, pid)
    t0 = time.perf_counter()
    cid = None
    if s["flagged"]:
        cid = cascade.new_case(con, pid, "detection", "flagged", detail={"band": s["band"]})
    con.commit()
    # The lab write and the worklist write are timed here; the stages in between come from live.py.
    s["stages"][0].update(output=f"LDL {ldl:.1f} mmol/L from the lab", ms=received_ms)
    s["stages"][-1].update(title="Added to worklist" if cid else "Worklist",
                           output="Added to the clinician's list" if cid else "Not flagged, not added",
                           ms=round((time.perf_counter() - t0) * 1000, 1))
    s["total_ms"] = round(sum(x["ms"] for x in s["stages"]), 1)
    return {"person_id": pid, "case_id": cid, "ldl": ldl, **s}
