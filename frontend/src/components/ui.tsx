/**
 * The small shared pieces: target-language text, audio, loading and error
 * states, progress rings.
 *
 * `Target` is the important one. Every string in Korean, Japanese or Mandarin
 * goes through it, so that the right font stack, the right `lang` attribute
 * (which screen readers and line breaking both need) and the right size are
 * applied in one place. A raw <span> holding 한국어 is a bug.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../lib/app-context";
import { hasVoiceFor, speak, stopSpeaking, synthesisAvailable } from "../lib/speech";
import type { LanguageNotReady } from "../lib/api";

// ==========================================================================
// Target-language text
// ==========================================================================

const SIZES = {
  inline: "text-[1.05em]",
  md: "text-xl",
  lg: "text-3xl",
  xl: "text-5xl",
  hero: "text-7xl",
} as const;

export function Target({
  children,
  lang,
  size = "inline",
  className = "",
}: {
  children: ReactNode;
  lang?: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const app = useApp();
  const code = lang ?? app.lang;
  return (
    <span
      lang={code}
      className={`target target-${code} ${SIZES[size]} ${className}`}
    >
      {children}
    </span>
  );
}

// ==========================================================================
// Audio
// ==========================================================================

export function AudioButton({
  text,
  lang,
  label,
  className = "",
  autoPlay = false,
}: {
  text: string;
  lang?: string;
  label?: string;
  className?: string;
  autoPlay?: boolean;
}) {
  const { lang: active, settings } = useApp();
  const code = lang ?? active;
  const [playing, setPlaying] = useState(false);
  const played = useRef(false);

  const play = () => {
    if (!text.trim()) return;
    setPlaying(true);
    const ok = speak(text, {
      lang: code,
      rate: settings?.playback_rate ?? 1,
      voiceName: settings?.tts_voice || undefined,
      onEnd: () => setPlaying(false),
    });
    if (!ok) setPlaying(false);
  };

  useEffect(() => {
    if (autoPlay && !played.current && settings?.audio_autoplay) {
      played.current = true;
      play();
    }
    return () => stopSpeaking();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, autoPlay]);

  if (!synthesisAvailable()) return null;

  // A missing voice is worth saying. Without one the browser reads Hangul with
  // an English voice, which sounds plausible and is completely wrong.
  const missing = !hasVoiceFor(code);

  return (
    <button
      type="button"
      onClick={play}
      title={
        missing
          ? `No ${code} voice is installed on this system, so playback may be wrong. Settings explains how to add one.`
          : label ?? "Listen"
      }
      aria-label={label ?? `Listen to ${text}`}
      className={`btn-ghost !px-3 !py-2 ${playing ? "animate-pop" : ""} ${
        missing ? "opacity-60" : ""
      } ${className}`}
    >
      <span aria-hidden>{playing ? "🔊" : "🔈"}</span>
      {missing && <span className="text-xs text-warn">no voice</span>}
    </button>
  );
}

// ==========================================================================
// States
// ==========================================================================

export function Loading({ what = "" }: { what?: string }) {
  return (
    <div className="flex items-center gap-3 p-8 text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-brand" />
      <span className="text-sm">Loading{what ? ` ${what}` : ""}…</span>
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-2xl bg-line/60" />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="card p-6" role="alert">
      <h2 className="mb-1 font-semibold text-bad">That did not work</h2>
      <p className="mb-4 text-sm text-muted">{error.message}</p>
      {onRetry && (
        <button className="btn-ghost" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

/**
 * A language that exists but is not finished.
 *
 * Deliberately not an error and deliberately not an empty list: an empty list
 * reads as a bug, and this is a roadmap. It shows what the language *does*
 * have and offers a way back to one that is further along.
 */
export function NotReady({ notReady }: { notReady: LanguageNotReady }) {
  const { languages, switchLanguage } = useApp();
  const ready = languages.filter(
    (l) => l.code !== notReady.language && l.status !== "planned",
  );
  return (
    <div className="card p-6">
      <h2 className="mb-2 text-lg font-semibold">Not built yet</h2>
      <p className="mb-4 text-sm leading-relaxed text-muted">{notReady.message}</p>
      {ready.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {ready.map((l) => (
            <button
              key={l.code}
              className="btn-ghost"
              onClick={() => void switchLanguage(l.code)}
            >
              <span aria-hidden>{l.flag}</span> Switch to {l.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Empty({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: { to: string; label: string };
}) {
  return (
    <div className="card p-8 text-center">
      <h2 className="mb-1 font-semibold">{title}</h2>
      <p className="mx-auto mb-4 max-w-md text-sm text-muted">{body}</p>
      {action && (
        <Link to={action.to} className="btn-primary">
          {action.label}
        </Link>
      )}
    </div>
  );
}

// ==========================================================================
// Progress
// ==========================================================================

export function Ring({
  percent,
  size = 64,
  stroke = 6,
  children,
}: {
  percent: number;
  size?: number;
  stroke?: number;
  children?: ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, percent));
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          strokeWidth={stroke} className="stroke-line"
        />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c - (pct / 100) * c}
          className="stroke-brand transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-xs font-semibold">
        {children ?? `${Math.round(pct)}%`}
      </div>
    </div>
  );
}

export function Bar({
  percent,
  label,
  tone = "brand",
}: {
  percent: number;
  label?: string;
  tone?: "brand" | "good" | "warn";
}) {
  const colour = { brand: "bg-brand", good: "bg-good", warn: "bg-warn" }[tone];
  return (
    <div>
      {label && (
        <div className="mb-1 flex justify-between text-xs text-muted">
          <span>{label}</span>
          <span>{Math.round(percent)}%</span>
        </div>
      )}
      <div className="h-2 overflow-hidden rounded-full bg-line">
        <div
          className={`h-full rounded-full ${colour} transition-[width] duration-500`}
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>
    </div>
  );
}

// ==========================================================================
// Layout helpers
// ==========================================================================

export function PageHeader({
  title,
  native,
  subtitle,
  actions,
}: {
  title: string;
  native?: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          {title}
          {native && (
            <Target className="ml-3 font-normal text-muted" size="md">
              {native}
            </Target>
          )}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Section({
  title,
  hint,
  children,
  right,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
  right?: ReactNode;
}) {
  return (
    <section className="mb-8">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-faint">
            {title}
          </h2>
          {hint && <p className="mt-0.5 text-xs text-faint">{hint}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

/**
 * The two-level explanation the whole curriculum is built on: the plain-words
 * version is shown, and the terminology is one click away and never first.
 */
export function TwoLevel({
  simple,
  technical,
  technicalLabel = "The precise version",
}: {
  simple: string;
  technical?: string;
  technicalLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  if (!simple && !technical) return null;
  return (
    <div>
      <div className="prose-teach whitespace-pre-line text-[0.975rem]">{simple}</div>
      {technical && (
        <div className="mt-3">
          <button
            className="text-xs font-semibold text-brand hover:underline"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
          >
            {open ? "Hide" : technicalLabel} {open ? "▲" : "▾"}
          </button>
          {open && (
            <p className="mt-2 rounded-xl bg-brand-soft/60 p-3 text-sm leading-relaxed text-muted">
              {technical}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function StatusDot({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    complete: ["bg-good", "Complete"],
    in_progress: ["bg-brand", "In progress"],
    foundation: ["bg-warn", "Foundation"],
    planned: ["bg-faint", "Planned"],
  };
  const [colour, label] = map[status] ?? ["bg-faint", status];
  return (
    <span className="chip" title={label}>
      <span className={`h-2 w-2 rounded-full ${colour}`} aria-hidden />
      {label}
    </span>
  );
}
