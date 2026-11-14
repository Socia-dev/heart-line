"""Points the app at a throwaway copy of the generated database. Import before heartline."""
import os
import shutil
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "data" / "heartline.db"
if not SRC.exists():
    raise SystemExit("Run `python -m heartline.generate` and `python -m heartline.train` before the tests.")
_tmp = Path(tempfile.mkdtemp(prefix="heartline-test-"))
COPY = _tmp / "heartline.db"
shutil.copy(SRC, COPY)
os.environ["HEARTLINE_DB"] = str(COPY)
