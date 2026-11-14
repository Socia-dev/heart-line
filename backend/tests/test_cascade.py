import unittest

from tests import _db  # noqa: F401
from tests._flow import client, confirm_new_result, run_story

from heartline import cascade, store


class CascadeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = client().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def test_consent_required_before_invitations(self):
        c = self.c
        c.post("/api/reset")
        pid = c.post("/api/simulate/new-result").json()["person_id"]
        c.post(f"/api/patients/{pid}/review", json={"action": "order_test"})
        case_id = c.get(f"/api/patients/{pid}").json()["case"]["id"]
        # Not confirmed yet.
        self.assertEqual(c.post(f"/api/patients/{pid}/consent", json={"consent": True}).status_code, 400)
        self.assertEqual(c.post(f"/api/cases/{case_id}/cascade").status_code, 400)
        c.post("/api/simulate/advance", json={"weeks": 2})
        # Confirmed but no consent yet, then consent declined.
        self.assertEqual(c.post(f"/api/cases/{case_id}/cascade").status_code, 400)
        c.post(f"/api/patients/{pid}/consent", json={"consent": False})
        self.assertEqual(c.post(f"/api/cases/{case_id}/cascade").status_code, 400)
        self.assertEqual(c.get("/api/invitations").json()["invitations"], [])
        self.assertEqual(c.get("/api/wellchild").json()["items"], [])
        c.post(f"/api/patients/{pid}/consent", json={"consent": True})
        r = c.post(f"/api/cases/{case_id}/cascade")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.json()["invited"] + r.json()["wellchild"], 0)
        self.assertEqual(c.post(f"/api/cases/{case_id}/cascade").status_code, 400)  # only once

    def test_deceased_never_invited_and_chain_continues(self):
        run_story(self.c)
        con = store.connect()
        dead = con.execute("SELECT COUNT(*) FROM invitations i JOIN people p ON p.id = i.person_id "
                           "WHERE p.death_date IS NOT NULL").fetchone()[0]
        dead += con.execute("SELECT COUNT(*) FROM wellchild w JOIN people p ON p.id = w.person_id "
                            "WHERE p.death_date IS NOT NULL").fetchone()[0]
        self.assertEqual(dead, 0)
        chained = con.execute("SELECT * FROM cases WHERE source='cascade' AND consent=1").fetchall()
        self.assertTrue(chained, "expected a positive relative who consented")
        for ch in chained:
            self.assertIsNotNone(ch["cascade_at"])
            self.assertIsNotNone(ch["index_of"])
        # The chain reached people beyond the index patient's own relatives.
        second = con.execute("SELECT COUNT(*) FROM invitations i JOIN cases c ON c.id = i.case_id "
                             "WHERE c.source='cascade'").fetchone()[0]
        second += con.execute("SELECT COUNT(*) FROM wellchild w JOIN cases c ON c.id = w.case_id "
                              "WHERE c.source='cascade'").fetchone()[0]
        self.assertGreater(second, 0)
        con.close()

    def test_deceased_relative_skipped_by_start_cascade(self):
        con = store.connect()
        cascade.reset(con)
        pid = con.execute("SELECT c.id FROM people c JOIN people m ON m.id = c.mother_id WHERE c.death_date IS NULL "
                          "AND m.death_date IS NOT NULL AND c.id NOT IN (SELECT person_id FROM cases) LIMIT 1").fetchone()[0]
        con.execute("INSERT INTO cases (person_id, source, status, consent, created_at, updated_at) "
                    "VALUES (?, 'detection', 'clinical_fh', 1, '2026-11-15', '2026-11-15')", (pid,))
        cid = con.execute("SELECT id FROM cases WHERE person_id=?", (pid,)).fetchone()[0]
        cascade.start_cascade(con, cid)
        mother = con.execute("SELECT mother_id FROM people WHERE id=?", (pid,)).fetchone()[0]
        self.assertIsNone(con.execute("SELECT 1 FROM invitations WHERE person_id=?", (mother,)).fetchone())
        con.close()

    def test_invalid_transitions(self):
        c = self.c
        c.post("/api/reset")
        pid = c.get("/api/worklist").json()["items"][0]["id"]
        self.assertEqual(c.post(f"/api/patients/{pid}/review", json={"action": "mark_clinical"}).status_code, 400)
        self.assertEqual(c.post(f"/api/patients/{pid}/review", json={"action": "dismiss"}).status_code, 200)
        self.assertEqual(c.post(f"/api/patients/{pid}/review", json={"action": "order_test"}).status_code, 400)

    def test_demo_is_repeatable(self):
        def outcome():
            run_story(self.c)
            con = store.connect()
            r = (sorted(tuple(x) for x in con.execute("SELECT person_id, status FROM cases WHERE source<>'detection'")),
                 sorted(tuple(x) for x in con.execute("SELECT person_id, status FROM invitations")))
            con.close()
            return r
        self.assertEqual(outcome(), outcome())

    def test_booking(self):
        c = self.c
        pid, case_id = confirm_new_result(c)
        c.post(f"/api/patients/{pid}/consent", json={"consent": True})
        c.post(f"/api/cases/{case_id}/cascade")
        tok = c.get("/api/invitations").json()["invitations"][0]["token"]
        view = c.get(f"/api/invite/{tok}").json()
        self.assertEqual(view["status"], "open")
        self.assertEqual(c.post(f"/api/invite/{tok}/book", json={"slot": view["slots"][0]}).status_code, 200)
        self.assertEqual(c.get(f"/api/invite/{tok}").json()["status"], "booked")
        self.assertEqual(c.post(f"/api/invite/{tok}/book", json={"slot": view["slots"][1]}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
