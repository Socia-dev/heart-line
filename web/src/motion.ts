import { useEffect, useRef, useState } from "react";

// Motion helpers. Every animation in Heart Line respects reduced motion and moves only
// transform and opacity. Durations: 160ms for presses, 240ms for things arriving, longer
// only for the time-jump, which is a story beat rather than UI feedback.

export const reduced = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

// A number that counts from its last value to the new one.
export function useCountUp(value: number, ms = 700): number {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (reduced() || from.current === value) {
      from.current = value;
      setShown(value);
      return;
    }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      setShown(Math.round(a + (value - a) * easeOut(t)));
      if (t < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    // If animation frames are paused (a background tab), still land on the right number.
    const settle = window.setTimeout(() => {
      cancelAnimationFrame(raf);
      from.current = value;
      setShown(value);
    }, ms + 80);
    return () => {
      // Interrupted by a newer value: finish this one at once, and count on from here.
      cancelAnimationFrame(raf);
      window.clearTimeout(settle);
      from.current = value;
      setShown(value);
    };
  }, [value, ms]);
  return shown;
}

export function CountUp({ value, ms }: { value: number; ms?: number }) {
  return useCountUp(value, ms).toLocaleString();
}

// Stagger children: pass the index, get a style for the CSS `rise` animation.
export const stagger = (i: number, step = 40, max = 12) => ({ "--d": `${Math.min(i, max) * step}ms` }) as React.CSSProperties;
