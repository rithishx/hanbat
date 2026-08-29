/**
 * Free practice.
 *
 * The list of drills comes from the backend's generator registry, so this
 * screen shows exactly what the *current* language can do and nothing else.
 * A Korean learner sees 받침 prediction; a Mandarin learner sees tone sandhi;
 * neither sees a greyed-out placeholder for the other's.
 */

import { useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync, useElapsed } from "../lib/hooks";
import { ExerciseCard, type Verdict } from "../components/Exercise";
import {
  Empty, ErrorState, Loading, NotReady, PageHeader, Section, Skeleton,
} from "../components/ui";
import type { Exercise } from "../lib/types";

/** Readable names for generator kinds. Anything unlisted falls back to a
 *  de-slugged version of its own id, so a new generator needs no edit here. */
const NAMES: Record<string, string> = {
  jamo_recognition: "Read the letters",
  jamo_audio: "Hear the letters",
  syllable_build: "Build syllable blocks",
  syllable_decompose: "Take blocks apart",
  syllable_read: "Read blocks",
  batchim_predict: "Predict the 받침 sound",
  batchim_choice: "Choose the 받침",
  count_syllables: "Count the blocks",
  conjugate: "Conjugate",
  particle_choice: "Choose the particle",
  choose_negation: "Negation",
  number_choice: "Numbers",
  listen_discriminate: "Tell the sounds apart",
  kana_recognition: "Read kana",
  kana_audio: "Hear kana",
  kana_pair: "Hiragana ↔ katakana",
  kana_typing: "Type kana",
  dakuten: "Dakuten marks",
  mora_count: "Count the beats",
  mora_discriminate: "Long or short?",
  verb_class: "Godan or ichidan?",
  counter_choice: "Counters",
  pinyin_read: "Read pinyin",
  pinyin_build: "Build a syllable",
  pinyin_type: "Type the pinyin",
  initial_discriminate: "Tell the initials apart",
  tone_identify: "Name the tone",
  tone_minimal_pair: "Same sound, different tone",
  tone_pair: "Tone pairs",
  tone_sandhi_predict: "How is it actually said?",
  measure_word_choice: "Measure words",
  aspect_choice: "了, 过, 着 or 在",
  word_order: "Word order",
  structure_produce: "Sentence patterns",
  hanzi_recognise: "Read characters",
  listen_type: "Type what you hear",
  listen_choose: "Which did you hear?",
  vocab_recall: "Say the word",
  vocab_recognise: "What does it mean?",
  pronounce: "Say it aloud",
  read_aloud: "Read aloud",
  trace: "Handwriting",
  word_read: "Read words",
  confusion_drill: "Fix a confusion",
  multiple_choice: "Mixed questions",
  concept_to_target: "Produce a sentence",
  concept_to_korean: "Produce a sentence",
};

function pretty(kind: string): string {
  return (
    NAMES[kind] ??
    kind.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
  );
}

export default function Practice() {
  const { lang, language } = useApp();
  const elapsed = useElapsed();
  const kinds = useAsync(() => api.practiceKinds(lang), [lang]);

  const [drill, setDrill] = useState<{ kind: string; exercises: Exercise[] } | null>(null);
  const [index, setIndex] = useState(0);
  const [right, setRight] = useState(0);
  const [asked, setAsked] = useState(0);
  const [busy, setBusy] = useState("");

  if (kinds.notReady) return <NotReady notReady={kinds.notReady} />;
  if (kinds.error) return <ErrorState error={kinds.error} onRetry={kinds.reload} />;
  if (kinds.loading || !kinds.data) return <Skeleton rows={4} />;

  const start = async (kind: string) => {
    setBusy(kind);
    try {
      const res = await api.practice(lang, {
        spec: { type: kind, count: 10 },
        seed: Math.floor(Math.random() * 100000),
      });
      const usable = res.exercises.filter(
        (e) => e.kind !== "unsupported" && e.kind !== "error",
      );
      if (usable.length) {
        setDrill({ kind, exercises: usable });
        setIndex(0);
        setRight(0);
        setAsked(0);
      } else {
        // The generator ran and produced nothing usable — almost always
        // because the content it needs is not authored yet. Say which.
        setDrill({ kind, exercises: res.exercises });
      }
    } finally {
      setBusy("");
    }
  };

  if (drill) {
    const ex = drill.exercises[index];
    if (!ex) {
      return (
        <>
          <PageHeader title={pretty(drill.kind)} />
          <Empty
            title={`${right} of ${asked} right`}
            body="Practice does not schedule anything — it is extra repetition on top of your reviews, which are what actually build memory."
            action={{ to: "/review", label: "Go to review" }}
          />
          <div className="mt-3 flex gap-2">
            <button className="btn-ghost" onClick={() => void start(drill.kind)}>
              Again
            </button>
            <button className="btn-quiet" onClick={() => setDrill(null)}>
              Choose another drill
            </button>
          </div>
        </>
      );
    }
    if (ex.kind === "unsupported" || ex.kind === "error") {
      return (
        <>
          <PageHeader title={pretty(drill.kind)} />
          <div className="card p-6">
            <p className="mb-2 font-semibold text-warn">Not available yet</p>
            <p className="mb-4 text-sm leading-relaxed text-muted">{ex.explain}</p>
            <button className="btn-ghost" onClick={() => setDrill(null)}>
              Back to drills
            </button>
          </div>
        </>
      );
    }

    return (
      <>
        <div className="mb-4 flex items-center justify-between">
          <h1 className="font-semibold">{pretty(drill.kind)}</h1>
          <button className="btn-quiet text-sm" onClick={() => setDrill(null)}>
            End
          </button>
        </div>
        <ExerciseCard
          key={index}
          exercise={ex}
          index={index}
          total={drill.exercises.length}
          onAnswered={(v: Verdict, given) => {
            if (v !== "self") {
              setAsked((a) => a + 1);
              if (v === "correct") setRight((r) => r + 1);
            }
            void api
              .answer(lang, {
                kind: ex.kind,
                skill: ex.skill,
                correct: v === "correct",
                item_type: ex.item_type,
                item_id: ex.item_id,
                expected: String(ex.answer ?? ""),
                given,
              })
              .catch(() => {});
          }}
          onNext={() => {
            if (index + 1 >= drill.exercises.length) {
              void api.session(lang, { seconds: elapsed(), kind: "practice" }).catch(() => {});
            }
            setIndex(index + 1);
          }}
        />
      </>
    );
  }

  const kindList = kinds.data.kinds;
  return (
    <>
      <PageHeader
        title="Practice"
        native={language?.native_name}
        subtitle="Extra repetition, outside the lesson order. Nothing here is scheduled — it is for when you want more of one thing."
      />
      <Section
        title="Drills"
        hint={`${kindList.length} available for ${language?.name ?? "this language"}`}
      >
        <div className="grid gap-2 sm:grid-cols-2">
          {kindList.map((k) => (
            <button
              key={k}
              className="card p-4 text-left transition-colors hover:bg-brand-soft/40 disabled:opacity-50"
              disabled={busy !== ""}
              onClick={() => void start(k)}
            >
              <span className="font-medium">{pretty(k)}</span>
              <span className="mt-0.5 block font-mono text-xs text-faint">{k}</span>
            </button>
          ))}
        </div>
      </Section>
      {busy && <Loading what="the drill" />}
    </>
  );
}
