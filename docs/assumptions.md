# Assumptions

Every number that shapes the synthetic world, the simulation or the projection, where it is set, where it came from, and what happens if it is wrong. "Chosen" means the team picked a plausible value and it has no source; those are the ones to replace first.

Sources are listed in full in `docs/research/05-evidence-and-judging.md`.

## The synthetic population (`backend/heartline/generate.py`)

| Assumption | Value | Source | If it is wrong |
| --- | --- | --- | --- |
| Share of Emirati founders carrying an FH variant | 1 in 100 | Chosen, near the Gulf FH Registry's 1 in 112 (Alhabib 2021). That figure is clinical criteria among screened adults, not a genetic prevalence | Lower real prevalence lowers PPV for every method in proportion |
| Carrier share in other groups | 1 in 150 to 1 in 300 | Chosen, around the global 1 in 250 to 300 | As above, by group |
| Chance a carrier parent passes the variant to a child | 0.5 | Autosomal dominant inheritance | Not in doubt. Tested in `tests/test_generate.py` |
| Untreated LDL in adult carriers | Mean 6.2 mmol/L, SD 1.2 (APOB lower, PCSK9 higher) | Chosen to be typical of heterozygous FH | A wider overlap with non-carriers lowers every accuracy figure |
| Untreated LDL in adult non-carriers | Mean 2.9 mmol/L rising slowly with age, SD 0.75 | Chosen | As above |
| Non-carriers with high cholesterol from other causes | 6%, shifted up by about 1.8 mmol/L | Chosen, and too low | **The largest known flaw.** In real populations most people above 4.9 mmol/L do not have a monogenic variant. More lookalikes would cut PPV sharply. See `limitations.md` |
| Early coronary disease in carriers | 38% of men, 20% of women by the premature-age cut-off | Chosen | Affects the DLCN personal-history item and the relatives' features |
| People who start a statin | Logistic in age, LDL and heart disease | Chosen | Changes how often LDL is masked |
| People on a statin who do not take it | 25% | Chosen | More non-adherence makes statin correction over-correct |
| Statin effect | 25% to 40% lower (moderate), 40% to 55% (high) | Standard dose-response ranges | Correction factors in `dlcn.py` assume 30% and 50% |
| Family history written in the chart | 35% when a relative had early heart disease, 15% when a relative has high LDL | Chosen. The scoping review names missing family history as a main gap | If charts are better than this, DLCN does better and the model's advantage shrinks |
| Lipid panels per adult | About 2.6 for Emiratis, 1.1 for expatriates; many have none | Chosen | 383 of 698 carriers have no panel and cannot be flagged at all |
| Family links | Complete for Emirati families; expatriates have 2 to 9 relatives abroad | Chosen | **The second largest flaw.** Real links will be partial, which weakens the linked-family model |

## The simulation (`backend/heartline/simulate.py`)

| Assumption | Value | Source | If it is wrong |
| --- | --- | --- | --- |
| A genetic test finds a variant that is there | 95% | Chosen | Lower sensitivity sends more true cases to "no variant found" |
| A genetic test never reports a variant that is not there | 100% | Simplification | Real panels report variants of uncertain significance, which need a pathway of their own |
| Test turnaround | 14 days | Chosen | Changes waits, not counts |
| Invited relatives who get tested (projection) | 30% | Recent trials: 21% of first-degree relatives in IMPACT-FH (JACC Adv 2024), 30.4% with patient-sent invitations in CATCH (JAMA Netw Open 2026), under a third in Wales (Cox 2024). Direct contact may do better, but no trial shows it yet | The projection's "found through family" scales almost linearly with this. It is a slider on the Programme page. At 60% the projection finds 421 instead of 379 |
| Invited relatives who book, in the scripted demo | 60% | Chosen so the guided demo shows a booking within a few clicks | Affects the demo story only, not the projection (`simulate.BOOK_RATE`) |
| Children tested at the visit they were flagged for | 70% | Chosen | As above, for children |
| No reply becomes "no response" | 28 days | Chosen | Changes waits |
| A relative's targeted test is always correct | 100% | Simplification | Small effect |

## The projection (`backend/heartline/pilot.py`)

| Assumption | Value | Source | If it is wrong |
| --- | --- | --- | --- |
| Clinician reviews per week | 20 | Chosen. A slider | Sets how fast the flagged list is worked through, so it sets the first six months |
| Patients who agree to family testing | 85% | Chosen. A slider | Scales everything after consent |
| Relatives contacted | First-degree only | Design choice | The Lee 2019 review reports 0.80 new cases per index patient for first-degree only and 3.65 when second- and third-degree relatives are included. Heart Line's 0.52, at 30% uptake, is below the first; at 60% uptake it is 0.69 |
| Length | 52 weeks | Chosen | Chains are still running at the end |
| Runs | 5 seeds; the range is shown | | A single run would hide the spread |

## Clinical statements in the interface

| Statement | Status |
| --- | --- |
| Lipid test for children from age 2; statin discussion from 8 to 10 | Not verified against a paediatric guideline in this pass. Verify before relying on it |
| DLCN thresholds and points | Implemented from the published criteria; unit-tested against hand-worked cases |
| Adult LDL of 4.9 mmol/L as "very high" | The usual threshold for severe primary hypercholesterolaemia |
| UAE law on consent and confidentiality | Not verified. No article numbers appear in the interface |
