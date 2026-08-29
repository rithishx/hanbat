/**
 * One exercise, rendered.
 *
 * The backend generates every drill for all three languages, so this component
 * dispatches on *shape* rather than on a list of kinds: if there are options
 * it is a choice, if it is a production drill it records, if it has ordered
 * chunks it is a sentence-builder, and otherwise the learner types. That keeps
 * a new Mandarin generator from needing a new React component — which is the
 * same separation the backend makes, seen from the other side.
 *
 * Three deliberate behaviours:
 *
 * The explanation is shown after every answer, right *and* wrong. "Correct ✓"
 * teaches nothing; "Correct — 本 is for bound things" teaches the category.
 *
 * A wrong answer is never a dead end. The right answer is shown with the
 * reason, and the item goes back into the queue.
 *
 * Speaking exercises are self-assessed and say so. There is no scoring engine
 * configured, and inventing a percentage would be a lie the learner would
 * believe.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useApp } from "../lib/app-context";
import { Recorder, recordingAvailable, scoreRecording } from "../lib/speech";
import type { Exercise } from "../lib/types";
import { AudioButton, Target } from "./ui";

export type Verdict = "correct" | "wrong" | "self";

interface Props {
  exercise: Exercise;
  index: number;
  total: number;
  onAnswered(verdict: Verdict, given: string): void;
  onNext(): void;
}

const SPEAKING = new Set(["pronounce", "read_aloud", "tone_pair", "repeat_then_produce"]);
const WRITING_PRACTICE = new Set(["trace"]);

export function ExerciseCard({ exercise, index, total, onAnswered, onNext }: Props) {
  const { lang, settings } = useApp();
  const [given, setGiven] = useState("");
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [revealed, setRevealed] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const answer = String(exercise.answer ?? "");
  const chunks = (exercise.options ?? []).length > 0 && exercise.kind === "word_order";
  const speaking = SPEAKING.has(exercise.kind);
  const writing = WRITING_PRACTICE.has(exercise.kind);
  const choice = !chunks && !speaking && !writing && (exercise.options?.length ?? 0) > 1;

  useEffect(() => {
    setGiven("");
    setVerdict(null);
    setRevealed(false);
    inputRef.current?.focus();
  }, [exercise]);

  const settle = (v: Verdict, value: string) => {
    if (verdict) return;
    setVerdict(v);
    setGiven(value);
    onAnswered(v, value);
  };

  const check = (value: string) => {
    const ok = normalise(value) === normalise(answer) ||
      acceptsVariant(exercise, value);
    settle(ok ? "correct" : "wrong", value);
  };

  return (
    <article className="card animate-fade-up p-5 sm:p-7">
      <div className="mb-4 flex items-center justify-between gap-3 text-xs text-faint">
        <span>
          {index + 1} of {total}
        </span>
        <span className="flex items-center gap-2">
          <span className="chip">{prettySkill(exercise.skill)}</span>
          {!exercise.hints && <span className="chip !text-warn">no hints</span>}
        </span>
      </div>

      <Prompt exercise={exercise} lang={lang} />

      {/* -------- answering -------- */}
      {!verdict && (
        <div className="mt-6">
          {choice && (
            <div className="grid gap-2 sm:grid-cols-2">
              {exercise.options.map((o) => (
                <button
                  key={o}
                  className="btn-ghost !justify-start !py-3.5 text-left"
                  onClick={() => check(o)}
                >
                  <Target lang={lang}>{o}</Target>
                </button>
              ))}
            </div>
          )}

          {chunks && (
            <ChunkBuilder
              chunks={exercise.options}
              lang={lang}
              onSubmit={(value) => check(value)}
            />
          )}

          {speaking && (
            <SpeakingPanel
              target={answer || exercise.audio}
              lang={lang}
              onDone={(v) => settle(v, "")}
            />
          )}

          {writing && (
            <WritingPanel
              target={answer}
              lang={lang}
              onDone={() => settle("self", answer)}
            />
          )}

          {!choice && !chunks && !speaking && !writing && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (given.trim()) check(given);
              }}
              className="flex flex-wrap gap-2"
            >
              <input
                ref={inputRef}
                value={given}
                onChange={(e) => setGiven(e.target.value)}
                placeholder="Type your answer"
                className="field flex-1"
                lang={lang}
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                aria-label="Your answer"
              />
              <button className="btn-primary" type="submit" disabled={!given.trim()}>
                Check
              </button>
            </form>
          )}

          {exercise.hints && settings?.romanization !== "never" && (
            <Hint exercise={exercise} revealed={revealed} onReveal={() => setRevealed(true)} />
          )}
        </div>
      )}

      {/* -------- feedback -------- */}
      {verdict && (
        <Feedback
          verdict={verdict}
          answer={answer}
          given={given}
          explain={exercise.explain}
          data={exercise.data}
          lang={lang}
          onNext={onNext}
        />
      )}
    </article>
  );
}

// ==========================================================================

function Prompt({ exercise, lang }: { exercise: Exercise; lang: string }) {
  const isAudioFirst =
    exercise.skill === "listening" || exercise.kind.startsWith("listen");
  return (
    <div>
      <p className="text-base leading-relaxed text-muted sm:text-lg">
        {exercise.prompt}
      </p>

      {isAudioFirst && exercise.audio && (
        <div className="mt-4 flex items-center gap-3">
          <AudioButton
            text={exercise.audio}
            lang={lang}
            autoPlay
            label="Play again"
            className="!px-5 !py-4 !text-lg"
          />
          <span className="text-xs text-faint">Play as many times as you need.</span>
        </div>
      )}

      {!isAudioFirst && exercise.audio && exercise.audio !== exercise.prompt && (
        <div className="mt-3">
          <AudioButton text={exercise.audio} lang={lang} />
        </div>
      )}
    </div>
  );
}

function Hint({
  exercise,
  revealed,
  onReveal,
}: {
  exercise: Exercise;
  revealed: boolean;
  onReveal: () => void;
}) {
  const hint =
    (exercise.data?.note as string) ||
    (exercise.data?.pronounced as string) ||
    (exercise.data?.one_line as string) ||
    "";
  if (!hint) return null;
  return (
    <div className="mt-4 text-sm">
      {revealed ? (
        <p className="rounded-xl bg-brand-soft/60 p-3 text-muted">{hint}</p>
      ) : (
        <button className="text-xs font-semibold text-brand hover:underline" onClick={onReveal}>
          Show a hint
        </button>
      )}
    </div>
  );
}

function Feedback({
  verdict,
  answer,
  given,
  explain,
  data,
  lang,
  onNext,
}: {
  verdict: Verdict;
  answer: string;
  given: string;
  explain: string;
  data: Record<string, unknown>;
  lang: string;
  onNext: () => void;
}) {
  const written = data?.written as string | undefined;
  const spoken = data?.spoken as string | undefined;

  return (
    <div
      className={`mt-6 rounded-2xl border p-4 ${
        verdict === "correct"
          ? "border-good/30 bg-good/5"
          : verdict === "wrong"
            ? "border-bad/30 bg-bad/5 animate-shake"
            : "border-line bg-brand-soft/40"
      }`}
      role="status"
      aria-live="polite"
    >
      <p className="mb-2 font-semibold">
        {verdict === "correct" && <span className="text-good">Correct</span>}
        {verdict === "wrong" && <span className="text-bad">Not quite</span>}
        {verdict === "self" && <span>Marked as practised</span>}
      </p>

      {verdict === "wrong" && (
        <p className="mb-2 text-sm">
          You wrote <span className="font-mono text-bad">{given || "—"}</span>. The answer is{" "}
          <Target lang={lang} className="font-semibold">
            {answer}
          </Target>
          .
        </p>
      )}

      {verdict !== "wrong" && answer && (
        <p className="mb-2 flex flex-wrap items-center gap-2 text-sm">
          <Target lang={lang} size="md" className="font-semibold">
            {answer}
          </Target>
          <AudioButton text={answer} lang={lang} />
        </p>
      )}

      {written && spoken && written !== spoken && (
        <p className="mb-2 text-sm text-muted">
          Written <span className="font-mono">{written}</span> · said{" "}
          <span className="font-mono font-semibold">{spoken}</span>
        </p>
      )}

      {/* Shown whether right or wrong. "Correct ✓" teaches nothing. */}
      {explain && <p className="text-sm leading-relaxed text-muted">{explain}</p>}

      <button className="btn-primary mt-4 w-full sm:w-auto" onClick={onNext} autoFocus>
        Continue →
      </button>
    </div>
  );
}

function ChunkBuilder({
  chunks,
  lang,
  onSubmit,
}: {
  chunks: string[];
  lang: string;
  onSubmit: (value: string) => void;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  const remaining = useMemo(() => {
    const left = [...chunks];
    for (const p of picked) {
      const i = left.indexOf(p);
      if (i >= 0) left.splice(i, 1);
    }
    return left;
  }, [chunks, picked]);

  return (
    <div>
      <div className="mb-3 flex min-h-[3.5rem] flex-wrap items-center gap-2 rounded-xl border border-dashed border-line p-3">
        {picked.length === 0 && (
          <span className="text-sm text-faint">Tap the pieces in order</span>
        )}
        {picked.map((p, i) => (
          <button
            key={`${p}-${i}`}
            className="btn-ghost !py-1.5"
            onClick={() => setPicked(picked.filter((_, j) => j !== i))}
            aria-label={`Remove ${p}`}
          >
            <Target lang={lang}>{p}</Target>
          </button>
        ))}
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {remaining.map((c, i) => (
          <button
            key={`${c}-${i}`}
            className="btn-ghost !py-1.5"
            onClick={() => setPicked([...picked, c])}
          >
            <Target lang={lang}>{c}</Target>
          </button>
        ))}
      </div>
      <button
        className="btn-primary"
        disabled={remaining.length > 0}
        onClick={() => onSubmit(picked.join(""))}
      >
        Check
      </button>
    </div>
  );
}

function SpeakingPanel({
  target,
  lang,
  onDone,
}: {
  target: string;
  lang: string;
  onDone: (v: Verdict) => void;
}) {
  const [recorder] = useState(() => new Recorder());
  const [state, setState] = useState<"idle" | "recording" | "done">("idle");
  const [clip, setClip] = useState<string | null>(null);
  const [error, setError] = useState("");
  const scoring = scoreRecording();

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <AudioButton
          text={target}
          lang={lang}
          label="Hear it"
          className="!px-5 !py-3.5"
        />
        <Target lang={lang} size="lg" className="font-semibold">
          {target}
        </Target>
      </div>

      {recordingAvailable() ? (
        <div className="flex flex-wrap items-center gap-3">
          {state !== "recording" ? (
            <button
              className="btn-ghost"
              onClick={async () => {
                try {
                  await recorder.start();
                  setState("recording");
                  setError("");
                } catch (e) {
                  setError(
                    e instanceof Error ? e.message : "Could not use the microphone.",
                  );
                }
              }}
            >
              ● Record yourself
            </button>
          ) : (
            <button
              className="btn-primary"
              onClick={async () => {
                const rec = await recorder.stop();
                setClip(rec.url);
                setState("done");
              }}
            >
              ■ Stop
            </button>
          )}
          {clip && <audio src={clip} controls className="h-9" />}
        </div>
      ) : (
        <p className="text-sm text-muted">
          This browser cannot record audio, so say it aloud and compare by ear.
        </p>
      )}

      {error && <p className="mt-2 text-sm text-bad">{error}</p>}

      <p className="mt-4 rounded-xl bg-brand-soft/50 p-3 text-xs leading-relaxed text-muted">
        {scoring.reason}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn-primary" onClick={() => onDone("self")}>
          I said it — continue
        </button>
        <button className="btn-quiet" onClick={() => onDone("wrong")}>
          I need more practice
        </button>
      </div>
    </div>
  );
}

function WritingPanel({
  target,
  lang,
  onDone,
}: {
  target: string;
  lang: string;
  onDone: () => void;
}) {
  return (
    <div>
      <div className="mb-4 grid place-items-center rounded-2xl border border-line bg-paper py-10">
        <Target lang={lang} size="hero" className="text-faint/50">
          {target}
        </Target>
      </div>
      <p className="mb-4 text-sm text-muted">
        Copy it on paper, tracing the shape twice. Handwriting is what makes a
        character stick — this is the one step the app cannot do for you.
      </p>
      <button className="btn-primary" onClick={onDone}>
        Done
      </button>
    </div>
  );
}

// ==========================================================================

function normalise(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/[.,!?。、！？·]/g, "")
    .replace(/\s+/g, " ");
}

/**
 * Some production drills legitimately have more than one right answer, and the
 * generator says so. Accepting only the canonical string would mark a correct
 * sentence wrong, which is the fastest way to make a learner stop trusting the
 * app.
 */
function acceptsVariant(exercise: Exercise, value: string): boolean {
  const accepts = exercise.data?.accepts as string[] | undefined;
  if (accepts?.some((a) => normalise(a) === normalise(value))) return true;
  if (exercise.data?.accepts_variants) {
    const a = normalise(String(exercise.answer ?? ""));
    const g = normalise(value);
    // Space-insensitive comparison: Japanese and Mandarin are written without
    // spaces, and a learner who adds them has not made a mistake worth marking.
    return a.replace(/ /g, "") === g.replace(/ /g, "");
  }
  return false;
}

function prettySkill(skill: string): string {
  return skill.charAt(0).toUpperCase() + skill.slice(1);
}
