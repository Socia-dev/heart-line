import { useState } from "react";
import { ApiError, post } from "../api";
import { Pipeline, Stage } from "../components/Pipeline";
import { ActionError } from "../components/State";
import WhyChart, { Why } from "../components/WhyChart";

type Result = {
  prob: number;
  calibrated: number;
  band: string;
  flagged: boolean;
  threshold: number;
  dlcn: { total: number; band: string; items: { group: string; reason: string; points: number }[] };
  why: Why;
  stages: Stage[];
};
type Row = { row: number; input: Record<string, string>; result?: Result; error?: string };

const MG = { ldl: 38.67, tc: 38.67, hdl: 38.67, tg: 88.57 } as const;
const DEFAULTS = { ldl: "6.5", tc: "8.5", hdl: "1.2", tg: "1.5" };
const FLAGS: [string, string][] = [
  ["early_cad", "Heart disease before 55 (men) or 60 (women)"],
  ["xanthoma", "Tendon xanthomas"],
  ["arcus", "Corneal arcus"],
  ["fhx_cad", "A parent, brother, sister or child had early heart disease"],
  ["fhx_ldl", "A parent, brother, sister or child has very high cholesterol"],
];

// Anyone can type in a cholesterol result, or upload a file of them, and see exactly how Heart Line scores it.
export default function Try() {
  const [unit, setUnit] = useState<"mmol" | "mgdl">("mmol");
  const [panel, setPanel] = useState<Record<string, string>>(DEFAULTS);
  const [age, setAge] = useState("38");
  const [sex, setSex] = useState("F");
  const [statin, setStatin] = useState("none");
  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const [res, setRes] = useState<Result | null>(null);
  const [run, setRun] = useState(0);
  const [shown, setShown] = useState(false);

  const [rows, setRows] = useState<Row[] | null>(null);
  const [csvErr, setCsvErr] = useState<ApiError | null>(null);
  const [sort, setSort] = useState<{ key: string; up: boolean }>({ key: "score", up: false });
  const [picked, setPicked] = useState<Row | null>(null);

  function switchUnit(u: "mmol" | "mgdl") {
    if (u === unit) return;
    const next: Record<string, string> = {};
    for (const k of Object.keys(panel) as (keyof typeof MG)[]) {
      const v = parseFloat(panel[k]);
      next[k] = isNaN(v) ? panel[k] : u === "mgdl" ? String(Math.round(v * MG[k])) : (v / MG[k]).toFixed(1);
    }
    setPanel(next);
    setUnit(u);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setShown(false);
    try {
      const r = await post<Result>("/api/score", { panel: { ...panel, unit }, context: { age, sex, statin, ...flags } });
      setRes(r);
      setRun(run + 1);
    } catch (x) {
      setErr(x as ApiError);
      setRes(null);
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    setCsvErr(null);
    setPicked(null);
    try {
      const text = await file.text();
      const r = await post<{ rows: Row[] }>("/api/score/csv", { text, unit });
      setRows(r.rows);
    } catch (x) {
      setCsvErr(x as ApiError);
      setRows(null);
    }
  }

  const sorted = rows
    ? [...rows].sort((a, b) => {
        const v = (r: Row) =>
          sort.key === "row" ? r.row : sort.key === "ldl" ? parseFloat(r.input.ldl) || 0 : sort.key === "dlcn" ? r.result?.dlcn.total ?? -1 : r.result?.calibrated ?? -1;
        return (v(a) - v(b)) * (sort.up ? 1 : -1);
      })
    : [];
  const th = (key: string, label: string, num = false) => (
    <th className={num ? "num" : ""}>
      <button className="link sort" onClick={() => setSort({ key, up: sort.key === key ? !sort.up : false })} aria-sort={sort.key === key ? (sort.up ? "ascending" : "descending") : "none"}>
        {label}
        {sort.key === key ? (sort.up ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );

  return (
    <div className="stack">
      <div>
        <h1>Try your own numbers</h1>
        <p className="lede">Type in a cholesterol result and see exactly how Heart Line scores it, step by step.</p>
      </div>

      <div className="grid g2 try">
        <form className="card" onSubmit={submit} noValidate>
          <div className="spread" style={{ alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>One result</h2>
            <div className="tabs" role="group" aria-label="Units">
              <button type="button" className={unit === "mmol" ? "on" : ""} onClick={() => switchUnit("mmol")}>
                mmol/L
              </button>
              <button type="button" className={unit === "mgdl" ? "on" : ""} onClick={() => switchUnit("mgdl")}>
                mg/dL
              </button>
            </div>
          </div>
          <div className="fields">
            {(
              [
                ["ldl", "LDL cholesterol"],
                ["tc", "Total cholesterol"],
                ["hdl", "HDL cholesterol"],
                ["tg", "Triglycerides"],
              ] as const
            ).map(([k, l]) => (
              <label key={k}>
                <span>
                  {l}
                  {k === "ldl" ? "" : " (optional)"}
                </span>
                <input inputMode="decimal" value={panel[k] ?? ""} aria-invalid={err?.code === `bad_${k}`} onChange={(e) => setPanel({ ...panel, [k]: e.target.value })} />
              </label>
            ))}
            <label>
              <span>Age</span>
              <input inputMode="numeric" value={age} aria-invalid={err?.code === "bad_age"} onChange={(e) => setAge(e.target.value)} />
            </label>
            <label>
              <span>Sex</span>
              <select value={sex} onChange={(e) => setSex(e.target.value)}>
                <option value="F">Female</option>
                <option value="M">Male</option>
              </select>
            </label>
            <label className="wide-field">
              <span>Statin</span>
              <select value={statin} onChange={(e) => setStatin(e.target.value)}>
                <option value="none">Not on a statin</option>
                <option value="moderate">Moderate intensity</option>
                <option value="high">High intensity</option>
              </select>
            </label>
          </div>
          <fieldset className="checks" style={{ marginTop: 16 }}>
            <legend className="small muted">Tick anything that applies</legend>
            {FLAGS.map(([k, l]) => (
              <label key={k}>
                <input type="checkbox" checked={!!flags[k]} onChange={(e) => setFlags({ ...flags, [k]: e.target.checked })} /> {l}
              </label>
            ))}
          </fieldset>
          {err && <ActionError error={err} />}
          <div className="row" style={{ marginTop: 16 }}>
            <button className="primary" disabled={busy}>
              {busy ? "Scoring" : "Score this result"}
            </button>
            <span className="small muted">Nothing you type in is stored.</span>
          </div>
        </form>

        <section className="card" aria-live="polite">
          {!res ? (
            <>
              <h2>What happens</h2>
              <p className="muted">
                Your numbers go through the same seven steps as a real lab result: features are worked out, the model scores them, the standard DLCN score
                is added, and the result is checked against the cut-off.
              </p>
              <p className="small muted">
                Typed-in numbers have no family records to link, so this uses Heart Line's own-record model. Scores are on a model trained on synthetic
                data.
              </p>
            </>
          ) : (
            <>
              <Pipeline key={run} stages={res.stages} onDone={() => setShown(true)} />
              {shown && (
                <div className="rise" style={{ marginTop: 20 }}>
                  <Outcome r={res} />
                </div>
              )}
            </>
          )}
        </section>
      </div>

      <section className="card">
        <div className="spread">
          <h2 style={{ margin: 0 }}>Many results at once</h2>
          <a href="/api/score/sample.csv" download>
            Download a sample file
          </a>
        </div>
        <p className="muted">
          A CSV file with one row per result. Only <strong>ldl</strong> is required; columns can be tc, hdl, tg, age, sex, statin (none, moderate, high) and
          yes or no for early_cad, xanthoma, arcus, fhx_cad and fhx_ldl. Values in {unit === "mmol" ? "mmol/L" : "mg/dL"}, as set above. Up to 500 rows.
          Nothing is stored.
        </p>
        <label className="file">
          <input type="file" accept=".csv,text/csv" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </label>
        {csvErr && <ActionError error={csvErr} />}
        {rows && (
          <div className="table-wrap rise" style={{ marginTop: 16 }}>
            <p className="small muted">
              {rows.filter((r) => r.result).length} scored
              {rows.some((r) => r.error) ? `, ${rows.filter((r) => r.error).length} could not be read` : ""}. Select a row to see how it was scored.
            </p>
            <table>
              <thead>
                <tr>
                  {th("row", "Row", true)}
                  {th("ldl", "LDL", true)}
                  {th("score", "Rating")}
                  {th("dlcn", "DLCN", true)}
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr key={r.row} className={r.result ? "link" : ""} onClick={() => r.result && setPicked(r)} aria-selected={picked?.row === r.row}>
                    <td className="num">{r.row}</td>
                    <td className="num">{r.input.ldl}</td>
                    <td>{r.result ? <strong>{r.result.band}</strong> : <span className="muted">{r.error}</span>}</td>
                    <td className="num">{r.result ? `${r.result.dlcn.total}, ${r.result.dlcn.band.toLowerCase()}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {picked?.result && (
          <div className="quiet rise" style={{ marginTop: 16 }} key={picked.row}>
            <h3>Row {picked.row}</h3>
            <Pipeline stages={picked.result.stages} play={false} />
            <div style={{ marginTop: 16 }}>
              <Outcome r={picked.result} />
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function Outcome({ r }: { r: Result }) {
  return (
    <div className="grid g2">
      <div>
        <div className="small muted">Heart Line, own-record model</div>
        <div className="band big">{r.flagged ? `${r.band} FH` : "Not flagged"}</div>
        <WhyChart why={r.why} compact />
      </div>
      <div>
        <div className="small muted">DLCN, the standard clinical score</div>
        <div className="band big">
          {r.dlcn.total} <span className="small">{r.dlcn.band.toLowerCase()}</span>
        </div>
        <DlcnTable items={r.dlcn.items} />
      </div>
    </div>
  );
}

export function DlcnTable({ items }: { items: { group: string; reason: string; points: number }[] }) {
  if (!items.length) return <p className="small muted">No points from what was entered.</p>;
  return (
    <table className="small">
      <tbody>
        {items.map((it) => (
          <tr key={it.group}>
            <td>{it.reason}</td>
            <td className="num">{it.points}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
