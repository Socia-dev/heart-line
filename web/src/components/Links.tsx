import { useEffect, useState } from "react";

export const GITHUB_URL = "https://github.com/Socia-dev/heart-line";
export const VIDEO_URL = "https://drive.google.com/drive/folders/1vBr8ByTN1hrzCwNuLixULjaVGx3elQ51";

const SEEN = "heartline-links-seen";

function seen(): boolean {
  try {
    return sessionStorage.getItem(SEEN) === "1";
  } catch {
    return false;
  }
}

// The demo video and the code, top right of every staff page. On the first load of a visit a
// short note points at them, then gets out of the way.
export default function Links() {
  const [hint, setHint] = useState(false);

  useEffect(() => {
    if (seen()) return;
    const show = setTimeout(() => setHint(true), 600);
    const hide = setTimeout(() => close(), 9000);
    return () => {
      clearTimeout(show);
      clearTimeout(hide);
    };
  }, []);

  function close() {
    setHint(false);
    try {
      sessionStorage.setItem(SEEN, "1");
    } catch {
      /* ignore */
    }
  }

  return (
    <div className={`ext ${hint ? "ext-hint" : ""}`}>
      <a className="ext-btn ext-video" href={VIDEO_URL} target="_blank" rel="noopener noreferrer" onClick={close}>
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path fill="currentColor" d="M8 5.14v13.72a1 1 0 0 0 1.52.85l11.2-6.86a1 1 0 0 0 0-1.7L9.52 4.29A1 1 0 0 0 8 5.14z" />
        </svg>
        Watch demo
      </a>
      <a className="ext-btn ext-gh" href={GITHUB_URL} target="_blank" rel="noopener noreferrer" onClick={close}>
        <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
          <path
            fill="currentColor"
            d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"
          />
        </svg>
        GitHub
      </a>
      {hint && (
        <div className="ext-note" role="status">
          <button className="ext-close" onClick={close} aria-label="Close">
            ×
          </button>
          <strong>New here?</strong> Watch the demo video, or see the code on GitHub.
        </div>
      )}
    </div>
  );
}
