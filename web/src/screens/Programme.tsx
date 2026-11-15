import { useEffect, useState } from "react";
import { useApi } from "../api";
import LineChart from "../components/LineChart";
import { LoadError, Loading } from "../components/State";

type Summary = {
  funnel: { step: string; count: number }[];
  open_cases: number;
  confirmed: number;
  dismissed_by_reason: Record<string, number>;
};
type Pilot = {
  label: string;
  runs: number;
  assumptions: { reviews_per_week: number; consent_rate: number; relative_uptake: number };
  totals: Record<string, number> & { found_with_cascade_range: number[]; new_cases_per_index_range: number[] };
  series: { month: number; cumulative_detection_only: number; cumulative_with_cascade: number }[];
  benchmarks: { source: string; new_cases_per_index: { label: string; value: number }[] };
};

// The programme lead's home: is it working, and what would a year look like under different assumptions?
export default function Programme() {
  const s = useApi<Summary>("/api/summary");
  const [reviews, setReviews] = useState(20);
  const [consent, setConsent] = useState(0.85);
  const [uptake, setUptake] = useState(0.6);
  const [q, setQ] = useState("reviews_per_week=20&consent_rate=0.85&uptake=0.6");
  useEffect(() => {
    const t = setTimeout(() => setQ(`reviews_per_week=${reviews}&consent_rate=${consent}&uptake=${uptake}`), 200);
    return () => clearTimeout(t);
  }, [reviews, consent, uptake]);
  const p = useApi<Pilot>(`/api/pilot?${q}`);

  if (s.error) return <LoadError error={s.error} retry={s.reload} />;
  const t = p.data?.totals;
  const max = Math.max(1, ...(s.data?.funnel.slice(1).map((f) => f.count) ?? [1]));
  const bmax = 3.65;
  return (
    <div className="stack">
      <div>
        <h1>Programme</h1>
        <p className="lede">One blood test can find a whole family. This page shows whether that is happening, with no patient names.</p>
      </div>

      <section className="card">
        <div className="spread">
          <h2>A year of the programme</h2>
          <span className="small muted">Projection on synthetic data, {p.data?.runs ?? 5} runs</span>
        </div>
        {!p.data || !t ? (
          <div className="skeleton" style={{ width: "60%" }} />
        ) : (
          <div className="grid g2" style={{ marginTop: 8 }}>
            <div>
              <div className="grid g2">
                <div className="stat">
                  <div className="n">{t.found_detection_only}</div>
                  <div className="l">found by screening alone</div>
                </div>
                <div className="stat">
                  <div className="n" style={{ color: "var(--brand)" }}>
                    {t.found_with_cascade}
                  </div>
                  <div className="l">
                    with family testing added ({t.found_with_cascade_range[0]} to {t.found_with_cascade_range[1]} across runs)
                  </div>
                </div>
              </div>
              <p style={{ marginTop: 14 }}>
                Each confirmed patient leads to <strong>{t.new_cases_per_index.toFixed(2)}</strong> more people found, {t.children_positive} of them children
                picked up at Well-Child Visits.
              </p>
              <div className="sliders">
                <Slider label="Clinician reviews a week" value={reviews} min={5} max={60} step={5} show={String(reviews)} set={setReviews} />
                <Slider label="Patients who agree to family testing" value={consent} min={0.3} max={1} step={0.05} show={`${Math.round(consent * 100)}%`} set={setConsent} />
                <Slider label="Invited relatives who get tested" value={uptake} min={0.2} max={0.9} step={0.05} show={`${Math.round(uptake * 100)}%`} set={setUptake} />
              </div>
            </div>
            <div>
              <LineChart
                labels={p.data.series.map((x) => String(x.month))}
                series={[
                  { name: "With family testing", color: "#9f1239", values: p.data.series.map((x) => x.cumulative_with_cascade) },
                  { name: "Screening alone", color: "#8a847e", values: p.data.series.map((x) => x.cumulative_detection_only) },
                ]}
              />
              <div className="legend">
                <span>
                  <i style={{ background: "#9f1239" }} />
                  With family testing
                </span>
                <span>
                  <i style={{ background: "#8a847e" }} />
                  Screening alone
                </span>
                <span>People found, by month</span>
              </div>
            </div>
          </div>
        )}
      </section>

      {p.data && t && (
        <section className="card">
          <h2>How that compares with published programmes</h2>
          <p className="muted">New cases found per confirmed patient. Heart Line invites first-degree relatives only, so the first published row is the like-for-like one.</p>
          <div className="bars">
            <div className="bar-row best">
              <span>Heart Line projection</span>
              <div className="track">
                <div className="fill" style={{ width: `${(t.new_cases_per_index / bmax) * 100}%` }} />
              </div>
              <strong style={{ textAlign: "right" }}>{t.new_cases_per_index.toFixed(2)}</strong>
            </div>
            {p.data.benchmarks.new_cases_per_index.map((b) => (
              <div className="bar-row" key={b.label}>
                <span>{b.label}</span>
                <div className="track">
                  <div className="fill" style={{ width: `${(b.value / bmax) * 100}%` }} />
                </div>
                <strong style={{ textAlign: "right" }}>{b.value.toFixed(2)}</strong>
              </div>
            ))}
          </div>
          <p className="small muted" style={{ marginTop: 12, marginBottom: 0 }}>
            {p.data.benchmarks.source} Going beyond first-degree relatives is the largest gain in the published evidence and is the next thing to add.
          </p>
        </section>
      )}

      <section className="card">
        <h2>In the demo so far</h2>
        {!s.data ? (
          <Loading rows={3} />
        ) : (
          <>
            <p className="muted">
              {s.data.funnel[0].count.toLocaleString()} people flagged by screening, {s.data.open_cases.toLocaleString()} still waiting for a clinician.
            </p>
            <div className="bars">
              {s.data.funnel.slice(1).map((f) => (
                <div className="bar-row" key={f.step}>
                  <span>{f.step}</span>
                  <div className="track">
                    <div className="fill" style={{ width: `${(f.count / max) * 100}%` }} />
                  </div>
                  <strong style={{ textAlign: "right" }}>{f.count}</strong>
                </div>
              ))}
            </div>
            {Object.keys(s.data.dismissed_by_reason).length > 0 && (
              <p className="small" style={{ marginTop: 12, marginBottom: 0 }}>
                Flags closed by clinicians:{" "}
                {Object.entries(s.data.dismissed_by_reason)
                  .map(([k, v]) => `${v} "${k.toLowerCase()}"`)
                  .join(", ")}
                . These disagreements are what the model should learn from.
              </p>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function Slider({ label, value, min, max, step, show, set }: { label: string; value: number; min: number; max: number; step: number; show: string; set: (n: number) => void }) {
  return (
    <label className="slider">
      <span>
        {label} <strong>{show}</strong>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => set(Number(e.target.value))} />
    </label>
  );
}
