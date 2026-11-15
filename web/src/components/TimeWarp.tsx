import { useEffect, useState } from "react";
import { changed, post } from "../api";
import { reduced } from "../motion";

type Advance = Record<string, number | string>;

// "Two weeks pass" as a short scene: the calendar runs forward, then what came back
// appears line by line. Click anywhere or wait to carry on.
let open: ((a: Advance) => void) | null = null;

export async function advanceTwoWeeks() {
  const r = await post<Advance>("/api/simulate/advance", { weeks: 2 });
  if (open) open(r);
  else changed();
  return r;
}

function lines(a: Advance): string[] {
  const out: string[] = [];
  const add = (n: number, one: string, many: string) => n > 0 && out.push(`${n} ${n === 1 ? one : many}`);
  add(Number(a.variants_found), "genetic result back: variant found", "genetic results back with a variant");
  if (Number(a.test_results) > Number(a.variants_found)) add(Number(a.test_results) - Number(a.variants_found), "genetic result back: no variant", "genetic results back with no variant");
  add(Number(a.tested), "relative came for a check", "relatives came for a check");
  add(Number(a.relatives_positive), "relative has FH", "relatives have FH");
  add(Number(a.wellchild_tested), "child tested at Well-Child", "children tested at Well-Child");
  add(Number(a.children_positive), "child has FH", "children have FH");
  add(Number(a.no_response), "invitation not answered", "invitations not answered");
  return out.length ? out : ["Nothing new came back."];
}

const day = (iso: string, plus: number) => {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + plus);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "long" });
};

export default function TimeWarp() {
  const [a, setA] = useState<Advance | null>(null);
  const [days, setDays] = useState(0);
  const [phase, setPhase] = useState<"run" | "show" | "out">("run");

  useEffect(() => {
    open = (r) => {
      setA(r);
      setDays(0);
      setPhase("run");
    };
    return () => {
      open = null;
    };
  }, []);

  useEffect(() => {
    if (!a) return;
    if (reduced()) {
      setDays(14);
      setPhase("show");
      changed();
      return;
    }
    let d = 0;
    const t = setInterval(() => {
      d += 1;
      setDays(d);
      if (d >= 14) {
        clearInterval(t);
        setPhase("show");
        changed(); // the page underneath updates while the results are read
      }
    }, 55);
    return () => clearInterval(t);
  }, [a]);

  useEffect(() => {
    if (phase !== "show" || !a) return;
    const t = setTimeout(close, 1400 + lines(a).length * 450);
    return () => clearTimeout(t);
  }, [phase, a]); // eslint-disable-line react-hooks/exhaustive-deps

  function close() {
    setPhase("out");
    setTimeout(() => setA(null), reduced() ? 0 : 200);
  }

  if (!a) return null;
  const from = String(a.from);
  return (
    <div className={`warp ${phase === "out" ? "leaving" : ""}`} onClick={close} role="status" aria-live="polite">
      <div className="warp-card">
        <div className="small muted">Two weeks pass</div>
        <div className="warp-date">{day(from, days)}</div>
        <div className="warp-track" aria-hidden="true">
          <span style={{ transform: `scaleX(${days / 14})` }} />
        </div>
        {phase !== "run" && (
          <ul className="warp-lines">
            {lines(a).map((l, i) => (
              <li key={l} className="rise" style={{ "--d": `${i * 220}ms` } as React.CSSProperties}>
                {l}
              </li>
            ))}
          </ul>
        )}
        {phase !== "run" && <div className="small muted warp-hint">Click to carry on</div>}
      </div>
    </div>
  );
}
