"""Email delivery: off without settings, a preview that sends nothing, and text that stays neutral."""
import os
import unittest
from unittest import mock

from tests import _db  # noqa: F401
from tests._flow import CLINICIAN, COORDINATOR, act, client, confirm_new_result

from heartline import mailer
from tests.test_voice import PERSONAL


class EmailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = client().__enter__()
        pid = confirm_new_result(cls.c)
        act(cls.c, pid, "consent_yes")
        act(cls.c, pid, "start_cascade", COORDINATOR)
        cls.inv = cls.c.get("/api/invitations", headers=COORDINATOR).json()["invitations"][0]

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def test_off_without_settings(self):
        self.assertFalse(self.c.get("/api/email/status").json()["configured"])
        r = self.c.post(f"/api/invitations/{self.inv['id']}/email", json={"to": "judge@example.com"}, headers=COORDINATOR)
        self.assertEqual(r.json()["code"], "email_unavailable")

    def test_preview_is_neutral_and_links_to_the_page(self):
        p = self.c.get(f"/api/invitations/{self.inv['id']}/email", headers=COORDINATOR).json()
        self.assertIn(f"/#/i/{self.inv['token']}", p["text"])
        body = (p["subject"] + p["text"]).replace(p["link"], "")
        for w in PERSONAL + [self.inv["via"]["name"], self.inv["relative"]["name"]]:
            self.assertNotIn(w.lower(), body.lower(), w)
        self.assertEqual(self.c.get(f"/api/invitations/{self.inv['id']}/email", headers=CLINICIAN).status_code, 403)

    def test_sends_with_settings_and_does_not_keep_the_address(self):
        sent = []
        with mock.patch.dict(os.environ, {"RESEND_API_KEY": "re_test_secret", "EMAIL_FROM": "demo@example.org"}), \
                mock.patch.object(mailer, "_resend", side_effect=lambda to, mail: sent.append(to)):
            bad = self.c.post(f"/api/invitations/{self.inv['id']}/email", json={"to": "not-an-address"}, headers=COORDINATOR)
            self.assertEqual(bad.status_code, 422)
            ok = self.c.post(f"/api/invitations/{self.inv['id']}/email", json={"to": "judge@example.com"}, headers=COORDINATOR)
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(sent, ["judge@example.com"])
            log = self.c.get("/api/audit?per_page=50", headers={"X-Demo-Role": "lead"}).text
            self.assertNotIn("judge@example.com", log)
            self.assertNotIn("re_test_secret", self.c.get("/api/email/status").text)


if __name__ == "__main__":
    unittest.main()
