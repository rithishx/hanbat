/**
 * The frame: navigation, language switcher, and the offline badge.
 *
 * Two layouts from one nav list — a sidebar on desktop, a bottom bar plus a
 * drawer on phones. The five items in the bottom bar are the ones a learner
 * uses every day; the rest are reference and settings, which are looked up
 * rather than lived in.
 */

import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useApp } from "../lib/app-context";
import { Target } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  /** Shown in the phone bottom bar. */
  primary?: boolean;
  /** Hidden when the active language does not declare this capability. */
  needs?: string;
}

export const NAV: NavItem[] = [
  { to: "/", label: "Today", icon: "◎", primary: true },
  { to: "/session", label: "Session", icon: "▶", primary: true },
  { to: "/learn", label: "Lessons", icon: "▤", primary: true },
  { to: "/review", label: "Review", icon: "↻", primary: true },
  { to: "/practice", label: "Practice", icon: "◈" },
  { to: "/writing", label: "Writing system", icon: "✎" },
  { to: "/vocabulary", label: "Vocabulary", icon: "▦" },
  { to: "/grammar", label: "Grammar", icon: "§" },
  { to: "/pronunciation", label: "Pronunciation lab", icon: "◊" },
  { to: "/conjugation", label: "Conjugation", icon: "⇄", needs: "conjugation" },
  { to: "/mistakes", label: "My mistakes", icon: "!" },
  { to: "/tutor", label: "Tutor", icon: "☉" },
  { to: "/search", label: "Search", icon: "⌕" },
  { to: "/progress", label: "Progress", icon: "▲", primary: true },
  { to: "/languages", label: "Languages", icon: "⬡" },
  { to: "/settings", label: "Settings", icon: "⚙" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const { language, languages, lang, switchLanguage, me } = useApp();
  const [drawer, setDrawer] = useState(false);
  const location = useLocation();

  useEffect(() => setDrawer(false), [location.pathname]);

  const items = NAV.filter(
    (i) => !i.needs || language?.capabilities?.includes(i.needs),
  );
  const primary = items.filter((i) => i.primary).slice(0, 5);

  return (
    <div className="min-h-dvh bg-paper">
      <a href="#main" className="skip-link">
        Skip to content
      </a>

      {/* ---- desktop sidebar ---- */}
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-line bg-raised lg:flex">
        <div className="px-5 py-5">
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold tracking-tight">Hanbat</span>
            <span className="chip !border-good/40 !text-good" title="No network required">
              offline
            </span>
          </div>
          <p className="mt-1 text-xs text-faint">Runs entirely on this machine</p>
        </div>

        <LanguagePicker
          languages={languages}
          active={lang}
          onPick={(c) => void switchLanguage(c)}
        />

        <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Main">
          {items.map((i) => (
            <NavLink
              key={i.to}
              to={i.to}
              end={i.to === "/"}
              className={({ isActive }) =>
                `mb-0.5 flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-brand-soft font-semibold text-brand"
                    : "text-muted hover:bg-brand-soft/60 hover:text-ink"
                }`
              }
            >
              <span aria-hidden className="w-4 text-center opacity-70">
                {i.icon}
              </span>
              {i.label}
            </NavLink>
          ))}
        </nav>

        {me && (
          <div className="border-t border-line px-5 py-3 text-xs text-faint">
            {me.streak.current > 0
              ? `${me.streak.current}-day streak 🔥`
              : "No streak yet — today can start one"}
          </div>
        )}
      </aside>

      {/* ---- phone top bar ---- */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-raised/95 px-4 py-3 backdrop-blur lg:hidden">
        <button
          className="btn-quiet !px-2"
          onClick={() => setDrawer(true)}
          aria-label="Open menu"
          aria-expanded={drawer}
        >
          ☰
        </button>
        <span className="font-semibold">Hanbat</span>
        <LanguageChip
          languages={languages}
          active={lang}
          onPick={(c) => void switchLanguage(c)}
        />
      </header>

      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setDrawer(false)}
            aria-hidden
          />
          <nav
            className="absolute inset-y-0 left-0 w-72 overflow-y-auto bg-raised p-4 animate-fade-up"
            aria-label="All sections"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="font-semibold">Menu</span>
              <button className="btn-quiet !px-2" onClick={() => setDrawer(false)}>
                ✕
              </button>
            </div>
            {items.map((i) => (
              <NavLink
                key={i.to}
                to={i.to}
                end={i.to === "/"}
                className={({ isActive }) =>
                  `mb-0.5 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${
                    isActive ? "bg-brand-soft font-semibold text-brand" : "text-muted"
                  }`
                }
              >
                <span aria-hidden className="w-4 text-center opacity-70">
                  {i.icon}
                </span>
                {i.label}
              </NavLink>
            ))}
          </nav>
        </div>
      )}

      {/* ---- content ---- */}
      <main
        id="main"
        className="mx-auto max-w-5xl px-4 pb-28 pt-6 lg:pb-12 lg:pl-64 lg:pr-6"
      >
        <div className="lg:pl-4">{children}</div>
      </main>

      {/* ---- phone bottom bar ---- */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-raised/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
        aria-label="Primary"
      >
        {primary.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            end={i.to === "/"}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 py-2.5 text-[0.68rem] ${
                isActive ? "font-semibold text-brand" : "text-muted"
              }`
            }
          >
            <span aria-hidden className="text-base">
              {i.icon}
            </span>
            {i.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function LanguagePicker({
  languages,
  active,
  onPick,
}: {
  languages: { code: string; name: string; native_name: string; flag: string; status: string }[];
  active: string;
  onPick: (code: string) => void;
}) {
  return (
    <div className="px-3 pb-3">
      <p className="label mb-1.5 px-2">Learning</p>
      <div className="space-y-1">
        {languages.map((l) => (
          <button
            key={l.code}
            onClick={() => onPick(l.code)}
            aria-current={l.code === active}
            className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors ${
              l.code === active
                ? "bg-brand-soft font-semibold text-brand"
                : "text-muted hover:bg-brand-soft/50"
            }`}
          >
            <span aria-hidden className="text-base">
              {l.flag}
            </span>
            <span className="flex-1">{l.name}</span>
            <Target lang={l.code} className="text-xs opacity-60">
              {l.native_name}
            </Target>
          </button>
        ))}
      </div>
    </div>
  );
}

function LanguageChip({
  languages,
  active,
  onPick,
}: {
  languages: { code: string; name: string; flag: string }[];
  active: string;
  onPick: (code: string) => void;
}) {
  const current = languages.find((l) => l.code === active);
  return (
    <label className="relative">
      <span className="sr-only">Language</span>
      <select
        value={active}
        onChange={(e) => onPick(e.target.value)}
        className="appearance-none rounded-xl border border-line bg-raised py-1.5 pl-8 pr-6 text-sm"
      >
        {languages.map((l) => (
          <option key={l.code} value={l.code}>
            {l.name}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden>
        {current?.flag ?? "🏳️"}
      </span>
    </label>
  );
}
