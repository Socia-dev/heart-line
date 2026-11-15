# Heart Line

One blood test can find a whole family.

Prototype for the Future Health Digital Innovation Challenge (hack2skill, Abu Dhabi), challenge C04, Precision Prevention and Screening.

Familial hypercholesterolaemia (FH) is inherited high cholesterol. It causes early heart attacks and is very treatable once found, yet most people who have it do not know. Heart Line spots likely FH in routine cholesterol results. A clinician confirms it and asks the patient about their family. With the patient's agreement, a coordinator invites parents, brothers, sisters and adult children to a free check, and children are tested at their next Well-Child Visit. Each relative who tests positive goes to their own clinician, who asks about their family in turn.

## What is real and what is not

- **All data is synthetic.** About 80,000 made-up people. No real patient data anywhere.
- **Every accuracy number is on synthetic data** and is higher than a real deployment would see. The Model page shows published figures beside Heart Line's and says why. See `docs/limitations.md`.
- **Messaging, lab results, bookings and Well-Child results are simulated.**
- **There is no sign-in.** A role switch stands in for four members of staff.
- **The FHIR export is a format, not an integration.**

## Run it

Needs Python 3.11 or later and Node 22.

```bash
cd backend
pip install -r requirements.txt
python -m heartline.generate      # synthetic population, about 10 seconds
python -m heartline.train         # models, scores, evaluation.json, about a minute
python -m uvicorn heartline.api:app --port 8010
```

In a second terminal:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8010 (`HEARTLINE_API` changes that).

Or as one container, serving everything on port 8010 (not yet built and run by the team; treat as untested):

```bash
docker build -t heartline .
docker run -p 8010:8010 heartline
```

Tests, from `backend/` after generate and train:

```bash
python -m unittest discover -s tests -t .
```

## The demo (about 3 minutes)

The bar under the header holds the demo controls and the role switch. "Demo story" in that bar lists the steps and ticks them off as they really happen.

1. **As the clinician.** Press New lab result. A first cholesterol result arrives and is flagged. The patient page shows a band (Likely), the DLCN score beside it, and the reasons for and against. Order the genetic test.
2. Press Advance two weeks. The variant is found. The page now gives the question to ask the patient and lists the relatives; untick anyone the patient does not want contacted. Press Patient agrees. The case is handed to the coordinator.
3. **Switch to the family coordinator.** The family is under To start. The page shows every relative, the exact message each will get in their language, the children who go to Well-Child, and who is not contacted and why. Send.
4. Under Invitations, open See their page for one relative. This is the relative's phone view, Arabic first. Book, decline, say you were already tested, or ask for a call.
5. Advance two weeks. **Switch back to the clinician.** A relative found through the family is under Results back, waiting for their own clinician to ask about their family. The first patient's tree shows who replied, never a relative's result.
6. **Switch to the programme lead.** Programme shows a year's projection with sliders and published programmes beside it. "Can we trust the flags?" shows the four-way comparison and why the numbers are too good. Audit shows every decision and who made it.

Reset clears the demo and keeps the population. Outcomes are seeded, so the story plays the same way each time.

## How it is built

```
backend/heartline/
  generate.py   synthetic population with linked families
  features.py   features and signed reasons
  train.py      cross-validated models, calibration, comparison, fairness -> evaluation.json
  machine.py    the workflow as one transition table: roles, guards, next step
  cascade.py    applies decisions: cases, consent, invitations, audit
  simulate.py   the demo's outside world (lab results, replies, time)
  pilot.py      12-month projection with adjustable assumptions
  fhir.py       FHIR R4 export
  api.py        HTTP, roles, redaction
web/src/
  screens/      Home (role queue), Patient, Families, Invite, Children, Programme, Model, Audit, About
  locale/       the relative's page in English and Arabic
```

Read next:

| Document | What it covers |
| --- | --- |
| `docs/architecture.md` | Modules, roles, how a request flows, what changes for a pilot |
| `docs/assumptions.md` | Every rate in the generator, simulation and projection, with its source |
| `docs/limitations.md` | What Heart Line cannot claim |
| `docs/DECISIONS.md` | 23 decisions, each with what was rejected |
| `docs/DESIGN.md` | The design system and how it was adapted from KUEC Attar |
| `docs/research/` | Studies of three in-house products, the open-source field, the evidence and the judging criteria |

## Results on synthetic data

34,977 people have at least one cholesterol result; 315 of them have FH. Intervals are 95% bootstrap intervals.

If clinicians review 233 flagged people (the number DLCN 6 or more flags), how many have FH:

| Method | People with FH found | AUROC | AUPRC |
| --- | --- | --- | --- |
| DLCN score, from the chart | 110 | 0.957 | 0.355 |
| DLCN with linked family records | 107 | 0.968 | 0.428 |
| Heart Line, own record only | 137 | 0.964 | 0.499 |
| Heart Line, with linked family records | 189 | 0.978 | 0.732 |

The worklist cut-off flags 623 people and finds 83% of those with FH (78% to 87%); 42% of its flags are right (37% to 46%). Published models in real populations report 1% to 15% for that last figure. Bands: of people marked Very likely, 86% had FH; Likely, 41%; Possible, 13%.

The 12-month projection finds 249 people by screening alone and 421 with family testing (412 to 431 across five runs): 0.69 new cases per confirmed patient. Published first-degree-only programmes report 0.80.
