import { Brief, fmtDate, useApi } from "../api";

type Item = {
  id: number;
  status: string;
  due_date: string;
  flagged_at: string;
  tested_at: string | null;
  child: Brief & { age_years: number };
  parents: Brief[];
  due: string[];
};

const LABEL: Record<string, string> = { due: "Due", tested_negative: "Tested negative", tested_positive: "Tested positive" };

export default function WellChild() {
  const { data, error } = useApi<{ items: Item[] }>("/api/wellchild");
  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading</p>;
  return (
    <div className="stack">
      <div>
        <h1>Well-Child</h1>
        <p className="lede">
          Children of confirmed families get a cholesterol test at their next Well-Child Visit, from age 2. If they test
          positive, statin treatment is usually discussed from age 8 to 10.
        </p>
      </div>
      <div className="card table-wrap" style={{ padding: 8 }}>
        <table>
          <thead>
            <tr>
              <th>Child</th>
              <th>Parents</th>
              <th>Flagged</th>
              <th>Due</th>
              <th>What to do</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((w) => (
              <tr key={w.id}>
                <td>
                  <a href={`#/patient/${w.child.id}`}>{w.child.name}</a>
                  <div className="small muted">
                    {w.child.age_years < 2 ? `${Math.round(w.child.age_years * 12)} months` : `${Math.floor(w.child.age_years)} years`}
                  </div>
                </td>
                <td className="small">
                  {w.parents.map((p, i) => (
                    <span key={p.id}>
                      {i > 0 && ", "}
                      <a href={`#/patient/${p.id}`}>{p.name}</a>
                    </span>
                  ))}
                </td>
                <td>{fmtDate(w.flagged_at)}</td>
                <td>{w.status === "due" ? fmtDate(w.due_date) : <span className="muted">Tested {fmtDate(w.tested_at)}</span>}</td>
                <td className="small">{w.due.join(". ")}</td>
                <td>
                  <span className={`pill ${w.status}`}>{LABEL[w.status]}</span>
                </td>
              </tr>
            ))}
            {data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  No children flagged yet. They appear here when a confirmed patient starts family testing.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="synthetic">Well-Child clinic results are simulated.</p>
    </div>
  );
}
