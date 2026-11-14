import { useEffect, useState } from "react";
import { Brief, scorePct, useApi } from "../api";

type Item = Brief & {
  case_id: number;
  status: string;
  status_label: string;
  source: string;
  score: number | null;
  dlcn_total: number | null;
  dlcn_band: string | null;
  reasons: string[];
  new: boolean;
  group: string;
};
type Page = { total: number; page: number; per_page: number; items: Item[] };

const STATUSES: [string, string][] = [
  ["open", "Open"],
  ["", "All"],
  ["flagged", "Flagged"],
  ["in_review", "In review"],
  ["test_ordered", "Test ordered"],
  ["confirmed_genetic", "Confirmed (genetic)"],
  ["clinical_fh", "Clinical FH"],
  ["no_variant", "No variant found"],
  ["dismissed", "Dismissed"],
];

export default function Worklist() {
  const [status, setStatus] = useState("open");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => setQuery(q), 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => setPage(1), [status, query]);
  const { data, error } = useApi<Page>(`/api/worklist?status=${status}&q=${encodeURIComponent(query)}&page=${page}`);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  return (
    <div className="stack">
      <div>
        <h1>Worklist</h1>
        <p className="lede">
          People flagged from routine cholesterol results, highest score first. A clinician reviews every one before
          anything else happens.
        </p>
      </div>
      <div className="row">
        <input placeholder="Search by name or MRN" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 260 }} aria-label="Search" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
          {STATUSES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        {data && <span className="muted small">{data.total.toLocaleString()} cases</span>}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="card table-wrap" style={{ padding: 8 }}>
        <table>
          <thead>
            <tr>
              <th>Patient</th>
              <th className="num">Score</th>
              <th>DLCN</th>
              <th>Why flagged</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((r) => (
              <tr key={r.case_id} className="link" onClick={() => (window.location.hash = `#/patient/${r.id}`)}>
                <td>
                  <a href={`#/patient/${r.id}`}>{r.name}</a> {r.new && <span className="pill new">New result</span>}
                  <div className="small muted">
                    {r.age}, {r.sex === "M" ? "male" : "female"}, {r.group}. {r.mrn}
                    {r.source !== "detection" && ` Found ${r.source === "cascade" ? "through a relative" : "at Well-Child"}.`}
                  </div>
                </td>
                <td className="num">{r.score == null ? "" : scorePct(r.score)}</td>
                <td>
                  {r.dlcn_band ?? ""}
                  {r.dlcn_total != null && <span className="muted"> ({r.dlcn_total})</span>}
                </td>
                <td className="small">{r.reasons.slice(0, 2).join(". ")}</td>
                <td>
                  <span className={`pill ${r.status}`}>{r.status_label}</span>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No cases match.
                </td>
              </tr>
            )}
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
      <p className="synthetic">Scores come from a model trained and tested on synthetic data.</p>
    </div>
  );
}
