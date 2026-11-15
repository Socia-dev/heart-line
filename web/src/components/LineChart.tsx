type Series = { name: string; color: string; values: number[] };

// Simple cumulative line chart for the pilot projection.
export default function LineChart({ series, labels, height = 220 }: { series: Series[]; labels: string[]; height?: number }) {
  const W = 640;
  const H = height;
  const pad = { l: 44, r: 16, t: 12, b: 28 };
  const max = Math.max(1, ...series.flatMap((s) => s.values));
  const nice = Math.ceil(max / 100) * 100 || 10;
  const x = (i: number) => pad.l + (i * (W - pad.l - pad.r)) / Math.max(1, labels.length - 1);
  const y = (v: number) => pad.t + (1 - v / nice) * (H - pad.t - pad.b);
  const ticks = [0, nice / 2, nice];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Cumulative people found by month">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#e6e6e4" />
          <text x={pad.l - 8} y={y(t) + 4} fontSize="12" textAnchor="end" fill="#70666a">
            {t}
          </text>
        </g>
      ))}
      {labels.map((l, i) => (
        <text key={l} x={x(i)} y={H - 8} fontSize="12" textAnchor="middle" fill="#70666a">
          {l}
        </text>
      ))}
      {series.map((s) => (
        <g key={s.name}>
          <polyline
            fill="none"
            stroke={s.color}
            strokeWidth="2.5"
            points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
          />
          <text x={x(s.values.length - 1) - 4} y={y(s.values[s.values.length - 1]) - 8} fontSize="12" textAnchor="end" fill={s.color} fontWeight="700">
            {s.values[s.values.length - 1]}
          </text>
        </g>
      ))}
    </svg>
  );
}
