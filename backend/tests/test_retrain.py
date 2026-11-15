"""The retrain job: one run at a time, quick runs cannot replace the model, and only the lead can start it."""
import threading
import unittest
from unittest import mock

from tests import _db  # noqa: F401
from tests._flow import CLINICIAN, LEAD, client

from heartline import retrain


class RetrainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = client().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def setUp(self):
        retrain._reset_for_tests()

    def test_cannot_run_twice_at_once(self):
        release = threading.Event()

        def slow(quick):
            release.wait(5)
            with retrain._lock:
                retrain._state.update(status="done", result={"quick": quick})

        with mock.patch.object(retrain, "_run", side_effect=slow):
            first = self.c.post("/api/model/retrain", json={"quick": True}, headers=LEAD)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json()["status"], "running")
            second = self.c.post("/api/model/retrain", json={"quick": False}, headers=LEAD)
            self.assertEqual(second.status_code, 422)
            self.assertEqual(second.json()["code"], "already_running")
            release.set()

    def test_a_quick_run_cannot_replace_the_model(self):
        with retrain._lock:
            retrain._state.update(status="done", quick=True, result={"quick": True})
        r = self.c.post("/api/model/retrain/apply", headers=LEAD)
        self.assertEqual(r.json()["code"], "quick_run")

    def test_nothing_to_apply_before_a_run(self):
        self.assertEqual(self.c.post("/api/model/retrain/apply", headers=LEAD).json()["code"], "nothing_to_apply")

    def test_only_the_programme_lead(self):
        self.assertEqual(self.c.post("/api/model/retrain", json={"quick": True}, headers=CLINICIAN).status_code, 403)
        self.assertEqual(self.c.get("/api/model/retrain", headers=CLINICIAN).status_code, 403)
        st = self.c.get("/api/model/retrain", headers=LEAD).json()
        self.assertIn("estimate", st)


if __name__ == "__main__":
    unittest.main()
