"""How a model score is shown to people.

The raw model output is not a probability. It is calibrated against outcomes (isotonic
regression, fitted inside the cross-validation folds) and then shown as a band in words.
The exact figure stays one level down, in Score details.
"""
from __future__ import annotations

MODEL_VERSION = "hl-2026.11-b"

# (name, lowest calibrated probability). Only people at or above the worklist cut-off get a band.
BANDS = (("Very likely", 0.60), ("Likely", 0.25), ("Possible", 0.0))
NOT_FLAGGED = "Not flagged"


def band_for(flagged: bool, calibrated: float) -> str:
    if not flagged:
        return NOT_FLAGGED
    for name, low in BANDS:
        if calibrated >= low:
            return name
    return BANDS[-1][0]
