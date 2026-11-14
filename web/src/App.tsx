import { useEffect, useState } from "react";
import DemoBar from "./components/DemoBar";
import Overview from "./screens/Overview";
import Worklist from "./screens/Worklist";
import Patient from "./screens/Patient";
import Families from "./screens/Families";
import Invite from "./screens/Invite";
import WellChild from "./screens/WellChild";
import Model from "./screens/Model";
import Audit from "./screens/Audit";

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
  return hash.replace(/^#/, "").split("/").filter(Boolean);
}

const NAV = [
  ["", "Overview"],
  ["worklist", "Worklist"],
  ["families", "Families"],
  ["wellchild", "Children"],
  ["model", "Model"],
] as const;

export default function App() {
  const route = useRoute();
  const [section, arg] = route;

  let screen;
  switch (section) {
    case "worklist":
      screen = <Worklist />;
      break;
    case "patient":
      screen = <Patient id={Number(arg)} />;
      break;
    case "families":
      screen = <Families />;
      break;
    case "invite":
      screen = <Invite token={arg} />;
      break;
    case "wellchild":
      screen = <WellChild />;
      break;
    case "model":
      screen = <Model />;
      break;
    case "audit":
      screen = <Audit />;
      break;
    default:
      screen = <Overview />;
  }
  const active = section === "patient" ? "worklist" : section === "invite" ? "families" : section ?? "";

  return (
    <>
      <div className="banner" role="note">
        <strong>Synthetic data. Not for clinical use.</strong>
        <span> Messaging and lab systems are mocks.</span>
      </div>
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
            {NAV.map(([href, label]) => (
              <a key={href} href={`#/${href}`} className={active === href ? "on" : ""}>
                {label}
              </a>
            ))}
          </nav>
        </div>
      </header>
      <DemoBar />
      <main className="wrap main">{screen}</main>
      <footer className="wrap footer small muted">
        Heart Line prototype on synthetic data. <a href="#/audit">Audit log</a>
      </footer>
    </>
  );
}
