import { Component, ReactNode, useEffect, useState } from "react";
import { ROLES, Role, changed, useApi, useRole } from "./api";
import DemoBar from "./components/DemoBar";
import Guide, { GuideState, startDemo } from "./components/Guide";
import About from "./screens/About";
import Audit from "./screens/Audit";
import Children from "./screens/Children";
import Families from "./screens/Families";
import Home from "./screens/Home";
import Invite, { InvitePreview } from "./screens/Invite";
import Model from "./screens/Model";
import Patient from "./screens/Patient";
import Programme from "./screens/Programme";
import Welcome from "./screens/Welcome";

function useRoute() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const f = () => {
      setHash(window.location.hash || "#/");
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return hash.replace(/^#/, "").split("?")[0].split("/").filter(Boolean);
}

// Each role has its own home and only the pages it needs. Shown when exploring freely.
const NAV: Record<Role, [string, string][]> = {
  clinician: [["", "My patients"]],
  coordinator: [
    ["", "My families"],
    ["families", "Invitations"],
    ["children", "Children"],
  ],
  nurse: [["", "Children due"]],
  lead: [
    ["", "Programme"],
    ["model", "Can we trust the flags?"],
    ["audit", "Audit"],
  ],
};

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="wrap main">
        <div className="card state">
          <h2>Something went wrong on this page</h2>
          <p className="muted">Nothing was changed. Reload to carry on.</p>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      </div>
    );
  }
}

function readMode(): "guide" | "free" {
  try {
    return localStorage.getItem("heartline-mode") === "free" ? "free" : "guide";
  } catch {
    return "guide";
  }
}

export default function App() {
  const [section, arg] = useRoute();
  const role = useRole();
  const [mode, setModeState] = useState(readMode);
  const [final, setFinal] = useState(false);
  const [starting, setStarting] = useState(false);
  const guide = useApi<GuideState>("/api/demo/guide");
  const setMode = (m: "guide" | "free") => {
    setModeState(m);
    try {
      localStorage.setItem("heartline-mode", m);
    } catch {
      /* ignore */
    }
  };

  // The invited relative's page stands alone: no staff navigation, no demo controls.
  if (section === "i") {
    return (
      <Boundary>
        <div className="banner" role="note">
          <strong>Demo on synthetic data.</strong> <span>No real message was sent.</span>
        </div>
        <main className="relative-page">
          <Invite token={arg} />
        </main>
      </Boundary>
    );
  }

  const guided = mode === "guide";
  const g = guide.data;
  const welcome = guided && g?.step === "start" && !section;
  const start = async () => {
    setStarting(true);
    try {
      await startDemo();
      changed();
    } finally {
      setStarting(false);
    }
  };

  let screen: ReactNode;
  if (welcome) screen = <Welcome start={start} busy={starting} free={() => setMode("free")} />;
  else if (section === "patient") screen = <Patient id={Number(arg)} />;
  else if (section === "invite") screen = <InvitePreview token={arg} />;
  else if (section === "about") screen = <About />;
  else if (section === "model") screen = <Model />;
  else if (section === "families" && role === "coordinator") screen = <Families />;
  else if (section === "children" && role === "coordinator") screen = <Children />;
  else if (section === "audit" && role === "lead") screen = <Audit />;
  else if (role === "nurse") screen = <Children />;
  else if (role === "lead") screen = <Programme />;
  else screen = <Home />;

  const active = ["families", "children", "model", "audit"].includes(section ?? "") ? section : section === "about" ? "none" : "";
  const me = ROLES.find((r) => r.id === role)!;
  return (
    <Boundary>
      <header className="top">
        <div className="wrap top-inner">
          <a className="brand" href="#/">
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <path
                fill="currentColor"
                d="M12 21s-7.5-4.6-9.6-9.3C.9 8.3 3 4.5 6.7 4.5c2.1 0 3.6 1.1 4.3 2.4.7-1.3 2.2-2.4 4.3-2.4 3.7 0 5.8 3.8 4.3 7.2C19.5 16.4 12 21 12 21z"
              />
            </svg>
            Heart Line
          </a>
          <nav className="nav">
            {!guided &&
              NAV[role].map(([href, label]) => (
                <a key={href} href={`#/${href}`} className={active === href ? "on" : ""}>
                  {label}
                </a>
              ))}
            <a href="#/about" className={section === "about" ? "on" : ""}>
              How it works
            </a>
          </nav>
          <span className="today">{guided ? "Synthetic data. Not for clinical use." : `Viewing as ${me.name}, ${me.title.toLowerCase()}. Synthetic data.`}</span>
        </div>
      </header>
      {guided ? (
        g && !welcome && <Guide g={g} final={final} setFinal={setFinal} onFree={() => setMode("free")} />
      ) : (
        <DemoBar onGuide={() => setMode("guide")} />
      )}
      <main className={`wrap main ${guided ? "guided" : ""}`} key={role}>
        {screen}
      </main>
    </Boundary>
  );
}
