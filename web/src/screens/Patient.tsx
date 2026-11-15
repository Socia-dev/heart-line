import { useEffect, useState } from "react";
import { ApiError, Brief, Role, changed, fmtDate, go, pct, post, useApi } from "../api";
import FamilyTree, { Legend, TreeNode } from "../components/FamilyTree";
import Fold from "../components/Fold";
import LabChart from "../components/LabChart";
import { ActionError, LoadError, Loading } from "../components/State";
import { CountUp } from "../motion";

type Reason = { text: string; direction: "for" | "against"; weight: number };
type Action = { id: string; label: string; primary: boolean; needs: string[] };
type PlanRow = { id: number; name: string; given: string; relation: string; age: number; lang: string; outcome: "invite" | "wellchild" | "none"; why?: string; message: string | null };
type Next = {
  key: string;
  title: string;
  detail: string;
  waiting_on: string | null;
  just_done?: string | null;
  actions: Action[];
  dismiss_reasons: Record<string, string>;
  plan?: { relatives: PlanRow[]; abroad: number; invite: number; wellchild: number };
};
type Case = {
  id: number;
  status: string;
  status_label: string;
  source: string;
  consent: number | null;
  consent_at: string | null;
  consent_excluded: number[];
  through_family: boolean;
  led_by?: Brief;
  progress: { invited: number; replied: number; wellchild: number; letter_abroad: number; tested?: number; found?: number };
};
type Data = {
  role: Role;
  person: Brief & {
    nationality_group: string;
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
    band: string;
    band_rate: number | null;
    flagged: boolean;
    raw: number;
    calibrated: number;
    dlcn_total: number;
    dlcn_band: string;
    dlcn_linked_total: number;
    dlcn_items: { group: string; reason: string; points: number }[];
    reasons: Reason[];
    live: boolean;
    model_version: string;
  };
  case: Case | null;
  next: Next | null;
  contact: { kind: "invitation" | "wellchild"; status: string; sent_at?: string; due_date?: string } | null;
  family: { nodes: TreeNode[]; relatives_abroad: number; results_visible: boolean };
  timeline: { id: number; date: string; actor: string; action: string; decision: boolean; detail: Record<string, unknown> | null }[];
  today: string;
};

const WAITING: Record<string, string> = { lab: "the genetics lab", clinician: "the clinician", coordinator: "the family coordinator" };
const CONTACT: Record<string, string> = {
  sent: "Invited to a cholesterol check. No reply yet.",
  replied: "Invited to a cholesterol check, and has replied.",
  booked: "Has booked a cholesterol check.",
  negative: "Tested clear. Nothing further.",
  positive: "Tested positive.",
  declined: "Declined the invitation. They will not be contacted again.",
  already_tested: "Says they have already been tested.",
  call_requested: "Asked for a phone call.",
  no_response: "Has not replied to the invitation.",
  due: "Cholesterol test due at the next Well-Child Visit.",
  tested_negative: "Tested clear at Well-Child.",
  tested_positive: "Tested positive at Well-Child.",
};

export default function Patient({ id }: { id: number }) {
  const { data, error, reload } = useApi<Data>(`/api/patients/${id}`);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [decisionsOnly, setDecisionsOnly] = useState(false);
  useEffect(() => setErr(null), [id]);

  if (error) return <LoadError error={error} retry={reload} />;
  if (!data) return <Loading rows={6} />;
  const { person: p, score, case: c, next } = data;

  async function act(action: string, inputs: Record<string, unknown> = {}) {
    setBusy(action);
    setErr(null);
    try {
      await post(`/api/patients/${id}/act`, { action, ...inputs });
      changed();
    } catch (e) {
      setErr(e as ApiError);
    } finally {
      setBusy(null);
    }
  }
  const timeline = decisionsOnly ? data.timeline.filter((t) => t.decision) : data.timeline;
  const forReasons = score?.reasons.filter((r) => r.direction === "for") ?? [];
  const against = score?.reasons.filter((r) => r.direction === "against") ?? [];
  const top = Math.max(0.001, ...against.map((r) => r.weight));

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

      {c?.through_family && (
        <p className="notice" style={{ margin: 0 }}>
          Found through family testing
          {c.led_by ? (
            <>
              , in the family of <a href={`#/patient/${c.led_by.id}`}>{c.led_by.name}</a>.
            </>
          ) : (
            ". Which relative led here is not shown to the clinician."
          )}
        </p>
      )}

      <div className={next?.plan ? "stack" : "grid g2"}>
        <section className="next step-in" key={next?.key ?? "none"}>
          {next?.just_done && (
            <p className="done-note pop" role="status">
              {next.just_done}
            </p>
          )}
          {next && c ? (
            <NextStep next={next} c={c} role={data.role} nodes={data.family.nodes} act={act} busy={busy} />
          ) : (
            <>
              <h2>Status</h2>
              <p style={{ margin: 0 }}>{data.contact ? CONTACT[data.contact.status] : "Not flagged. No action needed."}</p>
            </>
          )}
          {err && <ActionError error={err} />}
        </section>

        {score ? (
          <section className="card rise" style={{ "--d": "80ms" } as React.CSSProperties}>
            <h2>Why flagged</h2>
            <div className={`band big ${score.band.replace(" ", "-").toLowerCase()}`}>{score.band} FH</div>
            {forReasons.length > 0 ? (
              <ul className="reasons">
                {forReasons.map((r, i) => (
                  <li key={r.text} className="rise" style={{ "--d": `${200 + i * 90}ms` } as React.CSSProperties}>
                    {r.text}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No strong signals in the record.</p>
            )}
            {score.flagged && score.band_rate != null && (
              <p className="small muted" style={{ margin: "12px 0 0" }}>
                About {Math.round(score.band_rate * 10)} in 10 people with this rating had FH, in synthetic data. A suggestion, not a diagnosis.
              </p>
            )}
          </section>
        ) : (
          <section className="card">
            <h2>Not scored</h2>
            <p className="muted" style={{ margin: 0 }}>
              No cholesterol results on record, so the model has nothing to go on.
            </p>
          </section>
        )}
      </div>

      <section className="card">
        <div className="spread">
          <h2>Family</h2>
          <Legend nodes={data.family.nodes} />
        </div>
        {!data.family.results_visible && (
          <p className="small muted" style={{ marginTop: 6 }}>
            You can see who has been contacted and who has replied. Each adult relative's result stays with them and the family coordinator.
          </p>
        )}
        <div style={{ marginTop: 12 }}>
          <FamilyTree nodes={data.family.nodes} abroad={data.family.relatives_abroad} onOpen={(pid) => go(`#/patient/${pid}`)} />
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
          <Fold title="Score details" note={`DLCN ${score.dlcn_total}, and what points away`}>
            {against.length > 0 && (
              <>
                <h3>Points away from FH</h3>
                <Reasons items={against} top={top} against />
              </>
            )}
            <h3 style={{ marginTop: against.length ? 16 : 0 }}>
              Dutch Lipid Clinic Network score: {score.dlcn_total}, {score.dlcn_band.toLowerCase()}
            </h3>
            <p className="small muted">
              The standard clinical score, from what is written in this chart.
              {score.dlcn_linked_total > score.dlcn_total && ` It would be ${score.dlcn_linked_total} if relatives' records counted as family history.`}
            </p>
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
            <h3 style={{ marginTop: 16 }}>Model</h3>
            <dl className="facts small">
              <dt>Calibrated estimate</dt>
              <dd>{pct(score.calibrated)} (raw model output {score.raw.toFixed(3)})</dd>
              <dt>Version</dt>
              <dd>
                {score.model_version}, {score.live ? "scored when the result arrived" : "cross-validated"}. Trained on synthetic data.{" "}
                <a href="#/model">How well does it work?</a>
              </dd>
            </dl>
            <h3 style={{ marginTop: 16 }}>From the record</h3>
            <dl className="facts small">
              <dt>Statin</dt>
              <dd>{p.statin_start ? `${p.statin_intensity} intensity since ${fmtDate(p.statin_start)}` : "None"}</dd>
              <dt>Heart disease</dt>
              <dd>{p.cad_age ? `At age ${Math.round(p.cad_age)}${p.early_cad ? ", early" : ""}` : "None"}</dd>
              <dt>Examination</dt>
              <dd>{[p.xanthoma && "Tendon xanthomas", p.arcus && "Corneal arcus"].filter(Boolean).join(", ") || "Not recorded"}</dd>
              <dt>Family history</dt>
              <dd>{[p.fhx_recorded_cad && "Early heart disease", p.fhx_recorded_ldl && "High cholesterol"].filter(Boolean).join(", ") || "Not recorded in the chart"}</dd>
            </dl>
          </Fold>
        )}

        <Fold title="What has happened" note={`${data.timeline.length} entries`}>
          <label className="small row" style={{ gap: 6, marginBottom: 8 }}>
            <input type="checkbox" checked={decisionsOnly} onChange={(e) => setDecisionsOnly(e.target.checked)} /> Decisions by staff only
          </label>
          {timeline.length ? (
            <table className="small">
              <tbody>
                {timeline.map((h) => (
                  <tr key={h.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDate(h.date)}</td>
                    <td>
                      {h.action}
                      {h.detail && <span className="muted"> {says(h.detail)}</span>}
                    </td>
                    <td className="muted">{h.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">Nothing recorded yet.</p>
          )}
          {data.role === "clinician" && (
            <p className="small" style={{ marginTop: 12 }}>
              <a href={`/api/fhir/Patient/${p.id}`} target="_blank" rel="noreferrer">
                Export this record as FHIR R4
              </a>
            </p>
          )}
        </Fold>
      </div>
    </div>
  );
}

// Detail from an audit row as a short phrase. Only a few keys are worth a reader's time.
export function says(d: Record<string, unknown>) {
  const pick = ["reason", "result_due", "found_variant", "result", "language", "slot", "basis", "why", "due"];
  const parts = pick.filter((k) => d[k] != null).map((k) => (k === "result_due" || k === "due" ? `due ${fmtDate(String(d[k]))}` : String(d[k])));
  return parts.length ? `(${parts.join(", ")})` : "";
}

function Reasons({ items, top, against }: { items: Reason[]; top: number; against?: boolean }) {
  return (
    <ul className="reason-bars">
      {items.map((r) => (
        <li key={r.text}>
          <span>{r.text}</span>
          <span className="track" aria-hidden="true">
            <span className={against ? "fill against" : "fill"} style={{ width: `${Math.max(6, (r.weight / top) * 100)}%` }} />
          </span>
        </li>
      ))}
    </ul>
  );
}

type Act = (action: string, inputs?: Record<string, unknown>) => void;

// Renders what the server says is next. The server decides which buttons exist; this decides how they look.
function NextStep({ next, c, role, nodes, act, busy }: { next: Next; c: Case; role: Role; nodes: TreeNode[]; act: Act; busy: string | null }) {
  const [closing, setClosing] = useState(false);
  const [reason, setReason] = useState("");
  const [skip, setSkip] = useState<number[]>([]);
  const can = (id: string) => next.actions.find((a) => a.id === id);
  const toggle = (id: number) => setSkip(skip.includes(id) ? skip.filter((x) => x !== id) : [...skip, id]);
  const btn = (a: Action | undefined, inputs?: Record<string, unknown>, label?: string) =>
    a && (
      <button key={a.id} className={a.primary ? "primary" : ""} disabled={busy !== null} onClick={() => act(a.id, inputs)}>
        {busy === a.id ? "Working" : label ?? a.label}
      </button>
    );
  const head = (
    <>
      <h2>{next.title}</h2>
      <p className="muted">{next.detail}</p>
    </>
  );
  const dismiss = can("dismiss");

  if (next.key === "consent" && can("consent_yes")) {
    const rel = nodes.filter((n) => n.first_degree && !n.deceased);
    return (
      <>
        {head}
        <p>
          "May we invite your close relatives to a free cholesterol check? The invitation won't mention you or your diagnosis. Children are tested at
          their next Well-Child Visit."
        </p>
        {rel.length > 0 && (
          <fieldset className="checks">
            <legend className="small muted">Untick anyone the patient does not want contacted</legend>
            {rel.map((n) => (
              <label key={n.id}>
                <input type="checkbox" checked={!skip.includes(n.id)} onChange={() => toggle(n.id)} /> {n.given}, {n.relation.toLowerCase()}, {n.age}
              </label>
            ))}
          </fieldset>
        )}
        <div className="row">
          {btn(can("consent_yes"), { exclude: skip })}
          {btn(can("consent_no"))}
        </div>
      </>
    );
  }

  if (next.key === "start" && next.plan && can("start_cascade")) {
    const plan = next.plan;
    const invites = plan.relatives.filter((r) => r.outcome === "invite");
    const kids = plan.relatives.filter((r) => r.outcome === "wellchild");
    const none = plan.relatives.filter((r) => r.outcome === "none");
    const n = invites.filter((r) => !skip.includes(r.id)).length;
    return (
      <>
        {head}
        <div className="table-wrap">
          <table className="small confirm">
            <thead>
              <tr>
                <th>Send</th>
                <th>Relative</th>
                <th>The exact message they get, by SMS</th>
              </tr>
            </thead>
            <tbody>
              {invites.map((r) => (
                <tr key={r.id}>
                  <td>
                    <input type="checkbox" aria-label={`Send to ${r.name}`} checked={!skip.includes(r.id)} onChange={() => toggle(r.id)} />
                  </td>
                  <td>
                    {r.name}
                    <div className="muted">
                      {r.relation}, {r.age}. {r.lang === "ar" ? "Arabic" : "English"}
                    </div>
                  </td>
                  <td dir={r.lang === "ar" ? "rtl" : "ltr"} lang={r.lang}>
                    {r.message}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {kids.length > 0 && (
          <p className="small">
            <strong>No message, flagged for Well-Child:</strong> {kids.map((k) => `${k.given} (${k.age})`).join(", ")}.
          </p>
        )}
        {none.length > 0 && (
          <p className="small muted">
            <strong>Not contacted:</strong> {none.map((k) => `${k.name} (${k.why?.toLowerCase()})`).join("; ")}.
          </p>
        )}
        {plan.abroad > 0 && <p className="small muted">{plan.abroad} relatives live abroad. A family letter is prepared for the patient to share.</p>}
        <p className="small">The message does not name the patient or the condition. This is a demo: nothing is really sent.</p>
        <div className="row">{btn(can("start_cascade"), { exclude: skip }, `Send ${n} invitation${n === 1 ? "" : "s"}`)}</div>
      </>
    );
  }

  if (next.key === "running") {
    const g = c.progress;
    const cells: [number, string, boolean?][] =
      role === "coordinator"
        ? [
            [g.invited, "relatives invited"],
            [g.tested ?? 0, "tested so far"],
            [g.found ?? 0, "found with FH", true],
          ]
        : [
            [g.invited, "relatives invited"],
            [g.replied, "have replied"],
            [g.wellchild, "children at Well-Child"],
          ];
    return (
      <>
        {head}
        <div className="grid" style={{ marginTop: 8, gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
          {cells.map(([n, l, hot]) => (
            <div className="stat" key={l}>
              <div className="n" style={hot ? { color: "var(--brand)" } : undefined}>
                <CountUp value={n} ms={900} />
              </div>
              <div className="l">{l}</div>
            </div>
          ))}
        </div>
        {g.letter_abroad > 0 && <p className="small muted" style={{ margin: "12px 0 0" }}>Family letter prepared for {g.letter_abroad} relatives abroad.</p>}
      </>
    );
  }

  return (
    <>
      {head}
      {next.waiting_on && <p className="small">Waiting on {WAITING[next.waiting_on]}.</p>}
      {closing && dismiss ? (
        <fieldset className="checks">
          <legend className="small muted">Why is this not FH?</legend>
          {Object.entries(next.dismiss_reasons).map(([k, label]) => (
            <label key={k}>
              <input type="radio" name="reason" checked={reason === k} onChange={() => setReason(k)} /> {label}
            </label>
          ))}
          <div className="row" style={{ marginTop: 8 }}>
            <button className="primary" disabled={!reason || busy !== null} onClick={() => act("dismiss", { reason })}>
              Close the flag
            </button>
            <button onClick={() => setClosing(false)}>Cancel</button>
          </div>
        </fieldset>
      ) : (
        <div className="row">
          {next.actions.filter((a) => a.id !== "dismiss").map((a) => btn(a))}
          {dismiss && (
            <button disabled={busy !== null} onClick={() => setClosing(true)}>
              {dismiss.label}
            </button>
          )}
        </div>
      )}
    </>
  );
}
