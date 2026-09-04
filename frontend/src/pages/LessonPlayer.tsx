/**
 * The lesson runtime.
 *
 * A lesson is a sequence of steps in a fixed pedagogical order —
 * warmup, learn, understand, hear, repeat, practice, recall, apply, review,
 * summary — and this walks them one screen at a time. Prose steps are read;
 * generated steps expand into exercises the backend produced for this
 * request, so a second run through the same lesson is not the same questions.
 *
 * The step name is shown. A learner who can see they are on "recall" and that
 * hints are off understands why it suddenly got harder, instead of concluding
 * they have got worse.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync, useElapsed } from "../lib/hooks";
import { ExerciseCard, type Verdict } from "../components/Exercise";
import {
  AudioButton, ErrorState, Loading, NotReady, Target, TwoLevel,
} from "../components/ui";
import type { Exercise, Lesson, LessonStep } from "../lib/types";

const STEP_LABEL: Record<string, string> = {
  warmup: "Warm up",
  learn: "Learn",
  understand: "Understand",
  hear: "Hear it",
  repeat: "Say it",
  practice: "Practise",
  recall: "Recall",
  apply: "Apply",
  produce: "Produce",
  review: "Into review",
  summary: "Summary",
};

/** One screen of the lesson: either prose, or a batch of exercises. */
type Screen =
  | { kind: "prose"; step: LessonStep; index: number }
  | { kind: "drill"; step: LessonStep; index: number; exercises: Exercise[] };

export default function LessonPlayer() {
  const { lessonId = "" } = useParams();
  const { lang } = useApp();
  const nav = useNavigate();
  const elapsed = useElapsed();

  const lesson = useAsync(() => api.lesson(lessonId, lang), [lessonId, lang]);
  const seed = useRef(Math.floor(Math.random() * 100000)).current;
  const drills = useAsync(
    () => api.lessonExercises(lessonId, lang, { seed }),
    [lessonId, lang],
  );

  const [screenIndex, setScreenIndex] = useState(0);
  const [itemIndex, setItemIndex] = useState(0);
  const [right, setRight] = useState(0);
  const [asked, setAsked] = useState(0);
  const [finished, setFinished] = useState(false);

  const screens = useMemo<Screen[]>(() => {
    const steps = (lesson.data?.body?.steps ?? []) as LessonStep[];
    const byId = new Map<string, Exercise[]>();
    for (const ex of drills.data?.exercises ?? []) {
      const id = ex.exercise_id ?? "";
      if (!byId.has(id)) byId.set(id, []);
      byId.get(id)!.push(ex);
    }
    return steps.map((step, i): Screen => {
      const id = `${lessonId}-s${String(i).padStart(2, "0")}`;
      const exercises = byId.get(id) ?? [];
      return exercises.length
        ? { kind: "drill", step, index: i, exercises }
        : { kind: "prose", step, index: i };
    });
  }, [lesson.data, drills.data, lessonId]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [screenIndex, itemIndex]);

  if (lesson.notReady) return <NotReady notReady={lesson.notReady} />;
  if (lesson.error) return <ErrorState error={lesson.error} onRetry={lesson.reload} />;
  if (lesson.loading || drills.loading || !lesson.data) return <Loading what="the lesson" />;

  const L = lesson.data;

  if (finished) {
    return <Done lesson={L} right={right} asked={asked} />;
  }

  const screen = screens[screenIndex];
  const progress = screens.length ? (screenIndex / screens.length) * 100 : 0;

  const nextScreen = async () => {
    if (screenIndex + 1 < screens.length) {
      setScreenIndex(screenIndex + 1);
      setItemIndex(0);
      return;
    }
    const score = asked ? right / asked : undefined;
    try {
      await api.saveLessonProgress(L.id, lang, {
        status: "completed",
        score,
        seconds: elapsed(),
      });
      await api.session(lang, { seconds: elapsed(), kind: "lesson" });
    } catch {
      /* progress is not worth blocking the celebration for */
    }
    setFinished(true);
  };

  return (
    <>
      {/* ---- header ---- */}
      <div className="mb-5">
        <div className="mb-2 flex items-center justify-between gap-3">
          <button className="btn-quiet !px-2 text-sm" onClick={() => nav("/learn")}>
            ← Lessons
          </button>
          <span className="text-xs text-faint">
            {screenIndex + 1} / {screens.length}
          </span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-brand transition-[width] duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <h1 className="mt-3 flex flex-wrap items-baseline gap-2 text-lg font-bold">
          {L.title}
          {L.title_native && (
            <Target lang={lang} className="font-normal text-muted">
              {L.title_native}
            </Target>
          )}
        </h1>
        {screen && (
          <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-brand">
            {STEP_LABEL[screen.step.step] ?? screen.step.step}
          </p>
        )}
      </div>

      {/* ---- body ---- */}
      {screen?.kind === "prose" && (
        <ProseStep step={screen.step} lang={lang} onNext={() => void nextScreen()} />
      )}

      {screen?.kind === "drill" && (
        <ExerciseCard
          key={`${screen.index}-${itemIndex}`}
          exercise={screen.exercises[itemIndex]}
          index={itemIndex}
          total={screen.exercises.length}
          onAnswered={(v: Verdict, given, meta) => {
            const ex = screen.exercises[itemIndex];
            if (v !== "self") {
              setAsked((a) => a + 1);
              if (v === "correct") setRight((r) => r + 1);
            }
            void api
              .answer(lang, {
                exercise_id: ex.exercise_id,
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
              .catch(() => {
                /* an unrecorded answer must not interrupt a lesson */
              });
          }}
          onNext={() => {
            if (itemIndex + 1 < screen.exercises.length) setItemIndex(itemIndex + 1);
            else void nextScreen();
          }}
        />
      )}

      {!screen && (
        <div className="card p-6">
          <p className="text-muted">This lesson has no steps yet.</p>
          <button className="btn-primary mt-4" onClick={() => void nextScreen()}>
            Finish
          </button>
        </div>
      )}
    </>
  );
}

// ==========================================================================

function ProseStep({
  step,
  lang,
  onNext,
}: {
  step: LessonStep;
  lang: string;
  onNext: () => void;
}) {
  // `body` is a paragraph or a list of them, depending on the step. The index
  // signature on LessonStep widens either to unknown, so normalise here rather
  // than casting at every use.
  const paragraphs: string[] = Array.isArray(step.body)
    ? (step.body as unknown[]).map(String)
    : step.body
      ? [String(step.body)]
      : [];

  return (
    <article className="card animate-fade-up p-5 sm:p-7">
      {step.heading && (
        <h2 className="mb-4 text-xl font-semibold leading-snug">{step.heading}</h2>
      )}

      {/* Characters being introduced, big enough to actually see. */}
      {Array.isArray(step.jamo) && <UnitStrip units={step.jamo as string[]} lang={lang} />}
      {Array.isArray(step.kana) && <UnitStrip units={step.kana as string[]} lang={lang} />}
      {Array.isArray(step.units) && <UnitStrip units={step.units as string[]} lang={lang} />}

      {paragraphs.map((p, i) => (
        <p key={i} className="mb-3 whitespace-pre-line leading-relaxed last:mb-0">
          {p}
        </p>
      ))}

      {Boolean(step.simple) && (
        <TwoLevel
          simple={String(step.simple)}
          technical={step.technical ? String(step.technical) : undefined}
        />
      )}

      {/* warmup: recall from the previous lesson */}
      {Array.isArray(step.questions) && (
        <Warmup questions={step.questions as { q: string; a: string }[]} />
      )}

      {/* apply: real words to read */}
      {Array.isArray(step.items) && step.items.length > 0 && (
        <WordList items={step.items as Record<string, string>[]} lang={lang} />
      )}

      {/* repeat: say it aloud */}
      {Array.isArray(step.targets) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {(step.targets as string[]).map((t) => (
            <span key={t} className="card flex items-center gap-2 px-3 py-2">
              <Target lang={lang} size="md">{t}</Target>
              <AudioButton text={t} lang={lang} />
            </span>
          ))}
        </div>
      )}

      {Array.isArray(step.points) && (
        <ul className="mt-2 space-y-2">
          {(step.points as string[]).map((p) => (
            <li key={p} className="flex gap-2.5 text-[0.975rem]">
              <span className="text-good" aria-hidden>✓</span>
              {p}
            </li>
          ))}
        </ul>
      )}

      {Boolean(step.note) && (
        <p className="mt-4 rounded-xl bg-brand-soft/60 p-3 text-sm leading-relaxed text-muted">
          {String(step.note)}
        </p>
      )}

      <button className="btn-primary mt-6 w-full sm:w-auto" onClick={onNext} autoFocus>
        Continue →
      </button>
    </article>
  );
}

function UnitStrip({ units, lang }: { units: string[]; lang: string }) {
  return (
    <div className="mb-5 flex flex-wrap gap-3">
      {units.map((u) => (
        <button
          key={u}
          className="card grid place-items-center px-5 py-4 transition-colors hover:bg-brand-soft"
          onClick={() => {
            const ev = new CustomEvent("noop");
            window.dispatchEvent(ev);
          }}
        >
          <Target lang={lang} size="xl" className="font-semibold">
            {u}
          </Target>
          <AudioButton text={u} lang={lang} className="mt-2 !border-0 !px-2 !py-1" />
        </button>
      ))}
    </div>
  );
}

function Warmup({ questions }: { questions: { q: string; a: string }[] }) {
  const [shown, setShown] = useState<number[]>([]);
  return (
    <div className="space-y-2">
      {questions.map((q, i) => (
        <div key={i} className="rounded-xl border border-line p-3">
          <p className="text-sm font-medium">{q.q}</p>
          {shown.includes(i) ? (
            <p className="mt-1 text-sm text-good">{q.a}</p>
          ) : (
            <button
              className="mt-1 text-xs font-semibold text-brand hover:underline"
              onClick={() => setShown([...shown, i])}
            >
              Show the answer
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function WordList({
  items,
  lang,
}: {
  items: Record<string, string>[];
  lang: string;
}) {
  return (
    <ul className="mt-4 divide-y divide-line rounded-xl border border-line">
      {items.map((it, i) => {
        const word = it.target ?? it.term ?? it.korean ?? "";
        if (!word) return null;
        return (
          <li key={i} className="flex items-center gap-3 p-3">
            <Target lang={lang} size="md" className="font-semibold">
              {word}
            </Target>
            <span className="flex-1 text-sm text-muted">
              {it.meaning}
              {it.pronounced && (
                <span className="ml-2 text-xs text-faint">said {it.pronounced}</span>
              )}
              {it.note && <span className="block text-xs text-faint">{it.note}</span>}
            </span>
            <AudioButton text={word} lang={lang} />
          </li>
        );
      })}
    </ul>
  );
}

function Done({
  lesson,
  right,
  asked,
}: {
  lesson: Lesson;
  right: number;
  asked: number;
}) {
  const pct = asked ? Math.round((right / asked) * 100) : null;
  return (
    <div className="card animate-fade-up p-8 text-center">
      <p className="mb-2 text-5xl" aria-hidden>✓</p>
      <h1 className="mb-1 text-2xl font-bold">{lesson.title}</h1>
      <p className="mb-6 text-sm text-muted">
        {pct === null
          ? "Read through. Nothing to score on this one."
          : `${right} of ${asked} right — ${pct}%.`}
      </p>

      {lesson.objectives?.length > 0 && (
        <ul className="mx-auto mb-6 max-w-md space-y-1.5 text-left text-sm text-muted">
          {lesson.objectives.map((o) => (
            <li key={o} className="flex gap-2">
              <span className="text-good" aria-hidden>✓</span>
              {o}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap justify-center gap-2">
        <Link className="btn-primary" to="/learn">
          Next lesson →
        </Link>
        <Link className="btn-ghost" to="/review">
          Review now
        </Link>
      </div>
      <p className="mt-4 text-xs text-faint">
        What you met here is now in your review queue. Coming back to it
        tomorrow is what turns it into memory.
      </p>
    </div>
  );
}
