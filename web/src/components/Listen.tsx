import { useEffect, useRef, useState } from "react";
import { useApi } from "../api";

type Status = { provider: "elevenlabs" | "device"; scripts: Record<string, string> };

// "Listen" on the relative's phone. Plays the ElevenLabs voice note when a key is set, otherwise
// reads the same words with the device's own voice and says so.
export default function Listen({ token, lang }: { token: string; lang: "ar" | "en" }) {
  const { data: st } = useApi<Status>("/api/voice/status");
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [mode, setMode] = useState<"elevenlabs" | "device" | null>(null);
  const [failed, setFailed] = useState(false);
  const ar = lang === "ar";

  useEffect(() => {
    if (st) setMode(st.provider);
  }, [st]);
  useEffect(
    () => () => {
      audio.current?.pause();
      window.speechSynthesis?.cancel();
    },
    [],
  );
  useEffect(() => {
    // Language switched: stop and start over.
    audio.current?.pause();
    audio.current = null;
    window.speechSynthesis?.cancel();
    setPlaying(false);
    setProgress(0);
  }, [lang]);

  function device() {
    const synth = window.speechSynthesis;
    if (!synth || !st) {
      setFailed(true);
      return;
    }
    if (playing) {
      synth.cancel();
      setPlaying(false);
      return;
    }
    const text = st.scripts[lang];
    const u = new SpeechSynthesisUtterance(text);
    u.lang = ar ? "ar-AE" : "en-GB";
    const v = synth.getVoices().find((x) => x.lang.toLowerCase().startsWith(ar ? "ar" : "en"));
    if (v) u.voice = v;
    u.rate = 0.95;
    u.onboundary = (e) => setProgress(Math.min(1, e.charIndex / text.length));
    u.onend = () => {
      setPlaying(false);
      setProgress(1);
    };
    u.onerror = () => {
      setPlaying(false);
      setFailed(true);
    };
    synth.cancel();
    synth.speak(u);
    setPlaying(true);
  }

  function eleven() {
    if (!audio.current) {
      const a = new Audio(`/api/invite/${token}/voice?lang=${lang}`);
      a.ontimeupdate = () => a.duration && setProgress(a.currentTime / a.duration);
      a.onended = () => {
        setPlaying(false);
        setProgress(1);
      };
      a.onerror = () => {
        // No clip available after all (no credits, offline): fall back to the device voice.
        audio.current = null;
        setPlaying(false);
        setMode("device");
      };
      audio.current = a;
    }
    const a = audio.current;
    if (playing) {
      a.pause();
      setPlaying(false);
    } else {
      if (a.ended) a.currentTime = 0;
      a.play().catch(() => setMode("device"));
      setPlaying(true);
    }
  }

  if (!st) return null;
  return (
    <div className="listen">
      <button className="listen-btn" onClick={mode === "elevenlabs" ? eleven : device} aria-pressed={playing}>
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          {playing ? <path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor" /> : <path d="M8 5v14l11-7z" fill="currentColor" />}
        </svg>
        {playing ? (ar ? "إيقاف" : "Pause") : ar ? "استمع إلى الرسالة" : "Listen to this message"}
      </button>
      <div className="listen-track" aria-hidden="true">
        <span style={{ transform: `scaleX(${progress})` }} />
      </div>
      <div className="small muted">
        {failed
          ? ar
            ? "لا يتوفر صوت على هذا الجهاز."
            : "This device has no voice available."
          : mode === "device"
            ? ar
              ? "صوت الجهاز"
              : "Device voice"
            : ar
              ? "رسالة صوتية"
              : "Voice note"}
      </div>
    </div>
  );
}
