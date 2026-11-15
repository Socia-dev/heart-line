"""The invitation as a short voice note, in Gulf-friendly Arabic or in English.

Older relatives may not read a text message. ElevenLabs turns the fixed, neutral invitation text into
speech. The text never contains a name, an ID, a diagnosis or anything about the patient who led to the
invitation: it is the same words for everyone (tests/test_voice.py checks this).

Configuration, in backend/.env (never committed):
    ELEVENLABS_API_KEY        required for real voice notes
    ELEVENLABS_VOICE_ID_AR    optional; otherwise a voice that speaks Arabic is picked from the account
    ELEVENLABS_VOICE_ID_EN    optional
    ELEVENLABS_MODEL_ID       optional; default eleven_multilingual_v2, which speaks Arabic

Every generated clip is cached under data/voice/ by a hash of text, voice and model, so a replay never
spends credits and the demo works offline once a clip exists. Without a key, the web page falls back to
the browser's own speech and says so.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

from .config import ENV_PATH, VOICE_CACHE

log = logging.getLogger("heartline.voice")
API = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_v2"

# The same words for every relative. No placeholders: nothing personal can be filled in.
SCRIPTS = {
    "ar": "مرحباً. هذه رسالة من برنامج صحة الأسرة في أبوظبي. ندعوك لإجراء فحص كوليسترول مجاني يستغرق نحو عشر دقائق، "
          "ولا تحتاج إلى الصيام. ارتفاع الكوليسترول ينتقل كثيراً بين أفراد العائلة، وعلاجه سهل عند اكتشافه مبكراً. "
          "يمكنك اختيار الموعد المناسب من الرابط في رسالتك. القرار لك، والفحص مجاني وسري. شكراً لك.",
    "en": "Hello. This is a message from the Abu Dhabi family health programme. You are invited to a free cholesterol "
          "check. It takes about ten minutes and you do not need to fast. High cholesterol often runs in families, and "
          "it is easy to treat when it is found early. You can choose a time from the link in your message. It is your "
          "choice, and the check is free and private. Thank you.",
}


class VoiceUnavailable(Exception):
    pass


def load_env(path: Path = ENV_PATH):
    """Read KEY=VALUE lines from backend/.env into the environment, without overriding what is already set."""
    if os.environ.get("HEARTLINE_NO_DOTENV") or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _key() -> str | None:
    return os.environ.get("ELEVENLABS_API_KEY") or None


def _model() -> str:
    return os.environ.get("ELEVENLABS_MODEL_ID") or DEFAULT_MODEL


def _request(method: str, path: str, body: dict | None = None, accept: str = "application/json") -> bytes:
    key = _key()
    if not key:
        raise VoiceUnavailable("No ElevenLabs key is set.")
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        # The response body can echo request details; keep only the status.
        raise VoiceUnavailable(f"ElevenLabs refused the request (HTTP {e.code}).") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise VoiceUnavailable(f"ElevenLabs could not be reached ({type(e).__name__}).") from None


def _choices_file() -> Path:
    return VOICE_CACHE / "voices.json"


def pick_voice(lang: str) -> str:
    """The voice for a language: from .env, else a remembered choice, else one picked from the account."""
    env = os.environ.get(f"ELEVENLABS_VOICE_ID_{lang.upper()}")
    if env:
        return env
    f = _choices_file()
    saved = json.loads(f.read_text()) if f.exists() else {}
    if lang in saved:
        return saved[lang]["id"]
    voices = json.loads(_request("GET", "/voices")).get("voices", [])
    if not voices:
        raise VoiceUnavailable("The ElevenLabs account has no voices.")

    def speaks(v) -> bool:
        langs = [x.get("language") for x in v.get("verified_languages") or []]
        return lang in langs or v.get("labels", {}).get("language") == lang
    chosen = next((v for v in voices if speaks(v)), voices[0])  # multilingual models can speak Arabic in any voice
    saved[lang] = {"id": chosen["voice_id"], "name": chosen.get("name", "")}
    VOICE_CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(saved, indent=2))
    log.warning("Heart Line voice for %s: %s (%s)", lang, saved[lang]["name"], "speaks it" if speaks(chosen) else "multilingual")
    return chosen["voice_id"]


def _tts(text: str, voice_id: str, model_id: str) -> bytes:
    return _request("POST", f"/text-to-speech/{voice_id}?output_format=mp3_44100_128",
                    {"text": text, "model_id": model_id, "voice_settings": {"stability": 0.55, "similarity_boost": 0.75}},
                    accept="audio/mpeg")


def cache_path(text: str, voice_id: str, model_id: str) -> Path:
    h = hashlib.sha256(f"{model_id}|{voice_id}|{text}".encode()).hexdigest()[:24]
    return VOICE_CACHE / f"{h}.mp3"


def clip(lang: str) -> Path:
    """The voice note for a language, from the cache if it exists, else generated once and cached."""
    if lang not in SCRIPTS:
        raise VoiceUnavailable("Unknown language.")
    model_id = _model()
    voice_id = pick_voice(lang)
    path = cache_path(SCRIPTS[lang], voice_id, model_id)
    if path.exists():
        return path
    audio = _tts(SCRIPTS[lang], voice_id, model_id)
    if not audio:
        raise VoiceUnavailable("ElevenLabs returned no audio.")
    VOICE_CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio)
    return path


def status() -> dict:
    """What the web page needs to know. Never includes the key itself."""
    f = _choices_file()
    saved = json.loads(f.read_text()) if f.exists() else {}
    voices = {}
    for lang in SCRIPTS:
        env = os.environ.get(f"ELEVENLABS_VOICE_ID_{lang.upper()}")
        voices[lang] = env and {"id": env, "name": "set in .env"} or saved.get(lang)
    return {"provider": "elevenlabs" if _key() else "device", "key_set": bool(_key()), "model": _model(),
            "voices": voices, "scripts": SCRIPTS,
            "cached": sorted(p.name for p in VOICE_CACHE.glob("*.mp3")) if VOICE_CACHE.exists() else []}
