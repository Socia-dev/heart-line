import { useEffect, useState } from "react";
import { changed, post, useApi } from "../api";
import ar from "../locale/ar.json";
import en from "../locale/en.json";

type Lang = "ar" | "en";
type View = {
  given: string;
  lang: Lang;
  state: "open" | "booked" | "declined" | "already_tested" | "call_requested" | "closed";
  slot: string | null;
  slots: string[];
};
const T: Record<Lang, typeof en> = { en, ar };

const CLINIC_AR: Record<string, string> = {
  "Al Bateen Family Health Centre": "مركز البطين لصحة الأسرة",
  "Mohammed Bin Zayed City Health Centre": "مركز مدينة محمد بن زايد الصحي",
  "Al Ain Healthy Family Clinic": "عيادة العين لصحة الأسرة",
};

function slotText(slot: string, lang: Lang) {
  const [when, clinic] = slot.split(" | ");
  if (!clinic) return { day: when, clinic: "" };
  const [d, time] = when.split(" ");
  const date = new Date(`${d}T${time}:00`);
  const locale = lang === "ar" ? "ar-AE-u-nu-latn" : "en-GB";
  const day = date.toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" });
  const hm = date.toLocaleTimeString(locale, { hour: "numeric", minute: "2-digit" });
  return { day: `${day}${lang === "ar" ? "،" : ","} ${hm}`, clinic: lang === "ar" ? CLINIC_AR[clinic] ?? clinic : clinic };
}

// What the invited relative sees on their phone: three short steps and four ways to answer.
export default function Invite({ token }: { token: string }) {
  const { data, error } = useApi<View>(`/api/invite/${token}`);
  const [lang, setLang] = useState<Lang>("en");
  const [step, setStep] = useState<"read" | "pick" | "already">("read");
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [why, setWhy] = useState(false);
  const known = data?.lang;
  useEffect(() => {
    if (known) setLang(known === "ar" ? "ar" : "en");
  }, [known]);

  const t = T[lang];
  const shell = (body: React.ReactNode) => (
    <div className="phone" dir={lang === "ar" ? "rtl" : "ltr"} lang={lang}>
      <div className="spread" style={{ alignItems: "center" }}>
        <span className="small muted">{t.from}</span>
        <button className="ghost small" onClick={() => setLang(lang === "ar" ? "en" : "ar")} lang={lang === "ar" ? "en" : "ar"}>
          {lang === "ar" ? "English" : "العربية"}
        </button>
      </div>
      {body}
      <p className="small muted" style={{ marginTop: 18, marginBottom: 0 }}>
        {t.mock}
      </p>
    </div>
  );

  if (error) return shell(<Closed t={t} />);
  if (!data) return shell(<div className="skeleton" style={{ width: "70%", marginTop: 16 }} />);

  async function respond(choice: string, extra: Record<string, unknown> = {}) {
    setBusy(true);
    setFailed(false);
    try {
      await post(`/api/invite/${token}/respond`, { choice, ...extra });
      changed();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }
  const err = failed && <p className="error">{t.error}</p>;

  if (data.state === "closed") return shell(<Closed t={t} />);
  if (data.state === "booked" && data.slot) {
    const s = slotText(data.slot, lang);
    return shell(
      <>
        <p className="small muted step">{t.step.replace("{n}", "3")}</p>
        <h1>{t.booked_title}</h1>
        <div className="notice">
          <strong>{s.day}</strong>
          <br />
          {s.clinic}
        </div>
        <p style={{ marginTop: 12 }}>{t.booked_body}</p>
      </>,
    );
  }
  if (data.state === "declined") return shell(<Outcome title={t.declined_title} body={t.declined_body} />);
  if (data.state === "call_requested") return shell(<Outcome title={t.call_title} body={t.call_body} />);
  if (data.state === "already_tested") return shell(<Outcome title={t.already_title} body={t.already_done} />);

  if (step === "already")
    return shell(
      <>
        <h1>{t.already_title}</h1>
        <p>{t.already_body}</p>
        <button className="primary wide" disabled={busy} onClick={() => respond("already_tested", { share: true })}>
          {t.share_yes}
        </button>
        <button className="wide" disabled={busy} onClick={() => respond("already_tested", { share: false })}>
          {t.share_no}
        </button>
        <button className="ghost wide" onClick={() => setStep("read")}>
          {t.back}
        </button>
        {err}
      </>,
    );

  if (step === "pick")
    return shell(
      <>
        <p className="small muted step">{t.step.replace("{n}", "2")}</p>
        <h1>{t.pick}</h1>
        <div role="radiogroup">
          {data.slots.map((s) => {
            const st = slotText(s, lang);
            return (
              <label key={s} className={`slot ${pick === s ? "on" : ""}`}>
                <input type="radio" name="slot" checked={pick === s} onChange={() => setPick(s)} />
                <span>
                  <strong>{st.day}</strong>
                  <br />
                  <span className="small muted">{st.clinic}</span>
                </span>
              </label>
            );
          })}
        </div>
        <button className="primary wide" disabled={!pick || busy} onClick={() => respond("book", { slot: pick })}>
          {t.book}
        </button>
        <button className="ghost wide" onClick={() => setStep("read")}>
          {t.back}
        </button>
        {err}
      </>,
    );

  return shell(
    <>
      <p className="small muted step">{t.step.replace("{n}", "1")}</p>
      <h1>{t.title}</h1>
      <p>{t.hello.replace("{name}", data.given)}</p>
      <p>{t.body}</p>
      <p className="muted">{t.detail}</p>
      <button className="primary wide" onClick={() => setStep("pick")}>
        {t.choose}
      </button>
      <button className="wide" onClick={() => setStep("already")}>
        {t.already}
      </button>
      <button className="wide" disabled={busy} onClick={() => respond("call_me")}>
        {t.call}
      </button>
      <button className="ghost wide" disabled={busy} onClick={() => respond("decline")}>
        {t.no}
      </button>
      {err}
      <button className="link small" aria-expanded={why} onClick={() => setWhy(!why)}>
        {t.why_q}
      </button>
      {why && <p className="small">{t.why_a}</p>}
      <p className="small muted" style={{ marginBottom: 0 }}>
        {t.privacy}
      </p>
    </>,
  );
}

function Outcome({ title, body }: { title: string; body: string }) {
  return (
    <>
      <h1>{title}</h1>
      <p>{body}</p>
    </>
  );
}

function Closed({ t }: { t: typeof en }) {
  return <Outcome title={t.closed_title} body={t.closed_body} />;
}

// Staff preview: the same page in a phone frame, with a link to open it on its own.
export function InvitePreview({ token }: { token: string }) {
  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>What the relative sees</h1>
          <p className="muted" style={{ margin: 0 }}>
            This is the page behind the link in the SMS. It works here: answer as the relative to see what happens next.
          </p>
        </div>
        <div className="row">
          <a href={`#/i/${token}`} target="_blank" rel="noreferrer">
            Open on its own
          </a>
          <a href="#/families">Back to invitations</a>
        </div>
      </div>
      <div className="phone-frame">
        <Invite token={token} />
      </div>
    </div>
  );
}
