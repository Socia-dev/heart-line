import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# HEARTLINE_DATA moves the whole data folder (database, model, evaluation, voice cache), so a test
# copy can run beside the main demo. HEARTLINE_DB still overrides the database file alone.
DATA = Path(os.environ.get("HEARTLINE_DATA", ROOT / "data"))
DB_PATH = Path(os.environ.get("HEARTLINE_DB", DATA / "heartline.db"))
MODEL_PATH = DATA / "model.joblib"
EVAL_PATH = DATA / "evaluation.json"
CANDIDATE = DATA / "candidate"   # a retrain writes here until someone chooses to use it
VOICE_CACHE = DATA / "voice"
ENV_PATH = Path(os.environ.get("HEARTLINE_ENV", ROOT / ".env"))

# Everything in the synthetic world is dated relative to this day.
REF_DATE = date(2026, 11, 15)

SEED = 7

# Premature coronary disease, as defined by the Dutch Lipid Clinic Network criteria.
PREMATURE_AGE = {"M": 55, "F": 60}

# Adult LDL at or above this is treated as "above the 95th percentile" (mmol/L).
LDL_P95_ADULT = 4.9
LDL_P95_CHILD = 3.5
