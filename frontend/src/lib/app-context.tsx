/**
 * Learner, settings and active language — the three things nearly every screen
 * needs.
 *
 * The active language lives here rather than in a URL segment because it is a
 * property of the learner, stored server-side, and switching it must switch
 * the *whole* app at once: lessons, vocabulary, grammar, review queue, level
 * scheme, greeting and skill labels. Threading it through routes would mean
 * every link had to remember it, and the one that forgot would quietly show
 * Korean content under a Japanese heading.
 */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import { api } from "./api";
import { loadVoices } from "./speech";
import type { Language, Me, Settings } from "./types";

interface AppState {
  me: Me | null;
  settings: Settings | null;
  languages: Language[];
  language: Language | null;
  lang: string;
  loading: boolean;
  error: string | null;
  refresh(): Promise<void>;
  switchLanguage(code: string): Promise<void>;
  updateSettings(patch: Partial<Settings>): Promise<void>;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [meRes, langRes] = await Promise.all([api.me(), api.languages()]);
      setMe(meRes);
      setLanguages(langRes.languages);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void loadVoices();
  }, [load]);

  const switchLanguage = useCallback(
    async (code: string) => {
      await api.setActiveLanguage(code);
      setMe((m) => (m ? { ...m, active_language: code } : m));
    },
    [],
  );

  const updateSettings = useCallback(async (patch: Partial<Settings>) => {
    // Applied optimistically: a theme toggle that waits for a round trip feels
    // broken, and the round trip is to localhost.
    setMe((m) => (m ? { ...m, settings: { ...m.settings, ...patch } } : m));
    const res = await api.saveSettings(patch);
    setMe((m) => (m ? { ...m, settings: res.settings } : m));
  }, []);

  const lang = me?.active_language ?? "ko";
  const language = useMemo(
    () => languages.find((l) => l.code === lang) ?? null,
    [languages, lang],
  );

  // Theme, size, contrast and motion are attributes on <html>, so the CSS
  // variables in index.css do the work and no component has to know.
  useEffect(() => {
    const s = me?.settings;
    if (!s) return;
    const root = document.documentElement;
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = s.theme === "dark" || (s.theme === "system" && prefersDark);
    root.dataset.theme = dark ? "dark" : "light";
    root.dataset.size = s.font_size;
    root.dataset.contrast = s.high_contrast ? "high" : "normal";
    root.dataset.font = s.dyslexia_font ? "dyslexia" : "default";
    root.dataset.motion = s.reduce_motion ? "reduced" : "full";
  }, [me?.settings]);

  const value: AppState = {
    me,
    settings: me?.settings ?? null,
    languages,
    language,
    lang,
    loading,
    error,
    refresh: load,
    switchLanguage,
    updateSettings,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be used inside <AppProvider>");
  return v;
}

/** The active language code — the argument almost every API call needs. */
export function useLang(): string {
  return useApp().lang;
}
