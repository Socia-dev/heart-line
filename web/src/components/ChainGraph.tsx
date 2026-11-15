import { useEffect, useRef } from "react";
import { go } from "../api";

export type ChainNode = { case_id: number; index_of: number | null; name: string; source: string; status: string; age: number; id: number; invited: number };

const NW = 168;
const NH = 52;
const COL = 220;
const ROW = 66;
const SOURCE: Record<string, string> = { detection: "Found by screening", cascade: "Found through a relative", wellchild: "Found at Well-Child" };

// Each detection case and everyone found through it, by generation of the chain. Links that are new
// since the last look draw themselves in, so each "two weeks pass" visibly grows the chain.
export default function ChainGraph({ nodes }: { nodes: ChainNode[] }) {
  const seen = useRef<Set<number> | null>(null);
  const fresh = (id: number) => seen.current !== null && !seen.current.has(id);
  useEffect(() => {
    seen.current = new Set(nodes.map((n) => n.case_id));
  }, [nodes]);

  const ids = new Set(nodes.map((n) => n.case_id));
  const kids = (id: number) => nodes.filter((n) => n.index_of === id);
  const roots = nodes.filter((n) => n.index_of == null || !ids.has(n.index_of));
  const at = new Map<number, { x: number; y: number }>();
  let row = 0;
  const place = (n: ChainNode, depth: number) => {
    const ks = kids(n.case_id);
    const start = row;
    ks.forEach((k) => place(k, depth + 1));
    if (!ks.length) row += 1;
    at.set(n.case_id, { x: depth, y: ks.length ? (start + row - 1) / 2 : row - 1 });
  };
  roots.forEach((r) => {
    place(r, 0);
    row += 0.4;
  });
  const depth = Math.max(0, ...[...at.values()].map((p) => p.x));
  const W = (depth + 1) * COL + 8;
  const H = Math.max(1, row) * ROW + 8;
  const px = (d: number) => 4 + d * COL;
  const py = (r: number) => 4 + r * ROW;

  return (
    <div className="table-wrap">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="How each case led to the next">
        {nodes
          .filter((n) => n.index_of != null && at.has(n.index_of))
          .map((n) => {
            const a = at.get(n.index_of!)!;
            const b = at.get(n.case_id)!;
            const x1 = px(a.x) + NW;
            const y1 = py(a.y) + NH / 2;
            const x2 = px(b.x);
            const y2 = py(b.y) + NH / 2;
            const xm = (x1 + x2) / 2;
            return (
              <path
                key={`l${n.case_id}`}
                className={fresh(n.case_id) || seen.current === null ? "draw" : ""}
                pathLength={1}
                d={`M${x1},${y1} H${xm} V${y2} H${x2}`}
                fill="none"
                stroke={n.source === "wellchild" ? "#b9cbe0" : "#9f1239"}
                strokeWidth="2"
              />
            );
          })}
        {nodes.map((n, i) => {
          const p = at.get(n.case_id);
          if (!p) return null;
          const root = n.index_of == null || !ids.has(n.index_of);
          return (
            <g
              key={n.case_id}
              className={`tree-node ${fresh(n.case_id) ? "tree-in" : seen.current === null ? "tree-in" : ""}`}
              style={{ "--d": seen.current === null ? `${p.x * 160 + i * 20}ms` : "500ms" } as React.CSSProperties}
              onClick={() => go(`#/patient/${n.id}`)}
            >
              <title>{`${n.name}: ${SOURCE[n.source]}`}</title>
              <rect x={px(p.x)} y={py(p.y)} width={NW} height={NH} rx={4} fill={root ? "#9f1239" : "#fff"} stroke={root ? "none" : "#d4d4d1"} />
              <text x={px(p.x) + 10} y={py(p.y) + 21} fontSize="13" fontWeight="700" fill={root ? "#fff" : "#1c1517"}>
                {n.name.length > 22 ? n.name.slice(0, 21) + "." : n.name}
              </text>
              <text x={px(p.x) + 10} y={py(p.y) + 39} fontSize="12" fill={root ? "#fde7ec" : "#5b5053"}>
                {root ? "Found by screening" : n.source === "wellchild" ? "Child, Well-Child" : `Found through family, ${n.age}`}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
