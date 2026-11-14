# Heart Line: build plan

Prototype for the Future Health Digital Innovation Challenge (hack2skill, Abu Dhabi), challenge C04, Population Health: Precision Prevention and Screening.

One line: one blood test can find a whole family.

## The idea

Familial hypercholesterolaemia (FH) is an inherited form of high cholesterol. It causes early heart attacks, and it's very treatable once found. It affects about 1 in 112 Gulf adults, roughly three times the global rate, yet most people who have it have never been diagnosed. Each person found has a 50% chance of passing it to each parent, sibling and child. Usually fewer than 1 in 4 relatives ever get tested.

Heart Line does four things:

1. **Find.** It scans routine cholesterol results and flags people who likely have FH.
2. **Confirm.** A clinician reviews each flag and orders a genetic test.
3. **Invite.** Once a case is confirmed and the patient consents, parents, siblings and adult children get private invitations to a free cholesterol check. The invitation never says who triggered it or why. Each relative who tests positive starts the same process for their own family, so it chains outward.
4. **Protect children.** Children of confirmed families are flagged for a cholesterol test at their next Well-Child Visit.

## Ground rules

- **No real patient data.** Everything runs on a synthetic population, and the UI says so clearly. Every accuracy number is labelled "on synthetic data".
- **No live messaging.** SMS, WhatsApp and lab integrations are mocks, and the UI labels them as mocks.
- **Ground truth stays in the `truth` table.** It's used only to simulate test results and to score the model. The API must never return it to the UI.
- **Human in the loop.** Nothing reaches a relative until a clinician has confirmed the case and the patient has consented.
- **Design rules** (the owner's house style): no all-caps eyebrow labels, no decorative lines or accent bars, no shadows, no numbered card labels or colored dots. Plain, direct copy. Arabic and English, with right-to-left layout for Arabic.

## Stack

- **Backend:** Python 3.13, FastAPI and uvicorn, LightGBM, scikit-learn, pandas, and the standard-library sqlite3. Everything is already installed on this machine.
- **Frontend:** React, Vite and TypeScript (Node 22). No UI library is needed.
- **Storage:** a single SQLite file at `backend/data/heartline.db`. This file is gitignored, so regenerate it rather than committing it.

## Layout

```
heart-line/
  PLAN.md
  README.md                 how to run it, what's synthetic
  backend/
    requirements.txt
    heartline/
      config.py             DONE  paths, REF_DATE 2026-11-15, seed, premature-age cut-offs
      generate.py           DONE  synthetic population -> SQLite
      dlcn.py               DONE  Dutch Lipid Clinic Network score with reasons
      features.py           TODO  per-person feature table (record-only and family-linked)
      train.py              TODO  cross-validated model, evaluation.json, model.joblib, scores table
      store.py              TODO  db helpers, first-degree relatives, audit log
      cascade.py            TODO  case state machine, invitations, Well-Child, simulate step
      pilot.py              TODO  12-month pilot projection, run in memory
      fhir.py               TODO  FHIR R4 bundle export per patient
      api.py                TODO  FastAPI app
    tests/                  TODO  dlcn, inheritance, privacy (no truth leaks), cascade
  web/                      TODO  React app
```

## Step 1: synthetic population (done)

Run `cd backend && python -m heartline.generate`. It produces about 80,000 people, 86,000 lipid panels and around 700 FH carriers (about 1 in 114).

- **Emirati families.** Three generations: grandparents, their children and spouses, and grandchildren. Half the spouses bring their own parents and siblings into the system, so a family chain can cross into another family.
- **Expatriate households.** Parents and children, with a `relatives_abroad` count. Cascade testing can't reach those relatives, which is a realistic limit to show.
- **Single expatriate workers.** No family in the system.
- **FH.** Founder prevalence varies by group. Each carrier parent passes it to each child with probability 0.5. Variants are spread across LDLR, APOB and PCSK9.
- **Clinical fields.** True LDL, statin use (moderate or high intensity, with 25% not taking it), coronary disease age, xanthomas, corneal arcus, and recorded family history. Family history is documented only 35% of the time (early heart disease) or 15% of the time (high LDL), because charts usually miss it.
- **Labs.** Emirati adults average about 2.6 panels, expatriates about 1.1, and many people have none. Statins lower the LDL measured after the start date.

**Tables:**
- `people`: no ground truth.
- `truth`: FH status, variant and true LDL.
- `spouses`
- `labs`

## Step 2: detection (`features.py`, `train.py`)

**Population:** everyone with at least one lipid panel.

**Features, model A (what one patient's record shows):**
- Highest and latest LDL, each corrected for statins with `dlcn.untreated`, plus the highest raw LDL.
- Highest total cholesterol, mean HDL, median triglycerides, number of panels.
- Age and sex.
- Statin use ever, and high-intensity statin.
- Early coronary disease, any coronary disease, xanthoma, arcus before 45.
- Recorded family history of early heart disease and of high LDL.

**Model B, the family-linked variant (Heart Line's technical edge):** model A's features plus what linked relatives' records show:
- Number of first-degree relatives in the system.
- Highest corrected LDL among them, and how many have high LDL.
- Whether any had early coronary disease.
- Whether any started a statin before age 40.

In production, the Emirati family book could supply these family links. Using relatives' data needs governance, so call that out on the model page.

**Training:**
- LightGBM with 5-fold `GroupKFold` grouped by `clan_id`, so families never sit on both sides of a split.
- Keep the out-of-fold predictions as everyone's honest scores.
- Fit one final model on all the data and save it to `model.joblib`. Step 6 uses it to score new results live.

**Reasons for each flag:** use LightGBM's built-in SHAP (`pred_contrib=True`) from the fold model that scored the person. Turn the top 3 positive contributions into plain sentences, for example "Highest LDL about 7.2 mmol/L after allowing for statins" or "Two relatives with very high LDL".

**DLCN:**
- Compute the score for everyone with labs, using only recorded family history (the classic version).
- Bands: above 8 definite, 6 to 8 probable, 3 to 5 possible.

**Evaluation (`evaluation.json`):**
- AUROC and AUPRC for DLCN, model A and model B.
- At the same number flagged as DLCN 6 or higher, the sensitivity and PPV of each method.
- A threshold table.
- Fairness: sensitivity and PPV by sex, nationality group and age band.
- A short model card covering intended use, data, limits, and "synthetic data only".

**Worklist threshold:** pick model B's cut-off from the threshold table, aiming for roughly 80% sensitivity at a PPV the worklist can handle. Record the choice in `evaluation.json`.

**`scores` table:** person_id, dlcn_total, dlcn_band, dlcn_items (JSON), prob_a, prob_b, reasons (JSON), flagged.

## Step 3: cascade engine (`store.py`, `cascade.py`)

**First-degree relatives:** parents, children, and full siblings (same mother and father). Exclude anyone deceased.

**Case statuses:**

```
flagged -> in_review -> test_ordered -> confirmed_genetic
                                    \-> no_variant -> clinical_fh (if DLCN >= 6) | dismissed
flagged -> dismissed
```

**Where cases come from:** `detection`, `cascade` (a relative who tested positive) or `wellchild`. Each case keeps `index_of`, the case that led to it.

**Genetic test:**
- For a detection case: finds the variant 95% of the time when one is present, and never reports one that isn't.
- For a relative: a targeted test for the family's known variant, always correct. If the family has no known variant (a clinical FH case), use an LDL cut-off instead.

**Consent:** the index patient must agree before any invitation is sent. Store who agreed and when.

**Starting a cascade (`start_cascade(case)`):**
- Adult first-degree relatives in the system get an invitation. Its token is random and doesn't reveal who started it. Language comes from the relative's `lang`.
- Children under 18 get a Well-Child flag instead.
- Relatives abroad are added to a count, and the patient gets a family letter to share with them.
- Skip anyone who is already a case or already invited.

**Invitation statuses:** `sent -> booked -> tested -> positive | negative`, or `no_response`.

**`advance(weeks=2)`:** the demo's "Advance two weeks" button. It moves time forward:
- Ordered tests return results.
- About 60% of invitations get booked, and booked ones get tested.
- Positive relatives become cascade cases with status `confirmed_genetic`. They consent with probability 0.85, and the coordinator then starts their cascade automatically. This produces the visible chain.
- About 70% of Well-Child flags due get tested, and positive children become cases.
- Use a seeded RNG so the demo plays out the same way every time.

**Audit log:** every flag, review, consent, invitation, result and data export. Each entry records the actor, the action, the subject and a timestamp.

**Live new result (`ingest_new_result()`):** picks an adult who has FH, has no labs and has relatives in the system. It adds a new lipid panel, scores it live with `model.joblib`, and creates a flagged case. This is the opening moment of the demo.

## Step 4: pilot projection (`pilot.py`)

Run 12 months of the workflow in memory on a copy of the data, with fixed seeds:
- Clinicians review the flagged list at a set capacity per week.
- Response rates are the same as in step 3.

**Return** monthly series and totals:
- People screened, flagged, confirmed by detection, relatives invited, uptake, relatives found positive, and children found.
- People found per detection case, which is the multiplier.
- Detection alone compared with detection plus cascade.

This drives the dashboard headline. Label it a projection on synthetic data.

## Step 5: FHIR export (`fhir.py`)

For one patient, export a FHIR R4 Bundle containing:
- **Patient.**
- **RelatedPerson,** one for each linked relative.
- **Observation,** one per lab, using LOINC codes in mmol/L:
  - LDL: 22748-8
  - Total cholesterol: 14647-2
  - HDL: 14646-4
  - Triglycerides: 14927-8
- **RiskAssessment,** holding the model score and DLCN.
- **Condition,** SNOMED 398036000, familial hypercholesterolaemia, once the case is confirmed.

The point to make is that the output is in the standard format a health information exchange expects. Don't claim it's integrated with Malaffi.

## Step 6: API (`api.py`)

```
GET  /api/summary                    headline numbers for the dashboard
GET  /api/evaluation                 evaluation.json
GET  /api/worklist?status=&q=&page=  cases with score, DLCN band, top reasons
GET  /api/patients/{id}              record, labs, DLCN breakdown, model score and reasons,
                                     family tree (relatives with case or invitation status), case history
POST /api/patients/{id}/review       {action: start_review|order_test|dismiss|mark_clinical, note}
POST /api/patients/{id}/consent      {consent: true|false}
POST /api/cases/{id}/cascade         start the cascade
GET  /api/invitations                coordinator view
GET  /api/invite/{token}             relative-facing view: no index details, no diagnosis
POST /api/invite/{token}/book        {slot}
GET  /api/wellchild
POST /api/simulate/new-result        ingest_new_result()
POST /api/simulate/advance           {weeks}
GET  /api/pilot                      projection
GET  /api/audit
GET  /api/fhir/Patient/{id}          FHIR bundle
POST /api/reset                      clear the demo state (cases, invitations, Well-Child, audit), keep the population
```

Allow CORS from the Vite dev server.

## Step 7: web app (`web/`)

**Screens:**
1. **Overview.** The pilot projection headline (people found per detection case, detection alone compared with detection plus cascade), live demo counters, and the "New lab result" and "Advance two weeks" buttons.
2. **Worklist.** Flagged cases sorted by score, with search, status filter, DLCN band and top reasons.
3. **Patient.**
   - Labs chart (LDL over time with statin periods shaded).
   - DLCN breakdown and model reasons.
   - Actions: review, order test, dismiss, mark as clinical FH, record consent, start cascade.
   - A family tree drawn as an SVG by generation, colored by status: unknown, invited, tested negative, confirmed, deceased, abroad.
4. **Families.** An invitations tracker and a chain view that shows how one detection case led to the next ones.
5. **Invitation preview.** A phone-sized relative view with an Arabic and English toggle, right-to-left for Arabic, and booking. The copy is neutral, along the lines of: "You're invited to a free cholesterol check. High cholesterol can run in families and is easy to treat when it's found early." It must not mention the relative who triggered the invitation or the diagnosis.
6. **Well-Child.** Children flagged, with what's due and when (lipid test from age 2, and statin discussion from 8 to 10 if positive).
7. **Model.** AUROC and AUPRC for DLCN and both models, sensitivity and PPV at the matched flag count, fairness tables, and the model card.
8. **Audit.** The audit log.

Keep a persistent banner on every screen: "Synthetic data. Not for clinical use."

## Step 8: tests and checks

- **DLCN:** unit tests against hand-worked examples.
- **Generator:** carrier rate among children of one carrier parent is close to 50%.
- **Privacy:**
  - No API response contains `truth` fields.
  - The invitation endpoint never returns the index patient's name, ID or diagnosis.
- **Cascade:** consent is required before invitations. Deceased relatives are never invited. A positive relative chains on.
- **End to end:**
  - Run generate, then train, then start the API and the web app.
  - Click through the demo story in the browser.
  - Check the Arabic right-to-left layout and the mobile width of the invitation screen.

## Demo story (about 3 minutes)

1. A new lab result arrives, and Heart Line flags the patient, with reasons.
2. The clinician confirms the flag and orders a genetic test. Advance two weeks, and a variant is found.
3. The patient consents, and their relatives appear on the family tree. One of them opens the invitation in Arabic and books a check.
4. Advance two more weeks. A sister tests positive, and her own family lights up: that's the chain. Her 6-year-old is flagged for a Well-Child Visit.
5. The overview shows the 12-month projection: how many people each detection case leads to.
6. The model page shows that the family-linked model beats the DLCN score at the same workload, with fairness checks and the audit trail.

## Open items outside the code

- Confirm the hack2skill submission format (video length, deck, repo link).
- Get one lipid or cardiology clinician's view on the worklist and on the biggest barrier to testing relatives.
- Check that the governance claims match Federal Decree-Law 49 of 2023 (consent in Article 6, confidentiality in Article 25) before putting article numbers on screen.
