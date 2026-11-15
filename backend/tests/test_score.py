"""The scoring endpoint: typed-in numbers, CSV rows, what-if on a record, and the stage timings."""
import unittest

from tests import _db  # noqa: F401
from tests._flow import CLINICIAN, LEAD, client

STAGES = ["received", "record", "features", "model", "clinical", "threshold", "worklist"]


class ScoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = client().__enter__()
        cls.c.post("/api/reset")

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def score(self, panel, context=None):
        return self.c.post("/api/score", json={"panel": panel, "context": context or {}})

    def test_typed_numbers_go_through_every_stage(self):
        r = self.score({"ldl": 7.2, "tc": 9.1, "hdl": 1.2, "tg": 1.4}, {"age": 34, "sex": "M"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual([s["key"] for s in body["stages"]], STAGES)
        self.assertTrue(all(s["ms"] >= 0 for s in body["stages"]))
        self.assertEqual(body["model"], "own")
        self.assertTrue(0 <= body["prob"] <= 1)
        why = body["why"]
        self.assertAlmostEqual(why["base"] + sum(s["value"] for s in why["steps"]), why["end"], places=2)

    def test_higher_ldl_scores_higher(self):
        low = self.score({"ldl": 3.0}, {"age": 40}).json()["prob"]
        high = self.score({"ldl": 8.0}, {"age": 40}).json()["prob"]
        self.assertGreater(high, low)

    def test_units_convert(self):
        mmol = self.score({"ldl": 7.0}).json()["prob"]
        mgdl = self.score({"ldl": 7.0 * 38.67, "unit": "mgdl"}).json()["prob"]
        self.assertAlmostEqual(mmol, mgdl, places=3)

    def test_bad_input_is_explained(self):
        self.assertEqual(self.score({"ldl": "abc"}).json()["code"], "bad_ldl")
        self.assertEqual(self.score({}).json()["code"], "bad_ldl")
        self.assertEqual(self.score({"ldl": 99}).status_code, 400)
        self.assertEqual(self.score({"ldl": 5}, {"age": 300}).json()["code"], "bad_age")

    def test_nothing_typed_in_is_stored(self):
        before = self.c.get("/api/summary").json()
        self.score({"ldl": 9.0})
        self.c.post("/api/score/csv", json={"text": self.c.get("/api/score/sample.csv").text})
        after = self.c.get("/api/summary").json()
        self.assertEqual((before["screened"], before["cases"]), (after["screened"], after["cases"]))

    def test_csv_scores_good_rows_and_explains_bad_ones(self):
        text = self.c.get("/api/score/sample.csv").text + "not-a-number,1,1,1\n"
        body = self.c.post("/api/score/csv", json={"text": text}).json()
        self.assertEqual(body["scored"], 5)
        self.assertEqual(body["failed"], 1)
        self.assertIn("must be a number", body["rows"][-1]["error"])
        self.assertEqual(self.c.post("/api/score/csv", json={"text": "a,b\n1,2"}).json()["code"], "no_ldl_column")

    def test_what_if_changes_the_score_but_not_the_record(self):
        pid = self.c.get("/api/queue", headers=CLINICIAN).json()["items"][0]["open"]
        real = self.c.get(f"/api/patients/{pid}/explain", headers=CLINICIAN).json()
        lower = self.c.post("/api/score", json={"person_id": pid, "overrides": {"ldl": 2.5}}, headers=CLINICIAN).json()
        self.assertLess(lower["prob"], real["prob"])
        again = self.c.get(f"/api/patients/{pid}/explain", headers=CLINICIAN).json()
        self.assertAlmostEqual(again["prob"], real["prob"], places=6)
        self.assertEqual(self.c.post("/api/score", json={"person_id": pid}, headers=LEAD).status_code, 403)


if __name__ == "__main__":
    unittest.main()
