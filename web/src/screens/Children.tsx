import { fmtDate, useApi } from "../api";
import { Empty, LoadError, Loading } from "../components/State";

type Item = { id: number; status: string; due_date: string; tested_at: string | null; child: { name: string; mrn: string; age_years: number }; due: string };
const LABEL: Record<string, string> = { due: "Due", tested_negative: "Tested clear", tested_positive: "Tested positive" };

// The Well-Child nurse's list. It names the child and the test, and nothing about why the family was flagged.
export default function Children() {
  const { data, error, reload } = useApi<{ items: Item[] }>("/api/wellchild");
  if (error) return <LoadError error={error} retry={reload} />;
  if (!data) return <Loading />;
  return (
    <div className="stack">
      <div>
        <h1>Children due a cholesterol test</h1>
        <p className="lede">Add a lipid test to the child's next Well-Child Visit, from age 2.</p>
      </div>
      <div className="card table-wrap" style={{ padding: 8 }}>
        {data.items.length === 0 ? (
          <Empty title="No children flagged">Children appear here when family testing starts for one of their parents.</Empty>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Child</th>
                <th>Visit</th>
                <th>What to do</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((w) => (
                <tr key={w.id}>
                  <td>
                    {w.child.name}
                    <div className="small muted">
                      {w.child.age_years < 2 ? `${Math.round(w.child.age_years * 12)} months` : `${Math.floor(w.child.age_years)} years`}. {w.child.mrn}
                    </div>
                  </td>
                  <td>{w.status === "due" ? fmtDate(w.due_date) : <span className="muted">Tested {fmtDate(w.tested_at)}</span>}</td>
                  <td className="small">{w.due}</td>
                  <td>
                    <span className={`pill ${w.status}`}>{LABEL[w.status]}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="small muted">Clinic results are simulated in this demo.</p>
    </div>
  );
}
