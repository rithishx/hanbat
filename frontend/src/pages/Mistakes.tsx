/**
 * Mistakes, and the patterns behind them.
 *
 * A list of wrong answers is not very useful. What is useful is noticing that
 * eleven of them are the same confusion — 은/는 versus 이/가, は versus が,
 * 不 versus 没 — and offering the short course that fixes it. The detection
 * lives in the adaptive engine, per language; this screen renders the result.
 */

import { useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import {
  Empty, ErrorState, NotReady, PageHeader, Section, Skeleton, Target,
} from "../components/ui";

export default function Mistakes() {
  const { lang, language } = useApp();
  const mistakes = useAsync(() => api.mistakeSummary(lang), [lang]);
  const dashboard = useAsync(() => api.dashboard(lang), [lang]);
  const [course, setCourse] = useState<string | null>(null);

  if (mistakes.notReady) return <NotReady notReady={mistakes.notReady} />;
  if (mistakes.error) return <ErrorState error={mistakes.error} onRetry={mistakes.reload} />;

  const confusions = dashboard.data?.confusions ?? [];
  const rows = mistakes.data?.mistakes ?? [];

  if (course) {
    return <MiniCourse confusionId={course} lang={lang} onBack={() => setCourse(null)} />;
  }

  return (
    <>
      <PageHeader
        title="Mistakes"
        native={language?.native_name}
        subtitle="Not a scoreboard. The point is to find the pattern and fix it once."
      />

      {mistakes.loading ? (
        <Skeleton rows={4} />
      ) : (
        <>
          {confusions.length > 0 && (
            <Section
              title="Patterns"
              hint="Two things you have not yet separated — worth twenty minutes"
            >
              <div className="grid gap-2">
                {confusions.map((c) => (
                  <button
                    key={c.id}
                    className="card p-4 text-left transition-colors hover:bg-brand-soft/40"
                    onClick={() => setCourse(c.id)}
                  >
                    <p className="font-semibold">{c.title}</p>
                    <p className="text-sm text-muted">{c.one_line}</p>
                    {c.count ? (
                      <p className="mt-1 text-xs text-faint">
                        {c.count} times so far
                      </p>
                    ) : null}
                  </button>
                ))}
              </div>
            </Section>
          )}

          {rows.length === 0 && confusions.length === 0 ? (
            <Empty
              title="Nothing recorded"
              body="Mistakes show up here once you have answered a few questions. They are not held against you — they are what the app uses to decide what to give you next."
              action={{ to: "/learn", label: "Do a lesson" }}
            />
          ) : (
            <Section title="Recent" hint={`${mistakes.data?.total ?? 0} recorded`}>
              <ul className="card divide-y divide-line">
                {rows.map((m) => (
                  <li key={m.id} className="flex items-center gap-3 p-3.5">
                    <span className="min-w-0 flex-1">
                      <span className="block">
                        <Target lang={lang} className="text-bad line-through">
                          {m.given || "—"}
                        </Target>
                        <span className="mx-2 text-faint" aria-hidden>→</span>
                        <Target lang={lang} className="text-good">
                          {m.expected}
                        </Target>
                      </span>
                      {m.explanation && (
                        <span className="mt-0.5 block text-xs text-muted">
                          {m.explanation}
                        </span>
                      )}
                    </span>
                    {m.times_seen > 1 && <span className="chip shrink-0">×{m.times_seen}</span>}
                    <button
                      className="btn-quiet !px-2 text-xs"
                      title="Mark as fixed"
                      onClick={async () => {
                        await api.resolveMistake(String(m.id), lang).catch(() => {});
                        mistakes.reload();
                      }}
                    >
                      ✓
                    </button>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </>
      )}
    </>
  );
}

function MiniCourse({
  confusionId,
  lang,
  onBack,
}: {
  confusionId: string;
  lang: string;
  onBack: () => void;
}) {
  const course = useAsync(() => api.miniCourse(confusionId, lang), [confusionId, lang]);
  const [step, setStep] = useState(0);

  if (course.loading) return <Skeleton rows={3} />;
  if (course.error) return <ErrorState error={course.error} onRetry={course.reload} />;
  if (!course.data) return null;

  const steps = course.data.steps ?? [];
  const s = steps[step];

  return (
    <>
      <button className="btn-quiet mb-4 !px-2 text-sm" onClick={onBack}>
        ← Mistakes
      </button>
      <PageHeader title={course.data.title} subtitle={`Step ${step + 1} of ${steps.length}`} />

      {s && (
        <article className="card animate-fade-up p-6">
          {s.heading && <h2 className="mb-3 text-lg font-semibold">{s.heading}</h2>}
          <div className="prose-teach whitespace-pre-line">{s.body}</div>
        </article>
      )}

      <div className="mt-4 flex justify-between">
        <button
          className="btn-quiet"
          disabled={step === 0}
          onClick={() => setStep(step - 1)}
        >
          ← Back
        </button>
        {step + 1 < steps.length ? (
          <button className="btn-primary" onClick={() => setStep(step + 1)}>
            Next →
          </button>
        ) : (
          <button className="btn-primary" onClick={onBack}>
            Done
          </button>
        )}
      </div>
    </>
  );
}
