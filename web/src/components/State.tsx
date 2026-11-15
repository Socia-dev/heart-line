import { ReactNode } from "react";
import { ApiError } from "../api";

// What to say for each refusal the server can send, and what the person can do about it.
const COPY: Record<string, { title: string; help: string }> = {
  offline: { title: "Can't reach Heart Line", help: "Check that the service is running on port 8010, then try again." },
  not_your_view: { title: "This page belongs to another role", help: "Switch role in the bar above, or go back to your own list." },
  wrong_role: { title: "Not a step for your role", help: "Hand it to the person named, or switch role in the bar above." },
  wrong_status: { title: "This step is no longer available", help: "The case has moved on. Reload to see where it is now." },
  no_consent: { title: "No consent yet", help: "The clinician needs to record the patient's agreement first." },
  already_started: { title: "Already sent", help: "Invitations for this family have gone out. Reload to see replies." },
  missing_reason: { title: "Choose a reason", help: "Pick the reason that fits best before closing." },
  invitation_closed: { title: "This invitation is closed", help: "It has been answered or has expired." },
  no_demo_patient: { title: "No demo patient left", help: "Use Reset in the demo bar to start again." },
  person_not_found: { title: "No such person", help: "Go back to your list." },
};

export function describe(e: ApiError) {
  return COPY[e.code] ?? { title: "That didn't work", help: e.message };
}

export function LoadError({ error, retry }: { error: ApiError; retry?: () => void }) {
  const c = describe(error);
  return (
    <div className="card state" role="alert">
      <h2>{c.title}</h2>
      <p className="muted">{c.help}</p>
      <div className="row">
        {retry && <button onClick={retry}>Try again</button>}
        <a href="#/">Back to my list</a>
      </div>
    </div>
  );
}

export function ActionError({ error }: { error: ApiError }) {
  const c = describe(error);
  return (
    <p className="error" role="alert">
      <strong>{c.title}.</strong> {c.help}
    </p>
  );
}

export function Loading({ rows = 4 }: { rows?: number }) {
  return (
    <div className="card" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <strong>{title}</strong>
      {children && <p className="muted" style={{ margin: "4px 0 0" }}>{children}</p>}
    </div>
  );
}
