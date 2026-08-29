/**
 * Today.
 *
 * One screen that answers "what should I do right now", in the order the
 * answer actually matters: reviews that are due, the next lesson, and then the
 * things worth knowing about. Skills and streaks are below the fold on
 * purpose — they are feedback, not instructions.
 */

import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import {
  Bar, ErrorState, NotReady, PageHeader, Ring, Section, Skeleton, Target,
} from "../components/ui";
import type { Recommendation } from "../lib/types";

export default function Dashboard() {
  const { lang, language, me } = useApp();
  const { data, loading, error, notReady, reload } = useAsync(
    () => api.dashboard(lang),
    [lang],
  );
  // Fetched separately: the dashboard summarises progress, and which scripts a
  // language has is the writing endpoint's business.
  const scripts = useAsync(() => api.writingSystems(lang), [lang]);

  if (notReady) return <NotReady notReady={notReady} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <Skeleton rows={4} />;

  const d = data;
  const due = d.today.reviews_due;
  const name = me?.name ? `, ${me.name}` : "";

  return (
    <>
      <PageHeader
        title={`${d.greeting.english}${name}`}
        native={d.greeting.native}
        subtitle={
          d.level_details?.name
            ? `${d.level || d.estimated_level} · ${d.level_details.name}`
            : undefined
        }
      />

      {/* ---- what to do now ---- */}
      <div className="mb-8 grid gap-3 sm:grid-cols-2">
        <Link
          to="/review"
          className={`card flex items-center gap-4 p-5 transition-colors hover:bg-brand-soft/50 ${
            due > 0 ? "!border-brand/40" : ""
          }`}
        >
          <Ring percent={due > 0 ? 100 : 0} size={56}>
            <span className="text-base font-bold">{due}</span>
          </Ring>
          <div>
            <p className="font-semibold">
              {due > 0 ? "Reviews are due" : "Nothing due right now"}
            </p>
            <p className="text-sm text-muted">
              {due > 0
                ? `${due} card${due === 1 ? "" : "s"} waiting. This is the part that makes it stick.`
                : `Next batch: ${d.srs.due_tomorrow} tomorrow.`}
            </p>
          </div>
        </Link>

        <Link
          to={d.next_lesson ? `/learn/${d.next_lesson.id}` : "/learn"}
          className="card flex items-center gap-4 p-5 transition-colors hover:bg-brand-soft/50"
        >
          <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-brand-soft text-2xl" aria-hidden>
            ▤
          </span>
          <div className="min-w-0">
            <p className="font-semibold">
              {d.next_lesson ? "Next lesson" : "Browse lessons"}
            </p>
            <p className="truncate text-sm text-muted">
              {d.next_lesson?.title ?? "Pick up where you left off"}
            </p>
          </div>
        </Link>
      </div>

      {/* ---- today's goal ---- */}
      <Section title="Today">
        <div className="card p-5">
          <Bar
            percent={d.today.percent}
            label={`${d.today.minutes_done} of ${d.today.goal_minutes} minutes`}
            tone={d.today.percent >= 100 ? "good" : "brand"}
          />
          <div className="mt-4 flex flex-wrap gap-4 text-sm text-muted">
            <span>
              🔥 <strong className="text-ink">{d.streak.current}</strong> day streak
            </span>
            <span>
              ★ <strong className="text-ink">{d.xp}</strong> XP
            </span>
            <span>
              ✓ <strong className="text-ink">{d.known.all}</strong> items known
            </span>
          </div>
        </div>
      </Section>

      {/* ---- what the app noticed ---- */}
      {(d.recommendations?.length ?? 0) > 0 && (
        <Section title="Worth doing" hint="Chosen from what you have got wrong recently">
          <div className="grid gap-2">
            {d.recommendations!.map((r, i) => (
              <Link
                key={`${r.kind}-${i}`}
                to={hrefFor(r)}
                className="card flex items-start justify-between gap-4 p-4 hover:bg-brand-soft/40"
              >
                <div>
                  <p className="font-medium">{r.title}</p>
                  <p className="text-sm text-muted">{r.reason}</p>
                </div>
                <span className="chip shrink-0 capitalize">{r.kind}</span>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {(d.confusions?.length ?? 0) > 0 && (
        <Section
          title="Something you keep mixing up"
          hint="Not a random wrong answer — a pattern"
        >
          <div className="grid gap-2">
            {d.confusions!.map((c) => (
              <Link
                key={c.id}
                to="/mistakes"
                className="card p-4 hover:bg-brand-soft/40"
              >
                <p className="font-medium">{c.title}</p>
                <p className="text-sm text-muted">{c.one_line}</p>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* ---- the writing system, while it still matters ---- */}
      {d.script_mastery < 0.95 && (scripts.data?.writing_systems.length ?? 0) > 0 && (
        <Section title="Writing system" hint="Everything else waits on this">
          <div className="grid gap-2 sm:grid-cols-2">
            {scripts.data!.writing_systems.map((w) => (
              <Link key={w.id} to="/writing" className="card p-4 hover:bg-brand-soft/40">
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="font-medium">{w.name}</span>
                  <Target lang={lang} className="text-muted">
                    {w.native_name}
                  </Target>
                </div>
                {w.is_closed_inventory ? (
                  <Bar percent={(w.mastery ?? 0) * 100} />
                ) : (
                  <p className="text-xs text-faint">
                    An open set — taught by frequency, never finished.
                  </p>
                )}
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* ---- four skills ---- */}
      <Section
        title="Skills"
        hint={
          Object.values(d.skills).every((s) => s.attempts === 0)
            ? "Nothing measured yet — these fill in as you answer"
            : undefined
        }
      >
        <div className="card divide-y divide-line">
          {Object.values(d.skills).map((s) => (
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
              <span className="w-20 shrink-0 text-right text-xs text-faint">
                {s.attempts === 0 ? "no data" : `${s.attempts} tried`}
              </span>
            </div>
          ))}
        </div>
      </Section>

      {language?.status !== "in_progress" && language?.status_note && (
        <p className="rounded-2xl border border-warn/30 bg-warn/5 p-4 text-sm leading-relaxed text-muted">
          <strong className="text-warn">Where {language.name} stands: </strong>
          {language.status_note}
        </p>
      )}
    </>
  );
}

/** Where a recommendation points. The payload's shape follows its kind. */
function hrefFor(r: Recommendation): string {
  if (r.kind === "lesson" && r.payload?.lesson_id) return `/learn/${r.payload.lesson_id}`;
  if (r.kind === "confusion") return "/mistakes";
  if (r.kind === "review") return "/review";
  return "/practice";
}
