# 05. What the judges score and what the literature says

Two outside yardsticks for Heart Line: the challenge's own criteria, and the published evidence on finding FH and testing families. Both were read on 15 Nov 2026. Each section ends with what it means for the code.

## 1. The challenge

Source: `https://hack2skill.com/event/futurehealthchallenge/` (Future Health Digital Innovation Challenge, with Microsoft, Inception and MBZUAI named on the page).

**Timeline on the page**

| Date | What |
| --- | --- |
| 15 Oct | Registration opens, build starts |
| 10 Nov | Registration closes |
| **20 Nov** | **Working prototypes due** |
| 20 to 30 Nov | Evaluation |
| 7 to 11 Dec | Awards at GITEX 2026 |

Today is 15 Nov. That leaves five days.

**Deliverables named on the page:** a working prototype, technical documentation, assumptions, and limitations. The page does not mention a video, a deck or a repository link. The full text of challenge C04 and the data and IP rules sit in collapsed sections I could not read; `PLAN.md` already lists "confirm the submission format" as an open item, and it still is.

**Evaluation criteria** (no weights are published):

1. Health impact and clinical relevance
2. Technical depth and architecture
3. Working solution and demonstration quality
4. Responsible AI, safety and data governance
5. Scalability and deployment readiness
6. Commercial viability and path to pilot

The page also says selected solutions get "a readiness assessment and a potential pathway beyond the Challenge". The organisers are looking for things that could become a pilot, not just a demo.

### Heart Line against each criterion, as it stands today

| Criterion | Where Heart Line is strong | Where it is thin |
| --- | --- | --- |
| Health impact and clinical relevance | Real, under-served problem with a Gulf-specific angle. The workflow matches how cascade testing is done. | The story stops at "confirmed". Nothing shows a statin started, an LDL falling, or a heart attack avoided. The impact number (1.7) is weaker than the literature (see section 3) and is not compared to it. |
| Technical depth and architecture | Family-linked model with grouped cross-validation, SHAP reasons, a seeded simulation, FHIR export, privacy tests. | About 1,700 lines of Python and 2,300 of TypeScript. No roles, no real data path in, state machine is an if/else chain, no architecture document. |
| Working solution and demo quality | Runs end to end; the demo story works in about ten clicks. | One browser, one role. Only the relative's screen is in Arabic. No hosted link. |
| Responsible AI, safety, governance | Synthetic-only banner, consent gate, audit log, fairness tables, model card, truth table kept out of the API. | An uncalibrated score is labelled a "chance". No intervals. **A relative's test result is visible on the index patient's page**, which is a confidentiality problem (see `06`). Consent cannot be withdrawn. No named human accountable for each step. |
| Scalability and deployment readiness | FHIR export; API is clean. | SQLite with no migration story, no auth, no way to load a real population, no container, no monitoring. |
| Commercial viability and path to pilot | Clear buyer (a health authority or a provider network). | Nothing in the product or the docs says what a pilot costs, who runs it, or what it saves. |

Two of the six criteria (deployment readiness, commercial path) are close to untouched. One (responsible AI) has a real defect to fix. This is where the remaining days should go, ahead of more UI polish.

## 2. Evidence on detecting FH from health records

Source: Osei et al., "A Scoping Review of Electronic Health Records-Based Screening Algorithms for Familial Hypercholesterolemia", JACC: Advances, Oct 2024 (PMC11733818). It covers 14 algorithms across 27 studies.

**Published performance**

| Algorithm | Study and setting | Sensitivity | Specificity | PPV |
| --- | --- | --- | --- | --- |
| DLCN 6 or more | Qureshi 2021 | 37.5% | 95.5% | 33.0% |
| Simon Broome, possible FH | Qureshi 2021 | 56.3% | 70.9% | 10.3% |
| FAMCAT 1 | Weng 2019, prevalence 1 in 250 | 72% | 84% | 1.8% |
| FAMCAT 1 | Akyea 2020, prevalence 1 in 250 | 77.5% | 81.1% | 0.68% |
| FAMCAT 2 | Akyea 2020, prevalence 1 in 250 | 69.4% | 92.8% | 1.58% |
| Gradient boosting | Akyea 2020, prevalence 1 in 250 | 58.3% | 95.8% | 5.3% |
| Random forest | Akyea 2020 | 69.1% | 92.0% | 3.4% |
| Ensemble | Akyea 2020 | 30.5% | 99.3% | 15.5% |
| FIND FH | Banda 2019, internal, enriched sample (1 in 30) | 75% | 99% | 88% |
| FIND FH | Gidding 2023, against genetic testing | 12.1% | 99.1% | 5.9% |

A second source (Journal of the American Heart Association, 2024, doi 10.1161/JAHA.123.034434) reports that a newer ML model would find 74.9% of UK patients with FH aged 40 or over against 69.6% for FAMCAT, the tool currently recommended in English primary care.

**Inputs these algorithms use:** age, sex, highest cholesterol, triglycerides, lipid-lowering drugs, recorded family history, diabetes, kidney disease, personal history of early heart attack. The review's summary of inputs does not mention any algorithm using linked relatives' own records. I could not confirm from the review that none does.

**Gaps the review names:** few validation and clinical-utility studies, little evidence across diverse populations, missing or miscoded family history and examination findings in records, patients who cannot be reached or do not respond, low awareness, and privacy rules.

### What this means for Heart Line

**a. Heart Line's DLCN number matches the literature.** DLCN 6 or more scores 35% sensitivity and 47% PPV on Heart Line's synthetic data (`README.md`, model results table). Qureshi 2021 reports 37.5% and 33.0%. That agreement is worth showing: it is evidence the synthetic population is not absurd.

**b. Heart Line's model numbers are far better than anything published, and that is a warning, not a win.** Model B shows 83% sensitivity at 42% PPV at the worklist cut-off, and 81% PPV at the DLCN-matched workload. Real-world ML models at general-population prevalence report PPVs of 3% to 15%. FIND FH went from 88% PPV on an enriched sample to 5.9% against genetic testing.

Why Heart Line's numbers are inflated:

- The synthetic world is cleaner than reality. In `backend/heartline/generate.py` only 6% of non-carriers get a polygenic LDL bump (the `rng.random() < 0.06` branch in `true_ldl`), so there are few FH lookalikes. In real populations most people with LDL above 4.9 mmol/L do not have a monogenic variant.
- Family links are complete. Every Emirati relative is in the system with their labs joined perfectly.
- Prevalence is about 1 in 114, twice or more the rate in the UK studies, which raises PPV on its own.

What to do:

1. Say this on the Model page and in the docs, with the published table beside Heart Line's. A judge who knows the field will trust a team that shows FAMCAT's 1.6% PPV next to its own number and explains the gap.
2. Add a "harder world" setting to the generator (more polygenic high cholesterol, 30% to 50% of family links missing, noisier labs) and report results under both. The honest claim is the **relative** one: family-linked features beat record-only features under every setting. That claim can survive contact with real data; "81% PPV" cannot.
3. Calibrate the score or stop presenting it as a probability (see `04`, PyHealth).

**c. Using relatives' records is the differentiator.** None of the reviewed algorithms is described as using linked family records. Heart Line's model A to model B jump (AUPRC 0.50 to 0.73 on synthetic data) is the technical claim to lead with, stated as a hypothesis that needs real data and with the governance cost attached (using one person's record to score another needs a legal basis).

**d. The review's gaps are a to-do list Heart Line can answer directly.** "Unreachable patients or lack of response" maps to the contact plan and reminders. "Missing family history in records" is exactly why linked records help. "Lack of evidence across diverse populations" maps to the fairness tables. Quoting the review's gaps and pointing at the matching feature is an easy, credible structure for the technical document.

## 3. Evidence on cascade testing

Source: Lee et al., "New Case Detection by Cascade Testing in Familial Hypercholesterolemia: A Systematic Review of the Literature", Circulation: Genomic and Precision Medicine, 2019 (PMC9875692). Ten studies, on average 242 index patients and 826 relatives each.

| Finding | Number |
| --- | --- |
| Share of tested relatives who are positive | 44.8% on average (range 30% to 60.5%) |
| New cases found per index patient | 1.65 on average (range 0.22 to 8.0) |
| Direct contact by the programme vs asking the patient to tell relatives | 2.06 vs 0.86 new cases per index patient |
| Going beyond first-degree relatives vs first-degree only | 3.65 vs 0.80 |
| Genetic testing of relatives vs cholesterol testing only | 2.47 vs 0.42 |
| Response when relatives are contacted indirectly | 35% in one study (Marks et al.) |

The authors conclude that active approaches with direct contact find more cases, that including second- and third-degree relatives finds more, and that genetic testing does better than cholesterol alone. The paper's own abstract puts FH prevalence at 1 in 250 with fewer than 10% of patients diagnosed.

A further source (Dutch national programme, abstract via QxMD, id 42760204) reports annual cascade tests rising from 1,416 in 2014 to 4,356 in 2024 and annual positives from 165 to 541.

### What this means for Heart Line

**a. Heart Line's design choices are the ones the evidence favours.** Direct contact by the programme (with the index patient's consent) and a targeted genetic test for the family's variant are both in the high-yield column. The README and the pitch should say that these were chosen because of this review, and cite it.

**b. Heart Line's own projection is conservative, and it is not compared to anything.** The pilot projection finds 252 people by screening and 440 in total, which is 0.75 new cases per index patient (`backend/heartline/pilot.py`, `people_per_detection_case` at line 152 reports it as 1.7 people in total per index patient). The published average is 1.65 new cases, and 2.06 with direct contact.

Reasons Heart Line comes in lower:

- First-degree relatives only (`store.first_degree`, `backend/heartline/store.py:67`). The review's first-degree-only figure is 0.80, which Heart Line's 0.75 matches closely. That is a second point of agreement with the literature worth stating.
- Relatives already on the screening worklist are counted as found by screening, not by the cascade.
- Expatriate families have most relatives abroad.
- Twelve months only; chains are still running at the end.

What to do:

1. Put the published range on the Overview next to Heart Line's number: "0.75 new cases per index patient in this projection. Published programmes: 0.8 with first-degree relatives only, 1.65 on average, 3.65 when second-degree relatives are included."
2. Add second-degree relatives as an option in both the workflow and the projection, and show the difference. This is the highest-leverage clinical feature available: the evidence says it is the difference between 0.80 and 3.65.
3. Make the projection's assumptions adjustable (reviews per week, consent rate, uptake, first-degree vs second-degree) so a health-system planner can enter their own numbers. A fixed chart is a claim; a calculator is a tool.
4. Run the projection over many seeds and show a range, not a single line.

**c. The headline framing should change.** "1.7 people found for every person found by screening" needs a sentence of explanation every time. "Every confirmed patient leads to about one more person found, usually a child or a sibling who had no idea" is plainer, and "Screening alone finds 252. Adding family testing finds 440" already works and should lead.

## 4. Prevalence in the Gulf

Source: Alhabib et al., "Familial Hypercholesterolemia in the Arabian Gulf Region: Clinical results of the Gulf FH Registry", PLoS One, 2021 (PMC8177652).

- 306 of 34,234 screened adults met DLCN criteria for probable or definite FH: 0.9%, or 1 in 112.
- The authors describe this as about three times the worldwide estimate.
- Among those identified, 34% were on high-intensity statins and 10% on ezetimibe.
- A related estimate for Qatar is 1 in 125.

### What this means for Heart Line

- `PLAN.md` says FH "affects about 1 in 112 Gulf adults". The registry figure is a **clinical** prevalence by DLCN score among people screened in participating centres, not a genetic prevalence in the general population. The wording should be "about 1 in 112 adults screened in the Gulf FH Registry met clinical criteria", with the citation. A cardiologist on the panel will know the difference.
- The treatment figure is a second impact story Heart Line ignores: even among people identified, only a third were on high-intensity statins. A "treatment gap" step after confirmation (is the patient on a high-intensity statin, is LDL at target) would turn Heart Line from a finding tool into a finding-and-closing tool, which is what the "health impact" criterion rewards. It also matches another Population Health challenge theme reported for this event, "closing the gap between screening and care".

## 5. Numbers to verify before they go on a slide

| Claim | Status |
| --- | --- |
| 1 in 112 in the Gulf | Verified, with the caveat above |
| "About three times the global rate" | Verified as the registry authors' statement |
| "Fewer than 1 in 4 relatives get tested" (`PLAN.md`) | **Not verified.** The closest figure found is a 35% response to indirect contact in one study. Find a source or change the sentence. |
| "Each relative has a 50% chance" | Standard for an autosomal dominant condition; 44.8% average yield in tested relatives is the empirical counterpart |
| Federal Decree-Law 49 of 2023, Articles 6 and 25 | **Not verified.** Still open from `PLAN.md`. Do not put article numbers on screen until checked. |
| Children: lipid test from age 2, statin discussion from 8 to 10 | Not checked in this pass. Verify against a paediatric lipid guideline before relying on it. |
