import { pct, range, useApi } from "../api";
import Fold from "../components/Fold";
import { Curves, Population } from "../components/ModelCharts";
import Retrain from "../components/Retrain";
import { LoadError, Loading } from "../components/State";

type At = { name: string; flagged: number; found: number; sensitivity: number; ppv: number; sensitivity_ci: number[]; ppv_ci: number[] };
type Metric = { name: string; auroc: number; auprc: number; auroc_ci: number[]; auprc_ci: number[] };
type FairRow = { group: string; people: number; with_fh: number; small: boolean; sensitivity: number; sensitivity_ci: number[]; dlcn_sensitivity: number };
type Evaluation = {
  curves?: Record<string, { roc: number[][]; pr: number[][]; point: { fpr: number; tpr: number; precision: number } }>;
  model_version: string;
  population: { people: number; with_labs: number; with_fh_with_labs: number; with_fh_total: number };
  metrics: Record<string, Metric>;
  matched_workload: { flag_count: number; methods: Record<string, At> };
  worklist_threshold: At & { threshold: number; why: string };
  bands: { band: string; people: number; with_fh: number; observed_rate: number }[];
  calibration: { method: string; brier_raw: number; brier_calibrated: number; curve: { from: number; to: number; people: number; predicted: number; observed: number }[] };
  fairness: Record<string, FairRow[]>;
  misses: { missed: number; found: number; rows: { what: string; among_missed: number; among_found: number }[] };
  published: { note: string; review: string; rows: { method: string; source: string; sensitivity: number; ppv: number }[] };
  model_card: { intended_use: string; data: string; family_data_governance: string; validation: string; limits: string[] };
};
const ORDER = ["dlcn", "dlcn_linked", "own", "linked"];

// "Can we trust the flags?" One comparison on top, the honest caveat next, everything else folded.
export default function Model() {
  const { data: e, error, reload } = useApi<Evaluation>("/api/evaluation");
  if (error) return <LoadError error={error} retry={reload} />;
  if (!e) return <Loading />;
  const m = e.matched_workload.methods;
  const max = Math.max(...ORDER.map((k) => m[k].found));
  const w = e.worklist_threshold;
  return (
    <div className="stack">
      <div>
        <h1>Can we trust the flags?</h1>
        <p className="lede">
          What the model gets right, where it misses, and why these numbers are higher than a real hospital would see. Everything here is measured on
          synthetic data.
        </p>
      </div>

      <section className="card">
        <h2>Same workload, more people found</h2>
        <p className="muted">
          If clinicians review {e.matched_workload.flag_count} flagged people, this is how many of them have FH, out of {e.population.with_fh_with_labs} who
          have it and have a cholesterol result.
        </p>
        <div className="bars" style={{ marginTop: 16 }}>
          {ORDER.map((k) => (
            <div key={k} className={`bar-row ${k === "linked" ? "best" : ""}`}>
              <span>{m[k].name}</span>
              <div className="track">
                <div className="fill" style={{ width: `${(m[k].found / max) * 100}%` }} />
              </div>
              <strong style={{ textAlign: "right" }}>{m[k].found}</strong>
            </div>
          ))}
        </div>
        <p style={{ marginTop: 16, marginBottom: 0 }}>
          Reading the two pairs: giving DLCN the relatives' records changes little ({m.dlcn.found} to {m.dlcn_linked.found}), and the model on one record
          finds {m.own.found}. It is the model using relatives' records together that finds <strong>{m.linked.found}</strong>. That relative gain is the
          claim to test on real data.
        </p>
      </section>

      {e.curves && (
        <section className="card">
          <h2>Across every possible cut-off</h2>
          <p className="muted">
            Each line shows how a method trades finding more people against flagging more people who turn out not to have FH. Higher and further left is
            better. On synthetic data.
          </p>
          <Curves curves={e.curves} k={e.matched_workload.flag_count} />
        </section>
      )}

      <section className="card">
        <h2>Retrain it here</h2>
        <p className="muted">
          This runs the real training: cross-validation grouped by family, calibration, then the same comparison as above. Each fold appears as it
          finishes. Nothing changes for anyone until you choose to use the new model.
        </p>
        <Retrain current={e.metrics} />
      </section>

      <section className="card">
        <h2>Everyone with a result</h2>
        <p className="muted">
          Each dot is one person. Across is their highest LDL, up is the model's score. People above the dashed line are on a clinician's worklist. Hover
          for the rating; click to open the record.
        </p>
        <Population />
      </section>

      <section className="notice">
        <h2>Why these numbers are too good</h2>
        <p>{e.published.note}</p>
        <div className="table-wrap">
          <table className="small">
            <thead>
              <tr>
                <th>Method</th>
                <th>Where</th>
                <th className="num">Finds (sensitivity)</th>
                <th className="num">Flags that are right (PPV)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <strong>Heart Line at its worklist cut-off</strong>
                </td>
                <td>Synthetic</td>
                <td className="num">{pct(w.sensitivity)}</td>
                <td className="num">{pct(w.ppv)}</td>
              </tr>
              <tr>
                <td>DLCN 6 or more, in Heart Line's data</td>
                <td>Synthetic</td>
                <td className="num">{pct(m.dlcn.sensitivity)}</td>
                <td className="num">{pct(m.dlcn.ppv)}</td>
              </tr>
              {e.published.rows.map((r) => (
                <tr key={r.method}>
                  <td>{r.method}</td>
                  <td>{r.source}</td>
                  <td className="num">{pct(r.sensitivity, 1)}</td>
                  <td className="num">{pct(r.ppv, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small" style={{ marginBottom: 0 }}>
          DLCN behaves in the synthetic data much as it does in the published study, which is some evidence the population is not absurd. {e.published.review}
        </p>
      </section>

      <div>
        <Fold title="What each score band means" note="Observed rates per band">
          <p className="muted small">Clinicians see a band in words, not a percentage. This is how often people in each band had FH.</p>
          <table className="small">
            <thead>
              <tr>
                <th>Band</th>
                <th className="num">People</th>
                <th className="num">With FH</th>
                <th className="num">Rate</th>
              </tr>
            </thead>
            <tbody>
              {e.bands.map((b) => (
                <tr key={b.band}>
                  <td>{b.band}</td>
                  <td className="num">{b.people.toLocaleString()}</td>
                  <td className="num">{b.with_fh}</td>
                  <td className="num">{pct(b.observed_rate, b.observed_rate < 0.01 ? 2 : 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small muted">
            The worklist cut-off flags {w.flagged} people and finds {pct(w.sensitivity)} of those with FH ({range(w.sensitivity_ci)}). {w.why}
          </p>
        </Fold>

        <Fold title="Where it misses" note={`${e.misses.missed} people with FH below the cut-off`}>
          <p className="muted small">
            The {e.misses.missed} people with FH that the worklist does not flag, compared with the {e.misses.found} it does.
          </p>
          <table className="small">
            <thead>
              <tr>
                <th></th>
                <th className="num">Among those missed</th>
                <th className="num">Among those found</th>
              </tr>
            </thead>
            <tbody>
              {e.misses.rows.map((r) => (
                <tr key={r.what}>
                  <td>{r.what}</td>
                  <td className="num">{pct(r.among_missed)}</td>
                  <td className="num">{pct(r.among_found)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Fold>

        <Fold title="Accuracy with intervals" note="AUROC, AUPRC, sensitivity, PPV">
          <table className="small">
            <thead>
              <tr>
                <th>Method</th>
                <th className="num">AUROC</th>
                <th className="num">AUPRC</th>
                <th className="num">Sensitivity at {e.matched_workload.flag_count}</th>
                <th className="num">PPV at {e.matched_workload.flag_count}</th>
              </tr>
            </thead>
            <tbody>
              {ORDER.map((k) => (
                <tr key={k}>
                  <td>{m[k].name}</td>
                  <td className="num">
                    {e.metrics[k].auroc.toFixed(3)}
                    <div className="muted">{e.metrics[k].auroc_ci.map((x) => x.toFixed(3)).join(" to ")}</div>
                  </td>
                  <td className="num">
                    {e.metrics[k].auprc.toFixed(3)}
                    <div className="muted">{e.metrics[k].auprc_ci.map((x) => x.toFixed(3)).join(" to ")}</div>
                  </td>
                  <td className="num">
                    {pct(m[k].sensitivity)}
                    <div className="muted">{range(m[k].sensitivity_ci)}</div>
                  </td>
                  <td className="num">
                    {pct(m[k].ppv)}
                    <div className="muted">{range(m[k].ppv_ci)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small muted">Second lines are 95% bootstrap intervals.</p>
        </Fold>

        <Fold title="Calibration" note="Does the estimate match what happens?">
          <p className="muted small">
            {e.calibration.method}. Brier score {e.calibration.brier_calibrated.toFixed(4)} after calibration, {e.calibration.brier_raw.toFixed(4)} before: the
            raw output was already close, so calibration changes little here.
          </p>
          <table className="small">
            <thead>
              <tr>
                <th>Estimated chance</th>
                <th className="num">People</th>
                <th className="num">Average estimate</th>
                <th className="num">Actually had FH</th>
              </tr>
            </thead>
            <tbody>
              {e.calibration.curve.map((c) => (
                <tr key={c.from}>
                  <td>
                    {pct(c.from)} to {pct(c.to)}
                  </td>
                  <td className="num">{c.people.toLocaleString()}</td>
                  <td className="num">{pct(c.predicted, 1)}</td>
                  <td className="num">{pct(c.observed, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Fold>

        <Fold title="Fairness" note="By sex, nationality group and age">
          <p className="muted small">Share of people with FH that the worklist finds in each group, with a 95% interval. Groups with fewer than 20 people with FH are too small to read.</p>
          <div className="grid g2">
            {Object.entries(e.fairness).map(([title, rows]) => (
              <div key={title} className="table-wrap">
                <h3>{title}</h3>
                <table className="small">
                  <thead>
                    <tr>
                      <th>Group</th>
                      <th className="num">With FH</th>
                      <th className="num">Heart Line finds</th>
                      <th className="num">DLCN finds</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.group} className={r.small ? "dim" : ""}>
                        <td>{r.group}</td>
                        <td className="num">{r.with_fh}</td>
                        <td className="num">
                          {r.small ? "Too few to read" : pct(r.sensitivity)}
                          {!r.small && <div className="muted">{range(r.sensitivity_ci)}</div>}
                        </td>
                        <td className="num">{r.small ? "" : pct(r.dlcn_sensitivity)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </Fold>

        <Fold title="Model card" note={e.model_version}>
          <dl className="facts">
            <dt>Intended use</dt>
            <dd>{e.model_card.intended_use}</dd>
            <dt>Data</dt>
            <dd>{e.model_card.data}</dd>
            <dt>Validation</dt>
            <dd>{e.model_card.validation}</dd>
            <dt>Relatives' data</dt>
            <dd>{e.model_card.family_data_governance}</dd>
            <dt>Limits</dt>
            <dd>
              <ul className="reasons">
                {e.model_card.limits.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </dd>
          </dl>
        </Fold>
      </div>

      <p className="small muted">
        Synthetic population of {e.population.people.toLocaleString()} people. {e.population.with_fh_total - e.population.with_fh_with_labs} of the{" "}
        {e.population.with_fh_total} people with FH have no cholesterol result, so no method can flag them. Family testing is how they get found.
      </p>
    </div>
  );
}
