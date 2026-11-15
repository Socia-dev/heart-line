import { useState } from "react";
import { ApiError, ROLES, Role, changed, fmtDate, go, post, setRole, useRole } from "../api";
import { describe } from "./State";

export type GuideState = {
  step: "start" | "review" | "wait_test" | "consent" | "send" | "relative" | "wait_family" | "found" | "stopped";
  person_id: number | null;
  invite_token: string | null;
  found_person_id: number | null;
  today: string;
};

const ORDER = ["review", "wait_test", "consent", "send", "relative", "wait_family", "found", "overview"];
const WHO: Record<string, string> = {
  clinician: "You are Dr. Layla, a lipid clinician.",
  coordinator: "You are Omar, the family coordinator.",
  lead: "You are Dr. Saeed, the programme lead.",
  relative: "You are an invited relative, on your phone.",
};

type Step = {
  role?: Role; // the member of staff this step belongs to
  page?: string; // where it happens
  who?: string;
  text: string; // what to do, once you are in the right place
  before?: string; // what to say before switching person or page
  open?: string; // button that takes you there
  time?: boolean; // the step is "two weeks pass"
};

function stepFor(g: GuideState, final: boolean): Step {
  const patient = `#/patient/${g.person_id}`;
  if (final)
    return {
      role: "lead",
      page: "#/",
      before: "Last, the view from above.",
      open: "Continue as Dr. Saeed, the programme lead",
      text: "No patient names here. A year of the programme, with and without family testing. That is the whole demo.",
    };
  switch (g.step) {
    case "review":
      return {
        role: "clinician",
        page: patient,
        open: "Open the flagged patient",
        text: "A cholesterol result just came in and Heart Line flagged it. Read why on the right, then press Order genetic test.",
      };
    case "wait_test":
      return { text: "The genetic test is with the lab.", time: true };
    case "consent":
      return {
        role: "clinician",
        page: patient,
        open: "Open the patient",
        text: "The test confirmed it. Now ask about his family: untick anyone he wants left out, then press Patient agrees.",
      };
    case "send":
      return {
        role: "coordinator",
        page: patient,
        before: "The patient agreed. Contacting relatives is a different person's job.",
        open: "Continue as Omar, the family coordinator",
        text: "Check who gets which message. Children go to their Well-Child Visit instead. Then press Send.",
      };
    case "relative":
      return {
        page: `#/invite/${g.invite_token}`,
        who: WHO.relative,
        before: "The invitations are out. See what a relative receives.",
        open: "Open a relative's phone",
        text: "The message never says who it came from or why. Pick any answer. English is at the top of the phone.",
      };
    case "wait_family":
      return { text: "Relatives are replying and getting tested.", time: true };
    case "found":
      return {
        role: "clinician",
        page: g.found_person_id ? `#/patient/${g.found_person_id}` : "#/",
        before: g.found_person_id ? "A relative tested positive." : "The relatives who came were all clear.",
        open: g.found_person_id ? "Continue as that relative's clinician" : "Continue as Dr. Layla",
        text: g.found_person_id
          ? "He was found through his family, and now his own clinician asks about his family. That is how one result reaches a whole family."
          : "Nobody new was found this time.",
      };
    case "stopped":
      return { text: "This case was closed, or the patient declined. Nothing was sent to anyone. Restart to try the other path." };
    default:
      return { text: "A new cholesterol result is about to arrive." };
  }
}

const here = (page: string) => (window.location.hash || "#/") === page;

// The guided demo: one instruction at a time, and one button when the next move is not on the page itself.
export default function Guide({ g, final, setFinal, onFree }: { g: GuideState; final: boolean; setFinal: (b: boolean) => void; onFree: () => void }) {
  const role = useRole();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const s = stepFor(g, final);
  const n = final ? ORDER.length : ORDER.indexOf(g.step) + 1;
  const inPlace = (!s.role || s.role === role) && (!s.page || here(s.page));

  async function run(f: () => Promise<unknown>) {
    setBusy(true);
    setErr(null);
    try {
      await f();
      changed();
    } catch (e) {
      const d = describe(e as ApiError);
      setErr(`${d.title}. ${d.help}`);
    } finally {
      setBusy(false);
    }
  }
  const start = () =>
    run(async () => {
      setFinal(false);
      await startDemo();
    });
  const restart = () =>
    run(async () => {
      await post("/api/reset");
      setFinal(false);
      setRole("clinician");
      go("#/");
    });
  const arrive = () => {
    if (s.role) setRole(s.role);
    if (s.page) go(s.page);
    changed();
  };

  let button = null;
  if (g.step === "start") button = { label: "Start: a new lab result arrives", act: start };
  else if (s.time) button = { label: "Two weeks pass", act: () => run(() => post("/api/simulate/advance", { weeks: 2 })) };
  else if (!inPlace && s.open) button = { label: s.open, act: arrive };
  else if (g.step === "found" && !final) button = { label: "Next: the big picture", act: () => setFinal(true) };
  else if (g.step === "relative" && inPlace) button = { label: "Skip: two weeks pass", act: () => run(() => post("/api/simulate/advance", { weeks: 2 })), quiet: true };

  const who = inPlace ? s.who ?? (s.role ? WHO[s.role] : null) : null;
  return (
    <div className="guide" role="region" aria-label="Guided demo">
      <div className="wrap guide-inner">
        <div className="guide-text">
          <div className="small muted">
            Guided demo{n > 0 ? `, step ${n} of ${ORDER.length}` : ""}. {fmtDate(g.today)}
          </div>
          <p>
            {who && <strong>{who} </strong>}
            {inPlace ? s.text : s.before ?? s.text}
          </p>
          {err && <p className="small">{err}</p>}
        </div>
        <div className="guide-actions">
          {button && (
            <button className={"quiet" in button ? "" : "primary"} disabled={busy} onClick={button.act}>
              {busy ? "Working" : button.label}
            </button>
          )}
          <div className="row small">
            <button className="link" disabled={busy} onClick={restart}>
              Restart
            </button>
            <button className="link" onClick={onFree}>
              Explore on my own
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export const roleName = (r: Role) => ROLES.find((x) => x.id === r)!;

export async function startDemo() {
  const r = await post<{ person_id: number }>("/api/simulate/new-result");
  setRole("clinician");
  go(`#/patient/${r.person_id}`);
}
