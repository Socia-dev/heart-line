# Heart Line, phase 2: make the real system visible

The ML, the clinical score and the cascade engine are real code. The demo hides that: a judge sees buttons and results, never the work in between. Phase 2 makes the work visible, lets anyone enter their own data, and adds an Arabic voice invitation through ElevenLabs.

## Principles for every item

- **Seamless and automated.** Anything the system does by itself plays out on screen without extra clicks: animations run, charts fill in, the next step is suggested.
- **The user decides.** Anything that changes a person's care or contacts someone (confirm, consent, send, book) needs a clear, labelled click. Nothing is ever sent or confirmed automatically.
- **Show real work, never fake it.** Every animation is driven by a real backend call and shows real values and real timings. If something is precomputed or cached, label it.
- **Synthetic data stays labelled** everywhere. External calls (ElevenLabs, email) are the only real things leaving the app, and they carry no personal data.
- **House design rules apply** (see `docs/DESIGN.md`):
  - No all-caps labels, decorative lines or shadows.
  - Plain copy.
  - Every animation is turned off under reduced motion.
- **Fit the guided demo.** New moments slot into the existing guided demo (`Guide.tsx`, `Steps.tsx`, `DemoBar.tsx`) as steps with one instruction each.

## A. Score any lab result

**Backend:** `POST /api/score` takes one lipid panel plus optional context (age, sex, statin and intensity, early heart disease, xanthoma, arcus, family history answers). It returns:
- The model probability and band.
- The DLCN total, band and items.
- The signed reasons (SHAP).
- The feature values used, and the timing of each stage in milliseconds.

It uses the saved model A, since there are no linked relatives for a typed-in person. Say so on screen.

**Web:** a "Try your own numbers" page, linked from the welcome screen and the header.
- Simple fields in mmol/L, with a mg/dL toggle.
- Sensible defaults, and validation with plain error messages.
- On submit it runs the live pipeline animation (item 1) and shows the why-chart (item 2).
- **CSV upload:** one row per panel, with a sample file to download. It scores every row and shows a sortable table; clicking a row opens its full breakdown.
- Nothing typed in is stored. Say so under the form.

## B. Real-world numbers check

- Compare the synthetic population with published real data:
  - LDL distribution by age band and sex against published figures (US NHANES lipid data, plus published UAE or Gulf lipid figures where available).
  - FH prevalence against the Gulf FH registry estimate.
  - Statin use rate.
- Store the reference figures with their sources in `backend/heartline/reference.py`. Use only numbers from citable sources, and cite each one.
- **Web:** a "Is the synthetic data realistic?" section on the Model page. Show overlaid distribution charts and a small table of synthetic vs published figures, with sources. Where it doesn't match, say so plainly.

## C. Real invitation delivery (optional, by email)

- If `RESEND_API_KEY` or SMTP settings are in `backend/.env`, the coordinator can send an invitation to an email address they type in. Typically this is a judge's own address during the demo.
- The email holds the neutral invitation text (Arabic and English), the booking link and the voice note (item 8).
- Show a clear preview, then "Send to this address" as a separate click.
- Without a key, the button explains how to enable sending and the in-app phone preview still works.

## 1. Live scoring pipeline

- When "New lab result" runs (and on page A), show a horizontal pipeline with these stages:
  1. Result received
  2. Record pulled
  3. Features computed
  4. Model scored
  5. Clinical score
  6. Threshold check
  7. Added to worklist
- Each stage lights up in turn and shows its real output, for example:
  - "14 features" (expandable to the values)
  - "Probability 0.81"
  - "DLCN 7, probable"
  - "Above the 0.15 cut-off"
- The backend returns per-stage timings; display them. Pace the animation so a person can follow it (about 300 to 500 ms per stage) while showing the true timing next to each stage.
- At the end, the patient lands in the worklist with a short highlight, and the guided demo moves on.

## 2. Why-chart per patient

- A waterfall chart on the patient page. It starts from the base rate, adds each feature's signed contribution in order, and ends at the patient's score.
- Labels are plain, for example "Highest LDL 7.1 mmol/L (after allowing for statins): raises the score".
- Show the top 6 contributions and fold the rest into "Other factors".
- Show the DLCN breakdown beside it as a simple points table, so the clinical score and the model can be compared.
- Bars grow in on first view.

## 3. What-if sliders

On the patient page, a "What if?" panel with:
- Sliders for LDL and age.
- Toggles for statin (with intensity), early heart disease, xanthoma, and recorded family history.

**Behaviour:**
- Each change calls `POST /api/score` (debounced by about 150 ms). The score, the band and the why-chart update live, with a smooth transition.
- A "Back to the real record" button resets everything.
- Mark the panel clearly as exploration only: it never changes the record.

## 4. Retrain button

- On the Model page, "Retrain the model" runs the real cross-validated training.
- **Streaming:** use server-sent events or polling a job endpoint. Each fold appears as it finishes, with its AUROC, AUPRC and time taken. At the end, show the new totals and the comparison with the previous run.
- Guard it:
  - Only one run at a time.
  - Show the estimated time before starting.
  - The live demo keeps using the current model until the run finishes and the user clicks "Use the new model".
- If the run takes longer than about 60 seconds, offer a "quick run" (a 3-fold run on a sample), clearly labelled.

## 5. Model charts

- **ROC curves** for DLCN, model A and model B on one chart, with the matched-workload point marked on each.
- **Precision-recall curves** as a second tab.
- **Population scatter** of everyone tested (about 35,000 points; use canvas, not SVG):
  - x is highest corrected LDL, y is model probability.
  - FH cases found are highlighted, and the threshold line is drawn.
  - Hovering shows the person's band; clicking opens the patient page.
- Charts draw in on first view. Keep the "On synthetic data" label on each.

## 6. Animated family chain

- The family tree on the patient page and the Families page animates real state changes:
  - Invitations fly out from the confirmed person to each relative.
  - Nodes change color as results arrive.
  - A positive relative pulses, then their own relatives appear and the tree grows outward.
- **Chain view on the Families page:** a node-link graph of detection cases and every case found through them, laid out by generation.
  - Edges show "found through".
  - New links draw in after each "Advance two weeks".
- Driven by the real cascade state from the API, diffed against the previous state, so it animates only what actually changed.

## 7. Twelve-month playback

- On the Programme page, a play button runs the pilot projection month by month (about 1 second per month, with pause and a scrubber):
  - Counters tick up: screened, flagged, confirmed, invited, relatives found, children found.
  - A growing network or area chart shows detection-only finds against detection plus cascade.
  - The "people found per detection case" multiplier updates each month.
- The data comes from the real `pilot.py` output. Label it "Projection on synthetic data".

## 8. Arabic voice invitation (ElevenLabs)

**Purpose:** older relatives may not read a text message. The invitation can be played as a short voice note in Gulf-friendly Arabic or in English.

**Backend:** `backend/heartline/voice.py`.
- Read `ELEVENLABS_API_KEY` and optional `ELEVENLABS_VOICE_ID_AR` and `ELEVENLABS_VOICE_ID_EN` from `backend/.env`.
  - Load them with python-dotenv, or a few lines of manual parsing.
  - `.env` must be in `.gitignore` before anyone creates it. Add `backend/.env.example` with empty values.
- Call the ElevenLabs text-to-speech API: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}` with the `xi-api-key` header and a multilingual model that supports Arabic (check the current model names in the ElevenLabs docs).
- **Caching:** cache the MP3 under `backend/data/voice/` by a hash of text, voice and model. A replay never spends credits, and the demo works offline once generated.
- **Pick a voice:** if no voice ID is set, list voices with `GET /v1/voices` and pick one that supports Arabic. Log which voice was chosen.
- **Privacy:** the text sent to ElevenLabs is the fixed neutral invitation copy only. It holds no names, IDs, diagnosis or index-patient details. Write a test that asserts this.

**API:**
- `GET /api/invite/{token}/voice?lang=ar|en` returns the cached or freshly generated MP3.
- `GET /api/voice/status` reports whether a key is set and which voices are in use. It must never return the key.

**Web:**
- On the relative-facing invitation (phone view), a "Listen" button with a simple play and pause control and a progress bar.
- In the coordinator's send preview, "Include a voice note" is on by default when a key is set.
- **Without a key:** fall back to the browser's built-in speech synthesis (an `ar` voice if the browser has one), labelled "Device voice". The About page explains how to add the ElevenLabs key.

**Guided demo:** add a step where the relative opens the invitation and presses Listen.

## Order of work

1. A, then 1 and 2. These make the ML visible and judge-testable.
2. 3 and 5.
3. 8. The user is adding the ElevenLabs key to `backend/.env`.
4. 6 and 7.
5. 4.
6. B and C.

Commit after each item, with a plain commit message and no AI attribution.

## Done when

- Every item works in the browser on desktop, and the invitation and the "Try your own numbers" form also work at phone width.
- The guided demo includes the new moments without adding confusion. It's still one instruction at a time.
- Tests cover:
  - the scoring endpoint
  - voice caching and the no-personal-data rule
  - that the retrain job can't run twice at once
  - that no API response leaks `truth` fields or API keys
- `npm run build` and the backend tests pass.
- README and `docs/` are updated: how to add the ElevenLabs key, what's real and what's simulated, and the new endpoints.
