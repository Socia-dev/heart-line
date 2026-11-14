"""Shared demo flow for the API tests."""
from tests import _db  # noqa: F401

from fastapi.testclient import TestClient

from heartline.api import app


def client() -> TestClient:
    return TestClient(app)


def confirm_new_result(c: TestClient) -> tuple[int, int]:
    """Reset, ingest a new result, order the test and let it come back. Returns (person id, case id)."""
    c.post("/api/reset")
    pid = c.post("/api/simulate/new-result").json()["person_id"]
    c.post(f"/api/patients/{pid}/review", json={"action": "start_review"})
    c.post(f"/api/patients/{pid}/review", json={"action": "order_test"})
    c.post("/api/simulate/advance", json={"weeks": 2})
    return pid, c.get(f"/api/patients/{pid}").json()["case"]["id"]


def run_story(c: TestClient) -> int:
    """Play the demo story. Returns the index patient's id."""
    pid, case_id = confirm_new_result(c)
    c.post(f"/api/patients/{pid}/consent", json={"consent": True})
    c.post(f"/api/cases/{case_id}/cascade")
    for _ in range(3):
        c.post("/api/simulate/advance", json={"weeks": 2})
    return pid
