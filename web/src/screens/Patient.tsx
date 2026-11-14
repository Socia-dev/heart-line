import { ReactNode, useState } from "react";
import { Brief, changed, fmtDate, post, scorePct, useApi } from "../api";
import FamilyTree, { Legend, TreeNode } from "../components/FamilyTree";
import Fold from "../components/Fold";
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
    nationality_group: string;
    lang: string;
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

export default function Patient({ id }: { id: number }) {
  const { data, error } = useApi<Data>(`/api/patients/${id}`);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading</p>;
  const { person: p, score, case: c } = data;

  async function act(path: string, body?: unknown) {
    setBusy(true);
    setErr(null);
    try {
      await post(path, body);
      changed();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }
  const btn = (label: string, path: string, body?: unknown, primary = false) => (
    <button className={primary ? "primary" : ""} disabled={busy} onClick={() => act(path, body)}>
      {label}
    </button>
  );
  const reviewBtn = (label: string, action: string, primary = false) => btn(label, `/api/patients/${id}/review`, { action }, primary);

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{p.name}</h1>
          <p className="muted" style={{ margin: 0 }}>
            {p.deceased ? "Deceased" : `${p.age}`}, {p.sex === "M" ? "male" : "female"}, {p.nationality_group}. {p.mrn}
          </p>
        </div>
        {c && <span className={`pill ${c.status}`}>{c.status_label}</span>}
      </div>

      {c?.led_by && (
        <p className="notice" style={{ margin: 0 }}>
          Found through family testing, after <a href={`#/patient/${c.led_by.id}`}>{c.led_by.name}</a> was confirmed.
        </p>
      )}

      <div className="grid g2">
        <section className="next">
          <NextStep data={data} reviewBtn={reviewBtn} btn={btn} />
          {err && <p className="error" style={{ marginTop: 12 }}>{err}</p>}
        </section>

        <section className="card">
          {score ? (
            <>
              <div className="spread">
                <h2>Why flagged</h2>
                <span className="small muted">DLCN {score.dlcn_total}, {score.dlcn_band.toLowerCase()}</span>
              </div>
              <div className="row" style={{ alignItems: "baseline", gap: 10, margin: "4px 0 12px" }}>
                <span className="big-score">{scorePct(score.prob_b)}</span>
                <span className="muted">chance of FH, by the model</span>
              </div>
              {score.reasons.length > 0 ? (
                <ul className="reasons">
                  {score.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No strong signals in the record.</p>
              )}
              <p className="synthetic" style={{ marginTop: 12, marginBottom: 0 }}>
                Model trained on synthetic data.
              </p>
            </>
          ) : (
            <>
              <h2>Not scored</h2>
              <p className="muted" style={{ margin: 0 }}>
                No cholesterol results on record.
              </p>
            </>
          )}
        </section>
      </div>

      <section className="card">
        <div className="spread">
          <h2>Family</h2>
          <Legend />
        </div>
        <div style={{ marginTop: 12 }}>
          <FamilyTree nodes={data.family.nodes} abroad={data.family.relatives_abroad} onOpen={(pid) => (window.location.hash = `#/patient/${pid}`)} />
        </div>
      </section>

      <div>
        <Fold title="Cholesterol results" note={data.labs.length ? `${data.labs.length} on record` : "None on record"}>
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
                    <th>On a statin</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.labs].reverse().map((l, i) => (
                    <tr key={i}>
                      <td>{fmtDate(l.date)}</td>
                      <td className="num">{l.ldl.toFixed(1)}</td>
                      <td className="num">{l.tc.toFixed(1)}</td>
                      <td className="num">{l.hdl.toFixed(1)}</td>
                      <td className="num">{l.tg.toFixed(1)}</td>
                      <td>{l.on_statin ? "Yes" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="small muted">All values in mmol/L.</p>
            </div>
          )}
        </Fold>

        {score && (
          <Fold title="Score details" note={`DLCN ${score.dlcn_total}`}>
            <h3>Dutch Lipid Clinic Network score</h3>
            {score.dlcn_items.length ? (
              <table className="small">
                <tbody>
                  {score.dlcn_items.map((it) => (
                    <tr key={it.group}>
                      <td>{it.reason}</td>
                      <td className="num">{it.points} points</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">No points from the record.</p>
            )}
            <h3 style={{ marginTop: 16 }}>From the record</h3>
            <dl className="facts small">
              <dt>Statin</dt>
              <dd>{p.statin_start ? `${p.statin_intensity} intensity since ${fmtDate(p.statin_start)}` : "None"}</dd>
              <dt>Heart disease</dt>
              <dd>{p.cad_age ? `At age ${Math.round(p.cad_age)}${p.early_cad ? ", early" : ""}` : "None"}</dd>
              <dt>Examination</dt>
              <dd>{[p.xanthoma && "Tendon xanthomas", p.arcus && "Corneal arcus"].filter(Boolean).join(", ") || "Nothing noted"}</dd>
              <dt>Family history</dt>
              <dd>
                {[p.fhx_recorded_cad && "Early heart disease", p.fhx_recorded_ldl && "High cholesterol"].filter(Boolean).join(", ") || "Nothing written in the chart"}
              </dd>
            </dl>
            <p className="synthetic" style={{ marginTop: 12 }}>
              {score.live ? "Scored live by the final model." : "Cross-validated score."} The model also uses relatives' records. DLCN uses only family
              history written in the chart.
            </p>
          </Fold>
        )}

        <Fold title="History" note={`${data.history.length} entries`}>
          {data.history.length ? (
            <table className="small">
              <tbody>
                {data.history.map((h) => (
                  <tr key={h.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDate(h.sim_date)}</td>
                    <td>{h.action}</td>
                    <td className="muted">{h.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">Nothing recorded yet.</p>
          )}
          <p className="small" style={{ marginTop: 12 }}>
            <a href={`/api/fhir/Patient/${p.id}`} target="_blank" rel="noreferrer">
              Export this record as FHIR R4
            </a>
          </p>
        </Fold>
      </div>
    </div>
  );
}


type Btn = (label: string, path: string, body?: unknown, primary?: boolean) => ReactNode;

// One clear next step for the clinician, based on where the case is.
function NextStep({ data, reviewBtn, btn }: { data: Data; reviewBtn: (l: string, a: string, primary?: boolean) => ReactNode; btn: Btn }) {
  const c = data.case;
  const a = data.actions;
  const pid = data.person.id;

  if (!c) {
    const inv = data.invitation;
    const wc = data.wellchild;
    const text = inv
      ? {
          sent: `Invited to a cholesterol check on ${fmtDate(inv.sent_at)}. Not booked yet.`,
          booked: `Check booked${inv.slot ? ` for ${inv.slot.split(" | ")[0]}` : ""}.`,
          negative: "Tested clear. No further action.",
          positive: "Tested positive.",
          no_response: "Did not respond to the invitation.",
        }[inv.status]
      : wc
        ? wc.status === "due"
          ? `Cholesterol test due at the Well-Child Visit on ${fmtDate(wc.due_date)}.`
          : `Tested at Well-Child: ${wc.status === "tested_negative" ? "clear" : "positive"}.`
        : "Not flagged. No action needed.";
    return (
      <>
        <h2>Status</h2>
        <p style={{ margin: 0 }}>{text}</p>
      </>
    );
  }

  if (a.includes("order_test")) {
    return (
      <>
        <h2>Review this flag</h2>
        <p className="muted">If the reasons fit, order a genetic test. It takes about two weeks.</p>
        <div className="row">
          {reviewBtn("Order genetic test", "order_test", true)}
          {reviewBtn("Dismiss", "dismiss")}
        </div>
      </>
    );
  }
  if (c.status === "test_ordered") {
    return (
      <>
        <h2>Waiting for the genetic test</h2>
        <p className="muted" style={{ margin: 0 }}>
          Result due {fmtDate(c.test_due)}. Use Advance two weeks to get it.
        </p>
      </>
    );
  }
  if (c.status === "no_variant") {
    return (
      <>
        <h2>No variant found</h2>
        <p className="muted">
          {a.includes("mark_clinical") ? "The DLCN score is 6 or more, so this can still be recorded as clinical FH." : "The DLCN score is below 6."}
        </p>
        <div className="row">
          {a.includes("mark_clinical") && reviewBtn("Record as clinical FH", "mark_clinical", true)}
          {reviewBtn("Dismiss", "dismiss")}
        </div>
      </>
    );
  }
  if (c.status === "dismissed") {
    return (
      <>
        <h2>Dismissed</h2>
        <p className="muted" style={{ margin: 0 }}>No further action.</p>
      </>
    );
  }

  const found = c.found_variant ? `Confirmed: ${c.found_variant}.` : "Confirmed as clinical FH.";
  if (a.includes("consent")) {
    return (
      <>
        <h2>Ask about family testing</h2>
        <p className="muted">{found}</p>
        <p>
          "May we invite your parents, brothers, sisters and adult children to a free cholesterol check? The invitation won't mention you or your
          diagnosis."
        </p>
        <div className="row">
          {btn("Patient agrees", `/api/patients/${pid}/consent`, { consent: true }, true)}
          {btn("Patient declines", `/api/patients/${pid}/consent`, { consent: false })}
        </div>
      </>
    );
  }
  if (c.consent === 0) {
    return (
      <>
        <h2>Family testing declined</h2>
        <p className="muted" style={{ margin: 0 }}>
          {found} The patient declined on {fmtDate(c.consent_at)}. Nobody has been contacted.
        </p>
      </>
    );
  }
  if (a.includes("start_cascade")) {
    return (
      <>
        <h2>Start family testing</h2>
        <p className="muted">
          {found} The patient agreed. Adults get a private invitation and children are flagged for their Well-Child Visit.
        </p>
        <div className="row">{btn("Start family testing", `/api/cases/${c.id}/cascade`, undefined, true)}</div>
      </>
    );
  }
  if (c.cascade_at) {
    const inv = c.invitations;
    const invited = Object.values(inv).reduce((x, y) => x + y, 0);
    const tested = (inv.positive ?? 0) + (inv.negative ?? 0);
    return (
      <>
        <h2>Family testing under way</h2>
        <p className="muted">{found}</p>
        <div className="grid" style={{ marginTop: 8, gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
          <div className="stat">
            <div className="n">{invited}</div>
            <div className="l">relatives invited</div>
          </div>
          <div className="stat">
            <div className="n">{tested}</div>
            <div className="l">tested so far</div>
          </div>
          <div className="stat">
            <div className="n" style={{ color: "var(--brand)" }}>
              {c.led_to.length}
            </div>
            <div className="l">found with FH</div>
          </div>
        </div>
        {c.wellchild > 0 && <p className="small muted" style={{ marginTop: 12, marginBottom: 0 }}>{c.wellchild} children flagged for Well-Child.</p>}
      </>
    );
  }
  return (
    <>
      <h2>Confirmed</h2>
      <p className="muted" style={{ margin: 0 }}>
        {found} {c.source === "wellchild" ? "The family decides about further testing." : ""}
      </p>
    </>
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
