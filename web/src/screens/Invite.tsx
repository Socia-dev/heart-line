import { useEffect, useState } from "react";
import { changed, post, useApi } from "../api";

type View = { given: string; lang: "ar" | "en"; status: "open" | "booked" | "closed"; slot: string | null; slots: string[]; mock: boolean };

const CLINIC_AR: Record<string, string> = {
  "Al Bateen Family Health Centre": "مركز البطين لصحة الأسرة",
  "Mohammed Bin Zayed City Health Centre": "مركز مدينة محمد بن زايد الصحي",
  "Al Ain Healthy Family Clinic": "عيادة العين لصحة الأسرة",
};

const T = {
  en: {
    title: "You're invited to a free cholesterol check",
    hello: (n: string) => `Hello ${n},`,
    body: "High cholesterol can run in families and is easy to treat when it's found early. We'd like to offer you a free blood test at a health centre near you.",
    detail: "It takes about 10 minutes and you don't need to fast.",
    choose: "Choose a time",
    book: "Book my check",
    booked: "You're booked",
    reminder: "We'll send you a reminder the day before.",
    closed: "This invitation has already been used. If you need help, call your health centre.",
    privacy: "Your information is private. Only your health centre can see it.",
    from: "Your local health centre",
    mock: "Demo only. No message was sent and no appointment was made.",
    at: "at",
  },
  ar: {
    title: "أنت مدعو لفحص كوليسترول مجاني",
    hello: (n: string) => `مرحباً ${n}،`,
    body: "قد يكون ارتفاع الكوليسترول متوارثاً في العائلة، وعلاجه سهل عند اكتشافه مبكراً. يسعدنا أن نقدم لك فحص دم مجانياً في مركز صحي قريب منك.",
    detail: "يستغرق الفحص حوالي 10 دقائق، ولا تحتاج إلى الصيام.",
    choose: "اختر الموعد المناسب",
    book: "احجز موعدي",
    booked: "تم حجز موعدك",
    reminder: "سنرسل لك تذكيراً قبل الموعد بيوم.",
    closed: "تم استخدام هذه الدعوة من قبل. إذا احتجت إلى مساعدة، اتصل بمركزك الصحي.",
    privacy: "معلوماتك سرية، ولا يطلع عليها إلا مركزك الصحي.",
    from: "مركزك الصحي",
    mock: "عرض تجريبي فقط. لم تُرسل أي رسالة ولم يُحجز أي موعد.",
    at: "في",
  },
};

function slotText(slot: string, lang: "ar" | "en") {
  const [when, clinic] = slot.split(" | ");
  const [d, time] = when.split(" ");
  const date = new Date(`${d}T${time}:00`);
  const locale = lang === "ar" ? "ar-AE" : "en-GB";
  const day = date.toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" });
  const hm = date.toLocaleTimeString(locale, { hour: "numeric", minute: "2-digit" });
  return { day: `${day}، ${hm}`.replace("،", lang === "ar" ? "،" : ","), clinic: lang === "ar" ? CLINIC_AR[clinic] ?? clinic : clinic };
}

export default function Invite({ token }: { token: string }) {
  const { data, error } = useApi<View>(`/api/invite/${token}`);
  const [lang, setLang] = useState<"ar" | "en">("en");
  const [pick, setPick] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (data) setLang(data.lang === "ar" ? "ar" : "en");
  }, [data?.lang]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading</p>;
  const t = T[lang];

  async function book() {
    if (!pick) return;
    setBusy(true);
    setErr(null);
    try {
      await post(`/api/invite/${token}/book`, { slot: pick });
      changed();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>Invitation preview</h1>
          <p className="muted">What the relative sees when they open the link on their phone.</p>
        </div>
        <div className="lang-toggle" role="group" aria-label="Language">
          <button className={lang === "ar" ? "on" : ""} onClick={() => setLang("ar")} lang="ar">
            العربية
          </button>
          <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>
            English
          </button>
        </div>
      </div>

      <div className="phone" dir={lang === "ar" ? "rtl" : "ltr"} lang={lang}>
        <p className="muted small">{t.from}</p>
        <h1>{t.title}</h1>
        <p>{t.hello(data.given)}</p>
        <p>{t.body}</p>
        <p className="muted">{t.detail}</p>

        {data.status === "open" && (
          <>
            <h3 style={{ marginTop: 18 }}>{t.choose}</h3>
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
            <button className="primary" disabled={!pick || busy} onClick={book}>
              {t.book}
            </button>
          </>
        )}
        {data.status === "booked" && data.slot && (
          <div className="notice" style={{ marginTop: 16 }}>
            <h3>{t.booked}</h3>
            <p style={{ margin: 0 }}>
              {slotText(data.slot, lang).day}
              <br />
              {slotText(data.slot, lang).clinic}
            </p>
            <p className="small muted" style={{ margin: "8px 0 0" }}>
              {t.reminder}
            </p>
          </div>
        )}
        {data.status === "closed" && <p className="quiet">{t.closed}</p>}
        {err && <p className="error">{err}</p>}
        <p className="small muted" style={{ marginTop: 18 }}>
          {t.privacy}
        </p>
        <p className="small muted">{t.mock}</p>
      </div>
      <p className="muted small" style={{ textAlign: "center" }}>
        <a href="#/families">Back to invitations</a>
      </p>
    </div>
  );
}
