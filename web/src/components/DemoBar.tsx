import { useState } from "react";
import { changed, fmtDate, post, useApi } from "../api";

type NewResult = { person_id: number; flagged: boolean };
type Advance = Record<string, number | string>;

function describe(a: Advance) {
  const parts = [
    [a.variants_found, "variant found", "variants found"],
    [a.relatives_positive, "relative tested positive", "relatives tested positive"],
    [a.children_positive, "child tested positive", "children tested positive"],
    [Number(a.tested) - Number(a.relatives_positive), "relative tested clear", "relatives tested clear"],
  ]
    .filter(([n]) => Number(n) > 0)
    .map(([n, one, many]) => `${n} ${Number(n) === 1 ? one : many}`);
  return parts.length ? parts.join(", ") + "." : "No new results.";
}

// Presenter controls, on every screen so the story never needs a detour.
export default function DemoBar() {
  const s = useApi<{ today: string }>("/api/summary");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function run(f: () => Promise<void>) {
    setBusy(true);
    try {
      await f();
      changed();
    } catch (e) {
      setMsg(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="demobar">
      <div className="wrap demobar-inner">
        <span className="muted small">Demo{s.data ? `, ${fmtDate(s.data.today)}` : ""}</span>
        <button
          className="primary"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const r = await post<NewResult>("/api/simulate/new-result");
              setMsg(null);
              window.location.hash = `#/patient/${r.person_id}`;
            })
          }
        >
          New lab result
        </button>
        <button
          disabled={busy}
          onClick={() =>
            run(async () => {
              const r = await post<Advance>("/api/simulate/advance", { weeks: 2 });
              setMsg(`Two weeks later: ${describe(r)}`);
            })
          }
        >
          Advance two weeks
        </button>
        <button
          className="ghost"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await post("/api/reset");
              setMsg("Demo reset.");
              window.location.hash = "#/";
            })
          }
        >
          Reset
        </button>
        {msg && <span className="small demobar-msg">{msg}</span>}
      </div>
    </div>
  );
}
