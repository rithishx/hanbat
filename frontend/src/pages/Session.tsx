/**
 * Today's session.
 *
 * The screen that answers "what should I do right now" once, instead of
 * leaving the learner to assemble an answer out of the review queue, the
 * lesson list and the practice menu. It shows the plan before starting it —
 * every block says why it is there and how long it takes — because a plan you
 * cannot see is indistinguishable from an app deciding things at you.
 *
 * Nothing is padded. If the plan is short, the note says why, and the screen
 * does not offer to top it up with filler.
 */

import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync, useElapsed } from "../lib/hooks";
import { ExerciseCard, type Verdict } from "../components/Exercise";
import {
  Bar, ErrorState, NotReady, PageHeader, Section, Skeleton, Target,
} from "../components/ui";
import type { Diagnosis, Exercise, SessionBlock } from "../lib/types";

const BLOCK_ICON: Record<string, string> = {
  review: "↻",
  remediation: "⌾",
  confusion: "!",
  weakness: "◈",
  calibrate: "◎",
  lesson: "▤",
  vocabulary: "▦",
  production: "✎",
};

export default function Session() {
  const { lang, language } = useApp();
  const nav = useNavigate();
  const elapsed = useElapsed();
  const [seed] = useState(() => Math.floor(Math.random() * 100000));

  const plan = useAsync(() => api.sessionPlan(lang, { seed }), [lang]);
  const [running, setRunning] = useState<number | null>(null);
  const [done, setDone] = useState<Set<string>>(new Set());

  if (plan.notReady) return <NotReady notReady={plan.notReady} />;
  if (plan.error) return <ErrorState error={plan.error} onRetry={plan.reload} />;
  if (plan.loading || !plan.data) return <Skeleton rows={4} />;

  const p = plan.data;
  const blocks = p.blocks;

  // ---- running a drill block ------------------------------------------
  if (running !== null && blocks[running]) {
    const block = blocks[running];
    return (
      <BlockRunner
        block={block}
        lang={lang}
        onFinish={() => {
          setDone((d) => new Set(d).add(block.id));
          setRunning(null);
          void api
            .session(lang, { seconds: elapsed(), kind: "session" })
            .catch(() => {});
        }}
        onQuit={() => setRunning(null)}
      />
    );
  }

  const start = (index: number) => {
    const block = blocks[index];
    if (block.kind === "review") return nav("/review");
    if (block.kind === "lesson" && block.payload.lesson_id)
      return nav(`/learn/${block.payload.lesson_id}`);
    if (block.kind === "confusion") return nav("/mistakes");
    // The most specific block there is: one rule, taught then drilled across
    // modalities. It has its own page because it is not a drill.
    if (block.kind === "remediation" && block.payload.point_id)
      return nav(`/fix/${block.payload.point_id}`);
    setRunning(index);
  };

  const completed = blocks.filter((b) => done.has(b.id)).length;

  return (
    <>
      <PageHeader
        title="Today's session"
        native={language?.native_name}
        subtitle={`About ${p.planned_minutes} minutes, in the order that teaches best.`}
      />

      {blocks.length > 0 && (
        <div className="mb-6">
          <Bar
            percent={(completed / blocks.length) * 100}
            label={`${completed} of ${blocks.length} done`}
            tone={completed === blocks.length ? "good" : "brand"}
          />
        </div>
      )}

      <p className="card mb-6 p-4 text-sm leading-relaxed text-muted">{p.note}</p>

      {blocks.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="mb-2 text-4xl" aria-hidden>☕</p>
          <h2 className="mb-1 text-lg font-semibold">Nothing to do right now</h2>
          <p className="mx-auto mb-5 max-w-md text-sm leading-relaxed text-muted">
            That is a real answer rather than an empty screen. The app will not
            invent work to fill the time you set aside.
          </p>
          <Link className="btn-ghost" to="/vocabulary">
            Browse vocabulary anyway
          </Link>
        </div>
      ) : (
        <ol className="space-y-3">
          {blocks.map((b, i) => {
            const finished = done.has(b.id);
            return (
              <li key={b.id}>
                <div
                  className={`card p-5 ${finished ? "opacity-60" : ""} ${
                    i === 0 && !finished ? "!border-brand" : ""
                  }`}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-3">
                    <span
                      className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand"
                      aria-hidden
                    >
                      {finished ? "✓" : BLOCK_ICON[b.kind] ?? "•"}
                    </span>
                    <h2 className="flex-1 font-semibold">{b.title}</h2>
                    <span className="chip shrink-0">{b.minutes} min</span>
                  </div>

                  <p className="mb-4 text-sm leading-relaxed text-muted">{b.why}</p>

                  <button
                    className={finished ? "btn-ghost" : "btn-primary"}
                    onClick={() => start(i)}
                  >
                    {finished ? "Do it again" : "Start"}
                  </button>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {p.focus.length > 0 && (
        <Section
          title="What this session is aiming at"
          hint="Weighted by your scores and your recent mistakes"
        >
          <div className="card divide-y divide-line">
            {p.focus.map((f) => (
              <div key={f.skill} className="flex items-center gap-4 p-4">
                <span className="w-28 shrink-0 text-sm font-medium capitalize">
                  {f.skill}
                </span>
                <div className="flex-1">
                  <Bar percent={f.weight * 100} tone={f.weight > 0.7 ? "warn" : "brand"} />
                </div>
                <span className="w-56 shrink-0 text-right text-xs text-faint">
                  {f.why}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

// ==========================================================================

function BlockRunner({
  block,
  lang,
  onFinish,
  onQuit,
}: {
  block: SessionBlock;
  lang: string;
  onFinish: () => void;
  onQuit: () => void;
}) {
  const specs = useMemo(() => block.payload.specs ?? [], [block]);
  const drills = useAsync(async () => {
    const batches = await Promise.all(
      specs.map((s) =>
        api
          .practice(lang, { spec: s, seed: Math.floor(Math.random() * 100000) })
          .then((r) => r.exercises)
          .catch(() => [] as Exercise[]),
      ),
    );
    return batches.flat();
  }, [block.id, lang]);

  const [index, setIndex] = useState(0);
  const [right, setRight] = useState(0);
  const [asked, setAsked] = useState(0);
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);

  if (drills.loading) return <Skeleton rows={3} />;
  if (drills.error) return <ErrorState error={drills.error} onRetry={drills.reload} />;

  const usable = (drills.data ?? []).filter(
    (e) => e.kind !== "unsupported" && e.kind !== "error",
  );
  const blocked = (drills.data ?? []).find((e) => e.kind === "unsupported");

  if (usable.length === 0) {
    return (
      <>
        <button className="btn-quiet mb-4 !px-2 text-sm" onClick={onQuit}>
          ← Session
        </button>
        <div className="card p-6">
          <h2 className="mb-2 font-semibold text-warn">Nothing to drill here</h2>
          <p className="mb-4 text-sm leading-relaxed text-muted">
            {blocked?.explain ??
              "This block produced no exercises, which usually means the content it needs is not written yet."}
          </p>
          <button className="btn-primary" onClick={onFinish}>
            Skip this block
          </button>
        </div>
      </>
    );
  }

  const exercise = usable[index];

  if (!exercise) {
    const pct = asked ? Math.round((right / asked) * 100) : null;
    return (
      <>
        <div className="card animate-fade-up p-8 text-center">
          <p className="mb-2 text-4xl" aria-hidden>✓</p>
          <h2 className="mb-1 text-lg font-semibold">{block.title}</h2>
          <p className="mb-5 text-sm text-muted">
            {pct === null ? "Done." : `${right} of ${asked} right — ${pct}%.`}
          </p>
          <button className="btn-primary" onClick={onFinish}>
            Back to the session →
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-3">
        <button className="btn-quiet !px-2 text-sm" onClick={onQuit}>
          ← Session
        </button>
        <span className="text-xs text-faint">{block.title}</span>
      </div>

      <ExerciseCard
        key={index}
        exercise={exercise}
        index={index}
        total={usable.length}
        diagnosis={diagnosis}
        onAnswered={(v: Verdict, given, meta) => {
          if (v !== "self") {
            setAsked((a) => a + 1);
            if (v === "correct") setRight((r) => r + 1);
          }
          setDiagnosis(null);
          void api
            .answer(lang, {
              kind: exercise.kind,
              skill: exercise.skill,
              correct: v === "correct",
              item_type: exercise.item_type,
              item_id: exercise.item_id,
              expected: String(exercise.answer ?? ""),
              given,
              response_ms: meta.responseMs,
              had_options: meta.hadOptions,
            })
            .then((r) => setDiagnosis(r.diagnosis ?? null))
            .catch(() => {});
        }}
        onNext={() => {
          setDiagnosis(null);
          setIndex(index + 1);
        }}
      />

      <p className="mt-4 text-center text-xs text-faint">
        <Target lang={lang}>{block.skill}</Target>
        {block.skill && " · "}
        {usable.length - index - 1} left in this block
      </p>
    </>
  );
}
