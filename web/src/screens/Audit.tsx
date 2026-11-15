import { useEffect, useState } from "react";
import { fmtDate, useApi } from "../api";
import { Empty, LoadError, Loading } from "../components/State";
import { says } from "./Patient";

type Row = { id: number; date: string; actor: string; role: string; action: string; case_id: number | null; detail: Record<string, unknown> | null };

// Every step, who took it and in what role. Rows cannot be edited or deleted; the database refuses.
export default function Audit() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [decisions, setDecisions] = useState(true);
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(q);
      setPage(1);
    }, 250);
    return () => clearTimeout(t);
  }, [q]);
  const { data, error, reload } = useApi<{ total: number; items: Row[] }>(
    `/api/audit?page=${page}&per_page=50&decisions=${decisions}&q=${encodeURIComponent(query)}`,
  );
  if (error) return <LoadError error={error} retry={reload} />;
  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  const pick = (d: boolean) => {
    setDecisions(d);
    setPage(1);
  };
  return (
    <div className="stack">
      <div>
        <h1>Audit</h1>
        <p className="lede">Who did what, in which role, and when. Entries are append-only: the database refuses edits and deletions.</p>
      </div>
      <div className="row">
        <div className="tabs">
          <button className={decisions ? "on" : ""} onClick={() => pick(true)}>
            Decisions by staff
          </button>
          <button className={!decisions ? "on" : ""} onClick={() => pick(false)}>
            Everything
          </button>
        </div>
        <input placeholder="Filter by action or person" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 240 }} aria-label="Filter" />
        {data && <span className="muted small">{data.total.toLocaleString()} entries</span>}
      </div>
      {!data ? (
        <Loading />
      ) : (
        <div className="card table-wrap" style={{ padding: 8 }}>
          {data.items.length === 0 ? (
            <Empty title="Nothing recorded yet">Decisions appear here as clinicians and coordinators act.</Empty>
          ) : (
            <table className="small">
              <thead>
                <tr>
                  <th>Demo date</th>
                  <th>What happened</th>
                  <th>Who</th>
                  <th>Case</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDate(r.date)}</td>
                    <td>
                      {r.action} {r.detail && r.role !== "demo" && <span className="muted">{says(r.detail)}</span>}
                    </td>
                    <td>{r.actor}</td>
                    <td className="muted">{r.case_id ? `Case ${r.case_id}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {pages > 1 && (
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <span className="small muted">
            Page {page} of {pages}
          </span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}
