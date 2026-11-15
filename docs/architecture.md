# Architecture

## In one picture

```
 Browser (React, Vite, TypeScript)                       web/src
   role switch -> X-Demo-Role header on every request
        |
        v
 FastAPI                                                 backend/heartline/api.py
   who may see what (redaction by role)
        |
        +--> machine.py     the rules: one transition table, pure, no database
        +--> cascade.py     applies a decision: case, consent, invitations, audit row, one transaction
        +--> simulate.py    the demo's outside world: lab results, replies, time. Replaced in a pilot
        +--> pilot.py       12-month projection, in memory
        +--> fhir.py        FHIR R4 bundle export
        |
        v
 SQLite                                                  backend/data/heartline.db
   people, labs, spouses          the population (synthetic)
   truth                          ground truth; read only by simulate.py, train.py, pilot.py
   scores                         model output, DLCN, reasons, band, model version
   cases, invitations, wellchild  workflow state
   audit                          append-only; triggers refuse UPDATE and DELETE

 Offline:  generate.py -> features.py -> train.py -> scores, model.joblib, evaluation.json
```

## The rule that shapes everything

Nothing reaches a relative until a clinician has confirmed the case and the patient has agreed. That rule is one row in a table (`machine.TABLE`, the `start_cascade` transition with its `consented` guard), and it is checked in one function, `machine.decide`. Staff actions, lab results and the simulator all go through `cascade.act`, which calls `decide`. There is no other way to change a case.

`tests/test_machine.py` checks every combination of status, consent, role and action (more than 5,000) and asserts that a button is offered if and only if the server would accept it.

## Modules

| File | Job | Reads truth? |
| --- | --- | --- |
| `config.py` | Paths, the reference date, the seed. `HEARTLINE_DB` overrides the database path | No |
| `generate.py` | Builds the synthetic population with linked families | Writes it |
| `dlcn.py` | Dutch Lipid Clinic Network score with its items | No |
| `features.py` | Per-person features; signed reasons from SHAP values | No |
| `scoring.py` | Score bands and the model version | No |
| `train.py` | Cross-validated training, calibration, four-way comparison, intervals, fairness, `evaluation.json` | Yes, for labels |
| `machine.py` | Statuses, roles, the transition table, `decide`, `possible`, `next_step` | No |
| `store.py` | Schema for workflow tables, the simulated clock, relatives, `audit` | No |
| `cascade.py` | `act` (the one door), the contact plan, sending, the relative's replies | No |
| `simulate.py` | New result, lab results, bookings, Well-Child results, time | Yes, to decide outcomes |
| `pilot.py` | Projection with adjustable assumptions and published benchmarks | Yes |
| `fhir.py` | Patient, RelatedPerson, Observation, RiskAssessment, Condition | No |
| `api.py` | HTTP, role checks on views, redaction | No |

## Roles

Demo roles, chosen in the bar and sent as a header. There is no sign-in in the prototype.

| Role | May do | May see |
| --- | --- | --- |
| Clinician | Order the test, close a flag with a reason, reopen, record clinical FH, record or reopen consent | Their queue, a patient, whether each adult relative was contacted and replied. Not relatives' results. Not who the index patient is when their own patient was found through family testing |
| Family coordinator | Send invitations once consent is recorded | Families, every message, relatives' results, who led to whom |
| Well-Child nurse | (read only in the prototype) | Children due a test. Nothing about the family or the case |
| Programme lead | (read only) | Counts, the projection, model quality, the audit log. No patient pages |
| Invited relative | Book, decline, say they were already tested, ask for a call | Their own invitation, by token |
| Lab, system | Report a result, open a case | Not people. They are how results and timers enter |

A refused attempt by the wrong role is written to the audit log.

## What a request looks like

`POST /api/patients/{id}/act {"action": "consent_yes", "exclude": [13270]}` with `X-Demo-Role: clinician`:

1. `api.act` passes the role and inputs to `cascade.act`.
2. `cascade.act` loads the case and its facts and calls `machine.decide`.
3. `decide` checks the role, the status, the guard and the required inputs. It returns a `Decision` (columns to set, audit detail, an optional side effect) or raises `Refusal(kind, code, message)`.
4. `cascade.act` writes the case, the audit row (actor, role, action, from and to status) and any side effect in one transaction.
5. A `Refusal` becomes HTTP 403, 404, 422 or 400 with `{code, message}`. The page maps the code to copy with a way forward (`web/src/components/State.tsx`).

The next `GET /api/patients/{id}` returns `next`: a title, a sentence, who it is waiting on, and the buttons `machine.possible` allows for the caller's role. The page draws exactly that.

## Model

- Population: everyone with at least one lipid panel (34,977 in the default synthetic population).
- Two models (own record; own record plus linked first-degree relatives) and two rule scores (DLCN from the chart; DLCN with linked family records).
- LightGBM, 5-fold GroupKFold by extended family. Inside each training fold, 3 inner folds produce the predictions an isotonic calibrator is fitted on.
- Output per person: raw score, calibrated estimate, band, signed reasons, DLCN, model version, timestamp.
- Clinicians see the band and the reasons. The figure is in Score details.

## What would change for a pilot

| Today | Pilot |
| --- | --- |
| `simulate.py` invents results and replies | Lab and booking interfaces call `cascade.act` and `cascade.respond` |
| Demo role header | Sign-in and the provider's identity system; the role comes from the session |
| SQLite file | A managed database; the audit table keeps its append-only rule |
| Mock SMS text | A messaging provider; the templates in `cascade.SMS` and `web/src/locale/` are reviewed by a clinician and legal |
| Synthetic population | A data-sharing agreement, a real extract, and re-validation of the model before any flag is shown |
| Family links from the generator | An approved source of family links, with its own governance |

## Running it

See `README.md`. For a container: `docker build -t heartline . && docker run -p 8010:8010 heartline` builds the web app, generates the population, trains, and serves both from one port.
