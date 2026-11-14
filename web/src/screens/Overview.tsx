import { useState } from "react";
import { changed, post, scorePct, useApi } from "../api";
import LineChart from "../components/LineChart";

type Summary = {
  today: string;
  screened: number;
  open_cases: number;
  confirmed: number;
  confirmed_by_source: Record<string, number>;
  invitations: Record<string, number>;
  invitations_total: number;
  wellchild: Record<string, number>;
  wellchild_total: number;
  letters_abroad: number;
};
type Pilot = {
  label: string;
  assumptions: Record<string, number>;
  totals: Record<string, number>;
  series: { month: number; cumulative_detection_only: number; cumulative_with_cascade: number }[];
};
type NewResult = { person_id: number; case_id: number | null; ldl: number; prob: number; flagged: boolean; reasons: string[] };
type Advance = Record<string, number | string>;

export default function Overview() {
  const s = useApi<Summary>("/api/summary");
  const p = useApi<Pilot>("/api/pilot");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [last, setLast] = useState<NewResult | null>(null);
  const [adv, setAdv] = useState<Advance | null>(null);

  async function run<T>(f: () => Promise<T>, then: (x: T) => void) {
    setBusy(true);
    setErr(null);
    try {
      then(await f());
      changed();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  const t = p.data?.totals;
  const d = s.data;
  return (
    <div className="stack">
      <div>
        <h1>One blood test can find a whole family</h1>
        <p className="lede">
          Heart Line finds familial hypercholesterolaemia in routine cholesterol results, then helps each confirmed
          patient invite their parents, brothers, sisters and children to be tested.
        </p>
      </div>

      {t && p.data && (
        <section className="hero grid g2">
          <div>
            <div className="big">{t.people_per_detection_case.toFixed(1)}</div>
            <p style={{ fontSize: 18, marginTop: 10 }}>
              people found for every person found by screening, over a 12-month pilot.
            </p>
            <div className="grid g2" style={{ marginTop: 18 }}>
              <div className="stat">
                <div className="n">{t.found_detection_only}</div>
                <div className="l">found by screening alone</div>
              </div>
              <div className="stat">
                <div className="n" style={{ color: "var(--brand)" }}>
                  {t.found_with_cascade}
                </div>
                <div className="l">found with family testing added</div>
              </div>
            </div>
            <p className="synthetic" style={{ marginTop: 16 }}>
              {p.data.label}. {p.data.assumptions.reviews_per_week} clinician reviews a week, {Math.round(p.data.assumptions.consent_rate * 100)}% of
              patients consent, {Math.round(p.data.assumptions.relative_uptake * 100)}% of invited relatives get tested.{" "}
              {t.children_positive} of the people found are children, picked up at Well-Child Visits.
            </p>
          </div>
          <div>
            <h3>People found, cumulative</h3>
            <LineChart
              labels={p.data.series.map((x) => String(x.month))}
              series={[
                { name: "Screening plus family testing", color: "#9f1239", values: p.data.series.map((x) => x.cumulative_with_cascade) },
                { name: "Screening alone", color: "#8a847e", values: p.data.series.map((x) => x.cumulative_detection_only) },
              ]}
            />
            <div className="legend">
              <span>
                <i style={{ background: "#9f1239" }} />
                Screening plus family testing
              </span>
              <span>
                <i style={{ background: "#8a847e" }} />
                Screening alone
              </span>
              <span>Month of pilot</span>
            </div>
          </div>
        </section>
      )}

      <section className="card">
        <div className="spread">
          <h2>Live demo</h2>
          {d && <span className="muted small">{d.screened.toLocaleString()} synthetic people with lipid results scored</span>}
        </div>
        <p className="muted">Play the story one step at a time. Each button moves the synthetic world forward.</p>
        <div className="row" style={{ marginBottom: 16 }}>
          <button className="primary" disabled={busy} onClick={() => run(() => post<NewResult>("/api/simulate/new-result"), setLast)}>
            New lab result
          </button>
          <button disabled={busy} onClick={() => run(() => post<Advance>("/api/simulate/advance", { weeks: 2 }), setAdv)}>
            Advance two weeks
          </button>
          <button
            disabled={busy}
            onClick={() =>
              run(
                () => post("/api/reset"),
                () => {
                  setLast(null);
                  setAdv(null);
                },
              )
            }
          >
            Reset demo
          </button>
        </div>
        {err && <p className="error">{err}</p>}
        {last && (
          <div className="notice" style={{ marginBottom: 16 }}>
            <div className="spread">
              <strong>
                New result: LDL {last.ldl.toFixed(1)} mmol/L. {last.flagged ? `Flagged, score ${scorePct(last.prob)}.` : "Not flagged."}
              </strong>
              <a href={`#/patient/${last.person_id}`}>Open patient</a>
            </div>
            {last.reasons.length > 0 && (
              <ul className="reasons" style={{ marginTop: 8 }}>
                {last.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        {adv && (
          <div className="quiet" style={{ marginBottom: 16 }}>
            <strong>Two weeks passed.</strong>{" "}
            {[
              [adv.variants_found, "variant found", "variants found"],
              [adv.tested, "relative tested", "relatives tested"],
              [adv.relatives_positive, "relative positive", "relatives positive"],
              [adv.wellchild_tested, "child tested", "children tested"],
              [adv.children_positive, "child positive", "children positive"],
              [adv.no_response, "invitation unanswered", "invitations unanswered"],
            ]
              .filter(([n]) => Number(n) > 0)
              .map(([n, one, many]) => `${n} ${Number(n) === 1 ? one : many}`)
              .join(", ") || "Nothing came back this time."}
          </div>
        )}
        {d && (
          <div className="grid g4">
            <Stat n={d.open_cases} l="cases waiting for a clinician" href="#/worklist" />
            <Stat n={d.confirmed} l="confirmed" sub={confirmedBreakdown(d.confirmed_by_source)} />
            <Stat
              n={d.invitations_total}
              l="relatives invited"
              href="#/families"
              sub={d.invitations_total ? `${(d.invitations.booked ?? 0) + (d.invitations.positive ?? 0) + (d.invitations.negative ?? 0)} booked or tested` : undefined}
            />
            <Stat n={d.wellchild_total} l="children flagged for Well-Child" href="#/wellchild" sub={d.letters_abroad ? `${d.letters_abroad} relatives abroad reached by family letter` : undefined} />
          </div>
        )}
      </section>
    </div>
  );
}

function confirmedBreakdown(b: Record<string, number>) {
  const parts = [
    [b.detection, "by screening"],
    [b.cascade, "through relatives"],
    [b.wellchild, "at Well-Child"],
  ].filter(([n]) => n);
  return parts.length ? parts.map(([n, l]) => `${n} ${l}`).join(", ") : undefined;
}

function Stat({ n, l, sub, href }: { n: number; l: string; sub?: string; href?: string }) {
  const body = (
    <>
      <div className="n">{n.toLocaleString()}</div>
      <div className="l">{l}</div>
      {sub && <div className="small muted">{sub}</div>}
    </>
  );
  return <div className="stat quiet">{href ? <a href={href} style={{ color: "inherit" }}>{body}</a> : body}</div>;
}
