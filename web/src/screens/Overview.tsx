import { useApi } from "../api";
import LineChart from "../components/LineChart";

type Summary = {
  open_cases: number;
  confirmed: number;
  invitations_total: number;
  wellchild_total: number;
};
type Pilot = {
  label: string;
  totals: Record<string, number>;
  series: { month: number; cumulative_detection_only: number; cumulative_with_cascade: number }[];
};

export default function Overview() {
  const s = useApi<Summary>("/api/summary");
  const p = useApi<Pilot>("/api/pilot");
  const t = p.data?.totals;
  const d = s.data;
  return (
    <div className="stack">
      <div>
        <h1>One blood test can find a whole family</h1>
        <p className="lede">
          Heart Line spots inherited high cholesterol in routine blood tests. Once a doctor confirms it, the patient's close relatives are invited
          to be tested too.
        </p>
      </div>

      {t && p.data && (
        <section className="hero grid g2">
          <div>
            <div className="big">{t.people_per_detection_case.toFixed(1)}</div>
            <p style={{ fontSize: 18, marginTop: 10 }}>people found for every one found by screening, over a 12-month pilot.</p>
            <div className="grid g2" style={{ marginTop: 18 }}>
              <div className="stat">
                <div className="n">{t.found_detection_only}</div>
                <div className="l">found by screening alone</div>
              </div>
              <div className="stat">
                <div className="n" style={{ color: "var(--brand)" }}>
                  {t.found_with_cascade}
                </div>
                <div className="l">with family testing added</div>
              </div>
            </div>
            <p className="synthetic" style={{ marginTop: 16, marginBottom: 0 }}>
              {p.data.label}.
            </p>
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
        </section>
      )}

      {d && (
        <section>
          <h2>In the demo right now</h2>
          <div className="grid g4" style={{ marginTop: 12 }}>
            <Stat n={d.open_cases} l="flags to review" href="#/worklist" />
            <Stat n={d.confirmed} l="people confirmed" href="#/families" />
            <Stat n={d.invitations_total} l="relatives invited" href="#/families" />
            <Stat n={d.wellchild_total} l="children due a test" href="#/wellchild" />
          </div>
          <p className="muted small" style={{ marginTop: 12 }}>
            Start with New lab result in the bar above.
          </p>
        </section>
      )}
    </div>
  );
}

function Stat({ n, l, href }: { n: number; l: string; href: string }) {
  return (
    <a href={href} className="stat card" style={{ color: "inherit", textDecoration: "none" }}>
      <div className="n">{n.toLocaleString()}</div>
      <div className="l">{l}</div>
    </a>
  );
}
