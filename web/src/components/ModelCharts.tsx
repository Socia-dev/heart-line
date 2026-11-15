import { useEffect, useRef, useState } from "react";
import { go, setRole, useApi } from "../api";

type Curve = { roc: number[][]; pr: number[][]; point: { fpr: number; tpr: number; precision: number } };
const SERIES: [string, string, string][] = [
  ["dlcn", "DLCN score", "#82827e"],
  ["own", "Heart Line, own record", "#c7c2c3"],
  ["linked", "Heart Line, linked family", "#9f1239"],
];

// ROC and precision-recall curves for the three methods, with where each sits at the shared workload.
export function Curves({ curves, k }: { curves: Record<string, Curve>; k: number }) {
  const [tab, setTab] = useState<"roc" | "pr">("roc");
  const W = 520;
  const H = 360;
  const pad = { l: 48, r: 16, t: 12, b: 40 };
  const x = (v: number) => pad.l + v * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v) * (H - pad.t - pad.b);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  return (
    <div>
      <div className="tabs" role="tablist" style={{ marginBottom: 8 }}>
        <button role="tab" aria-selected={tab === "roc"} className={tab === "roc" ? "on" : ""} onClick={() => setTab("roc")}>
          ROC curve
        </button>
        <button role="tab" aria-selected={tab === "pr"} className={tab === "pr" ? "on" : ""} onClick={() => setTab("pr")}>
          Precision and recall
        </button>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={tab === "roc" ? "ROC curves" : "Precision-recall curves"} key={tab}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(0)} x2={x(1)} y1={y(t)} y2={y(t)} stroke="#e6e6e4" />
            <text x={pad.l - 8} y={y(t) + 4} fontSize="12" textAnchor="end" fill="#70666a">
              {t}
            </text>
            <text x={x(t)} y={H - 22} fontSize="12" textAnchor="middle" fill="#70666a">
              {t}
            </text>
          </g>
        ))}
        <text x={x(0.5)} y={H - 4} fontSize="12" textAnchor="middle" fill="#463c3f">
          {tab === "roc" ? "False positive rate" : "Recall (share of people with FH found)"}
        </text>
        <text x={12} y={y(0.5)} fontSize="12" textAnchor="middle" fill="#463c3f" transform={`rotate(-90 12 ${y(0.5)})`}>
          {tab === "roc" ? "True positive rate" : "Precision (flags that are right)"}
        </text>
        {tab === "roc" && <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="#d4d4d1" strokeDasharray="4 4" />}
        {SERIES.map(([key, , color], i) => {
          const c = curves[key];
          if (!c) return null;
          const pts = c[tab].map(([a, b]) => `${x(a)},${y(b)}`).join(" ");
          const pt = tab === "roc" ? [c.point.fpr, c.point.tpr] : [c.point.tpr, c.point.precision];
          return (
            <g key={key}>
              <polyline className="draw" style={{ "--d": `${i * 180}ms` } as React.CSSProperties} pathLength={1} points={pts} fill="none" stroke={color} strokeWidth={key === "linked" ? 3 : 2} />
              <circle className="pop" style={{ animationDelay: `${600 + i * 180}ms` }} cx={x(pt[0])} cy={y(pt[1])} r="6" fill="#fff" stroke={color} strokeWidth="3" />
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {SERIES.map(([key, name, color]) => (
          <span key={key}>
            <i style={{ background: color }} />
            {name}
          </span>
        ))}
        <span>Circles: where each method sits when {k} people are reviewed</span>
      </div>
    </div>
  );
}

type Scatter = { x: number[]; y: number[]; band: number[]; found: number[]; id: number[]; bands: string[]; threshold: number };

// Everyone with a result, drawn on canvas: LDL across, model score up (log scale), the cut-off as a line.
export function Population() {
  const { data } = useApi<Scatter>("/api/model/scatter");
  const ref = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<{ i: number; left: number; top: number } | null>(null);
  const W = 1000;
  const H = 440;
  const pad = { l: 56, r: 16, t: 16, b: 44 };
  const X0 = 0;
  const X1 = 16;
  const Y0 = Math.log10(0.0005);
  const px = (v: number) => pad.l + ((Math.min(v, X1) - X0) / (X1 - X0)) * (W - pad.l - pad.r);
  const py = (v: number) => pad.t + (1 - (Math.log10(Math.max(v, 0.0005)) - Y0) / (0 - Y0)) * (H - pad.t - pad.b);

  useEffect(() => {
    const cv = ref.current;
    if (!cv || !data) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = W * dpr;
    cv.height = H * dpr;
    const g = cv.getContext("2d")!;
    g.scale(dpr, dpr);
    const axes = () => {
      g.clearRect(0, 0, W, H);
      g.font = "12px Manrope, system-ui, sans-serif";
      g.fillStyle = "#70666a";
      g.strokeStyle = "#e6e6e4";
      for (const v of [0.001, 0.01, 0.1, 1]) {
        g.beginPath();
        g.moveTo(pad.l, py(v));
        g.lineTo(W - pad.r, py(v));
        g.stroke();
        g.textAlign = "right";
        g.fillText(String(v), pad.l - 8, py(v) + 4);
      }
      for (let v = 0; v <= 16; v += 2) {
        g.textAlign = "center";
        g.fillText(String(v), px(v), H - 24);
      }
      g.fillStyle = "#463c3f";
      g.fillText("Highest LDL, mmol/L, allowing for statins", (pad.l + W) / 2, H - 4);
    };
    const order = data.x.map((_, i) => i).sort((a, b) => data.found[a] - data.found[b] || data.y[a] - data.y[b]);
    const dot = (i: number) => {
      const f = data.found[i];
      const flagged = data.band[i] < data.bands.length - 1;
      g.fillStyle = f ? "#9f1239" : flagged ? "rgba(159,18,57,0.45)" : "rgba(70,60,63,0.18)";
      const r = f ? 4 : flagged ? 2.4 : 1.6;
      g.beginPath();
      g.arc(px(data.x[i]), py(data.y[i]), r, 0, Math.PI * 2);
      g.fill();
    };
    const line = () => {
      g.strokeStyle = "#9f1239";
      g.setLineDash([6, 4]);
      g.beginPath();
      g.moveTo(pad.l, py(data.threshold));
      g.lineTo(W - pad.r, py(data.threshold));
      g.stroke();
      g.setLineDash([]);
      g.fillStyle = "#9f1239";
      g.textAlign = "left";
      g.fillText(`Worklist cut-off, ${data.threshold}`, pad.l + 6, py(data.threshold) - 6);
    };
    axes();
    // One pass; the canvas fades in with CSS, so it never depends on animation frames running.
    order.forEach(dot);
    line();
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  function nearest(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!data || !ref.current) return null;
    const b = ref.current.getBoundingClientRect();
    const mx = ((e.clientX - b.left) / b.width) * W;
    const my = ((e.clientY - b.top) / b.height) * H;
    let best = -1;
    let bd = 64; // within 8 px
    for (let i = 0; i < data.x.length; i++) {
      const dx = px(data.x[i]) - mx;
      const dy = py(data.y[i]) - my;
      const d = dx * dx + dy * dy;
      if (d < bd) {
        bd = d;
        best = i;
      }
    }
    return best < 0 ? null : { i: best, left: e.clientX - b.left, top: e.clientY - b.top };
  }

  return (
    <div className="scatter">
      <div style={{ position: "relative" }}>
        <canvas
          ref={ref}
          className={data ? "rise" : ""}
          style={{ width: "100%", aspectRatio: `${W} / ${H}`, cursor: hover ? "pointer" : "default" }}
          onMouseMove={(e) => setHover(nearest(e))}
          onMouseLeave={() => setHover(null)}
          onClick={(e) => {
            const h = nearest(e);
            if (h && data) {
              setRole("clinician");
              go(`#/patient/${data.id[h.i]}`);
            }
          }}
          aria-label="Everyone with a cholesterol result, by LDL and model score"
        />
        {!data && <div className="skeleton" style={{ position: "absolute", inset: "40% 20%" }} />}
        {hover && data && (
          <div className="tip" style={{ left: hover.left + 12, top: hover.top - 12 }}>
            <strong>{data.bands[data.band[hover.i]]}</strong>
            <br />
            LDL {data.x[hover.i].toFixed(1)}, score {data.y[hover.i] < 0.001 ? "under 0.001" : data.y[hover.i].toFixed(3)}
            {data.found[hover.i] ? <><br />Confirmed in this demo</> : null}
            <br />
            <span className="muted">Click to open, as the clinician</span>
          </div>
        )}
      </div>
      <div className="legend" style={{ marginTop: 8 }}>
        <span>
          <i style={{ background: "rgba(70,60,63,0.35)" }} />
          Not flagged
        </span>
        <span>
          <i style={{ background: "rgba(159,18,57,0.5)" }} />
          Flagged
        </span>
        <span>
          <i style={{ background: "#9f1239" }} />
          Confirmed in this demo
        </span>
        <span>{data ? `${data.x.length.toLocaleString()} people. Score on a log scale. On synthetic data.` : ""}</span>
      </div>
    </div>
  );
}
