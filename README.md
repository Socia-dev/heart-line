# Heart Line

One blood test can find a whole family.

Prototype for the Future Health Digital Innovation Challenge (hack2skill, Abu Dhabi), challenge C04, Precision Prevention and Screening.

Familial hypercholesterolaemia (FH) is inherited high cholesterol. It causes early heart attacks and is very treatable once found, yet most people who have it do not know. Heart Line spots likely FH in routine cholesterol results. A clinician confirms it and asks the patient about their family. With the patient's agreement, a coordinator invites parents, brothers, sisters and adult children to a free check, and children are tested at their next Well-Child Visit. Each relative who tests positive goes to their own clinician, who asks about their family in turn.

## What is real and what is not

- **All data is synthetic.** About 80,000 made-up people. No real patient data anywhere.
- **Every accuracy number is on synthetic data** and is higher than a real deployment would see. The Model page shows published figures beside Heart Line's and says why. See `docs/limitations.md`.
- **Lab results, bookings and Well-Child results are simulated.** SMS is a preview, never sent.
- **Two things can leave the app, and only if you set them up:** the voice invitation (ElevenLabs) and one invitation emailed to an address you type in. Neither carries a name or anything about a patient.
- **The ML is real and runs live:** scoring, the why-chart, what-if and retraining all call the real models.
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

### Optional: voice and email

Copy `backend/.env.example` to `backend/.env` and fill in what you have. The file is git-ignored.

- `ELEVENLABS_API_KEY`: the invitation can be played as a recorded voice note in Arabic or English. Voices are picked from your account unless `ELEVENLABS_VOICE_ID_AR` and `ELEVENLABS_VOICE_ID_EN` are set; the model defaults to `eleven_multilingual_v2`. Each clip is made once and cached in `backend/data/voice/`. Without a key, the phone page reads the same words with the browser's own voice and labels it "Device voice".
- `RESEND_API_KEY` and `EMAIL_FROM` (or `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`): the coordinator can email one invitation to an address they type in, with the voice notes attached. `HEARTLINE_PUBLIC_URL` sets the base of the link in it.

Restart the API after changing `.env`.

Tests, from `backend/` after generate and train:

```bash
python -m unittest discover -s tests -t .
```

## The demo (about 3 minutes)

Open the app and press **Start the guided demo**. A strip under the header then says who you are and what to press at each of eight steps, and rings the button. The steps below are what it walks you through. **Explore on my own** swaps the guide for a role switch and the raw demo controls.

1. **As the clinician.** A first cholesterol result arrives. The scoring pipeline plays out stage by stage with real timings, then the patient opens: a band (Likely), a why-chart of what pushed the score up or down, and the DLCN score beside it. Try What if? to change LDL or age and watch it rescore. Order the genetic test.
2. Press Advance two weeks. The variant is found. The page now gives the question to ask the patient and lists the relatives; untick anyone the patient does not want contacted. Press Patient agrees. The case is handed to the coordinator.
3. **Switch to the family coordinator.** The family is under To start. The page shows every relative, the exact message each will get in their language, the children who go to Well-Child, and who is not contacted and why. Send.
4. Open a relative's phone. Press Listen to hear the invitation spoken, then book, decline, say you were already tested, or ask for a call. Under Invitations, "Email it to me" sends the real invitation to your own address if email is set up.
5. Advance two weeks. **Switch back to the clinician.** A relative found through the family is under Results back, waiting for their own clinician to ask about their family. The first patient's tree shows who replied, never a relative's result.
6. **Switch to the programme lead.** Programme plays the year month by month. "Can we trust the flags?" has ROC curves, a scatter of all 35,000 people, the realism check against published figures, and a Retrain button that runs the real training with each fold appearing as it finishes. Audit shows every decision and who made it.

Anyone can also open **Try your own numbers** to type in a result, or upload a CSV, and see exactly how it is scored.

Reset clears the demo and keeps the population. Outcomes are seeded, so the story plays the same way each time.

## How it is built

```
backend/heartline/
  generate.py   synthetic population with linked families
  features.py   features and signed reasons
  live.py       scoring stage by stage with timings, the why-chart, what-if
  retrain.py    retraining as a background job
  reference.py  published figures for the realism check, with sources
  voice.py      voice invitations through ElevenLabs, cached
  mailer.py     optional real email of one invitation
  train.py      cross-validated models, calibration, comparison, fairness -> evaluation.json
  machine.py    the workflow as one transition table: roles, guards, next step
  cascade.py    applies decisions: cases, consent, invitations, audit
  simulate.py   the demo's outside world (lab results, replies, time)
  pilot.py      12-month projection with adjustable assumptions
  fhir.py       FHIR R4 export
  api.py        HTTP, roles, redaction
web/src/
  screens/      Welcome, Home (role queue), Patient, Families, Invite, Children, Programme, Model, Audit, About, Try
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

The 12-month projection finds 249 people by screening alone and 379 with family testing (374 to 392 across five runs): 0.52 new cases per confirmed patient. It assumes 30% of invited relatives get tested, in line with recent trials (21% in IMPACT-FH, 30% in CATCH); the Programme page has a slider. Published first-degree-only programmes report 0.80 new cases per index patient.
