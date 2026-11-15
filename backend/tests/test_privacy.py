import json
import sqlite3
import unittest

from tests import _db
from tests._flow import CLINICIAN, COORDINATOR, LEAD, NURSE, client, run_story

TRUTH_KEYS = {"fh", "variant", "true_ldl", "truth"}
CLINICAL_WORDS = ["familial", "hypercholest", "FH", "variant", "diagnos", "LDLR", "APOB", "PCSK9", "case", "genetic",
                  "relative", "brother", "sister", "son", "daughter", "father", "mother"]
RESULT_STATUSES = {"confirmed", "negative", "declined", "already_tested", "assessing"}


def keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys(v)


class PrivacyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = client().__enter__()
        cls.pid = run_story(cls.c)
        cls.db = sqlite3.connect(_db.COPY)
        cls.db.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.c.__exit__(None, None, None)

    def invitations(self):
        return self.c.get("/api/invitations", headers=COORDINATOR).json()["invitations"]

    def responses(self):
        c = self.c
        out = [c.get("/api/summary").json(), c.get("/api/evaluation").json(), c.get("/api/pilot").json(),
               c.get("/api/invitations", headers=COORDINATOR).json(), c.get("/api/wellchild", headers=NURSE).json(),
               c.get("/api/audit?per_page=200", headers=LEAD).json(), c.get(f"/api/fhir/Patient/{self.pid}").json()]
        ids = {self.pid}
        for role in (CLINICIAN, COORDINATOR):
            for tab in ("review", "results", "done", "all", "start", "running", "phone"):
                q = c.get(f"/api/queue?tab={tab}", headers=role).json()
                out.append(q)
                ids |= {r["open"] for r in q["items"][:5]}
        ids |= {n["id"] for n in c.get(f"/api/patients/{self.pid}", headers=CLINICIAN).json()["family"]["nodes"]}
        for i in ids:
            for role in (CLINICIAN, COORDINATOR):
                out.append(c.get(f"/api/patients/{i}", headers=role).json())
        for i in self.invitations():
            out.append(c.get(f"/api/invite/{i['token']}").json())
        return out

    def test_no_truth_fields_in_any_response(self):
        for r in self.responses():
            found = TRUTH_KEYS & set(keys(r))
            self.assertFalse(found, f"truth field {found} leaked")
            self.assertNotIn("true_ldl", json.dumps(r))

    def test_untested_carrier_variant_not_revealed(self):
        rows = self.db.execute("""SELECT t.person_id, t.variant FROM truth t
            WHERE t.fh > 0 AND NOT EXISTS (SELECT 1 FROM cases c WHERE c.person_id = t.person_id) LIMIT 30""").fetchall()
        self.assertTrue(rows)
        for r in rows:
            body = self.c.get(f"/api/patients/{r['person_id']}", headers=COORDINATOR).text
            self.assertNotIn(r["variant"], body)

    def test_invitation_never_reveals_index_or_diagnosis(self):
        invs = self.invitations()
        self.assertTrue(invs)
        for i in invs:
            index = self.db.execute("SELECT p.* FROM cases c JOIN people p ON p.id = c.person_id WHERE c.id = ?",
                                    (i["case_id"],)).fetchone()
            r = self.c.get(f"/api/invite/{i['token']}")
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(set(body), {"given", "lang", "state", "slot", "slots", "mock"})
            self.assertNotIn(index["family"], r.text)
            self.assertNotIn(index["mrn"], r.text)
            self.assertNotIn(index["id"], [v for v in body.values() if isinstance(v, int)])
            for w in CLINICAL_WORDS:
                self.assertNotIn(w.lower(), r.text.lower(), w)
            # The SMS text itself is held to the same rule.
            for w in CLINICAL_WORDS + [index["family"]]:
                self.assertNotIn(w.lower(), i["message"].lower(), w)

    def test_clinician_sees_contact_status_but_not_relatives_results(self):
        """A relative's result follows the relative. The index patient's clinician sees whether
        each adult relative was contacted and replied, and nothing more."""
        clin = self.c.get(f"/api/patients/{self.pid}", headers=CLINICIAN).json()
        coord = self.c.get(f"/api/patients/{self.pid}", headers=COORDINATOR).json()
        tested = {r["person_id"] for r in self.db.execute(
            "SELECT person_id FROM invitations WHERE status IN ('positive','negative','declined')")}
        self.assertTrue(tested)
        seen = {n["id"]: n["status"] for n in clin["family"]["nodes"]}
        for pid in tested & set(seen):
            self.assertNotIn(seen[pid], RESULT_STATUSES, "an adult relative's result reached the clinician")
        self.assertTrue(RESULT_STATUSES & {n["status"] for n in coord["family"]["nodes"]})
        self.assertNotIn("found", clin["case"]["progress"])
        self.assertNotIn("tested", clin["case"]["progress"])
        self.assertIn("found", coord["case"]["progress"])

    def test_relatives_own_clinician_is_not_told_who_the_index_patient_is(self):
        found = self.db.execute("SELECT person_id FROM cases WHERE source='cascade' LIMIT 1").fetchone()
        self.assertIsNotNone(found)
        body = self.c.get(f"/api/patients/{found[0]}", headers=CLINICIAN).json()
        self.assertTrue(body["case"]["through_family"])
        self.assertNotIn("led_by", body["case"])

    def test_nurse_view_has_no_family_or_case_details(self):
        r = self.c.get("/api/wellchild", headers=NURSE)
        self.assertTrue(r.json()["items"])
        self.assertFalse({"parents", "case_id", "index_of"} & set(keys(r.json())))

    def test_unknown_token(self):
        self.assertEqual(self.c.get("/api/invite/not-a-token").status_code, 404)


if __name__ == "__main__":
    unittest.main()
