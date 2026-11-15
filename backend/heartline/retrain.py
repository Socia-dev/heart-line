"""Retraining from the Model page, as a background job the page can watch.

- One run at a time. A second request while one is running is refused.
- A full run writes to data/candidate and a scores_candidate table. The live demo keeps using the current
  model until someone chooses "Use the new model".
- A quick run (3 folds on a share of families) shows the process in a fraction of the time. It cannot
  replace the model, because it has only scored part of the population.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone

from . import store
from .config import CANDIDATE, DATA, DB_PATH, EVAL_PATH, MODEL_PATH
from .machine import Refusal

QUICK = {"folds": 3, "sample": 0.35}
TIMES = DATA / "train_times.json"

_lock = threading.Lock()
_state: dict = {"status": "idle", "events": [], "quick": False, "started": None, "finished": None, "error": None,
                "result": None, "applied": False}


def _times() -> dict:
    try:
        return json.loads(TIMES.read_text())
    except (OSError, ValueError):
        return {}


def estimate() -> dict:
    """Seconds for each kind of run, from the last real runs on this machine (or a first guess)."""
    t = _times()
    full = t.get("full")
    if full is None and EVAL_PATH.exists():
        full = json.loads(EVAL_PATH.read_text()).get("train_seconds")
    full = full or 90
    return {"full": round(full), "quick": round(t.get("quick") or max(10, full * 0.2))}


def state() -> dict:
    with _lock:
        s = json.loads(json.dumps(_state))
    s["estimate"] = estimate()
    s["elapsed"] = round(time.time() - s["started"], 1) if s["started"] and s["status"] == "running" else None
    return s


def _event(e: dict):
    with _lock:
        _state["events"].append({**e, "t": round(time.time() - (_state["started"] or time.time()), 1)})


def _run(quick: bool):
    from .train import train  # imported here so the API starts without loading the training stack
    try:
        opts = QUICK if quick else {"folds": 5, "sample": None}
        out = CANDIDATE / ("quick" if quick else "full")
        ev = train(DB_PATH, out_dir=out, table="scores_quick" if quick else "scores_candidate", progress=_event, **opts)
        seconds = ev["train_seconds"]
        t = _times()
        t["quick" if quick else "full"] = seconds
        TIMES.parent.mkdir(parents=True, exist_ok=True)
        TIMES.write_text(json.dumps(t))
        with _lock:
            _state.update(status="done", finished=time.time(), result={
                "seconds": seconds, "quick": quick, "metrics": {k: {"auroc": v["auroc"], "auprc": v["auprc"], "name": v["name"]}
                                                                 for k, v in ev["metrics"].items()},
                "found": {k: v["found"] for k, v in ev["matched_workload"]["methods"].items()},
                "threshold": ev["worklist_threshold"]["threshold"], "people": ev["population"]["with_labs"]})
    except Exception as e:  # report, do not crash the API
        with _lock:
            _state.update(status="failed", finished=time.time(), error=f"{type(e).__name__}: {e}")


def start(quick: bool) -> dict:
    with _lock:
        if _state["status"] == "running":
            raise Refusal("business", "already_running", "A retrain is already running. Wait for it to finish.")
        _state.update(status="running", events=[], quick=quick, started=time.time(), finished=None, error=None,
                      result=None, applied=False)
    threading.Thread(target=_run, args=(quick,), daemon=True).start()
    return state()


def apply(on_swap) -> dict:
    """Make the finished full run the live model. on_swap clears the caches that hold the old one."""
    with _lock:
        if _state["status"] != "done" or not _state["result"] or _state["applied"]:
            raise Refusal("business", "nothing_to_apply", "There is no finished run to use.")
        if _state["quick"]:
            raise Refusal("business", "quick_run", "A quick run only scored part of the population, so it cannot replace the model.")
    src = CANDIDATE / "full"
    con = store.connect(schema=False)
    try:
        con.execute("BEGIN")
        con.execute("DROP TABLE IF EXISTS scores")
        con.execute("ALTER TABLE scores_candidate RENAME TO scores")
        con.commit()
    finally:
        con.close()
    for name, dest in (("model.joblib", MODEL_PATH), ("evaluation.json", EVAL_PATH)):
        tmp = dest.with_suffix(dest.suffix + ".new")
        shutil.copy(src / name, tmp)
        os.replace(tmp, dest)
    on_swap()
    with _lock:
        _state["applied"] = True
        _state["events"].append({"kind": "stage", "text": "Now using the new model", "t": None,
                                 "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    return state()


def _reset_for_tests():
    with _lock:
        _state.update(status="idle", events=[], started=None, finished=None, error=None, result=None, applied=False)
