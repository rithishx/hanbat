/**
 * My Mistakes.
 *
 * Grouped by *why*, not by which skill it happened in. That distinction is the
 * point: "you did not know this word", "you knew it and mistyped it" and "you
 * heard it wrong" are three different problems, and a list that mixes them is
 * a scoreboard rather than a study plan.
 *
 * Careless slips are shown separately and are deliberately not scheduled for
 * extra study. A learner with thirty slips and two real gaps needs to slow
 * down, not to practise more — and telling them that is more useful than
 * quietly drilling them on words they already know.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import { ExerciseCard, type Verdict } from "../components/Exercise";
import {
  Empty, ErrorState, NotReady, PageHeader, Section, Skeleton, Target,
} from "../components/ui";
import type { Mistake } from "../lib/types";

/** Ordered so the reasons that need teaching come before the one that needs
 *  care. Anything the API sends that is not listed still renders, at the end. */
const ORDER = [
  "vocabulary", "grammar", "pronunciation", "listening",
  "reading", "writing", "careless", "unknown",
];

const TONE: Record<string, string> = {
  careless: "border-warn/40",
  unknown: "border-line",
};

export default function Mistakes() {
  const { lang, language } = useApp();
  const report = useAsync(() => api.mistakeSummary(lang), [lang]);
  const dashboard = useAsync(() => api.dashboard(lang), [lang]);
  const [course, setCourse] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [practice, setPractice] = useState<string | null>(null);

  if (report.notReady) return <NotReady notReady={report.notReady} />;
  if (report.error) return <ErrorState error={report.error} onRetry={report.reload} />;

  if (course) {
    return <MiniCourse confusionId={course} lang={lang} onBack={() => setCourse(null)} />;
  }

  if (practice) {
    return (
      <PractiseMistakes
        reason={practice}
        lang={lang}
        onBack={() => {
          setPractice(null);
          report.reload();
        }}
      />
    );
  }

  // A confusion that has become a weak point is already listed above, with a
  // fix attached. Showing it twice under two headings makes one problem look
  // like two.
  const listed = new Set(
    (report.data?.weak_points ?? []).map((w) => w.source_id),
  );
  const confusions = (dashboard.data?.confusions ?? []).filter(
    (c) => !listed.has(c.id),
  );
  const data = report.data;
  const groups = Object.entries(data?.by_reason ?? {}).sort(
    (a, b) => ORDER.indexOf(a[0]) - ORDER.indexOf(b[0]),
  );

  return (
    <>
      <PageHeader
        title="My mistakes"
        native={language?.native_name}
        subtitle="Grouped by why they happened. Fixing a reason fixes many of them at once."
      />

      {report.loading ? (
        <Skeleton rows={4} />
      ) : (
        <>
          {data?.summary?.note && (
            <p className="card mb-6 border-l-4 !border-l-brand p-4 text-sm leading-relaxed">
              {data.summary.note}
            </p>
          )}

          {data && data.total > 0 && (
            <div className="mb-6 grid gap-3 sm:grid-cols-2">
              <div className="card p-4">
                <p className="text-2xl font-bold">{data.summary.real_total}</p>
                <p className="text-xs text-faint">
                  things to learn — these come back as practice
                </p>
              </div>
              <div className="card p-4">
                <p className="text-2xl font-bold text-warn">
                  {data.summary.careless_total}
                </p>
                <p className="text-xs text-faint">
                  careless slips — not scheduled, on purpose
                </p>
              </div>
            </div>
          )}

          {/* One level below the reason groups: the specific rules and points
              behind them. "Pronunciation is weak" is not actionable; "you keep
              dropping the linking rule, here it is" is. */}
          {(data?.weak_points?.length ?? 0) > 0 && (
            <Section
              title="What keeps going wrong"
              hint="Specific points, not skills — each one has a fix"
            >
              <p className="mb-3 text-sm leading-relaxed text-muted">
                {data!.weak_point_summary}
              </p>
              <div className="grid gap-2">
                {data!.weak_points.map((w) => (
                  <div key={w.id} className="card flex flex-wrap items-center gap-3 p-4">
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold">
                        {w.title}
                        {w.native_title && (
                          <Target lang={lang} className="ml-2 font-normal text-muted">
                            {w.native_title}
                          </Target>
                        )}
                      </p>
                      <p className="text-sm text-muted">{w.simple}</p>
                      <p className="mt-1 text-xs text-faint">
                        {w.failures} time{w.failures === 1 ? "" : "s"} · {w.skill}
                      </p>
                    </div>
                    {w.warrants_remediation ? (
                      <Link className="btn-primary shrink-0" to={`/fix/${w.id}`}>
                        Fix this
                      </Link>
                    ) : (
                      <Link className="btn-quiet shrink-0" to={`/fix/${w.id}`}>
                        Practise it
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {confusions.length > 0 && (
            <Section
              title="Patterns worth fixing properly"
              hint="Two things you have not yet separated — twenty minutes each"
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
                      <p className="mt-1 text-xs text-faint">{c.count} times so far</p>
                    ) : null}
                  </button>
                ))}
              </div>
            </Section>
          )}

          {!data || data.total === 0 ? (
            <Empty
              title="Nothing recorded"
              body="Mistakes appear here once you have answered a few questions. They are not held against you — they are how the app decides what to give you next."
              action={{ to: "/session", label: "Start today's session" }}
            />
          ) : (
            groups.map(([reason, rows]) => {
              const info = data.reasons[reason];
              const expanded = open === reason;
              return (
                <section key={reason} className="mb-4">
                  <button
                    className={`card w-full p-4 text-left transition-colors hover:bg-brand-soft/30 ${
                      TONE[reason] ?? ""
                    }`}
                    onClick={() => setOpen(expanded ? null : reason)}
                    aria-expanded={expanded}
                  >
                    <div className="mb-1 flex items-center gap-3">
                      <h2 className="flex-1 font-semibold">
                        {info?.name ?? "Recorded before this was tracked"}
                      </h2>
                      <span className="chip shrink-0">{rows.length}</span>
                      <span aria-hidden className="text-faint">
                        {expanded ? "▴" : "▾"}
                      </span>
                    </div>
                    <p className="text-sm text-muted">
                      {info?.simple ??
                        "These were recorded before the app worked out why an answer was wrong. They have deliberately not been given a guessed reason after the fact."}
                    </p>
                    {info?.advice && (
                      <p className="mt-2 text-xs leading-relaxed text-faint">
                        {info.advice}
                      </p>
                    )}
                  </button>

                  {expanded && (
                    <>
                      {/* What to do about this group. Careless is the one
                          whose honest answer is "nothing" — so it gets the
                          advice and no button. */}
                      {data.next_steps?.[reason] && (
                        <div className="card mt-2 flex flex-wrap items-center gap-3 p-4">
                          <p className="min-w-0 flex-1 text-sm leading-relaxed">
                            <span className="label mr-2">Next</span>
                            {data.next_steps[reason].advice}
                          </p>
                          {data.next_steps[reason].practisable && (
                            <button
                              className="btn-primary shrink-0"
                              onClick={() => setPractice(reason)}
                            >
                              Practise these
                            </button>
                          )}
                        </div>
                      )}

                      <ul className="card mt-2 divide-y divide-line animate-fade-up">
                        {rows.map((m) => (
                          <MistakeRow
                            key={m.id}
                            mistake={m}
                            lang={lang}
                            onResolve={() => {
                              void api.resolveMistake(String(m.id), lang).catch(() => {});
                              report.reload();
                            }}
                          />
                        ))}
                      </ul>
                    </>
                  )}
                </section>
              );
            })
          )}

          {(data?.undiagnosed ?? 0) > 0 && (
            <p className="mt-6 text-xs leading-relaxed text-faint">
              {data!.undiagnosed} older mistake
              {data!.undiagnosed === 1 ? "" : "s"} carry no reason. The signals
              that classify one — how long you took, whether you had it right
              before — were not recorded at the time, and inventing a diagnosis
              after the fact would be a guess presented as a fact.
            </p>
          )}
        </>
      )}
    </>
  );
}

function MistakeRow({
  mistake,
  lang,
  onResolve,
}: {
  mistake: Mistake;
  lang: string;
  onResolve: () => void;
}) {
  return (
    <li className="flex items-center gap-3 p-3.5">
      <span className="min-w-0 flex-1">
        <span className="block">
          <Target lang={lang} className="text-bad line-through">
            {mistake.given || "—"}
          </Target>
          <span className="mx-2 text-faint" aria-hidden>→</span>
          <Target lang={lang} className="text-good">
            {mistake.expected}
          </Target>
        </span>
        {mistake.explanation && (
          <span className="mt-0.5 block text-xs text-muted">
            {mistake.explanation}
          </span>
        )}
        {mistake.reason_why && (
          <span className="mt-0.5 block text-xs text-faint">
            {mistake.reason_why}
          </span>
        )}
      </span>
      {mistake.times_seen > 1 && (
        <span className="chip shrink-0">×{mistake.times_seen}</span>
      )}
      <button
        className="btn-quiet !px-2 text-xs"
        title="Mark as fixed"
        onClick={onResolve}
      >
        ✓
      </button>
    </li>
  );
}

/**
 * The learner's own mistakes, asked again.
 *
 * Not a generated drill that happens to cover a weak skill — these are the
 * exact items, re-posed in the direction that proves they are fixed. A
 * vocabulary gap comes back as recall rather than recognition, because
 * recognising it a second time proves nothing.
 */
function PractiseMistakes({
  reason,
  lang,
  onBack,
}: {
  reason: string;
  lang: string;
  onBack: () => void;
}) {
  const drill = useAsync(
    () => api.practiseMistakes(lang, { reason, count: 12 }),
    [lang, reason],
  );
  const [index, setIndex] = useState(0);

  if (drill.loading) return <Skeleton rows={3} />;
  if (drill.error) return <ErrorState error={drill.error} onRetry={drill.reload} />;

  const items = drill.data?.exercises ?? [];
  const ex = items[index];

  return (
    <>
      <button className="btn-quiet mb-4 !px-2 text-sm" onClick={onBack}>
        ← My mistakes
      </button>

      {!ex ? (
        <>
          <PageHeader
            title={index > 0 ? "Done" : "Nothing to practise"}
            subtitle={drill.data?.note}
          />
          <div className="flex flex-wrap gap-2">
            <button className="btn-primary" onClick={onBack}>
              Back to my mistakes
            </button>
            {index > 0 && (
              <button
                className="btn-quiet"
                onClick={() => {
                  setIndex(0);
                  drill.reload();
                }}
              >
                Again
              </button>
            )}
          </div>
        </>
      ) : (
        <>
          <PageHeader title="Practising your mistakes" subtitle={drill.data?.note} />
          <ExerciseCard
            key={index}
            exercise={ex}
            index={index}
            total={items.length}
            onAnswered={(v: Verdict, given, meta) => {
              void api
                .answer(lang, {
                  kind: ex.kind,
                  skill: ex.skill,
                  correct: v === "correct",
                  item_type: ex.item_type,
                  item_id: ex.item_id,
                  expected: String(ex.answer ?? ""),
                  given,
                  response_ms: meta.responseMs,
                  had_options: meta.hadOptions,
                })
                .catch(() => {});
            }}
            onNext={() => setIndex(index + 1)}
          />
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
        <button className="btn-quiet" disabled={step === 0} onClick={() => setStep(step - 1)}>
          ← Back
        </button>
        {step + 1 < steps.length ? (
          <button className="btn-primary" onClick={() => setStep(step + 1)}>
            Next →
          </button>
        ) : (
          <Link className="btn-primary" to="/session">
            Practise it →
          </Link>
        )}
      </div>
    </>
  );
}
