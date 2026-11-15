import { useCallback, useEffect, useState } from "react";

export type Role = "clinician" | "coordinator" | "nurse" | "lead";
export const ROLES: { id: Role; name: string; title: string }[] = [
  { id: "clinician", name: "Dr. Layla", title: "Lipid clinician" },
  { id: "coordinator", name: "Omar", title: "Family coordinator" },
  { id: "nurse", name: "Hind", title: "Well-Child nurse" },
  { id: "lead", name: "Dr. Saeed", title: "Programme lead" },
];

// Demo roles, no sign-in. The choice is kept in the browser for convenience only.
let role: Role = "clinician";
try {
  const saved = localStorage.getItem("heartline-role") as Role | null;
  if (saved && ROLES.some((r) => r.id === saved)) role = saved;
} catch {
  /* storage unavailable: start as clinician */
}
export const getRole = () => role;
export function setRole(r: Role) {
  role = r;
  try {
    localStorage.setItem("heartline-role", r);
  } catch {
    /* ignore */
  }
  changed();
}

export class ApiError extends Error {
  code: string;
  kind: string;
  constructor(message: string, code = "unknown", kind = "unknown") {
    super(message);
    this.code = code;
    this.kind = kind;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, { ...init, headers: { "Content-Type": "application/json", "X-Demo-Role": role } });
  } catch {
    throw new ApiError("The Heart Line service is not reachable.", "offline", "offline");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(data.message ?? data.detail ?? r.statusText, data.code, data.kind);
  return data as T;
}
export const get = <T,>(path: string) => call<T>(path);
export const post = <T,>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

// Bumped after any action that changes state (or the role), so every screen refetches.
let version = 0;
const listeners = new Set<() => void>();
export function changed() {
  version += 1;
  listeners.forEach((f) => f());
}
export function useVersion() {
  const [v, setV] = useState(version);
  useEffect(() => {
    const f = () => setV(version);
    listeners.add(f);
    return () => {
      listeners.delete(f);
    };
  }, []);
  return v;
}
export function useRole(): Role {
  useVersion();
  return role;
}

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const v = useVersion();
  const load = useCallback(() => {
    if (!path) return;
    get<T>(path)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => {
        setData(null);
        setError(e instanceof ApiError ? e : new ApiError(String(e)));
      });
  }, [path]);
  useEffect(load, [load, v]);
  return { data, error, reload: load };
}

export const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;
export const range = (r: [number, number] | number[]) => `${pct(r[0])} to ${pct(r[1])}`;

export function fmtDate(iso: string | null | undefined, locale = "en-GB") {
  if (!iso) return "";
  return new Date(iso + "T00:00:00").toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
}

export const go = (hash: string) => {
  window.location.hash = hash;
};

export type Brief = { id: number; mrn: string; name: string; given: string; sex: string; age: number; deceased: boolean };
