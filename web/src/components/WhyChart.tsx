export type Why = {
  base: number;
  base_prob: number;
  end: number;
  end_prob: number;
  steps: { feature: string; label: string; value: number; raises: boolean }[];
};

const pct = (p: number) => (p < 0.01 ? "under 1%" : p > 0.99 ? "over 99%" : `${Math.round(p * 100)}%`);

// A waterfall: from the starting point (a typical person), each factor pushes the score up or down,
// ending at this person. Lengths are the model's own units (SHAP values), so they add up exactly.
export default function WhyChart({ why, compact }: { why: Why; compact?: boolean }) {
  let run = why.base;
  const rows = why.steps.map((s) => {
    const from = run;
    run += s.value;
    return { ...s, from, to: run };
  });
  const all = [why.base, why.end, ...rows.flatMap((r) => [r.from, r.to])];
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const span = Math.max(hi - lo, 0.001);
  const x = (v: number) => ((v - lo) / span) * 100;

  return (
    <div className={`why ${compact ? "compact" : ""}`} role="img" aria-label={`Score built up from ${pct(why.base_prob)} to ${pct(why.end_prob)}`}>
      <div className="why-row edge">
        <span className="why-label">Starting point, a typical person</span>
        <span className="why-track">
          <span className="why-mark" style={{ left: `${x(why.base)}%` }} />
        </span>
        <span className="why-val">{pct(why.base_prob)}</span>
      </div>
      {rows.map((r, i) => (
        <div className="why-row" key={r.feature}>
          <span className="why-label">{r.label}</span>
          <span className="why-track">
            <span
              className={`why-bar ${r.raises ? "up" : "down"}`}
              style={{ left: `${x(Math.min(r.from, r.to))}%`, width: `${Math.max(0.6, Math.abs(x(r.to) - x(r.from)))}%`, "--d": `${120 + i * 80}ms` } as React.CSSProperties}
            />
          </span>
          <span className="why-val small muted">{r.raises ? "raises" : "lowers"}</span>
        </div>
      ))}
      <div className="why-row edge">
        <span className="why-label">
          <strong>This person</strong>
        </span>
        <span className="why-track">
          <span className="why-mark end" style={{ left: `${x(why.end)}%` }} />
        </span>
        <span className="why-val">
          <strong>{pct(why.end_prob)}</strong>
        </span>
      </div>
    </div>
  );
}
