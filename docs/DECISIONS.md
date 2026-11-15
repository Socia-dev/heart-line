# Decisions

Numbered, newest last. Each says what was decided, why, and what was rejected. Add an entry when you change one.

| # | Decision | Why | Rejected |
| --- | --- | --- | --- |
| 1 | Synthetic data only, with ground truth in its own table that the API never reads | No real data was available, and keeping truth out of the API makes "the answer cannot leak" a testable property | Mixing truth columns into `people` |
| 2 | An own generator, not Synthea | Cascade testing needs linked families; Synthea has none | Synthea plus invented links |
| 3 | Cross-validation grouped by extended family | Relatives on both sides of a split would leak through the family features | Plain k-fold |
| 4 | Worklist cut-off at the highest raw score that keeps 80% sensitivity (0.04) | A screening list should miss few; the cost is more reviews | A fixed PPV target |
| 5 | Show a band in words, keep the figure in details | A raw model output is not a probability, and "6% chance" beside "Review this flag" would be distrusted | A percentage on the worklist |
| 6 | Calibrate inside the folds with isotonic regression | So the calibrated figure for a person never saw that person | Calibrating on the same out-of-fold scores it is reported on |
| 7 | Four-way comparison: DLCN, DLCN with linked family, model on own record, model with linked family | Separates "more data" from "better method". Without it the model's lead could be put down to data DLCN was denied | Model against chart-only DLCN alone |
| 8 | Reasons are signed, and unknown is never turned into evidence against | A clinician should see what argues against a flag; a missing examination is not a normal one | Top three positive reasons only |
| 9 | One transition table decides every change (`machine.py`) | The rules were written three times and could drift. One table can be tested exhaustively and shown to a clinician | `if` chains in the engine, the API and the page |
| 10 | Roles on every action, by a demo switch and a header | Separation of duties is the governance story; sign-in would add nothing to a prototype | No roles; or a real user table |
| 11 | The clinician records consent; the coordinator sends | Two trained roles, two steps. It also makes the hand-off visible in the demo | One "start family testing" button |
| 12 | A positive relative becomes a case waiting for their own clinician; nobody's consent is simulated | The project's first rule is that a person decides at each link. The earlier build rolled a die | Automatic consent at 85% to make the chain appear faster |
| 13 | A clinician sees whether adult relatives were contacted and replied, not their results | A relative agreed to be tested, not to have the result on a sibling's chart | Colouring the family tree by result for everyone |
| 14 | A relative's own clinician is not told which relative led to them | The invitation promises not to name the index patient; the chart must keep that promise | A "found after X was confirmed" link for all roles |
| 15 | Dismissing a flag needs one of four reasons and can be reopened | Disagreement with the model is the most useful feedback there is, and a mis-click must be reversible | A bare Dismiss button |
| 16 | The audit table is append-only by database trigger, and refused attempts are logged | An audit log that can be edited is not one | Trusting application code not to update it |
| 17 | The coordinator sees every recipient and the exact message before sending | Sending is the one step that cannot be taken back | A single press |
| 18 | The relative has four answers: book, already tested, call me, no thanks | "Ignore it" is not a choice a programme can learn from | Book or nothing |
| 19 | The simulator lives in its own module and goes through the same door as staff | So a pilot replaces one file, and no back door can set a status | Simulation inside the engine |
| 20 | First-degree relatives only | Simplest defensible scope for a first build | Second-degree relatives, which the evidence says would find far more. This is the next clinical feature |
| 21 | Keep LightGBM | It works and the deadline is close | An Explainable Boosting Machine, whose explanation is the model. Worth trying after submission |
| 22 | Interface on the KUEC Attar design system with red as the action colour | The owner's instruction. See `docs/DESIGN.md` for what was kept and adapted | A separate visual language |
| 23 | Published benchmarks sit beside Heart Line's own numbers, with the reason the synthetic figures are higher | A judge who knows the field will trust a team that shows FAMCAT's 1.6% PPV next to its own figure | Showing only Heart Line's numbers |
