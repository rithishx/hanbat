/**
 * The placement test.
 *
 * Sectioned by skill, with a stop rule the backend supplies: three wrong in a
 * row ends a section and moves on. That is not a shortcut, it is the point —
 * a learner who cannot read the script does not need eight more questions
 * proving it, and making them sit through the whole thing is how a placement
 * test turns into a discouraging exam.
 *
 * Skipping is a first-class answer and says so.
 */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import { ExerciseCard, type Verdict } from "../components/Exercise";
import { ErrorState, Loading, Target } from "../components/ui";
import type { Exercise, LevelDetails } from "../lib/types";

interface Section {
  /** The API labels a section by skill; either key identifies it. */
  id?: string;
  skill?: string;
  title: string;
  exercises: Exercise[];
}

const sectionId = (s: Section) => s.id ?? s.skill ?? s.title;

export default function Placement() {
  const nav = useNavigate();
  const { lang, refresh } = useApp();
  const { data, loading, error, reload } = useAsync(
    () => api.placementTest(lang),
    [lang],
  );

  const [sectionIndex, setSectionIndex] = useState(0);
  const [itemIndex, setItemIndex] = useState(0);
  const [wrongRun, setWrongRun] = useState(0);
  const [tally, setTally] = useState<Record<string, { right: number; asked: number }>>({});
  const [result, setResult] = useState<{ level: string; reason?: string; details?: LevelDetails } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const sections = useMemo<Section[]>(
    () => (data?.sections ?? []).filter((s) => s.exercises.length),
    [data],
  );

  if (loading) return <Page><Loading what="the placement test" /></Page>;
  if (error) return <Page><ErrorState error={error} onRetry={reload} /></Page>;
  if (!sections.length) return <Page><Loading /></Page>;

  if (result) {
    return (
      <Page>
        <div className="card animate-fade-up p-8 text-center">
          <p className="label mb-2">Starting level</p>
          <p className="mb-1 text-5xl font-bold text-brand">{result.level}</p>
          {result.details?.name && (
            <p className="mb-4 text-lg">{result.details.name}</p>
          )}
          {result.reason && (
            <p className="mx-auto mb-6 max-w-md text-sm leading-relaxed text-muted">
              {result.reason}
            </p>
          )}
          {result.details?.can_do && (
            <ul className="mx-auto mb-6 max-w-md space-y-1.5 text-left text-sm text-muted">
              {result.details.can_do.map((c) => (
                <li key={c} className="flex gap-2">
                  <span className="text-good" aria-hidden>✓</span>
                  {c}
                </li>
              ))}
            </ul>
          )}
          <button
            className="btn-primary"
            onClick={async () => {
              await refresh();
              nav("/", { replace: true });
            }}
          >
            Start learning →
          </button>
        </div>
      </Page>
    );
  }

  const section = sections[sectionIndex];
  const exercise = section.exercises[itemIndex];

  const record = (correct: boolean) => {
    const key = sectionId(section);
    setTally((t) => {
      const cur = t[key] ?? { right: 0, asked: 0 };
      return {
        ...t,
        [key]: { right: cur.right + (correct ? 1 : 0), asked: cur.asked + 1 },
      };
    });
  };

  const advance = (correct: boolean) => {
    const run = correct ? 0 : wrongRun + 1;
    setWrongRun(run);

    // The stop rule the API describes: three wrong in a row ends the section.
    const sectionDone = run >= 3 || itemIndex + 1 >= section.exercises.length;
    if (!sectionDone) {
      setItemIndex(itemIndex + 1);
      return;
    }
    setWrongRun(0);
    setItemIndex(0);
    if (sectionIndex + 1 < sections.length) {
      setSectionIndex(sectionIndex + 1);
    } else {
      void finish();
    }
  };

  const finish = async () => {
    setSubmitting(true);
    const scores: Record<string, number> = {};
    for (const [id, t] of Object.entries(tally)) {
      scores[id] = t.asked ? t.right / t.asked : 0;
    }
    for (const s of sections) if (!(sectionId(s) in scores)) scores[sectionId(s)] = 0;
    try {
      const res = await api.submitPlacement(lang, scores);
      setResult(res as unknown as { level: string; reason?: string; details?: LevelDetails });
    } catch (e) {
      setResult({ level: "pre-A1", reason: e instanceof Error ? e.message : undefined });
    }
    setSubmitting(false);
  };

  return (
    <Page>
      <div className="mb-5">
        <div className="mb-2 flex items-center justify-between text-xs text-faint">
          <span>
            Section {sectionIndex + 1} of {sections.length} · {section.title}
          </span>
          <button
            className="font-semibold text-brand hover:underline"
            onClick={() => void finish()}
            disabled={submitting}
          >
            Finish early
          </button>
        </div>
        <div className="flex gap-1" aria-hidden>
          {sections.map((s, i) => (
            <div
              key={sectionId(s)}
              className={`h-1 flex-1 rounded-full ${
                i < sectionIndex ? "bg-brand" : i === sectionIndex ? "bg-brand/50" : "bg-line"
              }`}
            />
          ))}
        </div>
      </div>

      <ExerciseCard
        key={`${sectionId(section)}-${itemIndex}`}
        exercise={exercise}
        index={itemIndex}
        total={section.exercises.length}
        onAnswered={(v: Verdict) => record(v === "correct")}
        onNext={() => advance(true)}
      />

      <div className="mt-4 text-center">
        <button className="btn-quiet text-sm" onClick={() => advance(false)}>
          Skip — I don't know this
        </button>
        <p className="mt-1 text-xs text-faint">
          Skipping is a real answer. It tells the test just as much as a wrong one.
        </p>
      </div>
    </Page>
  );
}

function Page({ children }: { children: React.ReactNode }) {
  const { language } = useApp();
  return (
    <div className="mx-auto min-h-dvh max-w-2xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-xl font-bold">
          Where should you start?
          {language && (
            <Target lang={language.code} className="ml-2 font-normal text-muted">
              {language.native_name}
            </Target>
          )}
        </h1>
      </header>
      {children}
    </div>
  );
}
