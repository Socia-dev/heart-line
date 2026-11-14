"""Case state machine, consent, invitations, Well-Child flags and the simulated clock.

Case statuses:
    flagged -> in_review -> test_ordered -> confirmed_genetic
                                         -> no_variant -> clinical_fh (DLCN 6 or more) | dismissed
    flagged | in_review -> dismissed

Nothing reaches a relative until a clinician has confirmed the case and the patient has
consented. Random outcomes are keyed on ids with a fixed seed, so the demo plays out the
same way every time. The `truth` table is read here only to simulate test results.
"""
from __future__ import annotations

import json
import random
import secrets
from datetime import date, timedelta

import joblib
import numpy as np
import pandas as pd

from . import dlcn, features, store
from .config import LDL_P95_ADULT, LDL_P95_CHILD, MODEL_PATH, SEED
from .store import audit, today

CONFIRMED = ("confirmed_genetic", "clinical_fh")
OPEN = ("flagged", "in_review", "test_ordered")

DETECTION_SENSITIVITY = 0.95
BOOK_RATE = 0.60
CONSENT_RATE = 0.85
WELLCHILD_RATE = 0.70
NO_RESPONSE_AFTER = 28  # days

SYSTEM = "Heart Line"
CLINICIAN = "Dr. Clinician (demo)"
COORDINATOR = "Family coordinator (demo)"


class Invalid(ValueError):
    pass


def roll(*key) -> float:
    return random.Random(f"{SEED}:" + ":".join(map(str, key))).random()


def _truth(con, pid: int):
    # Simulation only: the lab "knows" the real answer.
    return con.execute("SELECT fh, variant, true_ldl FROM truth WHERE person_id=?", (pid,)).fetchone()


def get_case(con, case_id: int):
    c = con.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if c is None:
        raise Invalid("No such case")
    return c


def case_for_person(con, pid: int):
    return con.execute("SELECT * FROM cases WHERE person_id=?", (pid,)).fetchone()


def _new_case(con, pid: int, source: str, status: str, index_of: int | None = None, variant: str | None = None) -> int:
    d = today(con).isoformat()
    cur = con.execute("INSERT INTO cases (person_id, source, index_of, status, created_at, updated_at, found_variant) "
                      "VALUES (?,?,?,?,?,?,?)", (pid, source, index_of, status, d, d, variant))
    return cur.lastrowid


def _set_status(con, case_id: int, status: str, **extra):
    cols = {"status": status, "updated_at": today(con).isoformat(), **extra}
    con.execute(f"UPDATE cases SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", (*cols.values(), case_id))


# ------------------------------------------------------------------ setup and reset

def init_cases(con):
    """Turn the screening run's flags into worklist cases."""
    if con.execute("SELECT COUNT(*) FROM cases").fetchone()[0]:
        return
    d = today(con).isoformat()
    rows = list(con.execute("SELECT person_id, prob_b FROM scores WHERE flagged=1 ORDER BY prob_b DESC"))
    con.executemany("INSERT INTO cases (person_id, source, status, created_at, updated_at) VALUES (?,?,?,?,?)",
                    [(r["person_id"], "detection", "flagged", d, d) for r in rows])
    audit(con, SYSTEM, "Screening run", "Routine lipid results", None,
          {"flagged": len(rows), "note": "Scored every person with a lipid panel; flagged above the worklist cut-off."})
    con.executemany(
        "INSERT INTO audit (sim_date, logged_at, actor, action, subject, person_id, detail) "
        "SELECT ?, datetime('now'), ?, 'Flagged', 'case ' || id, person_id, NULL FROM cases WHERE id=?",
        [(d, SYSTEM, cid) for (cid,) in con.execute("SELECT id FROM cases")])
    con.execute("INSERT OR REPLACE INTO sim (key, value) VALUES ('initialized', '1')")
    con.commit()


def reset(con):
    live = [r[0] for r in con.execute("SELECT DISTINCT person_id FROM labs WHERE source='live'")]
    if live:
        con.execute(f"DELETE FROM scores WHERE person_id IN ({','.join('?' * len(live))})", live)
        con.execute("DELETE FROM labs WHERE source='live'")
    for t in store.DEMO_TABLES:
        con.execute(f"DROP TABLE IF EXISTS {t}")
    con.executescript(store.DEMO_SCHEMA)
    con.commit()
    init_cases(con)


# ------------------------------------------------------------------ clinician actions

def review(con, pid: int, action: str, note: str | None = None, actor: str = CLINICIAN) -> dict:
    c = case_for_person(con, pid)
    if c is None:
        raise Invalid("This person has no open case")
    s = c["status"]
    if action == "start_review":
        if s != "flagged":
            raise Invalid(f"Cannot start a review from status {s}")
        _set_status(con, c["id"], "in_review")
        audit(con, actor, "Review started", f"case {c['id']}", pid, note)
    elif action == "order_test":
        if s not in ("flagged", "in_review"):
            raise Invalid(f"Cannot order a test from status {s}")
        due = (today(con) + timedelta(days=14)).isoformat()
        _set_status(con, c["id"], "test_ordered", test_due=due)
        audit(con, actor, "Genetic test ordered", f"case {c['id']}", pid, {"result_due": due, "note": note})
    elif action == "dismiss":
        if s not in ("flagged", "in_review", "no_variant"):
            raise Invalid(f"Cannot dismiss from status {s}")
        _set_status(con, c["id"], "dismissed")
        audit(con, actor, "Dismissed", f"case {c['id']}", pid, note)
    elif action == "mark_clinical":
        if s != "no_variant":
            raise Invalid("Clinical FH can only be recorded after a genetic test finds no variant")
        sc = con.execute("SELECT dlcn_total FROM scores WHERE person_id=?", (pid,)).fetchone()
        if sc is None or sc["dlcn_total"] < 6:
            raise Invalid("Clinical FH needs a DLCN score of 6 or more")
        _set_status(con, c["id"], "clinical_fh")
        audit(con, actor, "Marked as clinical FH", f"case {c['id']}", pid, note)
    else:
        raise Invalid(f"Unknown action {action}")
    con.commit()
    return dict(case_for_person(con, pid))


def record_consent(con, pid: int, consent: bool, actor: str = CLINICIAN) -> dict:
    c = case_for_person(con, pid)
    if c is None or c["status"] not in CONFIRMED:
        raise Invalid("Consent can only be recorded once the case is confirmed")
    con.execute("UPDATE cases SET consent=?, consent_by=?, consent_at=?, updated_at=? WHERE id=?",
                (int(consent), "Patient (recorded by " + actor + ")", today(con).isoformat(), today(con).isoformat(),
                 c["id"]))
    audit(con, actor, "Consent recorded" if consent else "Consent declined", f"case {c['id']}", pid,
          {"consent": bool(consent), "scope": "Invite parents, siblings and adult children; flag children for Well-Child"})
    con.commit()
    return dict(case_for_person(con, pid))


def start_cascade(con, case_id: int, actor: str = COORDINATOR, commit: bool = True) -> dict:
    c = get_case(con, case_id)
    if c["status"] not in CONFIRMED:
        raise Invalid("The case must be confirmed before relatives are contacted")
    if c["consent"] != 1:
        raise Invalid("The patient has not consented to contacting relatives")
    if c["cascade_at"]:
        raise Invalid("The cascade for this case has already started")
    now = today(con)
    index = store.person(con, c["person_id"])
    out = {"invited": 0, "wellchild": 0, "skipped": 0, "abroad": int(index["relatives_abroad"] or 0)}
    for r, rel in store.first_degree(con, c["person_id"]):
        rid = r["id"]
        busy = (con.execute("SELECT 1 FROM cases WHERE person_id=?", (rid,)).fetchone()
                or con.execute("SELECT 1 FROM invitations WHERE person_id=?", (rid,)).fetchone()
                or con.execute("SELECT 1 FROM wellchild WHERE person_id=?", (rid,)).fetchone())
        if busy:
            out["skipped"] += 1
            continue
        if store.age(r["birth_date"], now) < 18:
            two = date.fromisoformat(r["birth_date"]) + timedelta(days=int(365.25 * 2))
            due = max(now + timedelta(days=14), two).isoformat()
            con.execute("INSERT INTO wellchild (person_id, case_id, flagged_at, due_date, status) VALUES (?,?,?,?,?)",
                        (rid, c["id"], now.isoformat(), due, "due"))
            audit(con, actor, "Well-Child flag", f"person {rid}", rid, {"due": due})
            out["wellchild"] += 1
        else:
            token = secrets.token_urlsafe(12)
            con.execute("INSERT INTO invitations (token, person_id, case_id, lang, status, sent_at) VALUES (?,?,?,?,?,?)",
                        (token, rid, c["id"], r["lang"] or "en", "sent", now.isoformat()))
            audit(con, actor, "Invitation sent (mock SMS)", f"person {rid}", rid, {"lang": r["lang"]})
            out["invited"] += 1
    if out["abroad"]:
        con.execute("INSERT INTO family_letters (case_id, relatives_abroad, created_at) VALUES (?,?,?)",
                    (c["id"], out["abroad"], now.isoformat()))
        audit(con, actor, "Family letter prepared", f"case {c['id']}", c["person_id"],
              {"relatives_abroad": out["abroad"]})
    con.execute("UPDATE cases SET cascade_at=? WHERE id=?", (now.isoformat(), c["id"]))
    audit(con, actor, "Cascade started", f"case {c['id']}", c["person_id"], out)
    if commit:
        con.commit()
    return out


def book(con, token: str, slot: str) -> dict:
    inv = con.execute("SELECT * FROM invitations WHERE token=?", (token,)).fetchone()
    if inv is None:
        raise Invalid("Invitation not found")
    if inv["status"] != "sent":
        raise Invalid("This invitation has already been used")
    con.execute("UPDATE invitations SET status='booked', slot=?, booked_at=? WHERE id=?",
                (slot, today(con).isoformat(), inv["id"]))
    audit(con, "Invited relative", "Check booked", f"invitation {inv['id']}", inv["person_id"], {"slot": slot})
    con.commit()
    return {"status": "booked", "slot": slot}


# ------------------------------------------------------------------ simulated time

def _family_variant(con, case_id: int) -> str | None:
    c = get_case(con, case_id)
    return c["found_variant"] if c["status"] == "confirmed_genetic" else None


def _relative_positive(con, pid: int, family_variant: str | None, child: bool) -> bool:
    t = _truth(con, pid)
    if family_variant:  # targeted test for the family's known variant
        return t["variant"] == family_variant
    return t["true_ldl"] >= (LDL_P95_CHILD if child else LDL_P95_ADULT)  # no known variant: LDL cut-off


def _positive_relative(con, pid: int, index_case: int, source: str, auto_cascade: bool) -> int:
    fv = _family_variant(con, index_case)
    cid = _new_case(con, pid, source, "confirmed_genetic" if fv else "clinical_fh", index_case, fv)
    audit(con, SYSTEM, "Confirmed by family test", f"case {cid}", pid,
          {"family_variant": fv, "led_by_case": index_case} if fv else {"basis": "LDL cut-off", "led_by_case": index_case})
    if auto_cascade:
        if roll(pid, "consent") < CONSENT_RATE:
            con.execute("UPDATE cases SET consent=1, consent_by='Patient (recorded by coordinator)', consent_at=? "
                        "WHERE id=?", (today(con).isoformat(), cid))
            audit(con, COORDINATOR, "Consent recorded", f"case {cid}", pid, {"consent": True})
            start_cascade(con, cid, COORDINATOR + ", automatic", commit=False)
        else:
            con.execute("UPDATE cases SET consent=0, consent_by='Patient (recorded by coordinator)', consent_at=? "
                        "WHERE id=?", (today(con).isoformat(), cid))
            audit(con, COORDINATOR, "Consent declined", f"case {cid}", pid, {"consent": False})
    return cid


def advance(con, weeks: int = 2) -> dict:
    start = today(con)
    end = start + timedelta(days=7 * max(1, int(weeks)))
    store.set_day(con, end)
    e = end.isoformat()
    out = {"from": start.isoformat(), "to": e, "test_results": 0, "variants_found": 0, "booked": 0, "tested": 0,
           "relatives_positive": 0, "no_response": 0, "wellchild_tested": 0, "children_positive": 0}

    # Ordered genetic tests come back.
    for c in list(con.execute("SELECT * FROM cases WHERE status='test_ordered' AND test_due<=?", (e,))):
        t = _truth(con, c["person_id"])
        found = t["fh"] > 0 and roll(c["person_id"], "detect") < DETECTION_SENSITIVITY
        if found:
            _set_status(con, c["id"], "confirmed_genetic", found_variant=t["variant"])
            out["variants_found"] += 1
        else:
            _set_status(con, c["id"], "no_variant")
        out["test_results"] += 1
        audit(con, "Genetics lab (mock)", "Genetic test result", f"case {c['id']}", c["person_id"],
              {"result": "Variant found: " + t["variant"] if found else "No disease-causing variant found"})

    # Invitations sent before this step: some book and get tested within it; silence becomes no response.
    s = start.isoformat()
    invs = list(con.execute("SELECT * FROM invitations WHERE (status='booked' AND booked_at<=?) OR "
                            "(status='sent' AND sent_at<=?) ORDER BY id", (s, s)))
    for inv in invs:
        pid = inv["person_id"]
        if inv["status"] == "sent":
            if roll(pid, "book") < BOOK_RATE:
                con.execute("UPDATE invitations SET status='booked', slot='Booked by phone', booked_at=? WHERE id=?",
                            (s, inv["id"]))
                audit(con, "Invited relative", "Check booked", f"invitation {inv['id']}", pid, {"slot": "By phone"})
                out["booked"] += 1
            else:
                if (end - date.fromisoformat(inv["sent_at"])).days >= NO_RESPONSE_AFTER:
                    con.execute("UPDATE invitations SET status='no_response' WHERE id=?", (inv["id"],))
                    audit(con, SYSTEM, "No response", f"invitation {inv['id']}", pid)
                    out["no_response"] += 1
                continue
        positive = _relative_positive(con, pid, _family_variant(con, inv["case_id"]), child=False)
        con.execute("UPDATE invitations SET status=?, tested_at=? WHERE id=?",
                    ("positive" if positive else "negative", e, inv["id"]))
        audit(con, "Lab (mock)", "Relative tested", f"invitation {inv['id']}", pid,
              {"result": "positive" if positive else "negative"})
        out["tested"] += 1
        if positive:
            out["relatives_positive"] += 1
            _positive_relative(con, pid, inv["case_id"], "cascade", auto_cascade=True)

    # Well-Child visits that fall due.
    for w in list(con.execute("SELECT * FROM wellchild WHERE status='due' AND due_date<=? AND flagged_at<=?", (e, s))):
        pid = w["person_id"]
        if roll(pid, "wellchild", w["due_date"]) < WELLCHILD_RATE:
            positive = _relative_positive(con, pid, _family_variant(con, w["case_id"]), child=True)
            con.execute("UPDATE wellchild SET status=?, tested_at=? WHERE id=?",
                        ("tested_positive" if positive else "tested_negative", e, w["id"]))
            audit(con, "Well-Child clinic (mock)", "Child tested", f"person {pid}", pid,
                  {"result": "positive" if positive else "negative"})
            out["wellchild_tested"] += 1
            if positive:
                out["children_positive"] += 1
                _positive_relative(con, pid, w["case_id"], "wellchild", auto_cascade=False)
        else:
            nxt = (date.fromisoformat(w["due_date"]) + timedelta(days=91)).isoformat()
            con.execute("UPDATE wellchild SET due_date=? WHERE id=?", (nxt, w["id"]))
            audit(con, "Well-Child clinic (mock)", "Visit missed, rebooked", f"person {pid}", pid, {"due": nxt})

    audit(con, "Demo", "Time advanced", f"{weeks} weeks", None, out)
    con.commit()
    return out


# ------------------------------------------------------------------ a new result arrives

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = joblib.load(MODEL_PATH)
    return _MODEL


def _candidate(con) -> int:
    """An adult with FH, no lipid results yet and family in the system. Prefers someone whose
    sibling also carries the variant and has a young child, so the chain shows within the demo."""
    now = today(con)
    rows = list(con.execute(
        "SELECT p.id, p.birth_date FROM people p JOIN truth t ON t.person_id=p.id "
        "WHERE t.fh=1 AND t.true_ldl>=7 AND p.death_date IS NULL AND p.mother_id IS NOT NULL AND p.father_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM labs l WHERE l.person_id=p.id) "
        "AND NOT EXISTS (SELECT 1 FROM cases c WHERE c.person_id=p.id) "
        "AND NOT EXISTS (SELECT 1 FROM invitations i WHERE i.person_id=p.id) ORDER BY p.id"))
    best, best_score = None, -1
    for r in rows:
        a = store.age(r["birth_date"], now)
        if not 25 <= a <= 55 or roll(r["id"], "detect") >= DETECTION_SENSITIVITY:
            continue
        rel = store.first_degree(con, r["id"])
        if not rel or any(case_for_person(con, x["id"]) for x, _ in rel):
            continue
        variant = _truth(con, r["id"])["variant"]
        score = 1
        for x, kind in rel:
            if kind not in ("sister", "brother") or _truth(con, x["id"])["variant"] != variant:
                continue
            kids = [k for k in store.children_of(con, x["id"]) if 2 <= store.age(k["birth_date"], now) < 12]
            if roll(x["id"], "book") < BOOK_RATE and roll(x["id"], "consent") < CONSENT_RATE and kids:
                score = 3 if kind == "sister" else 2
        if score > best_score:
            best, best_score = r["id"], score
        if best_score == 3:
            break
    if best is None:
        raise Invalid("No suitable synthetic patient left for a new result")
    return best


def score_person(con, pid: int) -> dict:
    m = _model()
    ids = [pid] + [r["id"] for r, _ in store.first_degree(con, pid, include_deceased=True)]
    q = ",".join("?" * len(ids))
    people = pd.read_sql(f"SELECT * FROM people WHERE id IN ({q})", con, params=ids)
    labs = pd.read_sql(f"SELECT person_id, date, ldl, tc, hdl, tg, on_statin FROM labs WHERE person_id IN ({q})", con,
                       params=ids)
    X = features.build_from(people, labs, only_with_labs=False)
    row = X.loc[pid]
    x = row[m["features"]].to_numpy(dtype=float).reshape(1, -1)
    prob = float(m["model"].predict_proba(x)[0, 1])
    contrib = m["model"].booster_.predict(x, pred_contrib=True)[0]
    reasons = features.top_reasons(row, np.asarray(contrib), m["features"])
    d = dlcn.score(ldl_untreated=row["max_ldl_corr"], premature_cad=bool(row["early_cad"]),
                   xanthoma=bool(row["xanthoma"]), arcus_under_45=bool(row["arcus_u45"]),
                   fhx_premature_cad=bool(row["fhx_cad"]), fhx_high_ldl=bool(row["fhx_ldl"]))
    flagged = int(prob >= m["threshold"])
    con.execute("INSERT OR REPLACE INTO scores VALUES (?,?,?,?,?,?,?,?)",
                (pid, d["total"], d["band"], json.dumps(d["items"]), None, prob, json.dumps(reasons), flagged))
    return {"prob": prob, "flagged": bool(flagged), "reasons": reasons, "dlcn": d}


def ingest_new_result(con) -> dict:
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
    con.execute("INSERT INTO labs (person_id, date, ldl, tc, hdl, tg, on_statin, source) VALUES (?,?,?,?,?,?,?,'live')",
                (pid, now.isoformat(), ldl, round(ldl + hdl + tg / 2.2, 2), hdl, tg, int(on)))
    audit(con, "Lab interface (mock)", "New lipid result", f"person {pid}", pid, {"ldl": ldl})
    s = score_person(con, pid)
    cid = None
    if s["flagged"]:
        cid = _new_case(con, pid, "detection", "flagged")
        audit(con, SYSTEM, "Flagged", f"case {cid}", pid, {"score": round(s["prob"], 3), "reasons": s["reasons"]})
    con.commit()
    return {"person_id": pid, "case_id": cid, "ldl": ldl, **s}
