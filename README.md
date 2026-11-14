# Heart Line

One blood test can find a whole family.

Prototype for the Future Health Digital Innovation Challenge (hack2skill, Abu Dhabi), challenge C04, Precision Prevention and Screening. Heart Line finds familial hypercholesterolaemia (FH) in routine cholesterol results. A clinician confirms each case, the patient consents, and then parents, siblings and adult children get private invitations to a free cholesterol check. Each relative who tests positive starts the same process for their own family. Children are flagged for their next Well-Child Visit.

## What is real and what is not

- **All data is synthetic.** About 80,000 made-up people. No real patient data is used anywhere.
- **Every accuracy number is on synthetic data.** Real-world performance has not been measured.
- **Messaging, lab and Well-Child results are mocks.** No SMS or WhatsApp is sent. Test results are simulated from the `truth` table, which the API never returns.
- **The FHIR export is a format, not an integration.** It is not connected to Malaffi or any exchange.

## Run it

Needs Python 3.11 or later and Node 22.

```bash
cd backend
pip install -r requirements.txt
python -m heartline.generate      # synthetic population -> data/heartline.db (about 10 s)
python -m heartline.train         # models, evaluation.json, model.joblib, scores (about 30 s)
python -m uvicorn heartline.api:app --port 8010
```

In a second terminal:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `http://127.0.0.1:8010`; set `HEARTLINE_API` to point it somewhere else.

Tests (from `backend/`, after generate and train; they work on a temporary copy of the database):

```bash
python -m unittest discover -s tests -t .
```

## Demo story (about 3 minutes)

The demo bar under the header (New lab result, Advance two weeks, Reset) is on every screen, so most of the story happens on one patient page.

1. Select **New lab result**. A new LDL result arrives, Heart Line scores it live and opens the flagged patient, with the reasons.
2. Select **Order genetic test**, then **Advance two weeks**. The variant is found.
3. Select **Patient agrees**, then **Start family testing**. Relatives turn yellow on the family tree. On **Families**, open **Preview invitation** for one relative, switch to Arabic (right to left) and book a check.
4. **Advance two weeks** again. One relative tests positive and starts family testing for their own family; their children appear on the tree and on **Children**.
5. **Overview** shows the 12-month pilot projection: people found per person found by screening.
6. **Model** shows Heart Line against the DLCN score at the same workload. Accuracy tables, fairness and the model card are folded underneath. The audit log is linked in the footer.

**Reset** clears cases, invitations, Well-Child flags and the audit log, and keeps the population. Random outcomes are seeded by person, so the demo plays out the same way each time.

## How it works

`backend/heartline/`

| File | What it does |
| --- | --- |
| `config.py` | Paths, reference date 15 Nov 2026, seed. `HEARTLINE_DB` overrides the database path. |
| `generate.py` | Synthetic population: Emirati three-generation families, expatriate households, single workers. FH is inherited with probability 0.5 per child. |
| `dlcn.py` | Dutch Lipid Clinic Network score, with reasons. |
| `features.py` | Per-person features. Model A uses one record; model B adds what first-degree relatives' records show. |
| `train.py` | LightGBM, 5-fold GroupKFold by extended family. Out-of-fold scores, SHAP reasons, `evaluation.json`, `model.joblib`, `scores` table. |
| `store.py` | Database helpers, simulated clock, relatives, audit log. |
| `cascade.py` | Case state machine, consent, invitations, Well-Child flags, the two-week `advance()` step, `ingest_new_result()`. |
| `pilot.py` | 12-month pilot projection, run in memory. |
| `fhir.py` | FHIR R4 Bundle: Patient, RelatedPerson, Observation (LOINC), RiskAssessment, Condition (SNOMED 398036000). |
| `api.py` | FastAPI app. |

`web/src/screens/` holds the eight screens: Overview, Worklist, Patient, Families, Invite (relative's phone view), Children (Well-Child), Model and Audit.

### Case statuses

```
flagged -> in_review -> test_ordered -> confirmed_genetic
                                    \-> no_variant -> clinical_fh (DLCN 6 or more) | dismissed
flagged -> dismissed
```

Nothing reaches a relative until the case is confirmed and the patient has consented. Invitations never mention who triggered them or why; the privacy tests check this.

### Model results (synthetic data)

From `backend/data/evaluation.json` after a fresh generate and train. 34,977 people have at least one lipid panel; 315 of them have FH.

| Method | AUROC | AUPRC | Found at 233 flagged | Sensitivity | PPV |
| --- | --- | --- | --- | --- | --- |
| DLCN (chart family history only) | 0.957 | 0.355 | 110 | 35% | 47% |
| Model A (own record) | 0.964 | 0.499 | 137 | 43% | 59% |
| Model B (family-linked) | 0.978 | 0.732 | 189 | 60% | 81% |

233 is the number DLCN 6 or more flags. The worklist uses a model B cut-off of 0.04: 623 flagged, 83% sensitivity, 42% PPV.

The 12-month pilot projection (20 reviews a week) finds 252 people by screening alone and 440 with family testing added: 1.7 people per person found by screening.

## Limits

- Synthetic data only. The family links are complete here and will be patchier in real records.
- People with no lipid results cannot be flagged; family testing is how they get found.
- Model B uses relatives' records to score someone. That needs a legal basis and governance approval before any real use.
- Check governance claims against Federal Decree-Law 49 of 2023 before quoting article numbers.
