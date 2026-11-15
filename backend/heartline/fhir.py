"""FHIR R4 Bundle export for one patient.

Shows the data in the format a health information exchange expects. This is an export
format only; it is not connected to any exchange.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import store
from .features import reason_texts

LOINC = {"ldl": ("22748-8", "LDL cholesterol"), "tc": ("14647-2", "Total cholesterol"),
         "hdl": ("14646-4", "HDL cholesterol"), "tg": ("14927-8", "Triglycerides")}
REL_CODE = {"mother": ("MTH", "mother"), "father": ("FTH", "father"), "son": ("SONC", "son"),
            "daughter": ("DAUC", "daughter"), "brother": ("BRO", "brother"), "sister": ("SIS", "sister")}
BASE = "urn:heartline:"


def bundle(con, pid: int) -> dict:
    p = store.person(con, pid)
    if p is None:
        raise KeyError(pid)
    pref = f"Patient/{p['mrn']}"
    entries = []

    def add(resource):
        entries.append({"fullUrl": f"{BASE}{resource['resourceType']}/{resource['id']}", "resource": resource})

    patient = {
        "resourceType": "Patient", "id": p["mrn"],
        "meta": {"tag": [{"system": "urn:heartline", "code": "synthetic", "display": "Synthetic record"}]},
        "identifier": [{"system": "urn:heartline:mrn", "value": p["mrn"]}],
        "name": [{"family": p["family"], "given": [p["given"]]}],
        "gender": "male" if p["sex"] == "M" else "female",
        "birthDate": p["birth_date"],
        "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": p["lang"]}]}}],
    }
    if p["death_date"]:
        patient["deceasedDateTime"] = p["death_date"]
    add(patient)

    for r, rel in store.first_degree(con, pid, include_deceased=True):
        code, disp = REL_CODE[rel]
        add({"resourceType": "RelatedPerson", "id": f"{p['mrn']}-{r['mrn']}", "patient": {"reference": pref},
             "relationship": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-RoleCode",
                                           "code": code, "display": disp}]}],
             "name": [{"family": r["family"], "given": [r["given"]]}],
             "gender": "male" if r["sex"] == "M" else "female", "birthDate": r["birth_date"]})

    for lab in con.execute("SELECT * FROM labs WHERE person_id=? ORDER BY date", (pid,)):
        for key, (code, disp) in LOINC.items():
            add({"resourceType": "Observation", "id": f"lab{lab['id']}-{key}", "status": "final",
                 "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                           "code": "laboratory"}]}],
                 "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": disp}]},
                 "subject": {"reference": pref}, "effectiveDateTime": lab["date"],
                 "valueQuantity": {"value": lab[key], "unit": "mmol/L", "system": "http://unitsofmeasure.org",
                                   "code": "mmol/L"}})

    sc = con.execute("SELECT * FROM scores WHERE person_id=?", (pid,)).fetchone()
    if sc:
        add({"resourceType": "RiskAssessment", "id": f"risk-{p['mrn']}", "status": "final",
             "subject": {"reference": pref}, "occurrenceDateTime": store.today(con).isoformat(),
             "method": {"text": "Heart Line family-linked model (model B) and Dutch Lipid Clinic Network score"},
             "prediction": [{"outcome": {"coding": [{"system": "http://snomed.info/sct", "code": "398036000",
                                                     "display": "Familial hypercholesterolemia"}]},
                             "probabilityDecimal": round(sc["prob_b"], 4)}],
             "basis": [{"display": f"DLCN {sc['dlcn_total']} ({sc['dlcn_band']})"}],
             "note": [{"text": "; ".join(reason_texts(json.loads(sc["reasons"] or "[]")))},
                      {"text": "Score from a model trained on synthetic data. Not for clinical use."}]})

    c = con.execute("SELECT * FROM cases WHERE person_id=?", (pid,)).fetchone()
    if c and c["status"] in ("confirmed_genetic", "clinical_fh"):
        cond = {"resourceType": "Condition", "id": f"fh-{p['mrn']}",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                               "code": "active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                                   "code": "confirmed"}]},
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "398036000",
                                     "display": "Familial hypercholesterolemia"}]},
                "subject": {"reference": pref}, "recordedDate": c["updated_at"]}
        cond["note"] = [{"text": f"Genetic: {c['found_variant']}" if c["found_variant"] else "Clinical diagnosis (DLCN 6 or more)"}]
        add(cond)

    return {"resourceType": "Bundle", "type": "collection",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "meta": {"tag": [{"system": "urn:heartline", "code": "synthetic", "display": "Synthetic data"}]},
            "entry": entries}
