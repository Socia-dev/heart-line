"""Applies workflow decisions to the database: cases, consent, invitations and Well-Child flags.

The rules live in machine.py. This module loads a case, asks the machine, writes the
result and the audit row in one transaction. Nothing here invents an outcome; simulated
lab results, bookings and the passing of time are in simulate.py.
"""
from __future__ import annotations

import json
import secrets
from datetime import date, timedelta

from . import machine, store
from .machine import CONFIRMED, OPEN, Refusal  # noqa: F401  (re-exported for callers)
from .store import audit, today

INVITE_VALID_DAYS = 60
TEST_TURNAROUND_DAYS = 14

SMS = {
    "en": "Abu Dhabi family health programme: {given}, you are invited to a free cholesterol check. "
          "It takes 10 minutes. Choose a time: {link}",
    "ar": "برنامج صحة الأسرة في أبوظبي: {given}، ندعوك لإجراء فحص كوليسترول مجاني يستغرق 10 دقائق. "
          "اختر الموعد المناسب: {link}",
}


def sms_text(lang: str, given: str, token: str = "…") -> str:
    return SMS.get(lang, SMS["en"]).format(given=given, link=f"heartline.example/i/{token}")


# ------------------------------------------------------------------ loading

def get_case(con, case_id: int):
    c = con.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if c is None:
        raise Refusal("not_found", "case_not_found", "No such case.")
    return c


def case_for_person(con, pid: int):
    return con.execute("SELECT * FROM cases WHERE person_id=?", (pid,)).fetchone()


def facts(con, case) -> dict:
    """A case as the machine sees it: the row plus the few outside facts its guards read."""
    c = dict(case)
    sc = con.execute("SELECT dlcn_total FROM scores WHERE person_id=?", (c["person_id"],)).fetchone()
    c["dlcn_total"] = sc["dlcn_total"] if sc else None
    c["consent_excluded"] = json.loads(c["consent_excluded"] or "[]")
    return c


def new_case(con, pid: int, source: str, status: str, *, index_of: int | None = None, variant: str | None = None,
             role: str = machine.SYSTEM, event: str = "Flagged by screening", detail: dict | None = None) -> int:
    d = today(con).isoformat()
    root = None
    if index_of:
        parent = get_case(con, index_of)
        root = parent["family_root"] or parent["id"]
    cur = con.execute("INSERT INTO cases (person_id, source, index_of, family_root, status, created_at, updated_at, "
                      "found_variant) VALUES (?,?,?,?,?,?,?,?)", (pid, source, index_of, root, status, d, d, variant))
    audit(con, role, "case_opened", event, case_id=cur.lastrowid, person_id=pid, to_status=status, detail=detail)
    return cur.lastrowid


# ------------------------------------------------------------------ setup and reset

def init_cases(con):
    """Turn the screening run's flags into worklist cases."""
    if con.execute("SELECT COUNT(*) FROM cases").fetchone()[0]:
        return
    d = today(con).isoformat()
    rows = list(con.execute("SELECT person_id FROM scores WHERE flagged=1 ORDER BY prob_b DESC"))
    con.executemany("INSERT INTO cases (person_id, source, status, created_at, updated_at) VALUES (?,?,?,?,?)",
                    [(r["person_id"], "detection", "flagged", d, d) for r in rows])
    audit(con, machine.SYSTEM, "screening_run", f"Screening run: {len(rows)} people flagged",
          detail={"flagged": len(rows)})
    con.execute(
        "INSERT INTO audit (sim_date, logged_at, actor, actor_role, action_key, action, case_id, person_id, to_status) "
        "SELECT ?, datetime('now'), ?, ?, 'case_opened', 'Flagged by screening', id, person_id, 'flagged' FROM cases",
        (d, machine.ACTOR_NAME[machine.SYSTEM], machine.SYSTEM))
    con.execute("INSERT OR REPLACE INTO sim (key, value) VALUES ('initialized', '2')")
    con.commit()


def reset(con):
    """Demo reset: clears cases, contact and the audit log, and removes results added live."""
    live = [r[0] for r in con.execute("SELECT DISTINCT person_id FROM labs WHERE source='live'")]
    if live:
        con.execute(f"DELETE FROM scores WHERE person_id IN ({','.join('?' * len(live))})", live)
        con.execute("DELETE FROM labs WHERE source='live'")
    for t in store.DEMO_TABLES:
        con.execute(f"DROP TABLE IF EXISTS {t}")
    con.executescript(store.DEMO_SCHEMA)
    con.commit()
    init_cases(con)


# ------------------------------------------------------------------ the one door

def act(con, pid: int, role: str, action: str, inputs: dict | None = None, commit: bool = True) -> dict:
    """Every change to a case comes through here."""
    case = case_for_person(con, pid)
    if case is None:
        raise Refusal("not_found", "no_case", "This person has no case.")
    inputs = dict(inputs or {})
    if action == "order_test":
        inputs["due"] = (today(con) + timedelta(days=TEST_TURNAROUND_DAYS)).isoformat()
    try:
        d = machine.decide(facts(con, case), role, action, inputs)
    except Refusal as r:
        if r.kind == "permission":  # a refused attempt by the wrong role is worth keeping
            audit(con, role, "refused", f"Refused: {machine.BY_ACTION[action].label}", case_id=case["id"],
                  person_id=pid, detail={"why": r.message})
            con.commit()
        raise

    now = today(con).isoformat()
    cols = {**d.set, "updated_at": now}
    if "consent_excluded" in cols:
        cols["consent_excluded"] = json.dumps(cols["consent_excluded"])
    if action in ("consent_yes", "consent_no"):
        cols.update(consent_by=machine.ACTOR_NAME.get(role, role), consent_at=now)
    con.execute(f"UPDATE cases SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", (*cols.values(), case["id"]))
    audit(con, role, action, d.transition.event, case_id=case["id"], person_id=pid, from_status=case["status"],
          to_status=cols.get("status", case["status"]), detail=d.detail)

    out = {"done": d.transition.done}
    if d.run == "start_cascade":
        out["cascade"] = _send(con, get_case(con, case["id"]), role, [int(x) for x in inputs.get("exclude") or []],
                               bool(inputs.get("voice")))
    if commit:
        con.commit()
    return out


# ------------------------------------------------------------------ family testing

def plan_cascade(con, case) -> dict:
    """Who would be contacted and how. Used for the preview and for the real send, so they cannot differ."""
    now = today(con)
    index = store.person(con, case["person_id"])
    excluded = set(json.loads(case["consent_excluded"] or "[]"))
    rows = []
    for r, rel in store.first_degree(con, case["person_id"], include_deceased=True):
        rid = r["id"]
        age = int(store.age(r["birth_date"], now))
        row = {"id": rid, "name": store.full_name(r), "given": r["given"], "relation": rel.capitalize(), "age": age,
               "lang": r["lang"] or "en", "message": None}
        if r["death_date"]:
            row["outcome"], row["why"] = "none", "Deceased"
        elif rid in excluded:
            row["outcome"], row["why"] = "none", "The patient asked us not to contact this relative"
        elif (con.execute("SELECT 1 FROM cases WHERE person_id=?", (rid,)).fetchone()
              or con.execute("SELECT 1 FROM invitations WHERE person_id=?", (rid,)).fetchone()
              or con.execute("SELECT 1 FROM wellchild WHERE person_id=?", (rid,)).fetchone()):
            row["outcome"], row["why"] = "none", "Already in the programme"
        elif age < 18:
            two = date.fromisoformat(r["birth_date"]) + timedelta(days=int(365.25 * 2))
            row["outcome"], row["due"] = "wellchild", max(now + timedelta(days=14), two).isoformat()
            row["why"] = "Under 18: cholesterol test at the next Well-Child Visit. No message is sent."
        else:
            row["outcome"], row["message"] = "invite", sms_text(row["lang"], r["given"])
        rows.append(row)
    return {"relatives": rows, "abroad": int(index["relatives_abroad"] or 0),
            "invite": sum(r["outcome"] == "invite" for r in rows),
            "wellchild": sum(r["outcome"] == "wellchild" for r in rows)}


def _send(con, case, role: str, skip: list[int], voice: bool = False) -> dict:
    now = today(con)
    plan = plan_cascade(con, case)
    out = {"invited": 0, "wellchild": 0, "not_contacted": 0, "abroad": plan["abroad"]}
    for r in plan["relatives"]:
        if r["outcome"] == "invite" and r["id"] not in skip:
            token = secrets.token_urlsafe(12)
            con.execute("INSERT INTO invitations (token, person_id, case_id, lang, status, sent_at, expires_at) "
                        "VALUES (?,?,?,?,?,?,?)", (token, r["id"], case["id"], r["lang"], "sent", now.isoformat(),
                                                   (now + timedelta(days=INVITE_VALID_DAYS)).isoformat()))
            audit(con, role, "invitation_sent", "Invitation sent by SMS (mock)", person_id=r["id"],
                  detail={"language": "Arabic" if r["lang"] == "ar" else "English", "voice": "with a voice note" if voice else None})
            out["invited"] += 1
        elif r["outcome"] == "wellchild" and r["id"] not in skip:
            con.execute("INSERT INTO wellchild (person_id, case_id, flagged_at, due_date, status) VALUES (?,?,?,?,?)",
                        (r["id"], case["id"], now.isoformat(), r["due"], "due"))
            audit(con, role, "wellchild_flag", "Flagged for a cholesterol test at Well-Child", person_id=r["id"],
                  detail={"due": r["due"]})
            out["wellchild"] += 1
        else:
            out["not_contacted"] += 1
    if plan["abroad"]:
        con.execute("INSERT INTO family_letters (case_id, relatives_abroad, created_at) VALUES (?,?,?)",
                    (case["id"], plan["abroad"], now.isoformat()))
        audit(con, role, "family_letter", "Family letter prepared for relatives abroad", case_id=case["id"],
              person_id=case["person_id"], detail={"relatives_abroad": plan["abroad"]})
    con.execute("UPDATE cases SET cascade_at=? WHERE id=?", (now.isoformat(), case["id"]))
    return out


# ------------------------------------------------------------------ the invited relative

CHOICES = {"book": "booked", "decline": "declined", "already_tested": "already_tested", "call_me": "call_requested"}
CHOICE_EVENT = {"book": "Relative booked a check", "decline": "Relative declined the invitation",
                "already_tested": "Relative says they have already been tested",
                "call_me": "Relative asked for a phone call"}


def invitation_state(con, inv) -> str:
    """open, booked or closed, as the relative sees it."""
    if inv["status"] == "sent":
        return "open" if today(con).isoformat() <= (inv["expires_at"] or "9999") else "closed"
    return {"booked": "booked", "declined": "declined", "already_tested": "already_tested",
            "call_requested": "call_requested"}.get(inv["status"], "closed")


def respond(con, token: str, choice: str, slot: str | None = None, share: bool | None = None) -> dict:
    inv = con.execute("SELECT * FROM invitations WHERE token=?", (token,)).fetchone()
    if inv is None:
        raise Refusal("not_found", "invitation_not_found", "Invitation not found.")
    if choice not in CHOICES:
        raise Refusal("validation", "unknown_choice", "Unknown choice.")
    if invitation_state(con, inv) != "open":
        raise Refusal("business", "invitation_closed", "This invitation has already been answered or has expired.")
    if choice == "book" and not slot:
        raise Refusal("validation", "missing_slot", "Choose a time.")
    now = today(con).isoformat()
    con.execute("UPDATE invitations SET status=?, slot=?, booked_at=?, responded_at=?, share_result=? WHERE id=?",
                (CHOICES[choice], slot if choice == "book" else None, now if choice == "book" else None, now,
                 None if share is None else int(share), inv["id"]))
    audit(con, "relative", f"relative_{choice}", CHOICE_EVENT[choice], person_id=inv["person_id"],
          actor="Invited relative", detail={"slot": slot.replace(" | ", ", ") if slot and choice == "book" else None})
    con.commit()
    return {"status": CHOICES[choice], "slot": slot if choice == "book" else None}
