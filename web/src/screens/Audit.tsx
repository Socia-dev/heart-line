import { useEffect, useState } from "react";
import { fmtDate, useApi } from "../api";
import { detail } from "./Patient";

type Row = { id: number; sim_date: string; logged_at: string; actor: string; action: string; subject: string; person_id: number | null; detail: string | null };

export default function Audit() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(q);
      setPage(1);
    }, 250);
    return () => clearTimeout(t);
  }, [q]);
  const { data, error } = useApi<{ total: number; items: Row[] }>(`/api/audit?page=${page}&per_page=50&q=${encodeURIComponent(query)}`);
  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  return (
    <div className="stack">
      <div>
        <h1>Audit</h1>
        <p className="lede">Every flag, review, consent, invitation, result and data export, newest first.</p>
      </div>
      <div className="row">
        <input placeholder="Filter by action, actor or subject" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 280 }} aria-label="Filter" />
        {data && <span className="muted small">{data.total.toLocaleString()} entries</span>}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="card table-wrap" style={{ padding: 8 }}>
        <table className="small">
          <thead>
            <tr>
              <th>Demo date</th>
              <th>Action</th>
              <th>Actor</th>
              <th>Subject</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((r) => (
              <tr key={r.id}>
                <td style={{ whiteSpace: "nowrap" }}>
                  {fmtDate(r.sim_date)}
                  <div className="muted">{r.logged_at.slice(11, 19)} UTC</div>
                </td>
                <td>{r.action}</td>
                <td>{r.actor}</td>
                <td>{r.person_id ? <a href={`#/patient/${r.person_id}`}>{r.subject}</a> : r.subject}</td>
                <td className="muted">{detail(r.detail)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
    </div>
  );
}
