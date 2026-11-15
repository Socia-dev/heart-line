import { useEffect, useState } from "react";
import { ApiError, changed, get, post } from "../api";
import { ActionError } from "./State";

type Ev = { kind: "stage" | "fold" | "done"; text?: string; model?: string; fold?: number; folds?: number; people?: number; with_fh?: number; auroc?: number | null; auprc?: number | null; seconds?: number; t: number | null };
type Metric = { auroc: number; auprc: number; name: string };
type State = {
  status: "idle" | "running" | "done" | "failed";
  quick: boolean;
  events: Ev[];
  elapsed: number | null;
  error: string | null;
  applied: boolean;
  estimate: { full: number; quick: number };
  result: null | { seconds: number; quick: boolean; metrics: Record<string, Metric>; found: Record<string, number>; threshold: number; people: number };
};

const MODEL = { own: "Own record", linked: "Linked family" } as Record<string, string>;
const f3 = (n?: number | null) => (n == null ? "n/a" : n.toFixed(3));

// The real cross-validated training, run from the page. Each fold appears as it finishes.
export default function Retrain({ current }: { current: Record<string, Metric> }) {
  const [s, setS] = useState<State | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);

  const load = () => get<State>("/api/model/retrain").then(setS).catch((e) => setErr(e as ApiError));
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (s?.status !== "running") return;
    const t = setInterval(load, 700);
    return () => clearInterval(t);
  }, [s?.status]);

  async function start(quick: boolean) {
    setErr(null);
    try {
      setS(await post<State>("/api/model/retrain", { quick }));
    } catch (e) {
      setErr(e as ApiError);
    }
  }
  async function use() {
    setErr(null);
    try {
      setS(await post<State>("/api/model/retrain/apply"));
      changed();
    } catch (e) {
      setErr(e as ApiError);
    }
  }

  if (!s) return <div className="skeleton" style={{ width: "50%" }} />;
  const folds = s.events.filter((e) => e.kind === "fold");
  const stage = [...s.events].reverse().find((e) => e.kind === "stage");
  const running = s.status === "running";
  const est = s.quick ? s.estimate.quick : s.estimate.full;
  return (
    <div>
      {!running && (
        <div className="row">
          <button className="primary" onClick={() => start(false)}>
            Retrain the model
          </button>
          <span className="small muted">About {s.estimate.full} seconds on this machine.</span>
          {s.estimate.full > 60 && (
            <>
              <button onClick={() => start(true)}>Quick run instead</button>
              <span className="small muted">About {s.estimate.quick} seconds: 3 folds on a third of families, to watch the process. It cannot replace the model.</span>
            </>
          )}
        </div>
      )}
      {err && <ActionError error={err} />}

      {(running || s.status !== "idle") && (
        <div className="quiet" style={{ marginTop: 16 }} aria-live="polite">
          <div className="spread">
            <strong>
              {running ? (s.quick ? "Quick run in progress" : "Retraining") : s.status === "failed" ? "The run failed" : s.applied ? "Now using the new model" : "Run finished"}
            </strong>
            <span className="small muted">
              {running ? `${s.elapsed ?? 0} s of about ${est} s` : s.result ? `${s.result.seconds} s${s.result.quick ? ", quick run" : ""}` : ""}
            </span>
          </div>
          {running && (
            <div className="warp-track" style={{ margin: "8px 0" }} aria-hidden="true">
              <span style={{ transform: `scaleX(${Math.min(0.97, (s.elapsed ?? 0) / est)})`, transition: "transform 700ms linear" }} />
            </div>
          )}
          {running && stage && <p className="small muted" style={{ margin: 0 }}>{stage.text}</p>}
          {s.error && <p className="small">{s.error}</p>}
          {folds.length > 0 && (
            <table className="small" style={{ marginTop: 8 }}>
              <thead>
                <tr>
                  <th>Model</th>
                  <th className="num">Fold</th>
                  <th className="num">People held out</th>
                  <th className="num">AUROC</th>
                  <th className="num">AUPRC</th>
                  <th className="num">Time</th>
                </tr>
              </thead>
              <tbody>
                {folds.map((e) => (
                  <tr key={`${e.model}${e.fold}`} className="rise">
                    <td>{MODEL[e.model ?? ""] ?? e.model}</td>
                    <td className="num">
                      {e.fold} of {e.folds}
                    </td>
                    <td className="num">
                      {e.people?.toLocaleString()} ({e.with_fh} with FH)
                    </td>
                    <td className="num">{f3(e.auroc)}</td>
                    <td className="num">{f3(e.auprc)}</td>
                    <td className="num">{e.seconds} s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {s.result && (
            <div className="rise" style={{ marginTop: 12 }}>
              <table className="small">
                <thead>
                  <tr>
                    <th>Method</th>
                    <th className="num">AUROC now</th>
                    <th className="num">This run</th>
                    <th className="num">AUPRC now</th>
                    <th className="num">This run</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(s.result.metrics).map(([k, m]) => (
                    <tr key={k}>
                      <td>{m.name}</td>
                      <td className="num">{f3(current[k]?.auroc)}</td>
                      <td className="num">
                        <strong>{f3(m.auroc)}</strong>
                      </td>
                      <td className="num">{f3(current[k]?.auprc)}</td>
                      <td className="num">
                        <strong>{f3(m.auprc)}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="small muted">
                {s.result.quick
                  ? `A quick run on ${s.result.people.toLocaleString()} people, so its figures are noisier. The live model is unchanged.`
                  : "The live demo is still using the current model."}
              </p>
              {!s.result.quick && !s.applied && (
                <div className="row">
                  <button className="primary" onClick={use}>
                    Use the new model
                  </button>
                  <span className="small muted">Replaces the scores everyone sees. The worklist cut-off would be {s.result.threshold}.</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
