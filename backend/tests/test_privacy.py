import json
import sqlite3
import unittest

from tests import _db
from tests._flow import client, run_story

TRUTH_KEYS = {"fh", "variant", "true_ldl", "truth"}
CLINICAL_WORDS = ["familial", "hypercholest", "FH", "variant", "diagnos", "LDLR", "APOB", "PCSK9", "case"]


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

    def responses(self):
        c = self.c
        inv = c.get("/api/invitations").json()
        out = [c.get("/api/summary").json(), c.get("/api/evaluation").json(), c.get("/api/worklist").json(),
               c.get("/api/worklist?status=open&page=2").json(), inv, c.get("/api/wellchild").json(),
               c.get("/api/audit?per_page=200").json(), c.get("/api/pilot").json(),
               c.get(f"/api/fhir/Patient/{self.pid}").json()]
        ids = {self.pid} | {n["id"] for n in c.get(f"/api/patients/{self.pid}").json()["family"]["nodes"]}
        ids |= {r["id"] for r in c.get("/api/worklist").json()["items"]}
        for i in ids:
            out.append(c.get(f"/api/patients/{i}").json())
        for i in inv["invitations"]:
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
            body = self.c.get(f"/api/patients/{r['person_id']}").text
            self.assertNotIn(r["variant"], body)

    def test_invitation_never_reveals_index_or_diagnosis(self):
        invs = self.c.get("/api/invitations").json()["invitations"]
        self.assertTrue(invs)
        for i in invs:
            index = self.db.execute("SELECT p.* FROM cases c JOIN people p ON p.id = c.person_id WHERE c.id = ?",
                                    (i["case_id"],)).fetchone()
            r = self.c.get(f"/api/invite/{i['token']}")
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(set(body), {"given", "lang", "status", "slot", "slots", "mock"})
            self.assertNotIn(f"{index['given']} {index['family']}", r.text)
            self.assertNotIn(index["family"], r.text)
            self.assertNotIn(index["mrn"], r.text)
            self.assertNotIn(index["id"], [v for v in body.values() if isinstance(v, int)])
            for w in CLINICAL_WORDS:
                self.assertNotIn(w.lower(), r.text.lower(), w)

    def test_unknown_token(self):
        self.assertEqual(self.c.get("/api/invite/not-a-token").status_code, 404)


if __name__ == "__main__":
    unittest.main()
