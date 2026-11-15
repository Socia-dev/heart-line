import { useEffect, useRef, useState } from "react";
import { CountUp } from "../motion";

type Month = {
  month: number;
  reviewed: number;
  confirmed_detection: number;
  invited: number;
  tested: number;
  relatives_positive: number;
  children_positive: number;
  cumulative_detection_only: number;
  cumulative_with_cascade: number;
};

const SECOND = 1000; // one month per second

// The twelve-month projection played month by month: counters tick, the gap between screening
// alone and screening plus family testing opens up, and the multiplier settles.
export default function Playback({ series, screened }: { series: Month[]; screened: number }) {
  const [m, setM] = useState(12); // months shown; starts at the end so the page is complete before anyone presses play
  const [playing, setPlaying] = useState(false);
  const t = useRef<number>();

  useEffect(() => {
    if (!playing) return;
    t.current = window.setInterval(() => {
      setM((x) => {
        if (x >= 12) {
          setPlaying(false);
          return 12;
        }
        return x + 1;
      });
    }, SECOND);
    return () => window.clearInterval(t.current);
  }, [playing]);

  const play = () => {
    if (m >= 12) setM(0);
    setPlaying(true);
  };
  const upTo = series.slice(0, m);
  const sum = (k: keyof Month) => upTo.reduce((a, r) => a + (r[k] as number), 0);
  const det = upTo.length ? upTo[upTo.length - 1].cumulative_detection_only : 0;
  const all = upTo.length ? upTo[upTo.length - 1].cumulative_with_cascade : 0;

  // Area chart: the whole year's frame is fixed, the coloured areas grow to month m.
  const W = 640;
  const H = 240;
  const pad = { l: 40, r: 12, t: 12, b: 28 };
  const top = Math.max(10, Math.ceil(series[series.length - 1].cumulative_with_cascade / 100) * 100);
  const x = (i: number) => pad.l + (i / 12) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / top) * (H - pad.t - pad.b);
  const area = (key: "cumulative_detection_only" | "cumulative_with_cascade") =>
    `M${x(0)},${y(0)} ` + upTo.map((r, i) => `L${x(i + 1)},${y(r[key])}`).join(" ") + ` L${x(m)},${y(0)} Z`;

  return (
    <div className="playback">
      <div className="row" style={{ marginBottom: 12 }}>
        <button className="primary" onClick={playing ? () => setPlaying(false) : play}>
          {playing ? "Pause" : m >= 12 ? "Play the year" : "Carry on"}
        </button>
        <label className="scrub">
          <span className="small muted">Month {m} of 12</span>
          <input
            type="range"
            min={0}
            max={12}
            step={1}
            value={m}
            onChange={(e) => {
              setPlaying(false);
              setM(Number(e.target.value));
            }}
            aria-label="Month"
          />
        </label>
      </div>
      <div className="grid g2">
        <div>
          <div className="counters">
            <Counter n={screened} l="results screened" />
            <Counter n={sum("reviewed")} l="flags reviewed" />
            <Counter n={sum("confirmed_detection")} l="confirmed by screening" />
            <Counter n={sum("invited")} l="relatives invited" />
            <Counter n={sum("relatives_positive")} l="relatives found" hot />
            <Counter n={sum("children_positive")} l="children found" hot />
          </div>
          <p className="multiplier">
            {det ? (
              <>
                Every person found by screening has led to <strong>{(all / det).toFixed(2)}</strong> people found in all.
              </>
            ) : (
              "Press play to watch a year of the programme."
            )}
          </p>
        </div>
        <div>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`People found by month ${m}: ${all} with family testing, ${det} by screening alone`}>
            {[0, top / 2, top].map((v) => (
              <g key={v}>
                <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#e6e6e4" />
                <text x={pad.l - 6} y={y(v) + 4} fontSize="12" textAnchor="end" fill="#70666a">
                  {v}
                </text>
              </g>
            ))}
            {Array.from({ length: 13 }, (_, i) => (
              <text key={i} x={x(i)} y={H - 8} fontSize="12" textAnchor="middle" fill="#70666a">
                {i}
              </text>
            ))}
            {m > 0 && (
              <>
                <path d={area("cumulative_with_cascade")} fill="#9f1239" opacity="0.9" className="area" />
                <path d={area("cumulative_detection_only")} fill="#82827e" className="area" />
                <text x={x(m) - 6} y={y(all) - 8} fontSize="13" fontWeight="700" textAnchor="end" fill="#9f1239">
                  {all}
                </text>
              </>
            )}
            <line x1={x(m)} x2={x(m)} y1={pad.t} y2={H - pad.b} stroke="#1c1517" strokeWidth="1.5" className="scrub-line" />
          </svg>
          <div className="legend">
            <span>
              <i style={{ background: "#9f1239" }} />
              Screening plus family testing
            </span>
            <span>
              <i style={{ background: "#82827e" }} />
              Screening alone
            </span>
            <span>People found, by month. Projection on synthetic data.</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Counter({ n, l, hot }: { n: number; l: string; hot?: boolean }) {
  return (
    <div className="stat">
      <div className="n" style={hot ? { color: "var(--brand)" } : undefined}>
        <CountUp value={n} ms={800} />
      </div>
      <div className="l">{l}</div>
    </div>
  );
}
