// How Heart Line works, as one picture: who does what, in what order, and where the chain loops.
// Lanes are people; time runs left to right. Positions are computed from the two lists below.

const LANES = ["Heart Line", "Lipid clinician", "Patient", "Family coordinator", "Relative", "Well-Child nurse"];

type Step = { id: string; lane: number; col: number; text: string; strong?: boolean };
const STEPS: Step[] = [
  { id: "flag", lane: 0, col: 0, text: "A cholesterol result arrives. Heart Line flags likely FH, with reasons." },
  { id: "review", lane: 1, col: 1, text: "The clinician reviews the flag and orders a genetic test." },
  { id: "ask", lane: 1, col: 2, text: "Confirmed. The clinician asks the patient about family testing." },
  { id: "consent", lane: 2, col: 3, text: "The patient agrees, and can leave any relative out.", strong: true },
  { id: "send", lane: 3, col: 4, text: "The coordinator checks each recipient and message, then sends." },
  { id: "adult", lane: 4, col: 5, text: "Adult relatives answer on their phone and get a free test." },
  { id: "child", lane: 5, col: 5, text: "Children are tested at their next Well-Child Visit." },
  { id: "found", lane: 4, col: 6, text: "A relative found with FH goes to their own clinician." },
];
const LINKS: [string, string][] = [
  ["flag", "review"],
  ["review", "ask"],
  ["ask", "consent"],
  ["consent", "send"],
  ["send", "adult"],
  ["send", "child"],
  ["adult", "found"],
];

const LABEL = 128; // lane name column
const PITCH = 136; // column to column
const CARD_W = 124;
const ROW = 112;
const CARD_H = 96;
const TOP = 36;
const W = LABEL + 7 * PITCH;
const H = TOP + LANES.length * ROW;

const left = (s: Step) => LABEL + s.col * PITCH + (PITCH - CARD_W) / 2;
const top = (s: Step) => TOP + s.lane * ROW + (ROW - CARD_H) / 2;
const midY = (s: Step) => top(s) + CARD_H / 2;
const by = (id: string) => STEPS.find((s) => s.id === id)!;

function path(a: Step, b: Step) {
  const x1 = left(a) + CARD_W;
  const x2 = left(b);
  if (a.lane === b.lane) return `M${x1},${midY(a)} H${x2}`;
  const xm = x2 - 7; // turn just before the next step, clear of the consent line
  return `M${x1},${midY(a)} H${xm} V${midY(b)} H${x2}`;
}

export default function Flow() {
  const found = by("found");
  const ask = by("ask");
  const gateX = LABEL + 4 * PITCH; // between the patient's answer and the coordinator's send
  // The loop: from a relative who is found, back up to "asks about family testing", for their own family.
  const loopX = left(found) + CARD_W / 2;
  const loop = `M${loopX},${top(found)} V${midY(ask)} H${left(ask) + CARD_W}`;
  return (
    <div className="table-wrap">
      <div className="flow" style={{ width: W, height: H }} role="img" aria-label="How Heart Line works, step by step">
        {LANES.map((name, i) => (
          <div key={name} className={`flow-lane ${i % 2 ? "" : "alt"}`} style={{ top: TOP + i * ROW, height: ROW }}>
            <span>{name}</span>
          </div>
        ))}
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
          <defs>
            <marker id="flow-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="#70666a" />
            </marker>
            <marker id="flow-arrow-red" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="#9f1239" />
            </marker>
          </defs>
          <line x1={gateX} x2={gateX} y1={TOP} y2={H} stroke="#70666a" strokeDasharray="4 4" />
          {LINKS.map(([a, b]) => (
            <path key={a + b} d={path(by(a), by(b))} fill="none" stroke="#70666a" strokeWidth="1.5" markerEnd="url(#flow-arrow)" />
          ))}
          <path d={loop} fill="none" stroke="#9f1239" strokeWidth="2" markerEnd="url(#flow-arrow-red)" />
        </svg>
        <p className="flow-note" style={{ left: gateX + 10, top: TOP + 8, width: 3 * PITCH - 20 }}>
          Nothing is sent to anyone before this line. It takes a confirmed result and the patient's agreement to cross it.
        </p>
        <p className="flow-note red" style={{ left: left(ask) + CARD_W + 16, top: midY(ask) - 44, width: 3 * PITCH + 40 }}>
          Then the same steps start again for that relative's own family. This is how one result reaches a whole family.
        </p>
        {STEPS.map((s) => (
          <div key={s.id} className={`flow-step ${s.strong ? "strong" : ""}`} style={{ left: left(s), top: top(s), width: CARD_W, height: CARD_H }}>
            {s.text}
          </div>
        ))}
      </div>
    </div>
  );
}
