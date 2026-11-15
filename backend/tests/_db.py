"""Points the app at a throwaway copy of the data folder (database, model, evaluation). Import before heartline.

The source is HEARTLINE_DATA if set, otherwise backend/data. The voice cache is left empty, and API keys
are cleared so no test calls an outside service.
"""
import os
import shutil
import tempfile
from pathlib import Path

SRC = Path(os.environ.get("HEARTLINE_DATA", Path(__file__).resolve().parent.parent / "data"))
if not (SRC / "heartline.db").exists() or not (SRC / "model.joblib").exists():
    raise SystemExit("Run `python -m heartline.generate` and `python -m heartline.train` before the tests.")
_tmp = Path(tempfile.mkdtemp(prefix="heartline-test-"))
for name in ("heartline.db", "model.joblib", "evaluation.json"):
    shutil.copy(SRC / name, _tmp / name)
COPY = _tmp / "heartline.db"
DATA = _tmp
os.environ["HEARTLINE_DATA"] = str(_tmp)
os.environ.pop("HEARTLINE_DB", None)
for key in ("ELEVENLABS_API_KEY", "RESEND_API_KEY", "SMTP_HOST"):
    os.environ.pop(key, None)
os.environ["HEARTLINE_NO_DOTENV"] = "1"  # tests never read the developer's .env
