import { useCallback, useEffect, useState } from "react";

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText);
  return r.json();
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? r.statusText);
  return data as T;
}

// Bumped after any action that changes demo state, so every screen refetches.
let version = 0;
const listeners = new Set<() => void>();
export function changed() {
  version += 1;
  listeners.forEach((f) => f());
}

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [v, setV] = useState(version);
  useEffect(() => {
    const f = () => setV(version);
    listeners.add(f);
    return () => {
      listeners.delete(f);
    };
  }, []);
  const load = useCallback(() => {
    if (!path) return;
    get<T>(path)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, [path]);
  useEffect(load, [load, v]);
  return { data, error, reload: load };
}

export const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;

export function fmtDate(iso: string | null | undefined, locale = "en-GB") {
  if (!iso) return "";
  return new Date(iso + "T00:00:00").toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
}

export type Brief = { id: number; mrn: string; name: string; given: string; sex: string; age: number; deceased: boolean };

// Model scores shown as whole percentages, never 0% or 100%.
export const scorePct = (p: number) => (p >= 0.995 ? ">99%" : p < 0.005 ? "<1%" : `${Math.round(p * 100)}%`);
