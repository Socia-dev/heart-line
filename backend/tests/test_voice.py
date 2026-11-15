"""Voice invitations: the text carries nothing personal, clips are cached, and the key never leaves."""
import json
import os
import unittest
from unittest import mock

from tests import _db  # noqa: F401
from tests._flow import COORDINATOR, act, client, confirm_new_result

from heartline import voice

PERSONAL = ["{", "}", "fh", "familial", "hypercholest", "variant", "genetic", "diagnos", "brother", "sister", "father",
            "mother", "son ", "daughter", "relative", "LDLR", "APOB", "PCSK9", "HL-", "أخ", "أخت", "والد", "ابن", "وراثي"]


class VoiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = client().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def test_script_holds_nothing_personal(self):
        con_names = self.c.get("/api/invitations", headers=COORDINATOR)  # warm the app
        self.assertIn(con_names.status_code, (200, 403))
        for lang, text in voice.SCRIPTS.items():
            for w in PERSONAL:
                self.assertNotIn(w.lower(), text.lower(), (lang, w))

    def test_without_a_key_the_page_falls_back(self):
        st = self.c.get("/api/voice/status").json()
        self.assertEqual(st["provider"], "device")
        self.assertFalse(st["key_set"])
        pid, = [confirm_new_result(self.c)]
        act(self.c, pid, "consent_yes")
        act(self.c, pid, "start_cascade", COORDINATOR)
        tok = self.c.get("/api/invitations", headers=COORDINATOR).json()["invitations"][0]["token"]
        r = self.c.get(f"/api/invite/{tok}/voice?lang=ar")
        self.assertEqual(r.json()["code"], "voice_unavailable")
        self.assertEqual(self.c.get("/api/invite/nope/voice").status_code, 404)

    def test_clips_are_generated_once_then_served_from_the_cache(self):
        secret = "sk_test_do_not_leak_123456"
        calls = []

        def fake_tts(text, voice_id, model_id):
            calls.append((text, voice_id, model_id))
            for w in PERSONAL:
                assert w.lower() not in text.lower(), w
            return b"ID3fake-mp3"

        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": secret, "ELEVENLABS_VOICE_ID_AR": "voice-ar"}), \
                mock.patch.object(voice, "_tts", side_effect=fake_tts):
            p1 = voice.clip("ar")
            p2 = voice.clip("ar")
            self.assertEqual(p1, p2)
            self.assertEqual(len(calls), 1)
            self.assertEqual(p1.read_bytes(), b"ID3fake-mp3")
            self.assertEqual(calls[0][0], voice.SCRIPTS["ar"])
            st = self.c.get("/api/voice/status")
            self.assertEqual(st.json()["provider"], "elevenlabs")
            self.assertNotIn(secret, st.text)
            self.assertNotIn(secret, json.dumps(voice.status()))
            for path in ("/api/summary", "/api/evaluation", "/api/pilot"):
                self.assertNotIn(secret, self.c.get(path).text)


if __name__ == "__main__":
    unittest.main()
