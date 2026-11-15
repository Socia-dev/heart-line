import { useEffect, useRef, useState } from "react";
import { post, useApi } from "../api";
import { DlcnTable } from "../screens/Try";
import WhyChart, { Why } from "./WhyChart";

type Scored = {
  prob: number;
  band: string;
  flagged: boolean;
  dlcn: { total: number; band: string; items: { group: string; reason: string; points: number }[] };
  why: Why;
};
type Inputs = { ldl: number | null; age: number; statin: string; early_cad: boolean; xanthoma: boolean; arcus: boolean; fhx_cad: boolean; fhx_ldl: boolean; premature_age: number };
type Explained = Scored & { inputs: Inputs };

const TOGGLES: [keyof Inputs, string][] = [
  ["early_cad", "Early heart disease"],
  ["xanthoma", "Tendon xanthomas"],
  ["arcus", "Corneal arcus"],
  ["fhx_cad", "Family history of early heart disease in the chart"],
  ["fhx_ldl", "Family history of high cholesterol in the chart"],
];

// Why the model flagged this person, with the standard score beside it, and a what-if panel that
// rescored live. The what-if never touches the record.
export default function WhyCard({ pid, band, bandRate }: { pid: number; band: string; bandRate: number | null }) {
  const { data } = useApi<Explained>(`/api/patients/${pid}/explain`);
  const [open, setOpen] = useState(false);
  const [vals, setVals] = useState<Inputs | null>(null);
  const [alt, setAlt] = useState<Scored | null>(null);
  const timer = useRef<number>();

  useEffect(() => {
    if (data && !vals) setVals(data.inputs);
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const changedFromReal = !!(data && vals && JSON.stringify(vals) !== JSON.stringify(data.inputs));
  useEffect(() => {
    if (!open || !vals || !changedFromReal) {
      setAlt(null);
      return;
    }
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      try {
        setAlt(await post<Scored>("/api/score", { person_id: pid, overrides: vals }));
      } catch {
        /* keep the last good score on screen */
      }
    }, 150);
    return () => window.clearTimeout(timer.current);
  }, [vals, open]); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = alt ?? data;
  const set = (k: keyof Inputs, v: unknown) => vals && setVals({ ...vals, [k]: v });
  const reset = () => data && setVals(data.inputs);

  return (
    <section className="card rise" style={{ "--d": "80ms" } as React.CSSProperties}>
      <div className="spread" style={{ alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Why flagged</h2>
        <button className={open ? "" : "primary-outline"} onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Close what if" : "What if?"}
        </button>
      </div>
      {!shown ? (
        <div className="skeleton" style={{ width: "70%", marginTop: 16 }} />
      ) : (
        <div className="grid g2" style={{ marginTop: 12 }}>
          <div>
            <div className="small muted">Heart Line model, added by this tool</div>
            <div className="band big">{alt ? (alt.flagged ? `${alt.band} FH` : "Would not be flagged") : `${band} FH`}</div>
            <WhyChart why={shown.why} />
            <p className="small muted" style={{ marginTop: 8 }}>
              Each bar is how much one fact pushed the model's score up or down for this person.{" "}
              {!alt && bandRate != null && `About ${Math.round(bandRate * 10)} in 10 people rated ${band.toLowerCase()} had FH, in synthetic data. `}A
              suggestion, not a diagnosis.
            </p>
          </div>
          <div>
            <div className="small muted">DLCN, the standard clinical score</div>
            <div className="band big">
              {shown.dlcn.total} <span className="small">{shown.dlcn.band.toLowerCase()}</span>
            </div>
            <DlcnTable items={shown.dlcn.items} />
            <p className="small muted" style={{ marginTop: 8 }}>
              From what is written in this chart. Compare: the model also reads close relatives' records.
            </p>
          </div>
        </div>
      )}

      {open && vals && (
        <div className="whatif rise">
          <div className="spread" style={{ alignItems: "center" }}>
            <strong>What if? Exploration only. The record does not change.</strong>
            <button className="link" onClick={reset} disabled={!changedFromReal}>
              Back to the real record
            </button>
          </div>
          <div className="grid g2" style={{ marginTop: 12 }}>
            <div className="sliders" style={{ marginTop: 0 }}>
              <label className="slider">
                <span>
                  Untreated LDL <strong>{vals.ldl?.toFixed(1) ?? "none"} mmol/L</strong>
                </span>
                <input type="range" min={1} max={15} step={0.1} value={vals.ldl ?? 3} onChange={(e) => set("ldl", Number(e.target.value))} />
              </label>
              <label className="slider">
                <span>
                  Age <strong>{vals.age}</strong>
                </span>
                <input type="range" min={18} max={90} step={1} value={vals.age} onChange={(e) => set("age", Number(e.target.value))} />
              </label>
              <label className="slider">
                <span>Statin</span>
                <select value={vals.statin} onChange={(e) => set("statin", e.target.value)}>
                  <option value="none">None</option>
                  <option value="moderate">Moderate intensity</option>
                  <option value="high">High intensity</option>
                </select>
              </label>
            </div>
            <fieldset className="checks">
              {TOGGLES.map(([k, l]) => (
                <label key={k}>
                  <input type="checkbox" checked={!!vals[k]} onChange={(e) => set(k, e.target.checked)} /> {l}
                </label>
              ))}
            </fieldset>
          </div>
        </div>
      )}
    </section>
  );
}
