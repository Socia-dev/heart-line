"""Heart Line API.

Run: uvicorn heartline.api:app --port 8000   (from backend/)

The `truth` table is never read here. Test results are simulated inside cascade.py.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import cascade, fhir, pilot, store
from .config import EVAL_PATH, PREMATURE_AGE

app = FastAPI(title="Heart Line", description="Prototype on synthetic data. Not for clinical use.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

STATUS_LABEL = {
    "flagged": "Flagged", "in_review": "In review", "test_ordered": "Test ordered",
    "confirmed_genetic": "Confirmed (genetic)", "no_variant": "No variant found", "clinical_fh": "Clinical FH",
    "dismissed": "Dismissed",
}


def db():
    con = store.connect(schema=False)
    try:
        yield con
    finally:
        con.close()


@app.on_event("startup")
def startup():
    con = store.connect()
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='scores'").fetchone():
            raise RuntimeError("No scores table. Run `python -m heartline.train` first.")
        if not con.execute("SELECT 1 FROM sim WHERE key='initialized'").fetchone():
            cascade.init_cases(con)
    finally:
        con.close()


def bad(e: Exception):
    raise HTTPException(400, str(e))


def _person_brief(p, on: date) -> dict:
    return {"id": p["id"], "mrn": p["mrn"], "name": store.full_name(p), "given": p["given"], "sex": p["sex"],
            "age": int(store.age(p["birth_date"], on)), "deceased": p["death_date"] is not None}


# ------------------------------------------------------------------ overview

@lru_cache(maxsize=1)
def _pilot():
    return pilot.run()


@app.get("/api/summary")
def summary(con: sqlite3.Connection = Depends(db)):
    def counts(sql):
        return {r[0]: r[1] for r in con.execute(sql)}

    cases = counts("SELECT status, COUNT(*) FROM cases GROUP BY status")
    by_source = counts("SELECT source, COUNT(*) FROM cases WHERE status IN ('confirmed_genetic','clinical_fh') "
                       "GROUP BY source")
    inv = counts("SELECT status, COUNT(*) FROM invitations GROUP BY status")
    wc = counts("SELECT status, COUNT(*) FROM wellchild GROUP BY status")
    latest = con.execute("SELECT c.person_id, c.id FROM cases c JOIN labs l ON l.person_id=c.person_id "
                         "WHERE l.source='live' ORDER BY c.id DESC LIMIT 1").fetchone()
    p = _pilot()
    return {
        "today": store.today(con).isoformat(),
        "screened": con.execute("SELECT COUNT(*) FROM scores").fetchone()[0],
        "cases": cases,
        "open_cases": sum(cases.get(s, 0) for s in cascade.OPEN),
        "confirmed": sum(cases.get(s, 0) for s in cascade.CONFIRMED),
        "confirmed_by_source": by_source,
        "invitations": inv, "invitations_total": sum(inv.values()),
        "wellchild": wc, "wellchild_total": sum(wc.values()),
        "letters_abroad": con.execute("SELECT COALESCE(SUM(relatives_abroad),0) FROM family_letters").fetchone()[0],
        "latest_live": {"person_id": latest[0], "case_id": latest[1]} if latest else None,
        "pilot": {"label": p["label"], "totals": p["totals"]},
    }


@app.get("/api/evaluation")
def evaluation():
    if not EVAL_PATH.exists():
        raise HTTPException(404, "Run training first")
    return json.loads(EVAL_PATH.read_text())


@app.get("/api/pilot")
def pilot_projection():
    return _pilot()


# ------------------------------------------------------------------ worklist and patient

@app.get("/api/worklist")
def worklist(status: str = "", q: str = "", page: int = Query(1, ge=1), per_page: int = Query(25, le=100),
             con: sqlite3.Connection = Depends(db)):
    where, args = [], []
    if status == "open":
        where.append(f"c.status IN ({','.join('?' * len(cascade.OPEN))})")
        args += list(cascade.OPEN)
    elif status:
        where.append("c.status=?")
        args.append(status)
    if q:
        where.append("(p.given || ' ' || p.family LIKE ? OR p.mrn LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    w = ("WHERE " + " AND ".join(where)) if where else ""
    base = f"FROM cases c JOIN people p ON p.id=c.person_id LEFT JOIN scores s ON s.person_id=c.person_id {w}"
    total = con.execute(f"SELECT COUNT(*) {base}", args).fetchone()[0]
    rows = con.execute(f"SELECT c.*, p.*, c.id AS case_id, s.prob_b, s.dlcn_total, s.dlcn_band, s.reasons, "
                       f"(SELECT COUNT(*) FROM labs l WHERE l.person_id=c.person_id AND l.source='live') AS live "
                       f"{base} ORDER BY live DESC, s.prob_b DESC, c.id LIMIT ? OFFSET ?",
                       args + [per_page, (page - 1) * per_page]).fetchall()
    on = store.today(con)
    return {"total": total, "page": page, "per_page": per_page, "items": [{
        **_person_brief(r, on), "id": r["person_id"], "case_id": r["case_id"], "status": r["status"],
        "status_label": STATUS_LABEL[r["status"]], "source": r["source"], "score": r["prob_b"],
        "dlcn_total": r["dlcn_total"], "dlcn_band": r["dlcn_band"], "new": bool(r["live"]),
        "reasons": json.loads(r["reasons"] or "[]"), "group": r["nationality_group"]} for r in rows]}


def relative_status(con, pid: int, deceased: bool) -> str:
    if deceased:
        return "deceased"
    c = con.execute("SELECT status FROM cases WHERE person_id=?", (pid,)).fetchone()
    if c and c["status"] in cascade.CONFIRMED:
        return "confirmed"
    inv = con.execute("SELECT status FROM invitations WHERE person_id=?", (pid,)).fetchone()
    wc = con.execute("SELECT status FROM wellchild WHERE person_id=?", (pid,)).fetchone()
    if inv:
        return {"sent": "invited", "booked": "booked", "negative": "negative", "no_response": "no_response",
                "positive": "confirmed"}[inv["status"]]
    if wc:
        return {"due": "wellchild", "tested_negative": "negative", "tested_positive": "confirmed"}[wc["status"]]
    if c and c["status"] in cascade.OPEN:
        return "assessing"
    if c and c["status"] in ("no_variant", "dismissed"):
        return "not_confirmed"
    return "unknown"


def family_tree(con, pid: int) -> dict:
    on = store.today(con)
    me = store.person(con, pid)
    nodes: dict[int, dict] = {}

    def add(p, relation: str, gen: int, first_degree: bool = False):
        if p is None or p["id"] in nodes:
            return
        b = _person_brief(p, on)
        nodes[p["id"]] = {**b, "relation": relation, "generation": gen, "first_degree": first_degree,
                          "mother_id": p["mother_id"], "father_id": p["father_id"],
                          "status": "index" if p["id"] == pid else relative_status(con, p["id"], b["deceased"])}

    add(me, "This patient", 0)
    first = store.first_degree(con, pid, include_deceased=True)
    for r, rel in first:
        gen = {"mother": -1, "father": -1, "son": 1, "daughter": 1}.get(rel, 0)
        add(r, rel.capitalize(), gen, True)
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
    return {"nodes": list(nodes.values()), "relatives_abroad": me["relatives_abroad"] or 0}


def _actions(case, score) -> list[str]:
    if case is None:
        return []
    s = case["status"]
    acts = {"flagged": ["start_review", "order_test", "dismiss"], "in_review": ["order_test", "dismiss"],
            "no_variant": ["dismiss"] + (["mark_clinical"] if score and score["dlcn_total"] >= 6 else [])}.get(s, [])
    if s in cascade.CONFIRMED:
        if case["consent"] is None:
            acts.append("consent")
        elif case["consent"] == 1 and not case["cascade_at"]:
            acts.append("start_cascade")
    return acts


@app.get("/api/patients/{pid}")
def patient(pid: int, con: sqlite3.Connection = Depends(db)):
    p = store.person(con, pid)
    if p is None:
        raise HTTPException(404, "No such person")
    on = store.today(con)
    labs = [{"date": r["date"], "ldl": r["ldl"], "tc": r["tc"], "hdl": r["hdl"], "tg": r["tg"],
             "on_statin": bool(r["on_statin"]), "new": r["source"] == "live"}
            for r in con.execute("SELECT * FROM labs WHERE person_id=? ORDER BY date", (pid,))]
    sc = con.execute("SELECT * FROM scores WHERE person_id=?", (pid,)).fetchone()
    c = cascade.case_for_person(con, pid)
    case = None
    if c:
        case = {k: c[k] for k in c.keys()}
        case["status_label"] = STATUS_LABEL[c["status"]]
        if c["index_of"]:
            ic = cascade.get_case(con, c["index_of"])
            case["led_by"] = {"case_id": ic["id"], **_person_brief(store.person(con, ic["person_id"]), on)}
        case["led_to"] = [{"case_id": r["id"], "status": r["status"], **_person_brief(store.person(con, r["person_id"]), on)}
                          for r in con.execute("SELECT * FROM cases WHERE index_of=?", (c["id"],))]
        case["invitations"] = {r[0]: r[1] for r in con.execute(
            "SELECT status, COUNT(*) FROM invitations WHERE case_id=? GROUP BY status", (c["id"],))}
        case["wellchild"] = con.execute("SELECT COUNT(*) FROM wellchild WHERE case_id=?", (c["id"],)).fetchone()[0]
        letter = con.execute("SELECT relatives_abroad FROM family_letters WHERE case_id=?", (c["id"],)).fetchone()
        case["letter_abroad"] = letter[0] if letter else 0
    inv = con.execute("SELECT status, sent_at, slot FROM invitations WHERE person_id=?", (pid,)).fetchone()
    wc = con.execute("SELECT status, due_date FROM wellchild WHERE person_id=?", (pid,)).fetchone()
    return {
        "person": {**_person_brief(p, on), "birth_date": p["birth_date"], "death_date": p["death_date"],
                   "nationality_group": p["nationality_group"], "lang": p["lang"],
                   "relatives_abroad": p["relatives_abroad"], "statin_start": p["statin_start"],
                   "statin_intensity": p["statin_intensity"], "cad_age": p["cad_age"],
                   "early_cad": p["cad_age"] is not None and p["cad_age"] < PREMATURE_AGE[p["sex"]],
                   "xanthoma": bool(p["xanthoma"]), "arcus": bool(p["arcus"]),
                   "fhx_recorded_cad": bool(p["fhx_recorded_cad"]), "fhx_recorded_ldl": bool(p["fhx_recorded_ldl"])},
        "labs": labs,
        "score": None if sc is None else {
            "prob_b": sc["prob_b"], "prob_a": sc["prob_a"], "flagged": bool(sc["flagged"]),
            "dlcn_total": sc["dlcn_total"], "dlcn_band": sc["dlcn_band"], "dlcn_items": json.loads(sc["dlcn_items"]),
            "reasons": json.loads(sc["reasons"] or "[]"), "live": sc["prob_a"] is None},
        "case": case,
        "actions": _actions(c, sc),
        "invitation": dict(inv) if inv else None,
        "wellchild": dict(wc) if wc else None,
        "family": family_tree(con, pid),
        "history": [dict(r) for r in con.execute(
            "SELECT id, sim_date, actor, action, subject, detail FROM audit WHERE person_id=? ORDER BY id", (pid,))],
        "today": on.isoformat(),
    }


class ReviewIn(BaseModel):
    action: str
    note: str | None = None


@app.post("/api/patients/{pid}/review")
def review(pid: int, body: ReviewIn, con: sqlite3.Connection = Depends(db)):
    try:
        return cascade.review(con, pid, body.action, body.note)
    except cascade.Invalid as e:
        bad(e)


class ConsentIn(BaseModel):
    consent: bool


@app.post("/api/patients/{pid}/consent")
def consent(pid: int, body: ConsentIn, con: sqlite3.Connection = Depends(db)):
    try:
        return cascade.record_consent(con, pid, body.consent)
    except cascade.Invalid as e:
        bad(e)


@app.post("/api/cases/{case_id}/cascade")
def start_cascade(case_id: int, con: sqlite3.Connection = Depends(db)):
    try:
        return cascade.start_cascade(con, case_id)
    except cascade.Invalid as e:
        bad(e)


# ------------------------------------------------------------------ families

@app.get("/api/invitations")
def invitations(con: sqlite3.Connection = Depends(db)):
    on = store.today(con)
    invs = []
    for r in con.execute("SELECT i.*, c.person_id AS index_pid FROM invitations i JOIN cases c ON c.id=i.case_id "
                         "ORDER BY i.id DESC"):
        p = store.person(con, r["person_id"])
        ip = store.person(con, r["index_pid"])
        invs.append({"id": r["id"], "token": r["token"], "status": r["status"], "lang": r["lang"],
                     "sent_at": r["sent_at"], "slot": r["slot"], "booked_at": r["booked_at"], "tested_at": r["tested_at"],
                     "relative": _person_brief(p, on), "case_id": r["case_id"],
                     "via": {"case_id": r["case_id"], **_person_brief(ip, on)}})
    chain = []
    for c in con.execute("SELECT * FROM cases WHERE cascade_at IS NOT NULL OR index_of IS NOT NULL ORDER BY id"):
        n = {r[0]: r[1] for r in con.execute("SELECT status, COUNT(*) FROM invitations WHERE case_id=? GROUP BY status",
                                              (c["id"],))}
        chain.append({"case_id": c["id"], "index_of": c["index_of"], "source": c["source"], "status": c["status"],
                      "status_label": STATUS_LABEL[c["status"]], "consent": c["consent"], "cascade_at": c["cascade_at"],
                      "created_at": c["created_at"], "invited": sum(n.values()), "invitations": n,
                      "wellchild": con.execute("SELECT COUNT(*) FROM wellchild WHERE case_id=?", (c["id"],)).fetchone()[0],
                      **_person_brief(store.person(con, c["person_id"]), on), "id": c["person_id"]})
    letters = [dict(r) for r in con.execute("SELECT * FROM family_letters ORDER BY id DESC")]
    return {"invitations": invs, "chain": chain, "letters": letters, "today": on.isoformat()}


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
    """What the invited relative sees. It says nothing about who triggered it or why."""
    r = con.execute("SELECT person_id, lang, status, slot FROM invitations WHERE token=?", (token,)).fetchone()
    if r is None:
        raise HTTPException(404, "Invitation not found")
    p = store.person(con, r["person_id"])
    status = {"sent": "open", "booked": "booked"}.get(r["status"], "closed")
    return {"given": p["given"], "lang": r["lang"], "status": status, "slot": r["slot"],
            "slots": _slots(store.today(con)) if status == "open" else [], "mock": True}


class BookIn(BaseModel):
    slot: str


@app.post("/api/invite/{token}/book")
def invite_book(token: str, body: BookIn, con: sqlite3.Connection = Depends(db)):
    try:
        return cascade.book(con, token, body.slot)
    except cascade.Invalid as e:
        bad(e)


@app.get("/api/wellchild")
def wellchild(con: sqlite3.Connection = Depends(db)):
    on = store.today(con)
    out = []
    for r in con.execute("SELECT * FROM wellchild ORDER BY due_date, id"):
        p = store.person(con, r["person_id"])
        a = store.age(p["birth_date"], on)
        due = [("Lipid test at the Well-Child Visit" if a >= 2 else "Lipid test once the child turns 2")]
        if r["status"] == "tested_positive":
            due.append("Discuss statin treatment now" if a >= 8 else
                       f"Discuss statin treatment from age 8 to 10 (around {date.fromisoformat(p['birth_date']).year + 8})")
        parents = [store.person(con, p[c]) for c in ("mother_id", "father_id") if p[c]]
        out.append({"id": r["id"], "status": r["status"], "due_date": r["due_date"], "flagged_at": r["flagged_at"],
                    "tested_at": r["tested_at"], "child": {**_person_brief(p, on), "age_years": round(a, 1)},
                    "parents": [_person_brief(x, on) for x in parents], "case_id": r["case_id"], "due": due})
    return {"items": out, "today": on.isoformat()}


# ------------------------------------------------------------------ simulation, audit, export

@app.post("/api/simulate/new-result")
def new_result(con: sqlite3.Connection = Depends(db)):
    try:
        return cascade.ingest_new_result(con)
    except cascade.Invalid as e:
        bad(e)


class AdvanceIn(BaseModel):
    weeks: int = 2


@app.post("/api/simulate/advance")
def advance(body: AdvanceIn, con: sqlite3.Connection = Depends(db)):
    return cascade.advance(con, body.weeks)


@app.get("/api/audit")
def audit_log(page: int = Query(1, ge=1), per_page: int = Query(50, le=200), q: str = "",
              con: sqlite3.Connection = Depends(db)):
    w, args = "", []
    if q:
        w = "WHERE action LIKE ? OR actor LIKE ? OR subject LIKE ?"
        args = [f"%{q}%"] * 3
    total = con.execute(f"SELECT COUNT(*) FROM audit {w}", args).fetchone()[0]
    rows = con.execute(f"SELECT * FROM audit {w} ORDER BY id DESC LIMIT ? OFFSET ?",
                       args + [per_page, (page - 1) * per_page]).fetchall()
    return {"total": total, "page": page, "items": [dict(r) for r in rows]}


@app.get("/api/fhir/Patient/{pid}")
def fhir_bundle(pid: int, con: sqlite3.Connection = Depends(db)):
    try:
        b = fhir.bundle(con, pid)
    except KeyError:
        raise HTTPException(404, "No such person")
    store.audit(con, "Dr. Clinician (demo)", "FHIR export", f"person {pid}", pid, {"entries": len(b["entry"])})
    con.commit()
    return b


@app.post("/api/reset")
def reset(con: sqlite3.Connection = Depends(db)):
    cascade.reset(con)
    return {"ok": True}
