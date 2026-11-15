import { useState } from "react";
import { ApiError, ROLES, Role, changed, fmtDate, go, post, setRole, useApi, useRole } from "../api";
import { describe } from "./State";

type Advance = Record<string, number | string>;
type Summary = { today: string; story: { step: string; done: boolean; role: Role }[] };

function tell(a: Advance) {
  const parts = [
    [a.variants_found, "genetic result back", "genetic results back"],
    [a.relatives_positive, "relative tested positive", "relatives tested positive"],
    [a.children_positive, "child tested positive", "children tested positive"],
    [Number(a.tested) - Number(a.relatives_positive), "relative tested clear", "relatives tested clear"],
    [a.no_response, "invitation unanswered", "invitations unanswered"],
  ]
    .filter(([n]) => Number(n) > 0)
    .map(([n, one, many]) => `${n} ${Number(n) === 1 ? one : many}`);
  return parts.length ? parts.join(", ") + "." : "Nothing new came back.";
}

// Presenter controls. Everything here is demo scaffolding; none of it would exist in a pilot.
export default function DemoBar() {
  const role = useRole();
  const s = useApi<Summary>("/api/summary");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function run(f: () => Promise<void>) {
    setBusy(true);
    try {
      await f();
      changed();
    } catch (e) {
      setMsg(describe(e as ApiError).title + ". " + describe(e as ApiError).help);
    } finally {
      setBusy(false);
    }
  }
  const story = s.data?.story ?? [];
  const done = story.filter((x) => x.done).length;
  const next = story.find((x) => !x.done);

  return (
    <div className="demobar">
      <div className="wrap demobar-inner">
        <label className="small muted" htmlFor="role">
          Viewing as
        </label>
        <select
          id="role"
          value={role}
          onChange={(e) => {
            setRole(e.target.value as Role);
            go("#/");
          }}
        >
          {ROLES.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}, {r.title.toLowerCase()}
            </option>
          ))}
        </select>
        <span className="demobar-gap" />
        <span className="small muted">Demo{s.data ? `, ${fmtDate(s.data.today)}` : ""}</span>
        <button
          disabled={busy}
          onClick={() =>
            run(async () => {
              const r = await post<{ person_id: number }>("/api/simulate/new-result");
              setMsg("A new cholesterol result arrived and was flagged.");
              setRole("clinician");
              go(`#/patient/${r.person_id}`);
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
              setMsg(`Two weeks later: ${tell(r)}`);
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
              setRole("clinician");
              go("#/");
            })
          }
        >
          Reset
        </button>
        {story.length > 0 && (
          <button className="ghost" aria-expanded={open} onClick={() => setOpen(!open)}>
            Demo story, {done} of {story.length}
          </button>
        )}
      </div>
      {(msg || open) && (
        <div className="wrap demobar-more">
          {msg && <p className="small">{msg}</p>}
          {open && (
            <ol className="story small">
              {story.map((x) => (
                <li key={x.step} className={x.done ? "done" : x === next ? "next" : ""}>
                  {x.done ? "Done: " : x === next ? "Next: " : ""}
                  {x.step}
                  {x === next && <span className="muted"> (as {ROLES.find((r) => r.id === x.role)?.title.toLowerCase()})</span>}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
