# 09. Heart Line against the state of the art, and answers to "what about...?"

Checked 15 Nov 2026. Builds on `05-evidence-and-judging.md` (DLCN, FAMCAT and FIND FH numbers, the Lee 2019 cascade review, the Gulf FH Registry) and does not repeat it. Every external number has a source at the end of its line or in section 6. **UNVERIFIED** means it was seen only in a snippet or secondary report: do not put it on a slide.

Heart Line figures are from the current build on synthetic data (`backend/data/evaluation.json`, `/api/pilot`).

---

## 1. Where Heart Line sits, in one paragraph

Finding FH is done today in three separate ways that rarely meet:

- **Scoring records.** FAMCAT, FIND FH and DLCN-based alerts flag individuals.
- **Genomic screening.** Geisinger, Helix, Mayo and Healthy Nevada sequence everyone.
- **Cascade programmes.** Norway, the Netherlands, Wales, CATCH and IMPACT-FH contact relatives of known cases.

Each stops where the next one starts:

- Scoring tools stop at a flag. Dartmouth's FIND FH deployment turned 388 flags into 58 diagnoses, and the authors call the follow-up "labor-intensive".
- Cascade tools start from someone already confirmed.
- Genomic programmes find carriers but rarely reach the family: at Geisinger only 3.5% of relatives of FH carriers were tested.

Heart Line joins the three into one workflow. It flags from routine lipids, a clinician confirms, the patient consents, a coordinator contacts relatives directly, and children go to the Well-Child Visit. Every new positive starts the next round.

It also adds one modelling idea we found no published precedent for: **reading linked relatives' records as model input**. In the UAE that link is realistic, because Emirates ID and the electronic Family Book already hold family relationships.

What it lacks:
- validation on real patients
- regulatory status
- live integration with an EHR or HIE
- any evidence of uptake or outcomes

---

## 2. The landscape, side by side

### 2a. Finding FH in records and labs

| Approach | Who / where | Published performance | Status | Heart Line |
| --- | --- | --- | --- | --- |
| DLCN on coded records | Everywhere | Sensitivity 19 to 37.5% on real records, because family history and physical signs are rarely coded (Mohammadnia 2022; Qureshi 2021) | Standard of care in clinics | Shown beside every score. On synthetic data DLCN 6+ finds 35% at 47% PPV, in line with Qureshi |
| FAMCAT 2 (logistic, GP records) | England, PRIMIS, in EMIS | 68.8% sensitivity at 95% specificity, prospective, genetic reference (Qureshi 2021, n=260) | Registered medical device, GBP 200 per practice. No FAMCAT 3 published | Same idea (score the record), plus relatives |
| FIND FH (random forest) | US, Family Heart Foundation | 88% PPV internal, enriched sample (Banda 2019). Real use: Dartmouth 388 flags, 58 diagnoses (15%); Emory 26% likely FH | Deployed in US health systems, nonprofit | Same idea, plus relatives, plus the cascade that FIND FH leaves to the clinic |
| ML vs rules, all record algorithms | 22 studies, 20 on FH (Harris, JAMIA 2025) | AUROC 0.78 to 0.95; ML consistently beats rules; real-world PPV 11 to 67% | Review | Matches the direction; our AUROC is in the same range |
| TUDOR (11-feature logistic) | Welsh lipid clinics (Genedy 2026) | AUC 0.760. Moved to UK Biobank: 0.669, back to 0.756 after recalibration | Research | Evidence that any model, ours included, needs local recalibration |
| Lab interpretive comment | Western Australia (Bell, Hooper, Burnett) | Comment on LDL 6.5+ raised referrals; a call from the pathologist worked better (effect sizes UNVERIFIED) | Routine in some labs | Heart Line's score could ship as a smarter lab comment |
| Linked relatives as model input | Nobody found. Nearest: MEDPED relative cut-offs (1993); RIFTEHR family inference (Cell 2018); IMPACT-FH Aim 1 plans it, no results published | n/a | n/a | **Heart Line's core modelling idea.** Synthetic result: 189 found against 110 for DLCN at the same workload |
| LLM chart review for FH | Nobody found | n/a | Open gap | Not built. Obvious next step: read notes to fill DLCN's missing family-history items |

### 2b. Genomic screening

| Programme | Size | FH finding | What it shows |
| --- | --- | --- | --- |
| Mayo Tapestry (Samadder 2025) | 84,413 | 419 carriers (1 in 200). About 90% new; only 30.8% met DLCN; 10% at LDL goal | Phenotype tools miss most genetic carriers |
| Helix, 9 US systems (Levy 2025) | 228,602 | 1 in 198. 84% undiagnosed; 33% changed treatment in year 1 | Results change treatment for a third |
| Geisinger MyCode (Savatt 2025) | 175,500 exomes | 44% of 5,119 disclosed results cardiovascular; 3.5% of FH relatives tested (earlier data) | Finding the index is not the same as reaching the family |
| UK Biobank (Gratton 2023) | 140,439 | 1 in 288. An LDL cut-off over 4.8 mmol/L catches 40% of carriers with 10% false positives | "Just screen LDL" misses most |
| VA MVP-ROAR-FH trial (Vassy 2026) | 112 | LDL -10.5 mg/dL, not significant; 77% already treated | Returning a result is not enough |
| Emirati Genome Programme | About 800,000+ Emiratis | Returns pharmacogenomic reports (160,000+ in Malaffi). No FH return found | Could confirm Heart Line flags later |
| UAE premarital screening (since Jan 2025) | 570 genes, 840+ conditions | Couple carrier compatibility; FH not listed, and a single dominant carrier would not be reported anyway | Does not find FH |

### 2c. Finding FH in children

| Programme | What | Result |
| --- | --- | --- |
| Child-parent screening (Wald, NEJM 2016) | About 10,000 children at 1 to 2 years | 8 positives per 1,000 children screened, counting parents; 90% of positive parents started statins |
| Slovenia, since 1995 | Universal cholesterol at age 5, then genetic and family testing | 45 to 57% of referred children carry a variant; paediatric detection about 54% (UNVERIFIED snippet) |
| VRONI, Bavaria (Schmieder 2026) | 25,431 children aged 5 to 14 | Prevalence about 1 in 163 after correction |
| FH-PeDS, Slovenia (Kafol 2026) | ML paediatric score | AUC 0.904 against DLCN 0.852; external 0.867 |
| Wisconsin newborn blood spots (Peterson 2025) | 10,004 | 1 in 625 |

Heart Line is the opposite direction: from adults down to children. The two routes complement each other.

### 2d. Cascade testing and contacting relatives

| Programme or trial | Method | Result |
| --- | --- | --- |
| Norway (Page 2023) | Central testing, Oslo | 51.3% of estimated FH identified; 2.12 relatives found per index |
| Netherlands StOEH, 1994 to 2014 | Field workers visit relatives at home | 41.5% identified; 2.51 per index. Participation "plummeted" after direct approach stopped in 2014 |
| England (Page 2023; Cox 2024) | Mostly patient-mediated | About 4% identified (2018); 25% target would be met around 2096 at that rate |
| Wales vs Wessex (Cox 2024) | Direct contact vs letter via the patient | Direct contact OR 2.11 for a relative being tested; under a third of relatives tested overall |
| CATCH RCT, Switzerland (Nanchen, JAMA Netw Open 2026) | Patient sends pre-written SMS or email from a web platform | 30.4% vs 16.7% tested in 6 months; new cases 17.0% vs 8.1% |
| IMPACT-FH, Geisinger (2024) | Patient chooses packet, chatbot or clinician contact | 21.1% of first-degree relatives tested; direct contact strongly associated with testing (observational) |
| Geisinger chatbot (Schmidlen 2022) | Chatbot link sent by the patient | 62% opened, 57% of starters finished |
| Maryland RCT NCT05348564 | Direct vs indirect contact, randomised | Recruiting, no results |
| Hereditary cancer meta-analysis (Frey 2022) | Direct vs patient-mediated | Counselling uptake 63% vs 35% |
| UAE | Imperial College London Diabetes Centre and SEHA research project 2017 to 2020 (NCT03597958) | No standing public cascade programme found |

**Heart Line:** direct contact by a coordinator after the patient consents, with per-relative exclusions. That is the arm with the strongest uptake signal. In the projection, 60% of invited relatives test (literature: 21 to 30% in recent trials) and there are 0.69 new cases per index. That matches first-degree-only programmes (0.80) and sits below wider programmes (3.65).

### 2e. Products and companies

| Player | What it does | What Heart Line does that it does not | What it has that Heart Line lacks |
| --- | --- | --- | --- |
| Family Heart Foundation FIND FH | ML flag in US EHRs (Penn runs it in Epic) | Relatives' records, the cascade, Arabic | Real validation, live deployments |
| PRIMIS FAMCAT2 | EMIS searches, GBP 200 per practice | Relatives, the cascade | Registered device, primary-care footprint |
| TARB-Ex, Australia | FH screening in Best Practice software, used on 232,139 patients | Relatives, the cascade | Real use |
| Epic and Cerner | No packaged FH product. Systems build registries and alerts (UT Southwestern, Brigham FH-ALERT) | Packaged workflow | Sit inside the EHR |
| Nest Genomics, Genome Medical | Genomic programme and cascade services; family sharing under an NIH grant | Detection before genetics; Gulf fit | Genetic counsellors, lab operations |
| Ambry, formerly Invitae | Free testing for relatives within 90 days of the index report | Detection, coordination | Labs |
| Novartis | Cardiovascular Population Health Model adopted by DoH Abu Dhabi; ADPHC prevention MoU (May 2025); NHS inclisiran deal | FH-specific finding and families | Funding, relationships with DoH |
| M42 / Malaffi | Abu Dhabi HIE: 12.7 million patient profiles, 3,072 facilities, AI patient risk profile, genome programme | Family-aware FH module, cascade workflow | The data, the users, the mandate |
| DoH + Microsoft population health platform (GITEX 2025) | Digital twin; obesity and cancer first | A cardiovascular, family module | Scale, mandate |
| PureHealth | AI diagnostic lab, Pura app | Workflow | The labs where confirmation tests would run |

**Positioning line:** Heart Line is not a competitor to Malaffi or the DoH platform. It is the FH and family module they do not have, built to run on their data under a DoH data-sharing agreement.

---

## 3. Ahead, level and behind

**Ahead or new**
1. **Linked relatives as model input.** We found no published model that does this. Say "no published precedent found", not "first in the world".
2. **One loop from flag to family.** No product found does flag, confirm, consent, direct contact, children's route and chain in one system.
3. **Direct contact by a coordinator,** with per-relative exclusions. This is what ESHG 2025 recommends for highly actionable conditions like FH, and what the best-performing countries did.
4. **Privacy design:**
   - The index patient never sees a relative's result.
   - The invitation names no condition.
   - The audit log is append-only.
   - Truth data never reaches the API.
5. **Gulf fit:**
   - Arabic and English invitations, with a voice option for the 76% of UAE adults without adequate health literacy.
   - Uses Emirates ID and Family Book linkage.
   - Designed around DoH governance: a human makes the final decision.
6. **Honest ML reporting:**
   - Folds grouped by family.
   - Isotonic calibration with Brier score.
   - Bootstrap intervals.
   - Fairness tables by sex, nationality and age.
   - A misses analysis and a model card.
   - A realism check against published figures.

   This covers most of TRIPOD+AI. Most hackathon entries, and some published FH models, report less.

**Level**
- Model discrimination (AUROC 0.96 to 0.98 on synthetic data) is at the top of the published range (0.78 to 0.95). That is expected on clean synthetic data, and it is not a claim.
- On the synthetic data DLCN performs as published (35% sensitivity, 47% PPV against Qureshi's 37.5% and 33%), which supports the realism of the data.

**Behind**
1. No real patients, no external or temporal validation. TUDOR shows AUC drops when a model is moved (0.760 to 0.669) and needs local recalibration.
2. No decision-curve or net-benefit analysis.
3. No regulatory status (FAMCAT2 is a registered device). No DoH approval, DPIA or ADHICS mapping yet.
4. No EHR or HIE integration. The FHIR export is a format only.
5. Nothing after diagnosis: treatment, LDL at target, referral. The Gulf registry shows only 12% of high-risk patients at target. That gap is as big as the finding gap.
6. Weak spots in the cascade:
   - first-degree relatives only;
   - no generation skip past a dead relative;
   - no route for relatives abroad, beyond a count and a letter;
   - no tactics aimed at men;
   - no WhatsApp channel;
   - no Urdu, Hindi or Tagalog.
7. It cannot find carriers whose LDL looks normal. Genomic programmes show about 70% of carriers miss DLCN.
8. No Lp(a), no hard flag for suspected homozygous FH, no handling of variants of uncertain significance.

---

## 4. "What about...?" answers

Short answers to say out loud, then the facts behind them.

### The problem

**What about: is FH really common here?**
In Gulf clinics, about 1 in 112 adults met clinical criteria for probable or definite FH in the Gulf FH Registry, about three times the global estimate. Whole-genome data from Qatar gives about 1 in 125. Say "clinical criteria in clinic patients": it is not a genetic prevalence in the general population. A small Abu Dhabi study found only 7% of 229 severe cases had a known variant (Rimbert 2022). That is a reason to keep genetic confirmation in the loop, not a reason to skip it.

**What about: isn't this already solved by treatment?**
Treatment works. Children treated with statins had 1% cardiovascular events by 39, against 26% in their untreated parents (Luirink, NEJM 2019). The problem is finding people. Norway identifies 51% of FH, England about 4%. Even once found, only 12% of high-risk Gulf registry patients reached LDL target.

**What about: why does this matter in the UAE specifically?**
- Consanguinity is high: 50% in a 1990s study, 23% more recently.
- First heart attacks come about 10 years earlier than in Western registries (mean 56 in Gulf RACE-2).
- Families are large and linked by Emirates ID.

Avoid the often-quoted "first heart attack at 45": it comes from a press quote, not a study.

### The model

**What about FIND FH / FAMCAT: isn't this done?**
They score each person alone and stop at a flag. Heart Line adds two things: relatives' records as input, and the loop that turns a flag into tested relatives. FIND FH's real-world problem is exactly that loop: one network flagged 2,167 people and assessed 153.

**What about: why ML and not just DLCN?**
On real records DLCN catches 19 to 37% of FH, because family history and physical signs are rarely coded. ML beats rules across the 22 studies in the JAMIA 2025 review. We still show DLCN beside every score, because in specialist clinics DLCN can win (Australia 2026) and clinicians know it.

**What about your 0.98 AUROC / 42% PPV: isn't that too good?**
Yes, on synthetic data. Real deployments report PPV of 11 to 67% (JAMIA 2025) and as low as 5.9% against genetic testing (Gidding 2023). The Model page shows the published figures next to ours. The claim we make is relative: on the same data, adding relatives' records finds 189 people where DLCN finds 110 at the same workload. That is a hypothesis to test on Malaffi data, not a result.

**What about using one person's record to score another: is that allowed?**
It needs a lawful basis and a DoH data-sharing approval. Heart Line does not assume one:
- The relative feature is only a model input; no relative's data is shown on another person's screen.
- The model that runs on typed-in numbers uses the person's own record only.

UAE health data falls under Federal Law 2 of 2019 (ICT in health), not the general PDPL. Data must stay in the UAE unless an exception applies.

**What about family links: does Malaffi have them?**
Not that we could confirm. The relationships exist in the Federal Authority for Identity and Citizenship electronic Family Book (legal since July 2019). Malaffi codes family history in SNOMED. A pilot would link the two under a data-sharing agreement. US work (RIFTEHR, Cell 2018) inferred 7.4 million relationships from emergency-contact fields, a fallback where registries are not available.

**What about calibration and drift?**
- Calibration: isotonic regression fitted inside each training fold, with Brier scores shown.
- Drift: not monitored yet; a pilot would add it (Evidently or similar).
- Moving a model to a new setting loses accuracy (TUDOR: 0.760 to 0.669, back to 0.756 after recalibration), so the plan is to recalibrate on local data before go-live.

**What about fairness?**
Sensitivity by sex is 82% for women and 83% for men; by nationality group it is shown with intervals, and small groups are marked as small. The DLCN comparison is in the same table. The bigger real-world fairness issue is that women are diagnosed 3 to 7 years later (2026 review), and men are less likely to come forward for testing (OR about 1.5 to 1.7 in favour of women). The second is a cascade issue, not a model issue.

**What about the people you miss?**
They are shown, not hidden:
- On synthetic data the model misses 55 of 315 people with FH who have a result. The misses page says why (for example, only one cholesterol result).
- 383 of 698 carriers have no lipid result at all, and no scoring method can reach them. Family testing is the only route to them, and that is the point of the product.

**What about LLMs?**
We found no peer-reviewed paper using an LLM to find FH or compute DLCN. The useful place for one is reading clinical notes to fill DLCN's family-history and physical-sign items. We have not built it, and would only add it with a clinician confirming the extracted facts.

**What about Lp(a)?**
High Lp(a) raises measured LDL and can mimic FH. EAS recommends one Lp(a) test in a lifetime, and the 2026 ACC/AHA guideline recommends at least one in adults. Adding it as an input or an exclusion flag is a natural next step. The pelacarsen outcome trial (Lp(a)HORIZON, Nov 2026) was neutral, so the case is diagnostic, not therapeutic.

**What about homozygous FH?**
It is rare (about 1 in 250,000 to 360,000) and possibly more common with consanguinity (UNVERIFIED for the UAE). Untreated LDL above 10 mmol/L should be a hard flag straight to a lipid specialist, not a score. It is not built yet.

**What about polygenic high cholesterol?**
Many people with an FH-like profile have no variant and a high polygenic burden instead. Their relatives gain less from cascade testing. That is why genetic confirmation sits before any family contact, and why the synthetic data includes polygenic lookalikes. Our version has fewer of them than reality, which inflates PPV.

### Genomics

**What about just sequencing everyone? The UAE has a genome programme.**
Sequencing finds carriers that LDL-based tools miss (about 70% of Mayo's carriers did not meet DLCN). The Emirati Genome Programme returns pharmacogenomic reports today, and we found no FH return. Premarital screening checks couple carrier compatibility, so it will not report a single dominant FH variant. Where genomes exist, Heart Line uses them to confirm. Where they do not, which covers most residents, it chooses who to test. Also, finding a carrier is not the same as reaching the family: at Geisinger 3.5% of relatives of FH carriers were tested.

**What about the cost of genetic testing?**
A targeted test for a known family variant is cheaper than a panel:
- US panels: about USD 100 to 300 (secondary listing).
- UK private: GBP 150 to 350.

Cost-effectiveness of cascade testing:

| Analysis | Result |
| --- | --- |
| UK, NICE CG71 model | About GBP 3,000 per QALY (secondary) |
| Spain | EUR 29,608 per QALY from the payer's view; cost-saving from the societal view |
| Australia, cascade testing of children | AUD 3,023 per QALY |

### The family part

**What about contacting relatives directly: isn't that a privacy breach?**
The patient consents first and can exclude any relative. The invitation names no patient and no condition. European geneticists (ESHG, 2025) recommend a more active approach, including direct contact, for highly actionable conditions like FH. The Dutch 2019 guideline asks clinicians to offer direct informing. When the Netherlands stopped direct approach in 2014, participation fell. UAE Federal Decree-Law 49 of 2023 (human genome) does not address telling relatives. It also bars insurers from requiring or using genetic results (Art. 20 by our reading; verify the article number against the official text). A pilot needs a DoH policy position on direct contact.

**What about relatives who don't respond?**
Recent trials get 21 to 30% of relatives tested. Passive letters add little; navigation and follow-up work (FaCT: 73% vs 51%, UNVERIFIED journal). Heart Line has book, decline, already-tested and call-me options, with a 28-day expiry. Reminders and a phone script are designed but not built.

**What about relatives abroad?**
Common here, and in the UK 24 to 34% of relatives live outside the service area. Heart Line counts them and offers a letter the patient can pass on. A real handoff to another country's service is not built.

**What about children?**
Under-18s are never messaged. They go to their next Well-Child Visit for a cholesterol test.
- Testing age: EAS 2015 says from 5. The 2026 ACC/AHA guideline says cascade screening from 2.
- Statins: from 8 to 10 (EAS).

Universal child screening programmes (Slovenia, VRONI, Wald) go the other way, from children up to parents. Heart Line is complementary to them.

**What about deceased relatives?**
They are shown and never contacted. Skipping a generation to their children is not built yet.

**What about insurance and discrimination fears?**
They are real: refusals rose from 20% to 50% once life insurance was mentioned in one Australian study. The UAE genome law's ban on insurers using genetic results is a strong message to put on the relative's page. It is not there yet.

**What about the voice note: does it help?**
There is no published evidence for voice notes in cascade testing. The case for them is literacy: 23.9% of UAE adults had adequate health literacy (PLoS ONE 2022). The voice is synthetic (ElevenLabs), cached once, and says nothing personal. Without a key, the device voice reads the same words.

**What about WhatsApp instead of SMS?**
It is likely better reach in the Gulf; SEHA already books appointments on WhatsApp Business. The trust problem is the same either way: a health message from an unknown sender. The message should come from a named DoH or SEHA sender. The channel is an integration choice for the pilot, not a design change.

### Deployment and business

**What about integration?**
- Data in: Malaffi (M42) for lipid results and records, Emirates ID with the Family Book for links.
- Data out: FHIR export today, but a format only, missing FamilyMemberHistory, Consent, ServiceRequest and Task.
- Confirmation tests: PureHealth or SEHA labs.
- Hosting: an Azure UAE region for data residency.
- Security: ADHICS v2 controls, without which Malaffi access can be refused.

**What about regulation?**
DoH's 2018 AI policy requires a human to make the final decision, and Heart Line is built that way. The DoH Responsible AI Standard (October 2025) expects:
- transparency to patients
- a data protection impact assessment (DPIA)
- vendor audit rights

Under the US FDA's January 2026 guidance on decision support software, showing the basis of each recommendation (our why-chart and DLCN) is one of the criteria for software that is not a device. A risk score from lab data may still count as a device in the US and EU. We would seek regulatory advice before claiming otherwise.

**What about the business model and who pays?**
The buyer is a health authority or provider network: DoH, ADPHC, SEHA or PureHealth, as a module on Malaffi. The comparable price point in England is PRIMIS FAMCAT2 at GBP 200 per practice for the search tool alone. Pharma has paid for population cardiovascular programmes here (Novartis Population Health Model with DoH). The NHS inclisiran deal shows finding patients, not drug supply, is the bottleneck: 64,163 doses given against a 300,000-patient target.

**What about competitors here?**
- M42 runs Malaffi and has a general AI patient risk profile.
- The DoH and Microsoft platform covers obesity and cancer first.

We found no UAE FH case-finding or standing cascade programme. Present Heart Line as the FH and family module for their platforms.

**What about scale?**
The demo runs on 80,000 synthetic people and trains in about 3 minutes on a laptop. Malaffi holds 12.7 million profiles. Scoring is cheap; the limit is the number of clinician reviews per week, so the worklist cut-off is set by review capacity (the Programme page's planner). For production the database moves from SQLite to Postgres, and training is a scheduled batch.

**What about evidence it works?**
None yet on real people. The pilot plan is:
1. a retrospective run on a Malaffi extract to measure flags, PPV and the relatives effect;
2. a prospective pilot at one SEHA site measuring confirmed cases per 100 reviews and relatives tested per index.

DECIDE-AI is the reporting guide for that early live stage.

---

## 5. Numbers card

| Measure | Heart Line (synthetic) | Published |
| --- | --- | --- |
| DLCN 6+ sensitivity / PPV | 35% / 47% | 37.5% / 33% (Qureshi 2021) |
| Model AUROC | 0.96 own record, 0.98 with relatives | 0.78 to 0.95 (JAMIA 2025 review) |
| PPV at worklist cut-off | 42% at 83% sensitivity | 11 to 67% real world; FIND FH 15% of flags diagnosed at Dartmouth |
| Found at same workload (233 reviews) | 189 with relatives vs 110 DLCN | No published comparison found |
| Relatives tested of those invited | 60% (assumption) | 21% (IMPACT-FH), 30% (CATCH), under a third (Wales) |
| New cases per index | 0.69 (first-degree only) | 0.80 first-degree only; 1.65 average; 3.65 wider (Lee 2019) |
| Found in 12 months, screening vs screening plus families | 249 vs 421 | n/a |
| FH prevalence in data | 1 in 115 | 1 in 112 Gulf clinic, clinical (Alhabib 2021); 1 in 125 Qatar genomes |
| Mean LDL, adults | 3.04 mmol/L | 2.89 (US NHANES 2017 to 2018) |

The 60% uptake is the projection's assumption and is above recent trials. Either lower it to about 30% for the pitch, or say plainly that it is an assumption.

---

## 6. Corrections and things not to say

- **"Federal Decree-Law 49 of 2023, Articles 6 and 25"** (in `PLAN.md`). The law is real: it regulates use of the human genome and has been in force since 1 Dec 2023. The article numbers in our plan are unverified. One reading gives Art. 9 (results and counselling) and Art. 20 (insurers). Check against the official text before quoting any article.
- **"Fewer than 1 in 4 relatives get tested."** Now supported loosely. IMPACT-FH tested 21% of first-degree relatives, and Wales under a third. Cite those instead.
- **"FAMCAT 3".** Not published. Do not mention it.
- **"Italy's 2023 law on FH screening".** Law 130/2023 covers type 1 diabetes and coeliac disease, not FH.
- **"First heart attack at 45 in the UAE".** A press quote. Use "about 10 years younger than Western registries, mean 56" (Gulf RACE-2).
- **"First in the world to use relatives' records".** Say "we found no published model that does".
- **"Malaffi has family trees".** Not confirmed. The Family Book does.
- **"Under 10% diagnosed in the US" / "under 5% globally".** Commentary, not sourced. Use the country figures from Page 2023.

---

## 7. Sources

Detection and ML
- Harris et al., JAMIA 2025, doi:10.1093/jamia/ocaf140 (record algorithms for CDC Tier 1 conditions)
- Qureshi et al., Open Heart 2021, doi:10.1136/openhrt-2021-001752 (FAMCAT 1 vs 2 vs DLCN)
- Mohammadnia et al., EHJ Digital Health 2022, doi:10.1093/ehjdh/ztac059 (DLCN on coded records)
- Genedy et al., J Clin Lipidol 2026, doi:10.1016/j.jacl.2026.06.030 (TUDOR, transport and recalibration)
- Akyea et al., J Clin Lipidol 2026, doi:10.1016/j.jacl.2026.07.009 (FAMCAT vs DLCN in a lipid clinic)
- Hennessey et al., J Clin Lipidol 2025, doi:10.1016/j.jacl.2025.04.192 (FIND FH at Dartmouth)
- Kim et al., JACC Adv 2024, doi:10.1016/j.jacadv.2024.101184 (FIND FH at Emory)
- Williams et al., Am J Cardiol 1993, doi:10.1016/0002-9149(93)90155-6 (MEDPED)
- Polubriaginof et al., Cell 2018, doi:10.1016/j.cell.2018.08.011 (RIFTEHR)
- IMPACT-FH protocol, Circ Genom Precis Med 2021, doi:10.1161/CIRCGEN.120.003120
- PRIMIS FAMCAT2: https://www.nottingham.ac.uk/primis/projects/famcat2-tool.aspx

Genomics and children
- Samadder et al., Circ Genom Precis Med 2025, doi:10.1161/CIRCGEN.125.005174 (Mayo Tapestry)
- Levy et al., Circ Genom Precis Med 2025, doi:10.1161/circgen.125.005206 (Helix)
- Savatt et al., JAMA Netw Open 2025, doi:10.1001/jamanetworkopen.2025.0917 (Geisinger MyCode)
- Gratton et al., BMJ Public Health 2023, doi:10.1136/bmjph-2023-000021 (UK Biobank)
- Vassy et al., JAMA Netw Open 2026, doi:10.1001/jamanetworkopen.2025.49664 (VA trial)
- Wald et al., NEJM 2016 (child-parent screening; DOI not re-checked)
- Schmieder et al., Eur Heart J 2026, doi:10.1093/eurheartj/ehag403 (VRONI)
- Kafol et al., Eur J Prev Cardiol 2026, doi:10.1093/eurjpc/zwaf352 (FH-PeDS)
- Peterson et al., JAMA Cardiol 2025, doi:10.1001/jamacardio.2025.4047 (newborn blood spots)

Cascade testing and outcomes
- Page et al., PLOS Glob Public Health 2023, doi:10.1371/journal.pgph.0001795 (detection by country)
- Cox et al., J Clin Lipidol 2024, doi:10.1016/j.jacl.2024.08.007 (Wales and Wessex)
- Nanchen et al., JAMA Netw Open 2026, doi:10.1001/jamanetworkopen.2026.6100 (CATCH RCT)
- Jones et al., JACC Adv 2024;3(9):101198 (IMPACT-FH)
- Schmidlen et al., J Genet Couns 2022 (Geisinger chatbot)
- Frey et al., J Clin Oncol 2022, doi:10.1200/JCO.22.00303 (direct vs patient-mediated)
- de Wert et al., Eur J Hum Genet 2026, doi:10.1038/s41431-025-01945-3 (ESHG cascade recommendations)
- ABC v St George's [2020] EWHC 455 (QB)
- Luirink et al., NEJM 2019, doi:10.1056/NEJMoa1816454 (20-year paediatric statins)
- EAS FHSC, Lancet 2021, doi:10.1016/S0140-6736(21)01122-3 (treatment gap worldwide)
- Lazaro et al., J Clin Lipidol 2017, PMID 28391894 (Spain cost-effectiveness)
- Ademi et al., Atherosclerosis 2020, doi:10.1016/j.atherosclerosis.2020.05.007 (Australia, children)

UAE and Gulf
- Alhabib et al., PLoS One 2021, https://pmc.ncbi.nlm.nih.gov/articles/PMC8177652/ (Gulf FH Registry)
- Diboun et al., Front Genet 2022, doi:10.3389/fgene.2022.927504 (Qatar genomes)
- Rimbert et al., Front Genet 2022, doi:10.3389/fgene.2021.809256 (Emirati FH genetics)
- Malaffi figures: https://m42.ae/media-resources/news/malaffi-reaches-35-billion-clinical-records-setting-a-new-standard-for-healthcare-innovation-in-abu-dhabi/
- Malaffi SNOMED reference site: https://m42.ae/media-resources/news/m42-s-abu-dhabi-health-data-services-named-global-reference-site-by-snomed-international/
- Electronic Family Book: https://icp.gov.ae/en/family-book-from-the-paper-based-copy-to-the-electronic-version/
- Premarital genetic testing: https://mohap.gov.ae/en/w/genetic-testing-as-part-of-premarital-screening-for-emiratis
- Newborn genomic screening: https://www.doh.gov.ae/en/news/doh-launches-newborn-genetic-screening-programmes
- DoH population health platform: https://www.mediaoffice.abudhabi/en/health/department-of-health-abu-dhabi-unveils-worlds-1st-ai-powered-population-health-intelligence-platform-at-gitex-global-2025/
- Federal Law 2 of 2019 summary: https://tamimi.com/law-update-articles/the-federal-law-regulating-the-use-of-information-and-communication-technology-in-the-uae-healthcare-sector
- DoH 2018 AI policy: https://www.tamimi.com/news/new-policy-on-artificial-intelligence-in-healthcare-issued-by-the-department-of-health-abu-dhabi
- Federal Decree-Law 49 of 2023 (human genome), DHA copy: https://dha.gov.ae/uploads/062024/Federal%20Law_49_2023_Regulating%20the%20Use%20of%20the%20Human%20Genome202466484.pdf
- UAE health literacy, PLoS One 2022: https://pmc.ncbi.nlm.nih.gov/articles/PMC9534436/
- Novartis Population Health Model in Abu Dhabi: https://www.healthcareitnews.com/news/emea/abu-dhabi-second-world-adopt-population-health-model
- NHS inclisiran evaluation (LSE 2025): https://researchonline.lse.ac.uk/id/eprint/130877
- Challenge announcement: https://www.zawya.com/en/press-release/companies-news/future-health-launches-global-challenge-to-move-health-innovation-towards-real-world-application-1680763
