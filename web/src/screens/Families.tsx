import { Brief, fmtDate, useApi } from "../api";
import { Empty, LoadError, Loading } from "../components/State";

type Inv = { id: number; token: string; status: string; lang: string; sent_at: string; slot: string | null; relative: Brief; via: Brief; message: string };
type Family = Brief & {
  case_id: number;
  index_of: number | null;
  family_root: number;
  source: string;
  status_label: string;
  status: string;
  consent: number | null;
  cascade_at: string | null;
  invited: number;
  invitations: Record<string, number>;
  wellchild: number;
};
type Data = { invitations: Inv[]; families: Family[]; abroad: number };

const INV: Record<string, string> = {
  sent: "Waiting for a reply",
  booked: "Booked",
  positive: "Tested positive",
  negative: "Tested clear",
  no_response: "No reply",
  declined: "Declined",
  already_tested: "Already tested",
  call_requested: "Asked for a call",
};

// The coordinator's view of every invitation and how each family led to the next.
export default function Families() {
  const { data, error, reload } = useApi<Data>("/api/invitations");
  if (error) return <LoadError error={error} retry={reload} />;
  if (!data) return <Loading />;
  const roots = data.families.filter((c) => c.index_of == null || !data.families.some((x) => x.case_id === c.index_of));

  return (
    <div className="stack">
      <div>
        <h1>Invitations</h1>
        <p className="lede">Every message sent, what came back, and how one family led to the next.</p>
      </div>

      <section className="card">
        <h2>How each patient led to the next</h2>
        {roots.length ? (
          <ul className="chain">
            {roots.map((r) => (
              <ChainNode key={r.case_id} c={r} all={data.families} />
            ))}
          </ul>
        ) : (
          <Empty title="No families yet">Family testing starts once a clinician records a patient's consent. It then appears under To start on your home page.</Empty>
        )}
      </section>

      <section className="card">
        <div className="spread">
          <h2>Messages sent</h2>
          {data.abroad > 0 && <span className="muted small">Family letters cover {data.abroad} relatives abroad.</span>}
        </div>
        {data.invitations.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>To</th>
                  <th>Message, by SMS (mock)</th>
                  <th>Reply</th>
                  <th>Family of</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.invitations.map((i) => (
                  <tr key={i.id}>
                    <td>
                      <a href={`#/patient/${i.relative.id}`}>{i.relative.name}</a>
                      <div className="small muted">{fmtDate(i.sent_at)}</div>
                    </td>
                    <td className="small" dir={i.lang === "ar" ? "rtl" : "ltr"} lang={i.lang} style={{ maxWidth: 340 }}>
                      {i.message}
                    </td>
                    <td>
                      <span className={`pill ${i.status}`}>{INV[i.status]}</span>
                      {i.slot && <div className="small muted">{i.slot.replace(" | ", ", ")}</div>}
                    </td>
                    <td>
                      <a href={`#/patient/${i.via.id}`}>{i.via.name}</a>
                    </td>
                    <td>
                      <a href={`#/invite/${i.token}`}>See their page</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="No messages yet">Each invitation appears here with its exact wording once it is sent.</Empty>
        )}
      </section>
    </div>
  );
}

function ChainNode({ c, all }: { c: Family; all: Family[] }) {
  const kids = all.filter((x) => x.index_of === c.case_id);
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
            ? `Family testing from ${fmtDate(c.cascade_at)}: ${c.invited} invited, ${c.wellchild} children flagged, ${kids.length} found with FH.`
            : c.source === "wellchild"
              ? "Child. The family is already in the programme."
              : c.consent === 0
                ? "Declined contact with relatives."
                : c.consent === 1
                  ? "Patient agreed. Invitations not sent yet."
                  : "Waiting for their clinician to ask about their own family."}
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
