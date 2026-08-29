/**
 * Progress, on this language's own ladder.
 *
 * The scheme name is printed at the top for a reason: CEFR, JLPT and HSK are
 * not convertible, and a learner who is B1 in Korean and HSK3 in Mandarin has
 * not "reached the same place twice". Showing the scheme keeps that honest.
 *
 * Every language the learner has touched is listed at the bottom, each with
 * its own level — which is the visible face of the progress isolation the
 * database enforces.
 */

import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import {
  Bar, ErrorState, NotReady, PageHeader, Ring, Section, Skeleton, StatusDot, Target,
} from "../components/ui";
import type { LevelDetails, SkillScore } from "../lib/types";

export default function Progress() {
  const { lang, language, switchLanguage } = useApp();
  const progress = useAsync(() => api.progress(lang), [lang]);
  const dashboard = useAsync(() => api.dashboard(lang), [lang]);
  const all = useAsync(() => api.progressAll(), []);

  if (progress.notReady) return <NotReady notReady={progress.notReady} />;
  if (progress.error) return <ErrorState error={progress.error} onRetry={progress.reload} />;
  if (progress.loading || !progress.data) return <Skeleton rows={5} />;

  const p = progress.data;
  const d = dashboard.data;
  const ladder = (p.ladder ?? []) as LevelDetails[];
  const currentIndex = ladder.findIndex((l) => l.level === (d?.level || d?.estimated_level));

  return (
    <>
      <PageHeader
        title="Progress"
        native={language?.native_name}
        subtitle={`Measured on ${p.level_scheme}. This scale belongs to ${language?.name ?? "this language"} and does not convert to the others.`}
      />

      {d && (
        <div className="card mb-6 flex flex-wrap items-center gap-6 p-6">
          <Ring percent={((currentIndex + 1) / Math.max(1, ladder.length)) * 100} size={88}>
            <span className="text-lg font-bold">{d.level || d.estimated_level}</span>
          </Ring>
          <div className="min-w-0 flex-1">
            <p className="text-lg font-semibold">{d.level_details?.name}</p>
            {d.level_details?.milestone && (
              <p className="mt-1 text-sm text-muted">
                <span className="label">Next milestone: </span>
                {d.level_details.milestone}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted">
              <span>★ <strong className="text-ink">{d.xp}</strong> XP</span>
              <span>🔥 <strong className="text-ink">{d.streak.current}</strong> days</span>
              <span>✓ <strong className="text-ink">{d.known.all}</strong> known</span>
              {d.srs.accuracy !== null && (
                <span>◎ <strong className="text-ink">{Math.round(d.srs.accuracy)}%</strong> accurate</span>
              )}
            </div>
          </div>
        </div>
      )}

      {d && (
        <Section title="What you know">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              ["Vocabulary", d.known.vocab],
              ["Grammar", d.known.grammar],
              ["Writing system", d.known.script],
            ].map(([label, n]) => (
              <div key={String(label)} className="card p-4">
                <p className="text-2xl font-bold">{n as number}</p>
                <p className="text-xs text-faint">{label as string}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {d && (
        <Section title="Skills" hint="Measured from what you have actually answered">
          <div className="card divide-y divide-line">
            {Object.values(d.skills as Record<string, SkillScore>).map((s) => (
              <div key={s.skill} className="flex items-center gap-4 p-4">
                <div className="w-32 shrink-0">
                  <p className="text-sm font-medium">{s.name}</p>
                  <Target lang={lang} className="text-xs text-faint">
                    {s.native_name}
                  </Target>
                </div>
                <div className="flex-1">
                  <Bar percent={s.score} tone={s.score >= 70 ? "good" : "brand"} />
                </div>
                <span className="w-24 shrink-0 text-right text-xs text-faint">
                  {s.attempts === 0
                    ? "no data yet"
                    : `${s.attempts} answered`}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title={`The ${p.level_scheme} ladder`}>
        <ol className="space-y-2">
          {ladder.map((l, i) => {
            const state =
              i < currentIndex ? "past" : i === currentIndex ? "now" : "future";
            return (
              <li
                key={l.level}
                className={`card p-4 ${
                  state === "now" ? "!border-brand bg-brand-soft/40" : ""
                } ${state === "future" ? "opacity-60" : ""}`}
              >
                <div className="mb-1 flex flex-wrap items-baseline gap-2">
                  <span className="font-semibold">{l.level}</span>
                  <span className="text-sm">{l.name}</span>
                  {typeof l.korean === "string" && (
                    <Target lang={lang} className="text-xs text-faint">
                      {l.korean as string}
                    </Target>
                  )}
                  {state === "now" && (
                    <span className="chip !border-brand/40 !text-brand">you are here</span>
                  )}
                </div>
                {l.vocabulary && (
                  <p className="text-xs text-faint">{l.vocabulary}</p>
                )}
                {l.can_do && state !== "past" && (
                  <ul className="mt-2 space-y-1 text-sm text-muted">
                    {l.can_do.map((c) => (
                      <li key={c} className="flex gap-2">
                        <span aria-hidden className="text-faint">·</span>
                        {c}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ol>
      </Section>

      <Section
        title="Your languages"
        hint="Each on its own scale. Progress in one never counts towards another."
      >
        {all.loading ? (
          <Skeleton rows={3} />
        ) : (
          <div className="grid gap-2">
            {(all.data?.languages ?? []).map((L) => (
              <div
                key={L.code}
                className={`card flex flex-wrap items-center gap-4 p-4 ${
                  L.code === lang ? "!border-brand" : ""
                }`}
              >
                <span aria-hidden className="text-2xl">{L.flag}</span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">
                    {L.name}
                    <Target lang={L.code} className="ml-2 text-muted">
                      {L.native_name}
                    </Target>
                  </p>
                  <p className="text-xs text-faint">
                    {L.started
                      ? `${L.level || "—"} · ${L.known.all} known · ${L.xp} XP`
                      : "Not started"}
                  </p>
                </div>
                {L.due_now > 0 && (
                  <span className="chip !border-brand/40 !text-brand">
                    {L.due_now} due
                  </span>
                )}
                <StatusDot status={L.status} />
                {L.code !== lang && (
                  <button
                    className="btn-ghost !py-1.5 text-xs"
                    onClick={() => void switchLanguage(L.code)}
                  >
                    Switch
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs leading-relaxed text-faint">
          The daily streak is the one thing shared across languages — it measures
          whether you sat down at all, and splitting it would punish you for
          spending Tuesday on something else.
        </p>
        <Link className="btn-ghost mt-3 !py-1.5 text-xs" to="/languages">
          Manage languages
        </Link>
      </Section>
    </>
  );
}
