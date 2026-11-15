"""Shared demo flow for the API tests."""
from tests import _db  # noqa: F401

from fastapi.testclient import TestClient

from heartline.api import app

CLINICIAN = {"X-Demo-Role": "clinician"}
COORDINATOR = {"X-Demo-Role": "coordinator"}
NURSE = {"X-Demo-Role": "nurse"}
LEAD = {"X-Demo-Role": "lead"}


def client() -> TestClient:
    return TestClient(app)


def act(c: TestClient, pid: int, action: str, role=CLINICIAN, **inputs):
    return c.post(f"/api/patients/{pid}/act", json={"action": action, **inputs}, headers=role)


def confirm_new_result(c: TestClient) -> int:
    """Reset, ingest a new result, order the test and let it come back. Returns the person id."""
    c.post("/api/reset")
    pid = c.post("/api/simulate/new-result").json()["person_id"]
    act(c, pid, "order_test")
    c.post("/api/simulate/advance", json={"weeks": 2})
    return pid


def run_story(c: TestClient) -> int:
    """Play the demo story up to the first relatives being tested. Returns the index patient's id."""
    pid = confirm_new_result(c)
    act(c, pid, "consent_yes")
    act(c, pid, "start_cascade", COORDINATOR)
    for _ in range(3):
        c.post("/api/simulate/advance", json={"weeks": 2})
    return pid
