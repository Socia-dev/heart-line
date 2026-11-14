"""Database helpers: connections, demo-state tables, simulated clock, relatives and the audit log."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone

from .config import DB_PATH, REF_DATE

DEMO_SCHEMA = """
CREATE TABLE IF NOT EXISTS sim (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY, person_id INTEGER UNIQUE, source TEXT, index_of INTEGER, status TEXT,
  created_at TEXT, updated_at TEXT, test_due TEXT, variant TEXT,
  consent INTEGER, consent_by TEXT, consent_at TEXT, cascade_at TEXT
);
CREATE TABLE IF NOT EXISTS invitations (
  id INTEGER PRIMARY KEY, token TEXT UNIQUE, person_id INTEGER UNIQUE, case_id INTEGER, lang TEXT, status TEXT,
  sent_at TEXT, slot TEXT, booked_at TEXT, tested_at TEXT
);
CREATE TABLE IF NOT EXISTS wellchild (
  id INTEGER PRIMARY KEY, person_id INTEGER UNIQUE, case_id INTEGER, flagged_at TEXT, due_date TEXT, status TEXT,
  tested_at TEXT
);
CREATE TABLE IF NOT EXISTS family_letters (id INTEGER PRIMARY KEY, case_id INTEGER, relatives_abroad INTEGER,
  created_at TEXT);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, sim_date TEXT, logged_at TEXT, actor TEXT, action TEXT, subject TEXT, person_id INTEGER,
  detail TEXT
);
CREATE INDEX IF NOT EXISTS audit_person ON audit(person_id);
CREATE INDEX IF NOT EXISTS cases_status ON cases(status);
"""

DEMO_TABLES = ("cases", "invitations", "wellchild", "family_letters", "audit", "sim")


def connect(path=DB_PATH, schema: bool = True) -> sqlite3.Connection:
    con = sqlite3.connect(path, check_same_thread=False, timeout=15)
    con.row_factory = sqlite3.Row
    if schema:
        con.executescript(DEMO_SCHEMA)
    return con


# ------------------------------------------------------------------ simulated clock

def today(con) -> date:
    r = con.execute("SELECT value FROM sim WHERE key='day'").fetchone()
    return REF_DATE + timedelta(days=int(r["value"]) if r else 0)


def set_day(con, d: date):
    con.execute("INSERT OR REPLACE INTO sim (key, value) VALUES ('day', ?)", (str((d - REF_DATE).days),))


def age(birth: str, on: date) -> float:
    return (on - date.fromisoformat(birth)).days / 365.25


# ------------------------------------------------------------------ people and relatives

def person(con, pid: int):
    return con.execute("SELECT * FROM people WHERE id=?", (pid,)).fetchone()


def first_degree(con, pid: int, include_deceased: bool = False) -> list[tuple[sqlite3.Row, str]]:
    """Parents, children and full siblings, with the relation as seen from pid."""
    p = person(con, pid)
    if p is None:
        return []
    out = []
    for col, rel in (("mother_id", "mother"), ("father_id", "father")):
        if p[col]:
            out.append((person(con, p[col]), rel))
    for c in con.execute("SELECT * FROM people WHERE mother_id=? OR father_id=? ORDER BY birth_date", (pid, pid)):
        out.append((c, "son" if c["sex"] == "M" else "daughter"))
    if p["mother_id"] and p["father_id"]:
        for s in con.execute("SELECT * FROM people WHERE mother_id=? AND father_id=? AND id<>? ORDER BY birth_date",
                             (p["mother_id"], p["father_id"], pid)):
            out.append((s, "brother" if s["sex"] == "M" else "sister"))
    if not include_deceased:
        out = [(r, rel) for r, rel in out if r["death_date"] is None]
    return out


def spouses_of(con, pid: int) -> list[sqlite3.Row]:
    ids = [r[0] for r in con.execute("SELECT b FROM spouses WHERE a=? UNION SELECT a FROM spouses WHERE b=?", (pid, pid))]
    return [person(con, i) for i in ids]


def children_of(con, pid: int) -> list[sqlite3.Row]:
    return list(con.execute("SELECT * FROM people WHERE mother_id=? OR father_id=? ORDER BY birth_date", (pid, pid)))


def full_name(p) -> str:
    return f"{p['given']} {p['family']}"


# ------------------------------------------------------------------ audit

def audit(con, actor: str, action: str, subject: str, person_id: int | None = None, detail: dict | str | None = None):
    if isinstance(detail, dict):
        detail = json.dumps(detail)
    con.execute("INSERT INTO audit (sim_date, logged_at, actor, action, subject, person_id, detail) VALUES (?,?,?,?,?,?,?)",
                (today(con).isoformat(), datetime.now(timezone.utc).isoformat(timespec="seconds"), actor, action, subject,
                 person_id, detail))
