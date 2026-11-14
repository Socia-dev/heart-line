import { pct, useApi } from "../api";
import Fold from "../components/Fold";

type At = { flagged: number; found: number; sensitivity: number; ppv: number };
type FairRow = { group: string; people: number; with_fh: number; model_b: At; dlcn6: At };
type Evaluation = {
  population: { people: number; with_labs: number; with_fh_with_labs: number; with_fh_total: number };
  metrics: Record<string, { auroc: number; auprc: number }>;
  matched_workload: { flag_count: number } & Record<"DLCN" | "Model A" | "Model B", At>;
  thresholds: (At & { threshold: number })[];
  worklist_threshold: At & { threshold: number; why: string };
  fairness: Record<string, FairRow[]>;
  model_card: { intended_use: string; data: string; family_data_governance: string; validation: string; limits: string[]; features: Record<string, string[]> };
};

const METHODS = [
  ["DLCN", "DLCN score (usual clinical score)"],
  ["Model A", "Heart Line, patient's own record"],
  ["Model B", "Heart Line, with relatives' records"],
] as const;

export default function Model() {
  const { data: e, error } = useApi<Evaluation>("/api/evaluation");
  if (error) return <p className="error">{error}</p>;
  if (!e) return <p className="muted">Loading</p>;
  const m = e.matched_workload;
  const max = Math.max(...METHODS.map(([k]) => m[k].found));
  return (
    <div className="stack">
      <div>
        <h1>Model</h1>
        <p className="lede">How many people with inherited high cholesterol each method finds. All numbers are on synthetic data.</p>
      </div>

      <section className="card">
        <h2>Same workload, more people found</h2>
        <p className="muted">
          If doctors review {m.flag_count} flagged people, this is how many of them actually have FH. Out of {e.population.with_fh_with_labs} people
          with FH and a cholesterol result.
        </p>
        <div className="bars" style={{ marginTop: 16 }}>
          {METHODS.map(([k, name]) => (
            <div key={k} className={`bar-row ${k === "Model B" ? "best" : ""}`}>
              <span>{name}</span>
              <div className="track">
                <div className="fill" style={{ width: `${(m[k].found / max) * 100}%` }} />
              </div>
              <strong className="num" style={{ textAlign: "right" }}>
                {m[k].found}
              </strong>
            </div>
          ))}
        </div>
        <p style={{ marginTop: 16, marginBottom: 0 }}>
          Using relatives' records finds <strong>{m["Model B"].found - m.DLCN.found} more people</strong> than the DLCN score for the same number of
          reviews.
        </p>
      </section>

      <div>
        <Fold title="Accuracy" note="AUROC, AUPRC, sensitivity and PPV">
          <table className="small">
            <thead>
              <tr>
                <th>Method</th>
                <th className="num">AUROC</th>
                <th className="num">AUPRC</th>
                <th className="num">Sensitivity at {m.flag_count}</th>
                <th className="num">PPV at {m.flag_count}</th>
              </tr>
            </thead>
            <tbody>
              {METHODS.map(([k, name]) => (
                <tr key={k}>
                  <td>{name}</td>
                  <td className="num">{e.metrics[k].auroc.toFixed(3)}</td>
                  <td className="num">{e.metrics[k].auprc.toFixed(3)}</td>
                  <td className="num">{pct(m[k].sensitivity)}</td>
                  <td className="num">{pct(m[k].ppv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Fold>

        <Fold title="Worklist cut-off" note={`${e.worklist_threshold.flagged} flagged, ${pct(e.worklist_threshold.sensitivity)} found`}>
          <p className="muted">
            The worklist flags anyone with a score of {pct(e.worklist_threshold.threshold)} or more. {e.worklist_threshold.why}
          </p>
          <table className="small">
            <thead>
              <tr>
                <th className="num">Score at least</th>
                <th className="num">Flagged</th>
                <th className="num">Sensitivity</th>
                <th className="num">PPV</th>
              </tr>
            </thead>
            <tbody>
              {e.thresholds.map((t) => (
                <tr key={t.threshold} className={t.threshold === e.worklist_threshold.threshold ? "best" : ""}>
                  <td className="num">{pct(t.threshold)}</td>
                  <td className="num">{t.flagged}</td>
                  <td className="num">{pct(t.sensitivity)}</td>
                  <td className="num">{pct(t.ppv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Fold>

        <Fold title="Fairness" note="By sex, nationality group and age">
          <p className="muted small">
            Share of people with FH that the worklist finds in each group, against DLCN 6 or more. Small groups vary a lot.
          </p>
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
                      <tr key={r.group}>
                        <td>{r.group}</td>
                        <td className="num">{r.with_fh}</td>
                        <td className="num">{r.with_fh ? pct(r.model_b.sensitivity) : ""}</td>
                        <td className="num">{r.with_fh ? pct(r.dlcn6.sensitivity) : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </Fold>

        <Fold title="Model card" note="Use, data and limits">
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

      <p className="synthetic">
        Synthetic population of {e.population.people.toLocaleString()} people. {e.population.with_fh_total - e.population.with_fh_with_labs} of the{" "}
        {e.population.with_fh_total} people with FH have no cholesterol result, so no method can flag them. Family testing is how they get found.
      </p>
    </div>
  );
}

