import { useEffect, useState } from "react";
import { reduced } from "../motion";

export type Stage = { key: string; title: string; output: string; ms: number; detail?: unknown };

const PACE = 420; // per stage, so a person can follow it; the real time is shown beside each stage

function ms(n: number) {
  return n < 1 ? "under 1 ms" : n < 1000 ? `${Math.round(n)} ms` : `${(n / 1000).toFixed(1)} s`;
}

// The scoring pipeline as a row of stages that light up in turn. Every output and timing is real.
export function Pipeline({ stages, play = true, onDone }: { stages: Stage[]; play?: boolean; onDone?: () => void }) {
  const [lit, setLit] = useState(play && !reduced() ? 0 : stages.length);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!play || reduced()) {
      setLit(stages.length);
      onDone?.();
      return;
    }
    setLit(0);
    let i = 0;
    const t = setInterval(() => {
      i += 1;
      setLit(i);
      if (i >= stages.length) {
        clearInterval(t);
        onDone?.();
      }
    }, PACE);
    return () => clearInterval(t);
  }, [stages]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = stages.reduce((a, s) => a + s.ms, 0);
  const feats = stages.find((s) => s.key === "features")?.detail as { label: string }[] | undefined;
  return (
    <div className="pipeline">
      <ol>
        {stages.map((s, i) => (
          <li key={s.key} className={i < lit ? "on" : ""} aria-current={i === lit - 1 ? "step" : undefined}>
            <span className="pipe-title">{s.title}</span>
            <span className="pipe-out">{i < lit ? s.output : " "}</span>
            <span className="pipe-ms small muted">{i < lit ? ms(s.ms) : " "}</span>
          </li>
        ))}
      </ol>
      <div className="spread small muted" style={{ marginTop: 8 }}>
        <span>{lit >= stages.length ? `All seven stages in ${ms(total)} of real work.` : "Scoring…"}</span>
        {feats && lit > 2 && (
          <button className="link small" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? "Hide" : "Show"} the {feats.length} feature values
          </button>
        )}
      </div>
      {open && feats && (
        <ul className="feature-list small">
          {feats.map((f) => (
            <li key={f.label}>{f.label}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// The same pipeline over the page, for the moment a new lab result arrives.
let show: ((s: Stage[], then: () => void) => void) | null = null;

export function playPipeline(stages: Stage[], then: () => void) {
  if (show) show(stages, then);
  else then();
}

export default function PipelineOverlay() {
  const [run, setRun] = useState<{ stages: Stage[]; then: () => void } | null>(null);
  const [done, setDone] = useState(false);
  useEffect(() => {
    show = (stages, then) => {
      setDone(false);
      setRun({ stages, then });
    };
    return () => {
      show = null;
    };
  }, []);
  useEffect(() => {
    if (!done || !run) return;
    const t = setTimeout(finish, 1300);
    return () => clearTimeout(t);
  }, [done]); // eslint-disable-line react-hooks/exhaustive-deps

  function finish() {
    if (!run) return;
    const then = run.then;
    setRun(null);
    then();
  }
  if (!run) return null;
  return (
    <div className="warp" onClick={() => done && finish()} role="status" aria-live="polite">
      <div className="warp-card wide" onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <h2 style={{ margin: 0 }}>A new cholesterol result arrives</h2>
          {done && (
            <button className="primary" onClick={finish}>
              Open the patient
            </button>
          )}
        </div>
        <p className="small muted">Heart Line scores it the moment it lands. This is the real pipeline, with real timings.</p>
        <Pipeline stages={run.stages} onDone={() => setDone(true)} />
      </div>
    </div>
  );
}
