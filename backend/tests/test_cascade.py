import sqlite3
import unittest

from tests import _db  # noqa: F401
from tests._flow import CLINICIAN, COORDINATOR, LEAD, NURSE, act, client, confirm_new_result, run_story

from heartline import cascade, store


class CascadeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = client().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def invitations(self):
        return self.c.get("/api/invitations", headers=COORDINATOR).json()["invitations"]

    def test_consent_required_before_invitations(self):
        c = self.c
        c.post("/api/reset")
        pid = c.post("/api/simulate/new-result").json()["person_id"]
        act(c, pid, "order_test")
        # Not confirmed yet.
        self.assertEqual(act(c, pid, "consent_yes").status_code, 422)
        self.assertEqual(act(c, pid, "start_cascade", COORDINATOR).status_code, 422)
        c.post("/api/simulate/advance", json={"weeks": 2})
        # Confirmed but no consent yet, then consent declined.
        self.assertEqual(act(c, pid, "start_cascade", COORDINATOR).json()["code"], "no_consent")
        act(c, pid, "consent_no")
        self.assertEqual(act(c, pid, "start_cascade", COORDINATOR).status_code, 422)
        self.assertEqual(self.invitations(), [])
        self.assertEqual(c.get("/api/wellchild", headers=NURSE).json()["items"], [])
        # The patient reconsiders.
        self.assertEqual(act(c, pid, "consent_reopen").status_code, 200)
        act(c, pid, "consent_yes")
        r = act(c, pid, "start_cascade", COORDINATOR)
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.json()["cascade"]["invited"] + r.json()["cascade"]["wellchild"], 0)
        self.assertEqual(act(c, pid, "start_cascade", COORDINATOR).json()["code"], "already_started")  # only once

    def test_roles_are_enforced_on_the_server(self):
        c = self.c
        pid = confirm_new_result(c)
        self.assertEqual(act(c, pid, "consent_yes", COORDINATOR).status_code, 403)
        act(c, pid, "consent_yes")
        self.assertEqual(act(c, pid, "start_cascade", CLINICIAN).status_code, 403)
        self.assertEqual(act(c, pid, "start_cascade", NURSE).status_code, 403)
        self.assertEqual(c.get(f"/api/patients/{pid}", headers=LEAD).status_code, 403)
        self.assertEqual(c.get("/api/audit", headers=CLINICIAN).status_code, 403)
        self.assertEqual(c.get("/api/invitations", headers=CLINICIAN).status_code, 403)
        # The refused attempts are in the audit log.
        log = c.get("/api/audit?per_page=20", headers=LEAD).json()["items"]
        self.assertTrue(any(r["action"].startswith("Refused") for r in log))

    def test_preview_matches_what_is_sent_and_respects_the_patients_exclusions(self):
        c = self.c
        pid = confirm_new_result(c)
        tree = c.get(f"/api/patients/{pid}", headers=CLINICIAN).json()["family"]["nodes"]
        adults = [n["id"] for n in tree if n["first_degree"] and not n["deceased"] and n["age"] >= 18]
        self.assertGreater(len(adults), 1)
        act(c, pid, "consent_yes", exclude=[adults[0]])
        plan = c.get(f"/api/patients/{pid}", headers=COORDINATOR).json()["next"]["plan"]
        row = next(r for r in plan["relatives"] if r["id"] == adults[0])
        self.assertEqual(row["outcome"], "none")
        sent = act(c, pid, "start_cascade", COORDINATOR).json()["cascade"]
        self.assertEqual((sent["invited"], sent["wellchild"]), (plan["invite"], plan["wellchild"]))
        self.assertNotIn(adults[0], [i["relative"]["id"] for i in self.invitations()])

    def test_dismiss_needs_a_reason_and_can_be_reopened(self):
        c = self.c
        c.post("/api/reset")
        pid = c.get("/api/queue", headers=CLINICIAN).json()["items"][0]["open"]
        self.assertEqual(act(c, pid, "dismiss").json()["code"], "missing_reason")
        self.assertEqual(act(c, pid, "mark_clinical").status_code, 422)
        self.assertEqual(act(c, pid, "dismiss", reason="secondary_cause").status_code, 200)
        self.assertEqual(act(c, pid, "order_test").status_code, 422)
        self.assertEqual(act(c, pid, "reopen").status_code, 200)
        self.assertEqual(act(c, pid, "order_test").status_code, 200)

    def test_deceased_never_invited_and_no_consent_is_recorded_for_anyone(self):
        run_story(self.c)
        con = store.connect()
        dead = con.execute("SELECT COUNT(*) FROM invitations i JOIN people p ON p.id = i.person_id "
                           "WHERE p.death_date IS NOT NULL").fetchone()[0]
        dead += con.execute("SELECT COUNT(*) FROM wellchild w JOIN people p ON p.id = w.person_id "
                            "WHERE p.death_date IS NOT NULL").fetchone()[0]
        self.assertEqual(dead, 0)
        # Relatives found through the family are confirmed, but nobody has decided for them.
        found = con.execute("SELECT * FROM cases WHERE source IN ('cascade','wellchild')").fetchall()
        self.assertTrue(found, "expected a positive relative")
        for f in found:
            self.assertIsNone(f["consent"])
            self.assertIsNone(f["cascade_at"])
            self.assertIsNotNone(f["index_of"])
        # Every consent in the log was recorded by a clinician.
        who = {r[0] for r in con.execute("SELECT actor_role FROM audit WHERE action_key IN ('consent_yes','consent_no')")}
        self.assertEqual(who, {"clinician"})
        con.close()

    def test_the_chain_continues_with_a_person_at_each_link(self):
        c = self.c
        run_story(c)
        con = store.connect()
        nxt = con.execute("SELECT person_id FROM cases WHERE source='cascade' LIMIT 1").fetchone()
        con.close()
        self.assertIsNotNone(nxt)
        pid = nxt[0]
        self.assertEqual(c.get(f"/api/patients/{pid}", headers=CLINICIAN).json()["next"]["key"], "consent")
        act(c, pid, "consent_yes")
        r = act(c, pid, "start_cascade", COORDINATOR).json()["cascade"]
        self.assertGreater(r["invited"] + r["wellchild"], 0)

    def test_audit_log_is_append_only(self):
        run_story(self.c)
        con = store.connect()
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE audit SET actor='someone else'")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("DELETE FROM audit")
        con.close()

    def test_deceased_relative_listed_but_not_contacted(self):
        con = store.connect()
        cascade.reset(con)
        pid = con.execute("SELECT c.id FROM people c JOIN people m ON m.id = c.mother_id WHERE c.death_date IS NULL "
                          "AND m.death_date IS NOT NULL AND c.id NOT IN (SELECT person_id FROM cases) LIMIT 1").fetchone()[0]
        con.execute("INSERT INTO cases (person_id, source, status, consent, created_at, updated_at) "
                    "VALUES (?, 'detection', 'clinical_fh', 1, '2026-11-15', '2026-11-15')", (pid,))
        con.commit()
        mother = con.execute("SELECT mother_id FROM people WHERE id=?", (pid,)).fetchone()[0]
        plan = cascade.plan_cascade(con, cascade.case_for_person(con, pid))
        self.assertEqual(next(r for r in plan["relatives"] if r["id"] == mother)["why"], "Deceased")
        cascade.act(con, pid, "coordinator", "start_cascade")
        self.assertIsNone(con.execute("SELECT 1 FROM invitations WHERE person_id=?", (mother,)).fetchone())
        con.close()

    def test_demo_is_repeatable(self):
        def outcome():
            run_story(self.c)
            con = store.connect()
            r = (sorted(tuple(x) for x in con.execute("SELECT person_id, status FROM cases WHERE source<>'detection'")),
                 sorted(tuple(x) for x in con.execute("SELECT person_id, status FROM invitations")))
            con.close()
            return r
        self.assertEqual(outcome(), outcome())

    def test_relative_can_book_decline_or_ask_for_a_call(self):
        c = self.c
        pid = confirm_new_result(c)
        act(c, pid, "consent_yes")
        act(c, pid, "start_cascade", COORDINATOR)
        toks = [i["token"] for i in self.invitations()]
        view = c.get(f"/api/invite/{toks[0]}").json()
        self.assertEqual(view["state"], "open")
        self.assertEqual(c.post(f"/api/invite/{toks[0]}/respond", json={"choice": "book"}).json()["code"], "missing_slot")
        self.assertEqual(c.post(f"/api/invite/{toks[0]}/respond", json={"choice": "book", "slot": view["slots"][0]}).status_code, 200)
        self.assertEqual(c.get(f"/api/invite/{toks[0]}").json()["state"], "booked")
        self.assertEqual(c.post(f"/api/invite/{toks[0]}/respond", json={"choice": "decline"}).json()["code"], "invitation_closed")
        c.post(f"/api/invite/{toks[1]}/respond", json={"choice": "decline"})
        self.assertEqual(c.get(f"/api/invite/{toks[1]}").json()["state"], "declined")
        c.post(f"/api/invite/{toks[2]}/respond", json={"choice": "call_me"})
        phone = c.get("/api/queue?tab=phone", headers=COORDINATOR).json()
        self.assertEqual(phone["total"], 1)
        # A declined invitation is never chased or tested.
        for _ in range(3):
            c.post("/api/simulate/advance", json={"weeks": 2})
        status = {i["token"]: i["status"] for i in self.invitations()}
        self.assertEqual(status[toks[1]], "declined")

    def test_invitation_expires(self):
        c = self.c
        pid = confirm_new_result(c)
        act(c, pid, "consent_yes")
        act(c, pid, "start_cascade", COORDINATOR)
        tok = self.invitations()[0]["token"]
        con = store.connect()
        con.execute("UPDATE invitations SET expires_at='2020-01-01' WHERE token=?", (tok,))
        con.commit()
        con.close()
        self.assertEqual(c.get(f"/api/invite/{tok}").json()["state"], "closed")
        self.assertEqual(c.post(f"/api/invite/{tok}/respond", json={"choice": "decline"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
