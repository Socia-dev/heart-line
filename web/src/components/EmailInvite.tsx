import { useState } from "react";
import { ApiError, post, useApi } from "../api";
import { ActionError } from "./State";

type Preview = { subject: string; text: string; link: string; voice_notes: string[]; status: { configured: boolean; provider: string | null; how: string } };

// Send one invitation by real email, usually to a judge's own address. Preview first; sending is its own click.
export default function EmailInvite({ id, onClose }: { id: number; onClose: () => void }) {
  const { data } = useApi<Preview>(`/api/invitations/${id}/email`);
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const [sent, setSent] = useState<string | null>(null);

  async function send() {
    setBusy(true);
    setErr(null);
    try {
      await post(`/api/invitations/${id}/email`, { to });
      setSent(to);
    } catch (e) {
      setErr(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="quiet rise" style={{ marginTop: 12 }}>
      <div className="spread">
        <strong>Send this invitation by real email</strong>
        <button className="link" onClick={onClose}>
          Close
        </button>
      </div>
      {!data ? (
        <div className="skeleton" style={{ width: "60%" }} />
      ) : (
        <>
          <p className="small muted">
            For the demo: send it to your own address to see what a relative receives. The address is used once and not kept.
          </p>
          <div className="email-preview">
            <div className="small muted">Subject</div>
            <div>{data.subject}</div>
            <div className="small muted" style={{ marginTop: 8 }}>
              Message
            </div>
            <pre>{data.text}</pre>
            <div className="small muted">
              {data.voice_notes.length ? `Attached: ${data.voice_notes.join(", ")}` : "No voice note attached (no ElevenLabs key). The page in the link can read it aloud."}
            </div>
          </div>
          {data.status.configured ? (
            sent ? (
              <p className="done-note pop" style={{ marginTop: 12 }}>
                Sent to {sent}. Check that inbox.
              </p>
            ) : (
              <div className="row" style={{ marginTop: 12 }}>
                <input type="email" placeholder="you@example.com" value={to} onChange={(e) => setTo(e.target.value)} aria-label="Email address" style={{ minWidth: 240 }} />
                <button className="primary" disabled={busy || !to.includes("@")} onClick={send}>
                  {busy ? "Sending" : "Send to this address"}
                </button>
              </div>
            )
          ) : (
            <p className="small" style={{ marginTop: 12 }}>
              <strong>Email sending is not set up.</strong> {data.status.how} The phone preview works without it.
            </p>
          )}
          {err && <ActionError error={err} />}
        </>
      )}
    </div>
  );
}
