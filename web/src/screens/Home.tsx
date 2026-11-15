import { useEffect, useState } from "react";
import { Brief, go, useApi, useRole } from "../api";
import { Empty, LoadError, Loading } from "../components/State";

type Item = Brief & { status: string; status_label: string; why: string; open: number; band: string | null; new: boolean };
type Queue = {
  role: string;
  tab: string;
  tabs: { id: string; label: string; count: number }[];
  total: number;
  page: number;
  per_page: number;
  items: Item[];
  empty: string;
};

const INTRO = {
  clinician: ["My patients", "Flags to review and results to act on. Every flag is a suggestion; you decide."],
  coordinator: ["My families", "Families whose patient has agreed to testing. You contact the relatives and follow up."],
};

// The role's home: a queue of work. Each tab is a count; each row says why it is there.
export default function Home() {
  const role = useRole() as "clinician" | "coordinator";
  const [tab, setTab] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => setQuery(q), 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => setPage(1), [tab, query]);
  const { data, error, reload } = useApi<Queue>(`/api/queue?tab=${tab}&q=${encodeURIComponent(query)}&page=${page}`);
  const [title, lede] = INTRO[role] ?? INTRO.clinician;

  if (error) return <LoadError error={error} retry={reload} />;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;
  return (
    <div className="stack">
      <div>
        <h1>{title}</h1>
        <p className="lede">{lede}</p>
      </div>
      {!data ? (
        <Loading rows={6} />
      ) : (
        <>
          <div className="spread" style={{ alignItems: "center" }}>
            <div className="tabs" role="tablist">
              {data.tabs.map((t) => (
                <button key={t.id} role="tab" aria-selected={data.tab === t.id} className={data.tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
                  {t.label} <span className="count">{t.count.toLocaleString()}</span>
                </button>
              ))}
            </div>
            <input placeholder="Search by name or MRN" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 220 }} aria-label="Search" />
          </div>
          <div className="card table-wrap" style={{ padding: 8 }}>
            {data.items.length === 0 ? (
              <Empty title={query ? `Nobody matches "${query}"` : "Nothing here"}>{query ? "Check the spelling, or search by MRN." : data.empty}</Empty>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>{data.tab === "phone" ? "Relative" : "Patient"}</th>
                    <th>Why it is here</th>
                    {role === "clinician" && <th>Model says</th>}
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={`${r.id}-${r.status}`} className="link" onClick={() => go(`#/patient/${r.open}`)}>
                      <td>
                        <a href={`#/patient/${r.open}`}>{r.name}</a> {r.new && <span className="pill new">New result</span>}
                        <div className="small muted">
                          {r.age}, {r.sex === "M" ? "male" : "female"}
                        </div>
                      </td>
                      <td className="small">{r.why}</td>
                      {role === "clinician" && <td>{r.band && <span className={`band ${r.band.replace(" ", "-").toLowerCase()}`}>{r.band}</span>}</td>}
                      <td>
                        <span className={`pill ${r.status}`}>{r.status_label}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
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
        </>
      )}
    </div>
  );
}
