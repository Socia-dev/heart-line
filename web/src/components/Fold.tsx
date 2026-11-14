import { ReactNode } from "react";

// A section that starts closed, for detail most viewers don't need.
export default function Fold({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <details className="fold">
      <summary>
        {title} {note && <span className="muted">{note}</span>}
      </summary>
      <div className="fold-body">{children}</div>
    </details>
  );
}
