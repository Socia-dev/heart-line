"""Dutch Lipid Clinic Network (DLCN) score for familial hypercholesterolaemia.

Only the highest-scoring item in each group counts. LDL is in mmol/L and should be the
untreated value; for people on a statin we estimate it with a standard correction factor.
"""
from __future__ import annotations

STATIN_FACTOR = {"moderate": 0.7, "high": 0.5}


def untreated(ldl: float, on_statin: bool, intensity: str | None) -> float:
    if not on_statin:
        return ldl
    return ldl / STATIN_FACTOR.get(intensity or "moderate", 0.7)


def score(*, ldl_untreated: float | None, premature_cad: bool, xanthoma: bool, arcus_under_45: bool,
          fhx_premature_cad: bool, fhx_high_ldl: bool, fhx_xanthoma_or_child_high_ldl: bool = False,
          variant_found: bool = False) -> dict:
    items = []

    fam = 0
    if fhx_xanthoma_or_child_high_ldl:
        fam = 2
        items.append(("Family history", "Relative with tendon xanthomas, or a child with very high LDL", 2))
    elif fhx_premature_cad or fhx_high_ldl:
        fam = 1
        why = "Parent, sibling or child with early heart disease" if fhx_premature_cad else "Parent, sibling or child with very high LDL"
        items.append(("Family history", why, 1))

    clin = 0
    if premature_cad:
        clin = 2
        items.append(("Personal history", "Early coronary heart disease", 2))

    exam = 0
    if xanthoma:
        exam = 6
        items.append(("Examination", "Tendon xanthomas", 6))
    elif arcus_under_45:
        exam = 4
        items.append(("Examination", "Corneal arcus before age 45", 4))

    lab = 0
    if ldl_untreated is not None:
        for cut, pts in ((8.5, 8), (6.5, 5), (5.0, 3), (4.0, 1)):
            if ldl_untreated >= cut:
                lab = pts
                items.append(("LDL cholesterol", f"Untreated LDL about {ldl_untreated:.1f} mmol/L (at least {cut})", pts))
                break

    dna = 8 if variant_found else 0
    if dna:
        items.append(("DNA", "Disease-causing variant found", 8))

    total = fam + clin + exam + lab + dna
    if total > 8:
        band = "Definite"
    elif total >= 6:
        band = "Probable"
    elif total >= 3:
        band = "Possible"
    else:
        band = "Unlikely"
    return {"total": total, "band": band, "items": [{"group": g, "reason": r, "points": p} for g, r, p in items]}
