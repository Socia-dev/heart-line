# Limitations

What Heart Line cannot claim, in order of how much it matters.

## 1. It has never seen a real patient

Every person, result and family is synthetic. Nothing here shows the model works on real records. Before any real use it needs a data-sharing agreement, a real extract, and a fresh validation.

## 2. The accuracy figures are higher than a real deployment would see

On synthetic data the worklist finds 83% of people with FH who have a cholesterol result, and 42% of its flags are right. Published models in real populations report a PPV of 1% to 15% (`docs/research/05-evidence-and-judging.md`). Three reasons:

- The synthetic world has few people with high cholesterol from other causes (6% of non-carriers). In reality they outnumber people with FH.
- Family links are complete for Emirati families. Real links will have gaps.
- Prevalence is about 1 in 114, at least twice that of the populations in the published studies.

What can be said: in this synthetic world, a model that reads linked relatives' records finds 189 people with FH where the standard DLCN score finds 110, for the same number of reviews. Giving DLCN the same relatives' records does not close the gap (107). That relative result is a hypothesis for real data, not a finding.

## 3. Using a relative's record to score someone else needs a legal basis

The linked-family model reads other people's records. That is its advantage and its largest governance question. It needs a lawful basis, approval from the data owner, and clear information to patients. Heart Line does not settle this; it shows what the question is worth.

## 4. People with no cholesterol result cannot be flagged

383 of the 698 synthetic carriers have no lipid panel. No scoring method reaches them. Family testing is the only way Heart Line finds them, which is the point of the product, but it means screening alone misses more than half.

## 5. Only first-degree relatives are contacted

Published programmes that go to second- and third-degree relatives find several times more cases per index patient. Heart Line's projection (0.69 new cases per confirmed patient) is in line with first-degree-only programmes (0.80) and well below the wider ones (3.65).

## 6. The demo is scripted

- The patient behind "New lab result" is chosen, using ground truth, so that the flag fires, the test finds a variant and the family shows a chain (`simulate._demo_order`). The code says so.
- Test results, bookings and Well-Child results are generated from the truth table with fixed seeds.
- Roles are a switch, not a sign-in. The audit log records the role that was selected, not an authenticated person.

## 7. No real messages, labs or records systems

SMS is a text preview. The FHIR export has not been validated against a FHIR server and is not connected to Malaffi or any exchange. It lacks FamilyMemberHistory, Consent, ServiceRequest and Task resources.

## 8. Parts of the workflow are thin

- Reminders, a phone-call script and a contact plan are not built; an unanswered invitation simply becomes "no reply" after 28 days.
- The Well-Child nurse can see the list and cannot yet record anything.
- Nothing happens after a diagnosis: no referral, treatment or LDL-at-target tracking.
- Consent is all relatives minus those the patient excludes. It can be reopened after a refusal, and cannot yet be withdrawn once invitations have gone out.
- Genetic results are found or not found. Variants of uncertain significance are not modelled.

## 9. Clinical content has not been reviewed by a clinician

The wording of the consent question, the invitation, the answer to "why am I getting this?" and the children's pathway were written by the team. A lipid clinician, a genetic counsellor and, for a pilot, legal counsel should review them. The Arabic text needs a native medical reviewer.

## 10. Engineering

- SQLite and a single process. Fine for a demo.
- 34 backend tests; no automated browser tests. The interface was checked by hand at desktop and phone widths.
- One test run in about a dozen failed once and could not be reproduced. It is noted here until explained.
- The staff interface is English only.
