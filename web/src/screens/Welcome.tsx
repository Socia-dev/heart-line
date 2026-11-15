import Steps, { PEOPLE } from "../components/Steps";

// The first thing anyone sees: the idea, the five moves, and the people. Then one button.
export default function Welcome({ start, busy, free }: { start: () => void; busy: boolean; free: () => void }) {
  return (
    <div className="stack">
      <div className="welcome-head">
        <h1 className="display">One blood test can find a whole family</h1>
        <p className="lede">
          Inherited high cholesterol (FH) causes early heart attacks and is easy to treat once found. It runs in families, so every person found is a way
          to find more.
        </p>
        <div className="row" style={{ marginTop: 20 }}>
          <button className="primary" disabled={busy} onClick={start}>
            {busy ? "Starting" : "Start the guided demo"}
          </button>
          <button onClick={free}>Explore on my own</button>
          <span className="small muted">About 3 minutes. It tells you who you are and what to press at each step.</span>
        </div>
      </div>

      <section className="card">
        <h2>How it works</h2>
        <Steps />
      </section>

      <section className="card">
        <h2>The people involved</h2>
        <div className="people">
          {PEOPLE.map((p) => (
            <div key={p.id}>
              <h3>{p.name}</h3>
              <p>{p.job}</p>
              <p className="small muted">Sees: {p.sees}</p>
            </div>
          ))}
          <div>
            <h3>An invited relative</h3>
            <p>Gets a message on their phone and decides whether to come for a check.</p>
            <p className="small muted">Sees: their own invitation, in Arabic or English.</p>
          </div>
        </div>
      </section>
      <p className="small muted">Everything here is synthetic. No real patients, no real messages.</p>
    </div>
  );
}
