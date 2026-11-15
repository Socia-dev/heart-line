export type TreeNode = {
  id: number;
  given: string;
  name: string;
  relation: string;
  generation: number;
  status: string;
  age: number;
  deceased: boolean;
  mother_id: number | null;
  father_id: number | null;
  first_degree?: boolean;
};

// A few colours. The node's third line carries the finer detail (booked, Well-Child due).
const GROUPS = {
  index: { label: "This patient", fill: "var(--s-index)", ink: "#fff" },
  fh: { label: "Has FH", fill: "var(--s-confirmed)" },
  waiting: { label: "Invited, waiting", fill: "var(--s-invited)" },
  replied: { label: "Replied", fill: "var(--s-wellchild)" },
  clear: { label: "Tested clear", fill: "var(--s-negative)" },
  none: { label: "Not contacted", fill: "var(--s-unknown)", border: true },
  deceased: { label: "Deceased", fill: "var(--s-deceased)", ink: "#fff" },
} as const;
type Group = { label: string; fill: string; ink?: string; border?: boolean };

export const STATUS: Record<string, Group & { group: keyof typeof GROUPS }> = {
  index: { ...GROUPS.index, group: "index" },
  confirmed: { ...GROUPS.fh, label: "Has FH", group: "fh" },
  assessing: { ...GROUPS.waiting, label: "Being assessed", group: "waiting" },
  invited: { ...GROUPS.waiting, label: "Invited", group: "waiting" },
  booked: { ...GROUPS.waiting, label: "Check booked", group: "waiting" },
  call_requested: { ...GROUPS.waiting, label: "Asked for a call", group: "waiting" },
  wellchild: { ...GROUPS.waiting, label: "Well-Child test due", group: "waiting" },
  replied: { ...GROUPS.replied, label: "Replied", group: "replied" },
  already_tested: { ...GROUPS.replied, label: "Already tested", group: "replied" },
  negative: { ...GROUPS.clear, label: "Tested clear", group: "clear" },
  declined: { ...GROUPS.none, label: "Declined", group: "none" },
  no_response: { ...GROUPS.none, label: "No reply", group: "none" },
  unknown: { ...GROUPS.none, label: "Not contacted", group: "none" },
  deceased: { ...GROUPS.deceased, group: "deceased" },
};

const SLOT = 128;
const NW = 116;
const NH = 62;
const ROW = 112;

type Placed = { key: string; x: number; gen: number; node?: TreeNode; label?: [string, string, string]; status: string; parentX?: number };

export default function FamilyTree({ nodes, abroad, onOpen }: { nodes: TreeNode[]; abroad: number; onOpen: (id: number) => void }) {
  const index = nodes.find((n) => n.status === "index");
  if (!index) return null;
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const kidsOf = (id: number, gen: number) =>
    nodes.filter((n) => n.generation === gen && (n.mother_id === id || n.father_id === id)).sort((a, b) => b.age - a.age);

  const placed: Placed[] = [];
  const pos = new Map<number, number>();
  const put = (n: TreeNode, x: number, parentX?: number) => {
    placed.push({ key: String(n.id), x, gen: n.generation, node: n, status: n.status, parentX });
    pos.set(n.id, x);
  };

  // Generation 0: the index patient and full siblings by age, with the spouse beside the index.
  const row0 = nodes
    .filter((n) => n.generation === 0 && (n.id === index.id || ["Brother", "Sister"].includes(n.relation)))
    .sort((a, b) => b.age - a.age);
  const spouses = nodes.filter((n) => n.generation === 0 && ["Wife", "Husband"].includes(n.relation));
  const quiet = (s: string) => s === "unknown" || s === "deceased";

  let cursor = 0;
  for (const m of row0) {
    let kids = kidsOf(m.id, 1);
    const isIndex = m.id === index.id;
    const collapse = !isIndex && m.status !== "confirmed" && kids.length > 0 && kids.every((k) => quiet(k.status));
    const widths = collapse ? [1] : kids.map((k) => Math.max(1, kidsOf(k.id, 2).length));
    const span = Math.max(isIndex && spouses.length ? 1 + spouses.length : 1, widths.reduce((a, b) => a + b, 0));
    const center = cursor + span / 2;
    const mx = isIndex && spouses.length ? center - 0.5 * spouses.length : center;
    const coupleX = isIndex && spouses.length ? center : mx;
    put(m, mx);
    if (isIndex) spouses.forEach((s, i) => put(s, mx + 1 + i));
    if (collapse) {
      placed.push({
        key: `c${m.id}`,
        x: center,
        gen: 1,
        status: "unknown",
        label: [`${kids.length} ${kids.length === 1 ? "child" : "children"}`, `of ${m.given}`, "Not contacted"],
        parentX: mx,
      });
    } else {
      let c = cursor + (span - widths.reduce((a, b) => a + b, 0)) / 2;
      kids.forEach((k, i) => {
        const kx = c + widths[i] / 2;
        put(k, kx, coupleX);
        const gk = kidsOf(k.id, 2);
        gk.forEach((g, j) => put(g, c + j + 0.5 + (widths[i] - gk.length) / 2, kx));
        c += widths[i];
      });
      kids = [];
    }
    cursor += span;
  }

  // Parents above the siblings, grandparents above each parent.
  const sibXs = row0.map((m) => pos.get(m.id)!);
  const c0 = (Math.min(...sibXs) + Math.max(...sibXs)) / 2;
  const mother = index.mother_id ? byId.get(index.mother_id) : undefined;
  const father = index.father_id ? byId.get(index.father_id) : undefined;
  const parentsX = mother && father ? c0 : c0;
  if (mother) put(mother, father ? c0 - 0.5 : c0);
  if (father) put(father, mother ? c0 + 0.5 : c0);
  for (const [par, side] of [
    [mother, -1],
    [father, 1],
  ] as const) {
    if (!par) continue;
    const px = pos.get(par.id)!;
    const gps = nodes.filter((n) => n.generation === -2 && (n.id === par.mother_id || n.id === par.father_id));
    gps.forEach((g, i) => put(g, gps.length === 2 ? px + (side < 0 ? i - 1 : i) : px, undefined));
  }
  for (const p of placed) {
    if (p.gen === 0 && row0.some((m) => String(m.id) === p.key) && (mother || father)) p.parentX = parentsX;
    if (p.gen === -1 && p.node) {
      const gp = placed.filter((g) => g.gen === -2 && g.node && (g.node.id === p.node!.mother_id || g.node.id === p.node!.father_id));
      if (gp.length) p.parentX = gp.reduce((a, g) => a + g.x, 0) / gp.length;
    }
  }

  const gens = placed.map((p) => p.gen);
  const gMin = Math.min(...gens);
  const xs = placed.map((p) => p.x);
  const xMin = Math.min(...xs) - 0.5;
  const xMax = Math.max(...xs) + 0.5;
  const W = (xMax - xMin) * SLOT + 8;
  const H = (Math.max(...gens) - gMin + 1) * ROW - (ROW - NH) + 8;
  const cx = (x: number) => (x - xMin) * SLOT + 4;
  const cy = (g: number) => (g - gMin) * ROW + 4;

  return (
    <>
    <div className="tree-wrap">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Family tree">
        {placed
          .filter((p) => p.parentX !== undefined)
          .map((p) => {
            const x1 = cx(p.x);
            const y1 = cy(p.gen);
            const x2 = cx(p.parentX!);
            const y2 = cy(p.gen - 1) + NH;
            const ym = (y1 + y2) / 2;
            return <path key={`e${p.key}`} d={`M${x1},${y1} V${ym} H${x2} V${y2}`} fill="none" stroke="#c9c4be" strokeWidth="1.5" />;
          })}
        {placed.map((p) => {
          const st = STATUS[p.status] ?? STATUS.unknown;
          const x = cx(p.x) - NW / 2;
          const y = cy(p.gen);
          const lines: [string, string, string] = p.label ?? [
            p.node!.given,
            `${p.node!.relation}${p.node!.deceased ? "" : `, ${p.node!.age}`}`,
            st.label,
          ];
          const clickable = !!p.node && p.status !== "index";
          return (
            <g key={p.key} className={clickable ? "tree-node" : undefined} onClick={clickable ? () => onOpen(p.node!.id) : undefined}>
              <title>{p.node ? `${p.node.name}: ${st.label}` : lines.join(" ")}</title>
              <rect
                x={x}
                y={y}
                width={NW}
                height={NH}
                rx={10}
                fill={st.fill}
                stroke={st.border ? "#c9c4be" : "transparent"}
              />
              <text x={x + NW / 2} y={y + 21} textAnchor="middle" fontSize="13" fontWeight="650" fill={st.ink ?? "#1c1917"}>
                {lines[0].length > 15 ? lines[0].slice(0, 14) + "." : lines[0]}
              </text>
              <text x={x + NW / 2} y={y + 37} textAnchor="middle" fontSize="11.5" fill={st.ink ?? "#5f5a55"}>
                {lines[1]}
              </text>
              <text x={x + NW / 2} y={y + 53} textAnchor="middle" fontSize="11" fill={st.ink ?? "#5f5a55"}>
                {lines[2]}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
    {abroad > 0 && (
      <p className="small muted" style={{ marginTop: 8 }}>
        {abroad} more relatives live abroad. They get a family letter the patient can share.
      </p>
    )}
    </>
  );
}

export function Legend({ nodes }: { nodes: TreeNode[] }) {
  const present = new Set(nodes.map((n) => (STATUS[n.status] ?? STATUS.unknown).group));
  return (
    <div className="legend">
      {Object.entries(GROUPS)
        .filter(([k]) => present.has(k as keyof typeof GROUPS))
        .map(([k, g]) => (
          <span key={k}>
            <i style={{ background: g.fill }} />
            {g.label}
          </span>
        ))}
    </div>
  );
}
