/**
 * Small hooks shared across screens.
 *
 * `useAsync` exists instead of a data-fetching library because the app talks
 * to one local server over loopback: there is no latency to hide, no offline
 * queue to manage and no cache invalidation problem worth 40 kB of dependency.
 * What it does need is the thing a naive `useEffect` fetch gets wrong — not
 * writing the result of a stale request over a newer one when the learner
 * switches language mid-load.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { LanguageNotReady } from "./api";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  /** Set when the failure was "this language is not ready", which is a
   *  roadmap message rather than a bug and is rendered differently. */
  notReady: LanguageNotReady | null;
  reload(): void;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [notReady, setNotReady] = useState<LanguageNotReady | null>(null);
  const [nonce, setNonce] = useState(0);
  const generation = useRef(0);

  useEffect(() => {
    const mine = ++generation.current;
    setLoading(true);
    setError(null);
    setNotReady(null);
    fn()
      .then((res) => {
        if (mine !== generation.current) return;   // a newer request won
        setData(res);
      })
      .catch((e: unknown) => {
        if (mine !== generation.current) return;
        if (e instanceof LanguageNotReady) setNotReady(e);
        else setError(e instanceof Error ? e : new Error(String(e)));
      })
      .finally(() => {
        if (mine === generation.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, loading, error, notReady, reload };
}

/** Milliseconds of wall-clock time on a screen, for the study-time tracker. */
export function useElapsed(): () => number {
  const start = useRef(Date.now());
  return useCallback(() => (Date.now() - start.current) / 1000, []);
}

export function useKey(key: string, handler: (e: KeyboardEvent) => void, active = true) {
  const saved = useRef(handler);
  saved.current = handler;
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== key) return;
      const t = e.target as HTMLElement | null;
      // Never hijack a key the learner is typing into an answer box.
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) {
        if (key !== "Enter" && key !== "Escape") return;
      }
      saved.current(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [key, active]);
}

/** Persist a small piece of UI state — a chosen tab, a filter — per browser. */
export function useLocalState<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(`hanbat.${key}`);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        localStorage.setItem(`hanbat.${key}`, JSON.stringify(v));
      } catch {
        /* private browsing, or storage disabled — the app still works */
      }
    },
    [key],
  );
  return [value, set];
}
