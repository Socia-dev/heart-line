"""Heart Line API.

Run: uvicorn heartline.api:app --port 8010   (from backend/)

Every request carries a demo role in the X-Demo-Role header (no sign-in in the prototype).
The role decides what the caller may do (machine.py) and what they may see (redaction
below). The `truth` table is never read here.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import threading
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import cascade, features, fhir, live, machine, pilot, scoring, simulate, store, voice

voice.load_env()
from .config import EVAL_PATH, PREMATURE_AGE
from .features import reason_texts
from .machine import CONFIRMED, OPEN, Refusal

app = FastAPI(title="Heart Line", description="Prototype on synthetic data. Not for clinical use.")
app.add_middleware(
    CORSMiddleware, allow_methods=["*"], allow_headers=["*"],
    allow_origins=os.environ.get("HEARTLINE_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","))

STATUS_LABEL = {
    "flagged": "To review", "test_ordered": "Test ordered", "confirmed_genetic": "Confirmed",
    "no_variant": "No variant found", "clinical_fh": "Clinical FH", "dismissed": "Closed",
}
HTTP_STATUS = {"permission": 403, "not_found": 404, "business": 422, "validation": 400}


@app.exception_handler(Refusal)
def refused(_: Request, r: Refusal):
    return JSONResponse({"code": r.code, "message": r.message, "kind": r.kind}, status_code=HTTP_STATUS[r.kind])


def db():
    con = store.connect(schema=False)
    try:
        yield con
    finally:
        con.close()


def actor(x_demo_role: str | None = Header(None)) -> str:
    role = x_demo_role or "clinician"
    if role not in machine.ROLES:
        raise Refusal("validation", "unknown_role", "Unknown role.")
    return role


def allow(role: str, *roles: str):
    if role not in roles:
        raise Refusal("permission", "not_your_view", "This view is not available to your role.")


@app.on_event("startup")
def startup():
    threading.Thread(target=simulate.warm, daemon=True).start()  # so the first demo click is quick
    threading.Thread(target=live.warm, daemon=True).start()
    con = store.connect()
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(scores)")}
        if "prob_cal" not in cols:
            raise RuntimeError("Scores are missing or out of date. Run `python -m heartline.train` first.")
        v = con.execute("SELECT value FROM sim WHERE key='initialized'").fetchone()
        if v is None or v["value"] != "2" or "action_key" not in {r[1] for r in con.execute("PRAGMA table_info(audit)")}:
            cascade.reset(con)
    finally:
        con.close()


def _brief(p, on: date) -> dict:
    return {"id": p["id"], "mrn": p["mrn"], "name": store.full_name(p), "given": p["given"], "sex": p["sex"],
            "age": int(store.age(p["birth_date"], on)), "deceased": p["death_date"] is not None}


@lru_cache(maxsize=1)
def _evaluation() -> dict:
    return json.loads(EVAL_PATH.read_text()) if EVAL_PATH.exists() else {}


@app.get("/api/roles")
def roles():
    return [{"id": k, "name": v.split(", ")[0], "title": v.split(", ")[1]} for k, v in machine.ROLES.items()]


# ------------------------------------------------------------------ programme numbers

@lru_cache(maxsize=64)
def _pilot(reviews: int, consent: float, uptake: float):
    return pilot.run(reviews_per_week=reviews, consent_rate=consent, uptake=uptake)


@app.get("/api/pilot")
def pilot_projection(reviews_per_week: int = Query(pilot.REVIEWS_PER_WEEK, ge=5, le=60),
                     consent_rate: float = Query(simulate.CONSENT_RATE, ge=0.1, le=1.0),
                     uptake: float = Query(simulate.BOOK_RATE, ge=0.1, le=1.0)):
    return _pilot(reviews_per_week, round(consent_rate, 2), round(uptake, 2))


@app.get("/api/summary")
def summary(con: sqlite3.Connection = Depends(db)):
    def one(sql, *a):
        return con.execute(sql, a).fetchone()[0]

    def counts(sql):
        return {r[0]: r[1] for r in con.execute(sql)}

    cases = counts("SELECT status, COUNT(*) FROM cases GROUP BY status")
    inv = counts("SELECT status, COUNT(*) FROM invitations GROUP BY status")
    by_source = counts("SELECT source, COUNT(*) FROM cases WHERE status IN ('confirmed_genetic','clinical_fh') "
                       "GROUP BY source")
    confirmed = sum(cases.get(s, 0) for s in CONFIRMED)
    tested = inv.get("positive", 0) + inv.get("negative", 0)
    live = con.execute("SELECT c.person_id FROM cases c JOIN labs l ON l.person_id=c.person_id WHERE l.source='live' "
                       "ORDER BY c.id DESC LIMIT 1").fetchone()
    funnel = [
        ["Flagged by screening", one("SELECT COUNT(*) FROM cases WHERE source='detection'")],
        ["Genetic test ordered", one("SELECT COUNT(DISTINCT case_id) FROM audit WHERE action_key='order_test'")],
        ["Confirmed", confirmed],
        ["Patient agreed to family testing", one("SELECT COUNT(*) FROM cases WHERE consent=1")],
        ["Relatives invited", sum(inv.values())],
        ["Relatives tested", tested],
        ["Relatives found with FH", inv.get("positive", 0)],
        ["Children found with FH", one("SELECT COUNT(*) FROM wellchild WHERE status='tested_positive'")],
    ]
    # The demo story as a checklist, ticked from what has really happened.
    story = [
        ["A new result arrives and is flagged", live is not None, "clinician"],
        ["The clinician orders a genetic test", funnel[1][1] > 0, "clinician"],
        ["The variant is confirmed", by_source.get("detection", 0) > 0, "clinician"],
        ["The patient agrees to family testing", funnel[3][1] > 0, "clinician"],
        ["The coordinator sends the invitations", sum(inv.values()) > 0, "coordinator"],
        ["A relative answers on their phone", one("SELECT COUNT(*) FROM invitations WHERE responded_at IS NOT NULL") > 0,
         "coordinator"],
        ["A relative is found, and their own family starts", by_source.get("cascade", 0) > 0, "clinician"],
    ]
    return {
        "today": store.today(con).isoformat(),
        "screened": one("SELECT COUNT(*) FROM scores"),
        "cases": cases, "open_cases": sum(cases.get(s, 0) for s in OPEN), "confirmed": confirmed,
        "confirmed_by_source": by_source, "invitations": inv, "invitations_total": sum(inv.values()),
        "wellchild_total": one("SELECT COUNT(*) FROM wellchild"),
        "letters_abroad": one("SELECT COALESCE(SUM(relatives_abroad),0) FROM family_letters"),
        "dismissed_by_reason": {machine.DISMISS_REASONS.get(k, k): v for k, v in counts(
            "SELECT dismiss_reason, COUNT(*) FROM cases WHERE status='dismissed' GROUP BY dismiss_reason").items()},
        "funnel": [{"step": a, "count": b} for a, b in funnel],
        "story": [{"step": a, "done": bool(b), "role": c} for a, b, c in story],
        "latest_live": live[0] if live else None,
    }


@lru_cache(maxsize=2)
def _ldl_by_person(db_key: str) -> dict:
    """Highest statin-corrected LDL per person, from the recorded history. Cached: the history does not change."""
    con = store.connect(schema=False)
    try:
        X = features.build(con, history_only=True)
    finally:
        con.close()
    return {int(i): float(v) for i, v in X["max_ldl_corr"].items()}


@app.get("/api/model/scatter")
def scatter(role: str = Depends(actor), con: sqlite3.Connection = Depends(db)):
    """Everyone with a result: highest corrected LDL against the model's score, with each person's band.
    Arrays rather than objects, so 35,000 points stay small. No names, no ground truth."""
    allow(role, "lead", "clinician")
    ldl = _ldl_by_person(str(store.DB_PATH))
    confirmed = {r[0] for r in con.execute("SELECT person_id FROM cases WHERE status IN ('confirmed_genetic','clinical_fh')")}
    bands = [b[0] for b in scoring.BANDS] + [scoring.NOT_FLAGGED]
    out = {"x": [], "y": [], "band": [], "found": [], "id": []}
    for r in con.execute("SELECT person_id, prob_b, band FROM scores"):
        x = ldl.get(r[0])
        if x is None:
            continue
        out["x"].append(round(x, 2))
        out["y"].append(round(float(r[1]), 4))
        out["band"].append(bands.index(r[2]) if r[2] in bands else len(bands) - 1)
        out["found"].append(int(r[0] in confirmed))
        out["id"].append(r[0])
    return {**out, "bands": bands, "threshold": _evaluation().get("worklist_threshold", {}).get("threshold"),
            "label": "On synthetic data"}


@app.get("/api/evaluation")
def evaluation():
    if not _evaluation():
        raise Refusal("not_found", "not_trained", "Run training first.")
    return _evaluation()


# ------------------------------------------------------------------ role queues

QUEUES = {
    "clinician": [
        ("review", "To review", "c.status='flagged'"),
        ("results", "Results back", "(c.status='no_variant' OR (c.status IN ('confirmed_genetic','clinical_fh') "
                                    "AND c.consent IS NULL AND c.source<>'wellchild'))"),
        ("all", "Everyone", "1=1"),
    ],
    "coordinator": [
        ("start", "To start", "c.status IN ('confirmed_genetic','clinical_fh') AND c.consent=1 AND c.cascade_at IS NULL"),
        ("phone", "To phone", None),
        ("running", "Families in progress", "c.cascade_at IS NOT NULL"),
    ],
}
EMPTY = {
    "review": "Nothing waiting for review. New flags appear here as results arrive.",
    "results": "No results waiting. Genetic test results appear here when the lab reports.",
    "waiting": "No tests are out with the lab.",
    "done": "No confirmed patients yet.",
    "all": "No cases.",
    "start": "No families waiting to start. They appear here once a clinician records a patient's consent.",
    "phone": "Nobody to phone. Relatives who ask for a call or do not reply appear here.",
    "running": "No family testing has started yet.",
}


def _why(con, r, tab: str, on: date) -> str:
    if tab in ("review", "all") and r["status"] == "flagged":
        if r["source"] != "detection":
            return "Found through family testing"
        return (reason_texts(json.loads(r["reasons"] or "[]")) or [""])[0]
    if r["status"] == "test_ordered":
        return f"Result due {_d(r['test_due'])}"
    if r["status"] == "no_variant":
        return "No variant found. Decide how to close."
    if r["status"] == "dismissed":
        return machine.DISMISS_REASONS.get(r["dismiss_reason"] or "", "Closed")
    if r["source"] == "wellchild":
        return "Found at a Well-Child Visit. Refer to the paediatric lipid clinic."
    if r["consent"] is None:
        return ("Found through family testing. " if r["source"] != "detection" else "Variant found. ") + \
               "Ask about their family."
    if r["consent"] == 0:
        return "Declined family testing"
    if not r["cascade_at"]:
        plan = cascade.plan_cascade(con, r)
        return f"Patient agreed {_d(r['consent_at'])}. {plan['invite']} to invite, {plan['wellchild']} children."
    n = {x[0]: x[1] for x in con.execute("SELECT status, COUNT(*) FROM invitations WHERE case_id=? GROUP BY status",
                                         (r["case_id"],))}
    total = sum(n.values())
    replied = total - n.get("sent", 0) - n.get("no_response", 0)
    return f"{total} invited, {replied} replied, {n.get('sent', 0)} waiting"


def _d(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')}"


@app.get("/api/queue")
def queue(tab: str = "", q: str = "", page: int = Query(1, ge=1), per_page: int = Query(25, le=100),
          role: str = Depends(actor), con: sqlite3.Connection = Depends(db)):
    allow(role, "clinician", "coordinator")
    on = store.today(con)
    defs = QUEUES[role]
    tab = tab if tab in {d[0] for d in defs} else defs[0][0]
    phone_sql = ("FROM invitations i JOIN people p ON p.id=i.person_id JOIN cases c ON c.id=i.case_id "
                 "WHERE i.status IN ('call_requested','no_response')")
    tabs = []
    for key, label, where in defs:
        n = con.execute(f"SELECT COUNT(*) {phone_sql}" if where is None else
                        f"SELECT COUNT(*) FROM cases c WHERE {where}").fetchone()[0]
        tabs.append({"id": key, "label": label, "count": n})

    like, args = "", []
    if q:
        like = " AND (p.given || ' ' || p.family LIKE ? OR p.mrn LIKE ?)"
        args = [f"%{q}%", f"%{q}%"]
    items = []
    if tab == "phone":
        total = con.execute(f"SELECT COUNT(*) {phone_sql}{like}", args).fetchone()[0]
        for r in con.execute(f"SELECT i.status AS inv_status, i.sent_at, p.*, c.person_id AS index_pid {phone_sql}{like} "
                             f"ORDER BY i.status, i.sent_at LIMIT ? OFFSET ?", args + [per_page, (page - 1) * per_page]):
            items.append({**_brief(r, on), "status": r["inv_status"],
                          "status_label": "Asked for a call" if r["inv_status"] == "call_requested" else "No reply",
                          "why": f"Invited {_d(r['sent_at'])}, family of {store.full_name(store.person(con, r['index_pid']))}",
                          "open": r["index_pid"], "band": None, "new": False})
    else:
        where = next(d[2] for d in defs if d[0] == tab)
        base = (f"FROM cases c JOIN people p ON p.id=c.person_id LEFT JOIN scores s ON s.person_id=c.person_id "
                f"WHERE {where}{like}")
        total = con.execute(f"SELECT COUNT(*) {base}", args).fetchone()[0]
        rows = con.execute(
            f"SELECT p.*, c.id AS case_id, c.status, c.source, c.consent, c.consent_at, c.cascade_at, c.test_due, "
            f"c.dismiss_reason, c.person_id, c.consent_excluded, s.band, s.prob_b, s.reasons, "
            f"(SELECT COUNT(*) FROM labs l WHERE l.person_id=c.person_id AND l.source='live') AS live {base} "
            f"ORDER BY live DESC, c.updated_at DESC, s.prob_b DESC, c.id LIMIT ? OFFSET ?",
            args + [per_page, (page - 1) * per_page]).fetchall()
        for r in rows:
            items.append({**_brief(r, on), "case_id": r["case_id"], "status": r["status"],
                          "status_label": STATUS_LABEL[r["status"]], "why": _why(con, r, tab, on), "open": r["id"],
                          "band": r["band"] if r["source"] == "detection" else None, "new": bool(r["live"])})
    return {"role": role, "tab": tab, "tabs": tabs, "total": total, "page": page, "per_page": per_page,
            "items": items, "empty": EMPTY[tab]}


# ------------------------------------------------------------------ one patient

def relative_status(con, pid: int, deceased: bool, role: str, own_minor_child: bool) -> str:
    """What the viewer may know about a relative. A clinician sees whether a relative was
    contacted and has replied, never the relative's result. The family coordinator, who runs
    the testing, sees results. A parent's clinician does see their own young child's result."""
    if deceased:
        return "deceased"
    full = role == "coordinator" or own_minor_child
    c = con.execute("SELECT status FROM cases WHERE person_id=?", (pid,)).fetchone()
    inv = con.execute("SELECT status FROM invitations WHERE person_id=?", (pid,)).fetchone()
    wc = con.execute("SELECT status FROM wellchild WHERE person_id=?", (pid,)).fetchone()
    if full and c and c["status"] in CONFIRMED:
        return "confirmed"
    if inv:
        s = inv["status"]
        if full:
            return {"sent": "invited", "booked": "booked", "negative": "negative", "no_response": "no_response",
                    "positive": "confirmed", "declined": "declined", "already_tested": "already_tested",
                    "call_requested": "call_requested"}[s]
        return {"sent": "invited", "no_response": "no_response", "call_requested": "invited"}.get(s, "replied")
    if wc:
        if full:
            return {"due": "wellchild", "tested_negative": "negative", "tested_positive": "confirmed"}[wc["status"]]
        return "wellchild" if wc["status"] == "due" else "replied"
    if full and c and c["status"] in OPEN:
        return "assessing"
    return "unknown"


def family_tree(con, pid: int, role: str) -> dict:
    on = store.today(con)
    me = store.person(con, pid)
    nodes: dict[int, dict] = {}

    def add(p, relation: str, gen: int, first_degree: bool = False):
        if p is None or p["id"] in nodes:
            return
        b = _brief(p, on)
        mine = first_degree and gen == 1 and b["age"] < 18
        nodes[p["id"]] = {**b, "relation": relation, "generation": gen, "first_degree": first_degree,
                          "mother_id": p["mother_id"], "father_id": p["father_id"],
                          "status": "index" if p["id"] == pid else relative_status(con, p["id"], b["deceased"], role, mine)}

    add(me, "Patient", 0)
    first = store.first_degree(con, pid, include_deceased=True)
    for r, rel in first:
        add(r, rel.capitalize(), {"mother": -1, "father": -1, "son": 1, "daughter": 1}.get(rel, 0), True)
    for par_col in ("mother_id", "father_id"):
        if me[par_col]:
            par = store.person(con, me[par_col])
            for gp_col, label in (("mother_id", "Grandmother"), ("father_id", "Grandfather")):
                if par[gp_col]:
                    add(store.person(con, par[gp_col]), label, -2)
    for sp in store.spouses_of(con, pid):
        add(sp, "Husband" if sp["sex"] == "M" else "Wife", 0)
    for r, rel in first:
        if rel in ("brother", "sister"):
            for k in store.children_of(con, r["id"]):
                add(k, "Nephew" if k["sex"] == "M" else "Niece", 1)
        if rel in ("son", "daughter"):
            for k in store.children_of(con, r["id"]):
                add(k, "Grandson" if k["sex"] == "M" else "Granddaughter", 2)
    return {"nodes": list(nodes.values()), "relatives_abroad": me["relatives_abroad"] or 0,
            "results_visible": role == "coordinator"}


@app.get("/api/patients/{pid}")
def patient(pid: int, role: str = Depends(actor), con: sqlite3.Connection = Depends(db)):
    allow(role, "clinician", "coordinator")
    p = store.person(con, pid)
    if p is None:
        raise Refusal("not_found", "person_not_found", "No such person.")
    on = store.today(con)
    labs = [{"date": r["date"], "ldl": r["ldl"], "tc": r["tc"], "hdl": r["hdl"], "tg": r["tg"],
             "on_statin": bool(r["on_statin"]), "new": r["source"] == "live"}
            for r in con.execute("SELECT * FROM labs WHERE person_id=? ORDER BY date", (pid,))]
    sc = con.execute("SELECT * FROM scores WHERE person_id=?", (pid,)).fetchone()
    score = None
    if sc:
        reasons = json.loads(sc["reasons"] or "[]")
        rate = next((b["observed_rate"] for b in _evaluation().get("bands", []) if b["band"] == sc["band"]), None)
        score = {"band": sc["band"], "band_rate": rate, "flagged": bool(sc["flagged"]), "raw": sc["prob_b"],
                 "calibrated": sc["prob_cal"], "dlcn_total": sc["dlcn_total"], "dlcn_band": sc["dlcn_band"],
                 "dlcn_items": json.loads(sc["dlcn_items"]), "dlcn_linked_total": sc["dlcn_linked_total"],
                 "reasons": [r for r in reasons if isinstance(r, dict)], "live": sc["prob_a"] is None,
                 "model_version": sc["model_version"]}

    c = cascade.case_for_person(con, pid)
    case, nxt = None, None
    if c:
        f = cascade.facts(con, c)
        f["test_due_text"] = _d(c["test_due"])
        case = {k: c[k] for k in ("id", "status", "source", "created_at", "test_due", "found_variant", "consent",
                                  "consent_at", "consent_by", "cascade_at", "dismiss_reason")}
        case["status_label"] = STATUS_LABEL[c["status"]]
        case["consent_excluded"] = f["consent_excluded"]
        inv = {r[0]: r[1] for r in con.execute("SELECT status, COUNT(*) FROM invitations WHERE case_id=? GROUP BY status",
                                               (c["id"],))}
        invited = sum(inv.values())
        case["progress"] = {"invited": invited, "replied": invited - inv.get("sent", 0) - inv.get("no_response", 0),
                            "wellchild": con.execute("SELECT COUNT(*) FROM wellchild WHERE case_id=?", (c["id"],)).fetchone()[0],
                            "letter_abroad": (con.execute("SELECT relatives_abroad FROM family_letters WHERE case_id=?",
                                                          (c["id"],)).fetchone() or [0])[0]}
        if role == "coordinator":  # results follow the coordinator, not the family tree
            case["progress"]["tested"] = inv.get("positive", 0) + inv.get("negative", 0)
            case["progress"]["found"] = con.execute("SELECT COUNT(*) FROM cases WHERE index_of=?", (c["id"],)).fetchone()[0]
            if c["index_of"]:
                ic = cascade.get_case(con, c["index_of"])
                case["led_by"] = _brief(store.person(con, ic["person_id"]), on)
        case["through_family"] = c["source"] != "detection"
        nxt = {**machine.next_step(f, role), "actions": machine.possible(f, role),
               "dismiss_reasons": machine.DISMISS_REASONS}
        last = con.execute("SELECT action_key, sim_date FROM audit WHERE case_id=? AND action_key<>'refused' "
                           "ORDER BY id DESC LIMIT 1", (c["id"],)).fetchone()
        if last and last["sim_date"] == on.isoformat() and last["action_key"] in machine.BY_ACTION:
            nxt["just_done"] = machine.BY_ACTION[last["action_key"]].done or None  # what the last step did, today only
        if nxt["key"] == "start" and role == "coordinator":
            nxt["plan"] = cascade.plan_cascade(con, c)

    inv = con.execute("SELECT status, sent_at, slot FROM invitations WHERE person_id=?", (pid,)).fetchone()
    wc = con.execute("SELECT status, due_date FROM wellchild WHERE person_id=?", (pid,)).fetchone()
    contact = None
    if inv and (role == "coordinator" or not c):
        contact = {"kind": "invitation", "status": inv["status"] if role == "coordinator" else
                   {"sent": "sent", "no_response": "no_response"}.get(inv["status"], "replied"), "sent_at": inv["sent_at"]}
    elif wc:
        contact = {"kind": "wellchild", "status": wc["status"], "due_date": wc["due_date"]}

    return {
        "role": role,
        "person": {**_brief(p, on), "nationality_group": p["nationality_group"], "lang": p["lang"],
                   "statin_start": p["statin_start"], "statin_intensity": p["statin_intensity"], "cad_age": p["cad_age"],
                   "early_cad": p["cad_age"] is not None and p["cad_age"] < PREMATURE_AGE[p["sex"]],
                   "xanthoma": bool(p["xanthoma"]), "arcus": bool(p["arcus"]),
                   "fhx_recorded_cad": bool(p["fhx_recorded_cad"]), "fhx_recorded_ldl": bool(p["fhx_recorded_ldl"])},
        "labs": labs, "score": score, "case": case, "next": nxt, "contact": contact,
        "family": family_tree(con, pid, role),
        "timeline": [{"id": r["id"], "date": r["sim_date"], "actor": r["actor"], "action": r["action"],
                      "decision": r["actor_role"] in machine.ROLES and r["action_key"] != "refused",
                      "detail": json.loads(r["detail"]) if r["detail"] else None}
                     for r in con.execute("SELECT * FROM audit WHERE person_id=? ORDER BY id", (pid,))],
        "today": on.isoformat(),
    }


class ActIn(BaseModel):
    action: str
    reason: str | None = None
    note: str | None = None
    exclude: list[int] | None = None
    voice: bool | None = None


@app.post("/api/patients/{pid}/act")
def act(pid: int, body: ActIn, role: str = Depends(actor), con: sqlite3.Connection = Depends(db)):
    """The one door for staff actions on a case. The machine decides; this applies it."""
    return cascade.act(con, pid, role, body.action, body.model_dump(exclude={"action"}))


# ------------------------------------------------------------------ families and invitations

@app.get("/api/invitations")
def invitations(role: str = Depends(actor), con: sqlite3.Connection = Depends(db)):
    allow(role, "coordinator")
    on = store.today(con)
    invs = []
    for r in con.execute("SELECT i.*, c.person_id AS index_pid FROM invitations i JOIN cases c ON c.id=i.case_id "
                         "ORDER BY i.id DESC"):
        p = store.person(con, r["person_id"])
        invs.append({"id": r["id"], "token": r["token"], "status": r["status"], "lang": r["lang"],
                     "sent_at": r["sent_at"], "slot": r["slot"], "relative": _brief(p, on), "case_id": r["case_id"],
                     "message": cascade.sms_text(r["lang"], p["given"], r["token"][:6]),
                     "via": _brief(store.person(con, r["index_pid"]), on)})
    families = []
    for c in con.execute("SELECT * FROM cases WHERE cascade_at IS NOT NULL OR index_of IS NOT NULL ORDER BY id"):
        n = {r[0]: r[1] for r in con.execute("SELECT status, COUNT(*) FROM invitations WHERE case_id=? GROUP BY status",
                                              (c["id"],))}
        families.append({"case_id": c["id"], "index_of": c["index_of"], "family_root": c["family_root"] or c["id"],
                         "source": c["source"], "status": c["status"], "status_label": STATUS_LABEL[c["status"]],
                         "consent": c["consent"], "cascade_at": c["cascade_at"], "invited": sum(n.values()),
                         "invitations": n,
                         "wellchild": con.execute("SELECT COUNT(*) FROM wellchild WHERE case_id=?", (c["id"],)).fetchone()[0],
                         **_brief(store.person(con, c["person_id"]), on)})
    return {"invitations": invs, "families": families,
            "abroad": con.execute("SELECT COALESCE(SUM(relatives_abroad),0) FROM family_letters").fetchone()[0]}


CLINICS = ["Al Bateen Family Health Centre", "Mohammed Bin Zayed City Health Centre", "Al Ain Healthy Family Clinic"]


def _slots(on: date) -> list[str]:
    out, d = [], on + timedelta(days=1)
    while len(out) < 6:
        if d.weekday() < 5:
            out.append(f"{d.isoformat()} {'08:30' if len(out) % 2 == 0 else '16:00'} | {CLINICS[len(out) % 3]}")
        d += timedelta(days=1)
    return out


@app.get("/api/invite/{token}")
def invite_view(token: str, con: sqlite3.Connection = Depends(db)):
    """What the invited relative sees. No role, no sign-in, and nothing about who triggered it or why."""
    r = con.execute("SELECT * FROM invitations WHERE token=?", (token,)).fetchone()
    if r is None:
        raise Refusal("not_found", "invitation_not_found", "Invitation not found.")
    state = cascade.invitation_state(con, r)
    return {"given": store.person(con, r["person_id"])["given"], "lang": r["lang"], "state": state, "slot": r["slot"],
            "slots": _slots(store.today(con)) if state == "open" else [], "mock": True}


@app.get("/api/voice/status")
def voice_status():
    """Whether real voice notes are available, and the fixed script. Never the key."""
    return voice.status()


@app.get("/api/invite/{token}/voice")
def invite_voice(token: str, lang: str = "ar", con: sqlite3.Connection = Depends(db)):
    """The invitation as a voice note. The same neutral words for everyone; cached after the first time."""
    if con.execute("SELECT 1 FROM invitations WHERE token=?", (token,)).fetchone() is None:
        raise Refusal("not_found", "invitation_not_found", "Invitation not found.")
    try:
        path = voice.clip(lang)
    except voice.VoiceUnavailable as e:
        raise Refusal("business", "voice_unavailable", str(e))
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


class RespondIn(BaseModel):
    choice: str
    slot: str | None = None
    share: bool | None = None


@app.post("/api/invite/{token}/respond")
def invite_respond(token: str, body: RespondIn, con: sqlite3.Connection = Depends(db)):
    return cascade.respond(con, token, body.choice, body.slot, body.share)


@app.get("/api/wellchild")
def wellchild(role: str = Depends(actor), con: sqlite3.Connection = Depends(db)):
    allow(role, "nurse", "coordinator")
    on = store.today(con)
    out = []
    for r in con.execute("SELECT * FROM wellchild ORDER BY status='due' DESC, due_date, id"):
        p = store.person(con, r["person_id"])
        a = store.age(p["birth_date"], on)
        if r["status"] == "due":
            due = "Add a lipid test to the visit" if a >= 2 else "Lipid test once the child turns 2"
        elif r["status"] == "tested_positive":
            due = "Refer to the paediatric lipid clinic. " + (
                "Discuss statin treatment now." if a >= 8 else
                f"Discuss statin treatment from age 8 to 10 (around {date.fromisoformat(p['birth_date']).year + 8}).")
        else:
            due = "Nothing further"
        b = _brief(p, on)
        out.append({"id": r["id"], "status": r["status"], "due_date": r["due_date"], "tested_at": r["tested_at"],
                    "child": {"name": b["name"], "mrn": b["mrn"], "age_years": round(a, 1)}, "due": due})
    return {"items": out, "today": on.isoformat()}


# ------------------------------------------------------------------ demo controls, audit, export

# ------------------------------------------------------------------ score any result

class ScoreIn(BaseModel):
    panel: dict | None = None
    context: dict | None = None
    person_id: int | None = None
    overrides: dict | None = None


def _bad_input(e: live.BadInput):
    raise Refusal("validation", f"bad_{e.field}", e.message)


@app.post("/api/score")
def score(body: ScoreIn, x_demo_role: str | None = Header(None), con: sqlite3.Connection = Depends(db)):
    """Score numbers typed in by hand (own-record model), or a person in the population with some values
    changed (linked-family model). Stores nothing."""
    try:
        if body.person_id is not None:
            allow(actor(x_demo_role), "clinician", "coordinator")
            res, _ = live.score_record(con, body.person_id, body.overrides, "Exploration only. The record is unchanged.")
            return res
        return live.score_input(body.panel or {}, body.context)
    except live.BadInput as e:
        _bad_input(e)


@app.get("/api/patients/{pid}/explain")
def explain(pid: int, role: str = Depends(actor), con: sqlite3.Connection = Depends(db)):
    """The why-chart and the starting values for the what-if panel."""
    allow(role, "clinician", "coordinator")
    try:
        res, _ = live.score_record(con, pid, None, "Already on the worklist" if cascade.case_for_person(con, pid) else None)
        return {**res, "inputs": live.record_inputs(con, pid)}
    except live.BadInput as e:
        _bad_input(e)


SAMPLE_CSV = """ldl,tc,hdl,tg,age,sex,statin,early_cad,xanthoma,arcus,fhx_cad,fhx_ldl
7.2,9.1,1.2,1.4,34,M,none,no,no,no,yes,no
3.1,5.0,1.3,1.2,52,F,none,no,no,no,no,no
4.4,6.6,1.0,2.1,61,M,moderate,yes,no,no,no,no
5.6,7.8,1.4,1.1,28,F,none,no,no,yes,no,yes
9.4,11.5,1.1,1.6,19,M,none,no,yes,no,yes,yes
"""
YES = {"yes", "y", "true", "1"}
MAX_ROWS = 500


@app.get("/api/score/sample.csv")
def sample_csv():
    return Response(SAMPLE_CSV, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=heartline-sample.csv"})


class CsvIn(BaseModel):
    text: str
    unit: str = "mmol"


@app.post("/api/score/csv")
def score_csv(body: CsvIn):
    """Score every row of a CSV. One bad row does not stop the others. Stores nothing."""
    rows = list(csv.DictReader(io.StringIO(body.text.strip())))
    if not rows:
        raise Refusal("validation", "empty_csv", "The file has no rows. The first line should be the column names.")
    if "ldl" not in {k.strip().lower() for k in rows[0]}:
        raise Refusal("validation", "no_ldl_column", "The file needs an ldl column. Download the sample to see the layout.")
    if len(rows) > MAX_ROWS:
        raise Refusal("validation", "too_many_rows", f"Up to {MAX_ROWS} rows at a time.")
    out = []
    for i, raw in enumerate(rows, start=1):
        r = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            res = live.score_input({**{k: r.get(k) for k in ("ldl", "tc", "hdl", "tg")}, "unit": body.unit}, {
                "age": r.get("age") or None, "sex": r.get("sex") or "F", "statin": (r.get("statin") or "none").lower(),
                **{k: r.get(k, "").lower() in YES for k in ("early_cad", "xanthoma", "arcus", "fhx_cad", "fhx_ldl")}})
            out.append({"row": i, "input": r, "result": res})
        except live.BadInput as e:
            out.append({"row": i, "input": r, "error": e.message})
    return {"rows": out, "scored": sum("result" in x for x in out), "failed": sum("error" in x for x in out)}


@app.get("/api/demo/guide")
def guide(con: sqlite3.Connection = Depends(db)):
    """Where the guided demo stands, worked out from what has really happened. Demo scaffolding only."""
    on = store.today(con)
    c = con.execute("SELECT c.* FROM cases c JOIN labs l ON l.person_id=c.person_id WHERE l.source='live' "
                    "ORDER BY c.id DESC LIMIT 1").fetchone()
    out = {"step": "start", "person_id": None, "invite_token": None, "found_person_id": None, "today": on.isoformat()}
    if c is None:
        return out
    out["person_id"] = c["person_id"]
    s = c["status"]
    if s == "flagged":
        out["step"] = "review"
    elif s == "test_ordered":
        out["step"] = "wait_test"
    elif s in ("dismissed", "no_variant") or c["consent"] == 0:
        out["step"] = "stopped"
    elif c["consent"] is None:
        out["step"] = "consent"
    elif not c["cascade_at"]:
        out["step"] = "send"
    else:
        inv = con.execute("SELECT token FROM invitations WHERE case_id=? ORDER BY status='sent' DESC, id LIMIT 1",
                          (c["id"],)).fetchone()
        out["invite_token"] = inv["token"] if inv else None
        found = con.execute("SELECT person_id FROM cases WHERE index_of=? ORDER BY source='cascade' DESC, id LIMIT 1",
                            (c["id"],)).fetchone()
        replied = con.execute("SELECT COUNT(*) FROM invitations WHERE case_id=? AND responded_at IS NOT NULL",
                              (c["id"],)).fetchone()[0]
        if found:
            out["step"], out["found_person_id"] = "found", found["person_id"]
        elif on.isoformat() == c["cascade_at"] and not replied and inv:
            out["step"] = "relative"
        elif (on - date.fromisoformat(c["cascade_at"])).days < 14:
            out["step"] = "wait_family"
        else:
            out["step"] = "found"
    return out


@app.post("/api/simulate/new-result")
def new_result(con: sqlite3.Connection = Depends(db)):
    return simulate.ingest_new_result(con)


class AdvanceIn(BaseModel):
    weeks: int = 2


@app.post("/api/simulate/advance")
def advance(body: AdvanceIn, con: sqlite3.Connection = Depends(db)):
    return simulate.advance(con, body.weeks)


@app.post("/api/reset")
def reset(con: sqlite3.Connection = Depends(db)):
    cascade.reset(con)
    return {"ok": True}


@app.get("/api/audit")
def audit_log(page: int = Query(1, ge=1), per_page: int = Query(50, le=200), q: str = "", decisions: bool = False,
              role: str = Depends(actor), con: sqlite3.Connection = Depends(db)):
    allow(role, "lead")
    where, args = ["action_key<>'case_opened' OR actor_role<>'system'"], []
    if q:
        where.append("(action LIKE ? OR actor LIKE ?)")
        args += [f"%{q}%"] * 2
    if decisions:
        where.append(f"actor_role IN ({','.join('?' * len(machine.ROLES))})")
        args += list(machine.ROLES)
    w = "WHERE " + " AND ".join(f"({x})" for x in where)
    total = con.execute(f"SELECT COUNT(*) FROM audit {w}", args).fetchone()[0]
    rows = con.execute(f"SELECT * FROM audit {w} ORDER BY id DESC LIMIT ? OFFSET ?",
                       args + [per_page, (page - 1) * per_page]).fetchall()
    return {"total": total, "page": page, "items": [
        {"id": r["id"], "date": r["sim_date"], "logged_at": r["logged_at"], "actor": r["actor"], "role": r["actor_role"],
         "action": r["action"], "case_id": r["case_id"], "from": r["from_status"], "to": r["to_status"],
         "detail": json.loads(r["detail"]) if r["detail"] else None} for r in rows]}


@app.get("/api/fhir/Patient/{pid}")
def fhir_bundle(pid: int, con: sqlite3.Connection = Depends(db)):
    try:
        b = fhir.bundle(con, pid)
    except KeyError:
        raise Refusal("not_found", "person_not_found", "No such person.")
    store.audit(con, "clinician", "fhir_export", "Record exported as FHIR", person_id=pid,
                detail={"resources": len(b["entry"])})
    con.commit()
    return b


# In the container the built web app is served from the same origin.
_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
