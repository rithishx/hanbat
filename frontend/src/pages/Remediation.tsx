/**
 * Fixing one specific thing, properly.
 *
 * The mistakes screen says what went wrong and the dashboard says how you are
 * doing. Neither answers the question a learner actually has after failing the
 * same rule four times, which is "so what do I do about it". This page is that
 * answer, and it is deliberately not another round of the same question:
 * understand the rule, hear it, say it, then use it.
 *
 * Everything on it comes from the language's own engine — the explanation, the
 * examples, the drills — so it cannot drift into teaching something adjacent to
 * the thing the learner actually got wrong.
 */

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync, useElapsed } from "../lib/hooks";
import { ExerciseCard, type Verdict } from "../components/Exercise";
import {
  AudioButton, ErrorState, NotReady, PageHeader, Skeleton, Target, TwoLevel,
} from "../components/ui";
import type { Exercise } from "../lib/types";

/** The authored walkthrough for a confusion pair, folded into the fix. */
function MiniCourse({ confusionId, lang }: { confusionId: string; lang: string }) {
  const course = useAsync(() => api.miniCourse(confusionId, lang), [confusionId, lang]);
  const [open, setOpen] = useState(false);
  const steps = course.data?.steps ?? [];
  if (!steps.length) return null;

  return (
    <div className="mt-4 border-t border-line pt-4">
      <button
        className="text-xs font-semibold text-brand hover:underline"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {open ? "Hide" : "The longer walkthrough"} {open ? "▲" : "▾"}
      </button>
      {open && (
        <div className="mt-3 space-y-4">
          {steps.map((s, i) => (
            <div key={i}>
              {s.heading && <h3 className="mb-1 font-semibold">{s.heading}</h3>}
              <p className="whitespace-pre-line text-sm leading-relaxed text-muted">
                {s.body}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Remediation() {
  const { pointId = "" } = useParams();
  const { lang } = useApp();
  const nav = useNavigate();
  const elapsed = useElapsed();

  const plan = useAsync(() => api.remediation(lang, pointId), [lang, pointId]);
  const [step, setStep] = useState(0);
  const [drill, setDrill] = useState<Exercise[] | null>(null);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [finished, setFinished] = useState<string | null>(null);

  if (plan.notReady) return <NotReady notReady={plan.notReady} />;
  if (plan.error) return <ErrorState error={plan.error} onRetry={plan.reload} />;
  if (plan.loading || !plan.data) return <Skeleton rows={4} />;

  const p = plan.data;
  const steps = p.steps;
  const current = steps[step];

  const startStep = async (i: number) => {
    const s = steps[i];
    setStep(i);
    setIndex(0);
    setDrill(null);
    if (!s?.spec) return;
    setLoading(true);
    try {
      const res = await api.practice(lang, {
        spec: s.spec as Record<string, unknown>,
        seed: Math.floor(Math.random() * 100000),
      });
      setDrill(res.exercises);
    } finally {
      setLoading(false);
    }
  };

  const done = async () => {
    const r = await api.finishRemediation(lang, pointId);
    void api.session(lang, { seconds: elapsed(), kind: "remediation" }).catch(() => {});
    setFinished(r.note);
  };

  if (finished) {
    return (
      <>
        <PageHeader title="Done" subtitle={p.point.title} />
        <div className="card p-6">
          <p className="mb-4 text-sm leading-relaxed text-muted">{finished}</p>
          <div className="flex flex-wrap gap-2">
            <Link className="btn-primary" to="/session">
              Back to today's session
            </Link>
            <Link className="btn-quiet" to="/mistakes">
              My mistakes
            </Link>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <button className="btn-quiet mb-4 !px-2 text-sm" onClick={() => nav(-1)}>
        ← Back
      </button>

      <PageHeader
        title={p.point.title}
        native={p.point.native_title}
        subtitle={
          p.failures > 0
            ? `Wrong ${p.failures} time${p.failures === 1 ? "" : "s"} so far. About ${p.minutes} minutes to fix it.`
            : `About ${p.minutes} minutes. You have not got this wrong yet — this is here because you asked for it.`
        }
      />

      {/* The trail of steps, so the shape of the fix is visible up front. */}
      <ol className="mb-6 flex flex-wrap gap-2">
        {steps.map((s, i) => (
          <li key={s.id}>
            <button
              onClick={() => void startStep(i)}
              aria-current={i === step}
              className={`rounded-xl border px-3 py-1.5 text-sm transition-colors ${
                i === step
                  ? "border-brand bg-brand-soft font-semibold text-brand"
                  : i < step
                    ? "border-line bg-raised text-faint"
                    : "border-line bg-raised text-muted hover:bg-brand-soft/50"
              }`}
            >
              {i < step ? "✓ " : ""}
              {s.title}
            </button>
          </li>
        ))}
      </ol>

      {current && (
        <p className="card mb-4 border-l-4 !border-l-brand p-4 text-sm leading-relaxed">
          {current.why}
        </p>
      )}

      {/* ---- the teaching step ---- */}
      {current?.teach && (
        <>
          <article className="card mb-4 p-6">
            <TwoLevel
              simple={current.teach.simple}
              technical={current.teach.technical}
            />
            {/* A confusion pair already has an authored walkthrough. Showing it
                here rather than as a second offer elsewhere means the learner
                meets one account of the problem, not two. */}
            {p.point.kind === "confusion" && (
              <MiniCourse confusionId={p.point.source_id} lang={lang} />
            )}
            {current.teach.examples.length > 0 && (
              <div className="mt-5 border-t border-line pt-4">
                <p className="label mb-2">Worked examples</p>
                <div className="flex flex-wrap gap-2">
                  {current.teach.examples.map((ex) => (
                    <span
                      key={ex}
                      className="flex items-center gap-2 rounded-xl bg-paper px-3 py-2"
                    >
                      <Target lang={lang} size="md">{ex}</Target>
                      <AudioButton text={ex} lang={lang} />
                    </span>
                  ))}
                </div>
              </div>
            )}
          </article>

          {p.your_mistakes.length > 0 && (
            <div className="card mb-4 p-5">
              <p className="label mb-2">What you actually wrote</p>
              <ul className="space-y-1 text-sm">
                {p.your_mistakes.map((m, i) => (
                  <li key={i}>
                    <Target lang={lang} className="text-bad line-through">
                      {m.given || "—"}
                    </Target>
                    <span className="mx-2 text-faint" aria-hidden>→</span>
                    <Target lang={lang} className="text-good">{m.expected}</Target>
                    {m.times_seen > 1 && (
                      <span className="ml-2 chip">×{m.times_seen}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {/* ---- a drill step ---- */}
      {current?.spec && !drill && !loading && (
        <button className="btn-primary" onClick={() => void startStep(step)}>
          Start this step
        </button>
      )}
      {loading && <Skeleton rows={2} />}

      {drill && drill.length > 0 && index < drill.length && (
        <ExerciseCard
          key={index}
          exercise={drill[index]}
          index={index}
          total={drill.length}
          onAnswered={(v: Verdict, given, meta) => {
            const ex = drill[index];
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
      )}

      {/* A drill that produced nothing says why, rather than showing a blank. */}
      {drill && drill.length === 0 && (
        <p className="card p-5 text-sm text-muted">
          This step could not be built from the content that exists for this
          language yet. Skip on to the next one.
        </p>
      )}

      {/* ---- moving on ---- */}
      {(current?.teach || (drill && index >= drill.length) ||
        (drill && drill.length === 0)) && (
        <div className="mt-5 flex flex-wrap gap-2">
          {step + 1 < steps.length ? (
            <button className="btn-primary" onClick={() => void startStep(step + 1)}>
              Next: {steps[step + 1].title} →
            </button>
          ) : (
            <button className="btn-primary" onClick={() => void done()}>
              Mark this as fixed
            </button>
          )}
          {step > 0 && (
            <button className="btn-quiet" onClick={() => void startStep(step - 1)}>
              ← Back a step
            </button>
          )}
        </div>
      )}

      {/* What this language cannot do yet, said plainly rather than left out. */}
      {p.skipped.length > 0 && (
        <div className="mt-8 border-t border-line pt-4">
          {p.skipped.map((s) => (
            <p key={s.id} className="text-xs leading-relaxed text-faint">
              No <strong>{s.id}</strong> step: {s.why}
            </p>
          ))}
        </div>
      )}
    </>
  );
}
