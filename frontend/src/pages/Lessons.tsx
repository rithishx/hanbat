/**
 * The lesson list, grouped by unit.
 *
 * A locked lesson stays visible and says what is blocking it. Hiding it would
 * make the curriculum look shorter than it is and leave the learner with no
 * sense of where they are going; greying it out with "finish the Hangul unit
 * first" answers the question before it is asked.
 */

import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import {
  Bar, ErrorState, NotReady, PageHeader, Section, Skeleton, Target,
} from "../components/ui";
import type { LessonSummary } from "../lib/types";

export default function Lessons() {
  const { lang, language } = useApp();
  const lessons = useAsync(() => api.lessons(lang), [lang]);
  const units = useAsync(() => api.units(lang), [lang]);

  if (lessons.notReady) return <NotReady notReady={lessons.notReady} />;
  if (lessons.error) return <ErrorState error={lessons.error} onRetry={lessons.reload} />;
  if (lessons.loading || !lessons.data) return <Skeleton rows={5} />;

  const byUnit = new Map<string, LessonSummary[]>();
  for (const l of lessons.data.lessons) {
    const key = l.unit || l.level || "—";
    if (!byUnit.has(key)) byUnit.set(key, []);
    byUnit.get(key)!.push(l);
  }
  const unitStats = new Map(
    (units.data?.units ?? []).map((u) => [u.id, u]),
  );

  return (
    <>
      <PageHeader
        title="Lessons"
        native={language?.native_name}
        subtitle={`${lessons.data.lessons.length} lessons, in order. Each one ends where the next begins.`}
      />

      {[...byUnit.entries()].map(([unitId, items]) => {
        const stat = unitStats.get(unitId);
        return (
          <Section
            key={unitId}
            title={items[0]?.level || unitId}
            right={
              stat && (
                <span className="text-xs text-faint">
                  {stat.completed} / {stat.lessons} done
                </span>
              )
            }
          >
            {stat && (
              <div className="mb-3">
                <Bar percent={stat.percent} tone={stat.percent >= 100 ? "good" : "brand"} />
              </div>
            )}
            <ol className="grid gap-2">
              {items.map((l) => (
                <li key={l.id}>
                  <LessonRow lesson={l} lang={lang} />
                </li>
              ))}
            </ol>
          </Section>
        );
      })}
    </>
  );
}

function LessonRow({ lesson, lang }: { lesson: LessonSummary; lang: string }) {
  const done = lesson.status === "completed";
  const locked = lesson.locked;

  const inner = (
    <>
      <span
        className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl text-sm font-semibold ${
          done
            ? "bg-good/15 text-good"
            : locked
              ? "bg-line text-faint"
              : "bg-brand-soft text-brand"
        }`}
        aria-hidden
      >
        {done ? "✓" : locked ? "🔒" : lesson.ordinal}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-baseline gap-2">
          <span className="font-medium">{lesson.title}</span>
          {lesson.title_native && (
            <Target lang={lang} className="text-sm text-faint">
              {lesson.title_native}
            </Target>
          )}
        </span>
        {locked && lesson.blocked_by?.length ? (
          <span className="mt-0.5 block text-xs text-warn">
            Finish {lesson.blocked_by.join(", ")} first
          </span>
        ) : lesson.objectives?.length ? (
          <span className="mt-0.5 block truncate text-xs text-faint">
            {lesson.objectives[0]}
          </span>
        ) : null}
      </span>
      <span className="chip shrink-0">{lesson.est_minutes} min</span>
    </>
  );

  if (locked) {
    return (
      <div className="card flex cursor-not-allowed items-center gap-3 p-3.5 opacity-60">
        {inner}
      </div>
    );
  }
  return (
    <Link
      to={`/learn/${lesson.id}`}
      className="card flex items-center gap-3 p-3.5 transition-colors hover:bg-brand-soft/40"
    >
      {inner}
    </Link>
  );
}
