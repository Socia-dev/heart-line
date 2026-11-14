import { useState } from "react";
import { Brief, changed, fmtDate, post, scorePct, useApi } from "../api";
import FamilyTree, { Legend, TreeNode } from "../components/FamilyTree";
import LabChart from "../components/LabChart";

type Case = {
  id: number;
  status: string;
  status_label: string;
  source: string;
  created_at: string;
  test_due: string | null;
  found_variant: string | null;
  consent: number | null;
  consent_by: string | null;
  consent_at: string | null;
  cascade_at: string | null;
  led_by?: Brief & { case_id: number };
  led_to: (Brief & { case_id: number; status: string })[];
  invitations: Record<string, number>;
  wellchild: number;
  letter_abroad: number;
};
type Data = {
  person: Brief & {
    birth_date: string;
    nationality_group: string;
    lang: string;
    relatives_abroad: number;
    statin_start: string | null;
    statin_intensity: string | null;
    cad_age: number | null;
    early_cad: boolean;
    xanthoma: boolean;
    arcus: boolean;
    fhx_recorded_cad: boolean;
    fhx_recorded_ldl: boolean;
  };
  labs: { date: string; ldl: number; tc: number; hdl: number; tg: number; on_statin: boolean; new: boolean }[];
  score: null | {
    prob_b: number;
    flagged: boolean;
    dlcn_total: number;
    dlcn_band: string;
    dlcn_items: { group: string; reason: string; points: number }[];
    reasons: string[];
    live: boolean;
  };
  case: Case | null;
  actions: string[];
  invitation: { status: string; sent_at: string; slot: string | null } | null;
  wellchild: { status: string; due_date: string } | null;
  family: { nodes: TreeNode[]; relatives_abroad: number };
  history: { id: number; sim_date: string; actor: string; action: string; detail: string | null }[];
  today: string;
};

const INV_LABEL: Record<string, string> = {
  sent: "Invitation sent",
  booked: "Check booked",
  positive: "Tested positive",
  negative: "Tested negative",
  no_response: "No response",
};

const INV_PROGRESS: Record<string, string> = {
  positive: "tested positive",
  negative: "tested negative",
  booked: "booked",
  sent: "not yet booked",
  no_response: "did not respond",
};

export default function Patient({ id }: { id: number }) {
  const { data, error } = useApi<Data>(`/api/patients/${id}`);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [cascadeResult, setCascadeResult] = useState<Record<string, number> | null>(null);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading</p>;
  const { person: p, score, case: c } = data;

  async function act(path: string, body?: unknown, then?: (x: Record<string, number>) => void) {
    setBusy(true);
    setErr(null);
    try {
      const r = await post<Record<string, number>>(path, body);
      then?.(r);
      setNote("");
      changed();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }
  const review = (action: string) => act(`/api/patients/${id}/review`, { action, note: note || null });

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{p.name}</h1>
          <p className="muted">
            {p.deceased ? "Deceased" : `${p.age} years`}, {p.sex === "M" ? "male" : "female"}, {p.nationality_group}. {p.mrn}. Prefers{" "}
            {p.lang === "ar" ? "Arabic" : "English"}.
          </p>
        </div>
        <div className="row">
          {c && <span className={`pill ${c.status}`}>{c.status_label}</span>}
          <a className="btn" href={`/api/fhir/Patient/${p.id}`} target="_blank" rel="noreferrer">
            FHIR R4 export
          </a>
        </div>
      </div>

      {c?.led_by && (
        <div className="notice">
          Found through family testing after <a href={`#/patient/${c.led_by.id}`}>{c.led_by.name}</a> was confirmed.
        </div>
      )}
      {data.invitation && !c && (
        <div className="quiet">
          {INV_LABEL[data.invitation.status]}. Invited {fmtDate(data.invitation.sent_at)}
          {data.invitation.slot && `, booked for ${data.invitation.slot.replace(" | ", " at ")}`}.
        </div>
      )}
      {data.wellchild && (
        <div className="quiet">
          Flagged for a Well-Child Visit, due {fmtDate(data.wellchild.due_date)}. Status: {data.wellchild.status.replace("_", " ")}.
        </div>
      )}

      <div className="grid g2">
        <section className="card">
          <h2>Cholesterol results</h2>
          <LabChart labs={data.labs} statinStart={p.statin_start} today={data.today} />
          {data.labs.length > 0 && (
            <div className="table-wrap">
              <table className="small">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th className="num">LDL</th>
                    <th className="num">Total</th>
                    <th className="num">HDL</th>
                    <th className="num">TG</th>
                    <th>Statin</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.labs].reverse().map((l, i) => (
                    <tr key={i}>
                      <td>
                        {fmtDate(l.date)} {l.new && <span className="pill new">New</span>}
                      </td>
                      <td className="num">{l.ldl.toFixed(1)}</td>
                      <td className="num">{l.tc.toFixed(1)}</td>
                      <td className="num">{l.hdl.toFixed(1)}</td>
                      <td className="num">{l.tg.toFixed(1)}</td>
                      <td>{l.on_statin ? "Yes" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="small muted">mmol/L</p>
            </div>
          )}
        </section>

        <section className="card">
          <h2>Why this person was flagged</h2>
          {score ? (
            <>
              <div className="row" style={{ alignItems: "baseline" }}>
                <div className="stat">
                  <div className="n">{scorePct(score.prob_b)}</div>
                  <div className="l">family-linked model score</div>
                </div>
                <div className="stat">
                  <div className="n">{score.dlcn_total}</div>
                  <div className="l">DLCN, {score.dlcn_band.toLowerCase()}</div>
                </div>
              </div>
              {score.reasons.length > 0 ? (
                <ul className="reasons" style={{ margin: "12px 0" }}>
                  {score.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No strong signals in the record.</p>
              )}
              <h3>Dutch Lipid Clinic Network score</h3>
              {score.dlcn_items.length ? (
                <table className="small">
                  <tbody>
                    {score.dlcn_items.map((it) => (
                      <tr key={it.group}>
                        <td>{it.reason}</td>
                        <td className="num">{it.points}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No DLCN points from the record.</p>
              )}
              <p className="synthetic">
                {score.live ? "Scored live by the final model." : "Out-of-fold score."} Model trained and tested on synthetic data.
                DLCN uses only family history written in the chart.
              </p>
            </>
          ) : (
            <p className="muted">No lipid results, so this person has not been scored.</p>
          )}
          <h3 style={{ marginTop: 16 }}>From the record</h3>
          <dl className="facts small">
            <dt>Statin</dt>
            <dd>{p.statin_start ? `${p.statin_intensity} intensity since ${fmtDate(p.statin_start)}` : "None recorded"}</dd>
            <dt>Heart disease</dt>
            <dd>{p.cad_age ? `At age ${Math.round(p.cad_age)}${p.early_cad ? ", early" : ""}` : "None recorded"}</dd>
            <dt>Examination</dt>
            <dd>{[p.xanthoma && "Tendon xanthomas", p.arcus && "Corneal arcus"].filter(Boolean).join(", ") || "Nothing recorded"}</dd>
            <dt>Family history</dt>
            <dd>
              {[p.fhx_recorded_cad && "Early heart disease", p.fhx_recorded_ldl && "High cholesterol"].filter(Boolean).join(", ") ||
                "Nothing recorded"}
            </dd>
          </dl>
        </section>
      </div>

      {c && (
        <section className="card">
          <h2>Case</h2>
          <p className="muted">
            {c.source === "detection" ? "Flagged by screening" : c.source === "cascade" ? "Found through a relative" : "Found at a Well-Child Visit"} on{" "}
            {fmtDate(c.created_at)}.
            {c.status === "test_ordered" && c.test_due && ` Genetic test result due ${fmtDate(c.test_due)}.`}
            {c.found_variant && ` Variant found: ${c.found_variant}.`}
            {c.status === "clinical_fh" && !c.found_variant && " Clinical diagnosis, no known family variant."}
          </p>
          {err && <p className="error">{err}</p>}

          {data.actions.some((a) => ["start_review", "order_test", "dismiss", "mark_clinical"].includes(a)) && (
            <div className="stack">
              <textarea placeholder="Note for the record (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
              <div className="row">
                {data.actions.includes("start_review") && (
                  <button disabled={busy} onClick={() => review("start_review")}>
                    Start review
                  </button>
                )}
                {data.actions.includes("order_test") && (
                  <button className="primary" disabled={busy} onClick={() => review("order_test")}>
                    Order genetic test
                  </button>
                )}
                {data.actions.includes("mark_clinical") && (
                  <button className="primary" disabled={busy} onClick={() => review("mark_clinical")}>
                    Record as clinical FH
                  </button>
                )}
                {data.actions.includes("dismiss") && (
                  <button disabled={busy} onClick={() => review("dismiss")}>
                    Dismiss
                  </button>
                )}
              </div>
              {c.status === "test_ordered" && <p className="muted small">Use Advance two weeks on the overview to get the result.</p>}
            </div>
          )}

          {data.actions.includes("consent") && (
            <div className="notice">
              <h3>Ask the patient before anyone is contacted</h3>
              <p>
                May we send your parents, brothers, sisters and adult children a private invitation to a free cholesterol check?
                It will not mention you or your diagnosis. Children under 18 will be checked at their next Well-Child Visit.
              </p>
              <div className="row">
                <button className="primary" disabled={busy} onClick={() => act(`/api/patients/${id}/consent`, { consent: true })}>
                  Patient agrees
                </button>
                <button disabled={busy} onClick={() => act(`/api/patients/${id}/consent`, { consent: false })}>
                  Patient declines
                </button>
              </div>
            </div>
          )}
          {c.consent === 0 && <p className="muted">The patient declined contact with relatives on {fmtDate(c.consent_at)}. Nobody has been contacted.</p>}
          {c.consent === 1 && (
            <p className="muted">
              Consent recorded on {fmtDate(c.consent_at)} by {c.consent_by?.replace(/^Patient \(recorded by (.*)\)$/, "$1")}.
            </p>
          )}
          {data.actions.includes("start_cascade") && (
            <div className="row">
              <button className="primary" disabled={busy} onClick={() => act(`/api/cases/${c.id}/cascade`, undefined, setCascadeResult)}>
                Start family testing
              </button>
              <span className="muted small">Sends private invitations and flags children for Well-Child.</span>
            </div>
          )}
          {cascadeResult && (
            <p className="notice">
              {cascadeResult.invited} relatives invited, {cascadeResult.wellchild} children flagged for Well-Child
              {cascadeResult.abroad ? `, family letter prepared for ${cascadeResult.abroad} relatives abroad` : ""}.
            </p>
          )}
          {c.cascade_at && (
            <p>
              Family testing started {fmtDate(c.cascade_at)}:{" "}
              {Object.values(c.invitations).reduce((a, b) => a + b, 0)} relatives invited, {c.wellchild} children flagged for Well-Child
              {c.letter_abroad ? `, ${c.letter_abroad} relatives abroad reached by family letter` : ""}.{" "}
              <span className="muted">
                {Object.entries(INV_PROGRESS)
                  .filter(([k]) => c.invitations[k])
                  .map(([k, l]) => `${c.invitations[k]} ${l}`)
                  .join(", ")}
                .
              </span>
            </p>
          )}
          {c.led_to.length > 0 && (
            <p>
              Led to:{" "}
              {c.led_to.map((x, i) => (
                <span key={x.case_id}>
                  {i > 0 && ", "}
                  <a href={`#/patient/${x.id}`}>{x.name}</a>
                </span>
              ))}
              .
            </p>
          )}
        </section>
      )}

      <section className="card">
        <div className="spread">
          <h2>Family</h2>
          <Legend />
        </div>
        <p className="muted small" style={{ marginTop: 8 }}>
          Parents, brothers, sisters and children are invited. Nieces and nephews are shown when their parent is confirmed. Select anyone
          to open their record.
        </p>
        <FamilyTree nodes={data.family.nodes} abroad={data.family.relatives_abroad} onOpen={(pid) => (window.location.hash = `#/patient/${pid}`)} />
      </section>

      <section className="card">
        <h2>History</h2>
        {data.history.length ? (
          <table className="small">
            <tbody>
              {data.history.map((h) => (
                <tr key={h.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{fmtDate(h.sim_date)}</td>
                  <td>{h.action}</td>
                  <td className="muted">{h.actor}</td>
                  <td className="muted">{detail(h.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Nothing recorded yet.</p>
        )}
      </section>
    </div>
  );
}

export function detail(d: string | null) {
  if (!d) return "";
  try {
    const o = JSON.parse(d);
    if (typeof o !== "object" || o === null) return String(o);
    return Object.entries(o)
      .filter(([, v]) => v !== null && v !== "")
      .map(([k, v]) => `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.join("; ") : typeof v === "number" ? Math.round(v * 1000) / 1000 : v}`)
      .join(", ");
  } catch {
    return d;
  }
}
