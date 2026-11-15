type Lab = { date: string; ldl: number; on_statin: boolean; new: boolean };

const t = (d: string) => new Date(d + "T00:00:00").getTime();

// LDL over time, with the statin period shaded.
export default function LabChart({ labs, statinStart, today }: { labs: Lab[]; statinStart: string | null; today: string }) {
  if (!labs.length) return <p className="muted">No cholesterol results on record.</p>;
  const W = 560;
  const H = 220;
  const pad = { l: 40, r: 16, t: 14, b: 28 };
  const start = Math.min(t(labs[0].date), statinStart ? t(statinStart) : Infinity, t("2016-01-01"));
  const end = t(today);
  const yMax = Math.max(8, Math.ceil(Math.max(...labs.map((l) => l.ldl)) + 1));
  const x = (d: number) => pad.l + ((d - start) / (end - start)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / yMax) * (H - pad.t - pad.b);
  const years: number[] = [];
  for (let yr = new Date(start).getFullYear() + 1; yr <= new Date(end).getFullYear(); yr += 2) years.push(yr);
  const pts = labs.map((l) => [x(t(l.date)), y(l.ldl)] as const);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="LDL cholesterol over time">
      {statinStart && t(statinStart) <= end && (
        <g>
          <rect x={x(t(statinStart))} y={pad.t} width={x(end) - x(t(statinStart))} height={H - pad.t - pad.b} fill="#f4f4f3" />
          <text x={x(t(statinStart)) + 6} y={pad.t + 14} fontSize="12" fill="#5b5053">
            On a statin
          </text>
        </g>
      )}
      {[0, 2, 4, 6, 8, 10, 12, 14, 16].filter((v) => v <= yMax).map((v) => (
        <g key={v}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#e6e6e4" />
          <text x={pad.l - 8} y={y(v) + 4} fontSize="12" textAnchor="end" fill="#70666a">
            {v}
          </text>
        </g>
      ))}
      <line x1={pad.l} x2={W - pad.r} y1={y(4.9)} y2={y(4.9)} stroke="#70666a" strokeDasharray="4 4" />
      <text x={W - pad.r} y={y(4.9) - 5} fontSize="12" textAnchor="end" fill="#70666a">
        4.9 mmol/L
      </text>
      {years.map((yr) => (
        <text key={yr} x={x(t(`${yr}-01-01`))} y={H - 8} fontSize="12" textAnchor="middle" fill="#70666a">
          {yr}
        </text>
      ))}
      {pts.length > 1 && <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="#463c3f" strokeWidth="1.5" />}
      {labs.map((l, i) => (
        <g key={i}>
          <circle cx={pts[i][0]} cy={pts[i][1]} r={l.new ? 6 : 4.5} fill={l.new ? "#9f1239" : "#1c1517"} />
          <title>{`${l.date}: LDL ${l.ldl} mmol/L${l.on_statin ? " on a statin" : ""}`}</title>
        </g>
      ))}
      <text x={pad.l} y={pad.t - 2} fontSize="12" fill="#70666a">
        LDL mmol/L
      </text>
    </svg>
  );
}
