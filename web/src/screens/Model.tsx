import { pct, useApi } from "../api";

type At = { flagged: number; found: number; sensitivity: number; ppv: number };
type FairRow = { group: string; people: number; with_fh: number; model_b: At; dlcn6: At };
type Evaluation = {
  label: string;
  population: { people: number; with_labs: number; with_fh_with_labs: number; with_fh_total: number };
  metrics: Record<string, { auroc: number; auprc: number }>;
  matched_workload: { flag_count: number; note: string } & Record<"DLCN" | "Model A" | "Model B", At>;
  thresholds: (At & { threshold: number })[];
  worklist_threshold: At & { threshold: number; why: string };
  fairness: Record<string, FairRow[]>;
  model_card: { intended_use: string; data: string; family_data_governance: string; validation: string; limits: string[]; features: Record<string, string[]> };
};

const METHODS = [
  ["DLCN", "Dutch Lipid Clinic Network score", "The usual clinical score, using family history written in the chart"],
  ["Model A", "Model A", "One patient's own record"],
  ["Model B", "Model B, family-linked", "Model A plus what relatives' records show"],
] as const;

export default function Model() {
  const { data: e, error } = useApi<Evaluation>("/api/evaluation");
  if (error) return <p className="error">{error}</p>;
  if (!e) return <p className="muted">Loading</p>;
  const m = e.matched_workload;
  const gain = m["Model B"].found - m.DLCN.found;
  return (
    <div className="stack">
      <div>
        <h1>Model</h1>
        <p className="lede">
          How well each method finds familial hypercholesterolaemia among {e.population.with_labs.toLocaleString()} synthetic people with at
          least one cholesterol result, {e.population.with_fh_with_labs} of whom have it. All numbers are on synthetic data.
        </p>
      </div>

      <section className="notice">
        <h2>Same workload, more people found</h2>
        <p style={{ margin: 0 }}>
          If clinicians review {m.flag_count} people, the number DLCN 6 or more flags, the family-linked model finds {m["Model B"].found} people
          with FH against {m.DLCN.found} for DLCN. That is {gain} more people found for the same number of reviews. On synthetic data.
        </p>
      </section>

      <div className="grid g3">
        {METHODS.map(([k, name, what]) => (
          <section key={k} className="card">
            <h3>{name}</h3>
            <p className="small muted">{what}</p>
            <div className="row" style={{ gap: 24 }}>
              <div className="stat">
                <div className="n">{e.metrics[k].auroc.toFixed(3)}</div>
                <div className="l">AUROC</div>
              </div>
              <div className="stat">
                <div className="n">{e.metrics[k].auprc.toFixed(3)}</div>
                <div className="l">AUPRC</div>
              </div>
            </div>
          </section>
        ))}
      </div>

      <section className="card table-wrap">
        <h2>At the same number flagged</h2>
        <p className="muted small">{m.note} On synthetic data.</p>
        <table>
          <thead>
            <tr>
              <th>Method</th>
              <th className="num">Flagged</th>
              <th className="num">With FH found</th>
              <th className="num">Sensitivity</th>
              <th className="num">PPV</th>
            </tr>
          </thead>
          <tbody>
            {METHODS.map(([k, name]) => (
              <tr key={k} className={k === "Model B" ? "best" : ""}>
                <td>{name}</td>
                <td className="num">{m[k].flagged}</td>
                <td className="num">{m[k].found}</td>
                <td className="num">{pct(m[k].sensitivity)}</td>
                <td className="num">{pct(m[k].ppv)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card table-wrap">
        <h2>Worklist cut-off</h2>
        <p className="muted">
          The worklist uses a model B score of {pct(e.worklist_threshold.threshold)} or more. {e.worklist_threshold.why} It flags{" "}
          {e.worklist_threshold.flagged} people, finds {pct(e.worklist_threshold.sensitivity)} of those with FH, and {pct(e.worklist_threshold.ppv)} of
          flags turn out to have it. On synthetic data.
        </p>
        <table className="small">
          <thead>
            <tr>
              <th className="num">Model B score at least</th>
              <th className="num">Flagged</th>
              <th className="num">Found</th>
              <th className="num">Sensitivity</th>
              <th className="num">PPV</th>
            </tr>
          </thead>
          <tbody>
            {e.thresholds.map((t) => (
              <tr key={t.threshold} className={t.threshold === e.worklist_threshold.threshold ? "best" : ""}>
                <td className="num">{pct(t.threshold, t.threshold < 0.1 ? 0 : 0)}</td>
                <td className="num">{t.flagged}</td>
                <td className="num">{t.found}</td>
                <td className="num">{pct(t.sensitivity)}</td>
                <td className="num">{pct(t.ppv)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Fairness checks</h2>
        <p className="muted small">
          Sensitivity and PPV by group, for model B at the worklist cut-off and for DLCN 6 or more. Small groups have wide uncertainty. On synthetic
          data.
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
                    <th className="num">Sens. B</th>
                    <th className="num">PPV B</th>
                    <th className="num">Sens. DLCN</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.group}>
                      <td>
                        {r.group}
                        <div className="muted">{r.people.toLocaleString()} people</div>
                      </td>
                      <td className="num">{r.with_fh}</td>
                      <td className="num">{r.with_fh ? pct(r.model_b.sensitivity) : ""}</td>
                      <td className="num">{r.model_b.flagged ? pct(r.model_b.ppv) : ""}</td>
                      <td className="num">{r.with_fh ? pct(r.dlcn6.sensitivity) : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Model card</h2>
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
          <dt>Features</dt>
          <dd className="small">
            {Object.entries(e.model_card.features).map(([k, v]) => (
              <p key={k}>
                <strong>{k}:</strong> {v.join(", ")}
              </p>
            ))}
          </dd>
        </dl>
      </section>
      <p className="synthetic">
        Every number on this page comes from a synthetic population of {e.population.people.toLocaleString()} people. Of the{" "}
        {e.population.with_fh_total} people with FH in it, {e.population.with_fh_total - e.population.with_fh_with_labs} have no cholesterol results
        and cannot be flagged by any method; family testing is how they get found.
      </p>
    </div>
  );
}
