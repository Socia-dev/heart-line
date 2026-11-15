type Row = { key: string; what: string; published: number; as_published: string; synthetic: number; verdict: string; source: string; unit: string };
export type RealismData = {
  rows: Row[];
  sources: Record<string, { short: string; cite: string }>;
  notes: string[];
  synthetic: {
    adults: number;
    ldl_by_age_sex: { band: string; sex: string; ldl_mean: number; people: number }[];
    ldl_histogram: { edges: number[]; counts: number[] };
  };
};

const fmt = (r: Row, v: number) => (r.unit === "1 in" ? `1 in ${v}` : `${v.toFixed(2)} mmol/L`);

// The synthetic population next to published real figures, with sources, and plain words where it differs.
export default function Realism({ r }: { r: RealismData }) {
  const h = r.synthetic.ldl_histogram;
  const max = Math.max(...h.counts);
  const W = 600;
  const H = 200;
  const pad = { l: 8, r: 8, t: 12, b: 26 };
  const bw = (W - pad.l - pad.r) / h.counts.length;
  const x = (v: number) => pad.l + (v / h.edges[h.edges.length - 1]) * (W - pad.l - pad.r);
  const ldl = r.rows.find((x) => x.key === "ldl_mean")!;
  return (
    <div className="stack">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Measure</th>
              <th className="num">Published</th>
              <th className="num">Synthetic</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {r.rows.map((row) => (
              <tr key={row.key}>
                <td>
                  {row.what}
                  <div className="small muted">{r.sources[row.source]?.short}</div>
                </td>
                <td className="num">
                  {fmt(row, row.published)}
                  <div className="small muted">{row.as_published}</div>
                </td>
                <td className="num">{fmt(row, row.synthetic)}</td>
                <td>{row.verdict === "close" ? "Close" : <strong>{row.verdict[0].toUpperCase() + row.verdict.slice(1)}</strong>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid g2">
        <div>
          <h3>LDL across synthetic adults</h3>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Histogram of LDL in synthetic adults, with the published US mean marked">
            {h.counts.map((c, i) => (
              <rect
                key={i}
                className="bar-in"
                style={{ "--d": `${i * 25}ms` } as React.CSSProperties}
                x={pad.l + i * bw + 1}
                width={bw - 2}
                y={pad.t + (1 - c / max) * (H - pad.t - pad.b)}
                height={(c / max) * (H - pad.t - pad.b)}
                fill="#c7c2c3"
              />
            ))}
            <line x1={x(ldl.published)} x2={x(ldl.published)} y1={pad.t} y2={H - pad.b} stroke="#9f1239" strokeWidth="2" />
            <text x={x(ldl.published) + 6} y={pad.t + 12} fontSize="12" fill="#9f1239">
              Published US mean {ldl.published.toFixed(2)}
            </text>
            {[0, 2, 4, 6, 8, 10].map((v) => (
              <text key={v} x={x(v)} y={H - 8} fontSize="12" textAnchor="middle" fill="#70666a">
                {v}
              </text>
            ))}
          </svg>
          <p className="small muted">Latest LDL of {r.synthetic.adults.toLocaleString()} synthetic adults, mmol/L. The long tail on the right is mostly FH.</p>
        </div>
        <div>
          <h3>Mean LDL by age and sex, synthetic</h3>
          <table className="small">
            <thead>
              <tr>
                <th>Age</th>
                <th className="num">Women</th>
                <th className="num">Men</th>
              </tr>
            </thead>
            <tbody>
              {[...new Set(r.synthetic.ldl_by_age_sex.map((x) => x.band))].map((band) => {
                const f = r.synthetic.ldl_by_age_sex.find((x) => x.band === band && x.sex === "F");
                const m = r.synthetic.ldl_by_age_sex.find((x) => x.band === band && x.sex === "M");
                return (
                  <tr key={band}>
                    <td>{band}</td>
                    <td className="num">{f?.ldl_mean.toFixed(2)}</td>
                    <td className="num">{m?.ldl_mean.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <ul className="reasons small" style={{ marginTop: 12 }}>
            {r.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="small muted">
        Sources:
        <ul className="reasons">
          {Object.entries(r.sources).map(([k, s]) => (
            <li key={k}>{s.cite}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
