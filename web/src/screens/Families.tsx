import { Brief, fmtDate, useApi } from "../api";

type Inv = {
  id: number;
  token: string;
  status: string;
  lang: string;
  sent_at: string;
  slot: string | null;
  tested_at: string | null;
  relative: Brief;
  via: Brief & { case_id: number };
};
type ChainCase = Brief & {
  case_id: number;
  index_of: number | null;
  source: string;
  status: string;
  status_label: string;
  consent: number | null;
  cascade_at: string | null;
  created_at: string;
  invited: number;
  invitations: Record<string, number>;
  wellchild: number;
};
type Data = { invitations: Inv[]; chain: ChainCase[]; letters: { relatives_abroad: number }[] };

const INV: Record<string, string> = {
  sent: "Sent",
  booked: "Booked",
  positive: "Positive",
  negative: "Negative",
  no_response: "No response",
};

export default function Families() {
  const { data, error } = useApi<Data>("/api/invitations");
  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading</p>;
  const counts = data.invitations.reduce<Record<string, number>>((a, i) => ({ ...a, [i.status]: (a[i.status] ?? 0) + 1 }), {});
  const abroad = data.letters.reduce((a, l) => a + l.relatives_abroad, 0);
  const roots = data.chain.filter((c) => c.index_of == null || !data.chain.some((x) => x.case_id === c.index_of));

  return (
    <div className="stack">
      <div>
        <h1>Families</h1>
        <p className="lede">Every confirmed case who consents starts family testing. Each relative who tests positive starts it again for their own family.</p>
      </div>

      <section className="card">
        <h2>How each case led to the next</h2>
        {roots.length ? (
          <ul className="chain">
            {roots.map((r) => (
              <ChainNode key={r.case_id} c={r} all={data.chain} />
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing yet. Family testing starts from a confirmed patient's page.</p>
        )}
      </section>

      <section className="card">
        <div className="spread">
          <h2>Invitations</h2>
          <span className="muted small">
            {data.invitations.length} invitations
            {Object.entries(counts).map(([k, v]) => `, ${v} ${INV[k].toLowerCase()}`)}
            {abroad ? `. Family letters cover ${abroad} relatives abroad.` : ""}
          </span>
        </div>
        <p className="muted small">Sent by mock SMS. The invitation never says who it came from or why.</p>
        {data.invitations.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Relative</th>
                  <th>Status</th>
                  <th>From the family of</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.invitations.map((i) => (
                  <tr key={i.id}>
                    <td>
                      <a href={`#/patient/${i.relative.id}`}>{i.relative.name}</a>
                      <div className="small muted">{i.relative.age}</div>
                    </td>
                    <td>
                      <span className={`pill ${i.status}`}>{INV[i.status]}</span>

                    </td>
                    <td>
                      <a href={`#/patient/${i.via.id}`}>{i.via.name}</a>
                    </td>
                    <td>
                      <a href={`#/invite/${i.token}`}>Preview invitation</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No invitations yet.</p>
        )}
      </section>
    </div>
  );
}

function ChainNode({ c, all }: { c: ChainCase; all: ChainCase[] }) {
  const kids = all.filter((x) => x.index_of === c.case_id);
  const positives = (c.invitations.positive ?? 0) + kids.filter((k) => k.source === "wellchild").length;
  return (
    <li>
      <div className="chain-item">
        <div className="spread">
          <span>
            <a href={`#/patient/${c.id}`}>
              <strong>{c.name}</strong>
            </a>{" "}
            <span className="muted">
              {c.age}, {c.source === "detection" ? "found by screening" : c.source === "cascade" ? "found through a relative" : "found at Well-Child"}
            </span>
          </span>
          <span className={`pill ${c.status}`}>{c.status_label}</span>
        </div>
        <div className="small muted">
          {c.cascade_at
            ? `Family testing from ${fmtDate(c.cascade_at)}: ${c.invited} invited, ${c.wellchild} children flagged, ${positives} found positive.`
            : c.consent === 0
              ? "Declined contact with relatives."
              : c.source === "wellchild"
                ? "Child. Family decides about further testing."
                : "Waiting for consent."}
        </div>
      </div>
      {kids.length > 0 && (
        <ul className="chain">
          {kids.map((k) => (
            <ChainNode key={k.case_id} c={k} all={all} />
          ))}
        </ul>
      )}
    </li>
  );
}
