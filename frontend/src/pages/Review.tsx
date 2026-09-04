/**
 * Spaced repetition.
 *
 * Answer first, then grade yourself — the recall attempt is where the memory
 * gets strengthened, and a card that shows its answer immediately trains
 * recognition instead. The four buttons show the interval each would produce,
 * because "Good = 10 minutes, Easy = 4 days" makes the choice concrete in a
 * way that "Good / Easy" does not.
 *
 * There is no "keep going" past an empty queue. A finished queue is the
 * correct outcome, and offering more cards early is exactly the cramming the
 * scheduler is designed to prevent.
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync, useElapsed, useKey } from "../lib/hooks";
import {
  AudioButton, Bar, ErrorState, NotReady, PageHeader, Section, Skeleton, Target,
} from "../components/ui";
import type { Grade, ReviewItem } from "../lib/types";

/** What each adapted mode is called on screen. */
const MODE_LABEL: Record<string, string> = {
  recall: "Produce it",
  listen: "Listen first",
  speak: "Say it",
};

const GRADES: { id: Grade; label: string; key: string; tone: string }[] = [
  { id: "again", label: "Again", key: "1", tone: "text-bad" },
  { id: "hard", label: "Hard", key: "2", tone: "text-warn" },
  { id: "good", label: "Good", key: "3", tone: "text-brand" },
  { id: "easy", label: "Easy", key: "4", tone: "text-good" },
];

export default function Review() {
  const { lang } = useApp();
  const elapsed = useElapsed();
  const { data, loading, error, notReady, reload } = useAsync(
    () => api.reviewQueue(lang, 40),
    [lang],
  );
  const summary = useAsync(() => api.reviewSummary(lang), [lang]);

  const [index, setIndex] = useState(0);
  const [shown, setShown] = useState(false);
  const [graded, setGraded] = useState(0);
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    setIndex(0);
    setShown(false);
    setGraded(0);
    setFinished(false);
  }, [lang]);

  const items = data?.items ?? [];
  const item = items[index];

  const grade = async (g: Grade) => {
    if (!item) return;
    try {
      await api.gradeReview(lang, {
        item_type: item.card.item_type,
        item_id: item.card.item_id,
        grade: g,
      });
    } catch {
      /* an unrecorded grade must not lose the learner's place */
    }
    setGraded((n) => n + 1);
    if (index + 1 < items.length) {
      setIndex(index + 1);
      setShown(false);
    } else {
      void api.session(lang, { seconds: elapsed(), kind: "review" }).catch(() => {});
      setFinished(true);
    }
  };

  // Space reveals; 1-4 grade. Anki's keys, because anyone who has used a
  // flashcard app already has them in their fingers.
  useKey(" ", (e) => {
    if (!item || finished) return;
    e.preventDefault();
    if (!shown) setShown(true);
  });
  useKey("1", () => shown && !finished && void grade("again"));
  useKey("2", () => shown && !finished && void grade("hard"));
  useKey("3", () => shown && !finished && void grade("good"));
  useKey("4", () => shown && !finished && void grade("easy"));

  if (notReady) return <NotReady notReady={notReady} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <Skeleton rows={3} />;

  if (finished || items.length === 0) {
    return (
      <>
        <PageHeader title="Review" subtitle="Spaced repetition, scheduled per language" />
        <div className="card mb-6 p-8 text-center">
          <p className="mb-2 text-4xl" aria-hidden>
            {graded > 0 ? "✓" : "☕"}
          </p>
          <h2 className="mb-1 text-xl font-semibold">
            {graded > 0 ? `${graded} reviewed` : "Nothing due"}
          </h2>
          <p className="mx-auto max-w-md text-sm leading-relaxed text-muted">
            {data.summary.due_tomorrow > 0
              ? `${data.summary.due_tomorrow} card${data.summary.due_tomorrow === 1 ? " is" : "s are"} due tomorrow. Coming back then is what makes this work — reviewing early just moves the same card forward.`
              : "Nothing is scheduled yet. Finish a lesson and the words you meet will start appearing here."}
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <Link className="btn-primary" to="/learn">
              Do a lesson
            </Link>
            <Link className="btn-ghost" to="/practice">
              Free practice
            </Link>
          </div>
        </div>
        <Forecast summary={summary.data} />
      </>
    );
  }

  return (
    <>
      <div className="mb-5 flex items-center justify-between gap-4">
        <div className="flex-1">
          <Bar
            percent={(index / items.length) * 100}
            label={`${index} of ${items.length}`}
          />
        </div>
        <span className="chip">{item.card.state}</span>
      </div>

      {/* Why this card looks different from the last one. An unexplained
          change of format reads as a bug rather than as adaptation. */}
      {item.ask && item.ask.mode !== "recognise" && (
        <p className="mb-3 rounded-xl bg-brand-soft/60 p-3 text-sm leading-relaxed text-muted">
          <span className="label mr-2">{MODE_LABEL[item.ask.mode]}</span>
          {item.ask.why}
        </p>
      )}

      <Card item={item} lang={lang} shown={shown} onShow={() => setShown(true)} />

      {shown ? (
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {GRADES.map((g) => (
            <button
              key={g.id}
              onClick={() => void grade(g.id)}
              className="card p-3 text-center transition-colors hover:bg-brand-soft/50"
            >
              <span className={`block text-sm font-semibold ${g.tone}`}>{g.label}</span>
              <span className="block text-xs text-faint">{item.preview[g.id]}</span>
              <kbd className="mt-1 inline-block rounded border border-line px-1 text-[0.6rem] text-faint">
                {g.key}
              </kbd>
            </button>
          ))}
        </div>
      ) : (
        <button className="btn-primary mt-4 w-full" onClick={() => setShown(true)}>
          Show answer <kbd className="ml-1 opacity-70">space</kbd>
        </button>
      )}
    </>
  );
}

// ==========================================================================

function Card({
  item,
  lang,
  shown,
  onShow,
}: {
  item: ReviewItem;
  lang: string;
  shown: boolean;
  onShow: () => void;
}) {
  const c = item.content;
  const face = useMemo(() => faceOf(item), [item]);

  if (!c) {
    // A card whose content has gone — the word was removed from the
    // curriculum. Say so rather than rendering a blank card.
    return (
      <div className="card p-6">
        <p className="text-sm text-muted">
          This card points at <span className="font-mono">{item.card.item_id}</span>,
          which is no longer in the curriculum. Grade it “Easy” to retire it.
        </p>
      </div>
    );
  }

  return (
    <article className="card animate-fade-up p-6 text-center sm:p-10">
      <p className="label mb-4">{face.label}</p>

      <div className="mb-6">
        {face.hideFront && !shown ? (
          <div className="flex flex-col items-center gap-3">
            <AudioButton text={face.front} lang={lang} label="Play" autoPlay
                         className="!px-6 !py-4" />
            <span className="text-sm text-faint">
              Written form hidden — this one is for your ears.
            </span>
          </div>
        ) : (
          <Target lang={lang} size="hero" className="font-semibold">
            {face.front}
          </Target>
        )}
      </div>

      {shown ? (
        <div className="animate-fade-up border-t border-line pt-6">
          <p className="mb-3 text-2xl font-medium">{face.back}</p>

          {face.reading && (
            <p className="mb-2 text-sm text-muted">
              {face.reading}
              {face.pronounced && face.pronounced !== face.front && (
                <span className="ml-2 text-faint">said {face.pronounced}</span>
              )}
            </p>
          )}

          <div className="mb-4 flex justify-center">
            <AudioButton text={face.front} lang={lang} autoPlay />
          </div>

          {face.example && (
            <p className="mx-auto max-w-md text-sm text-muted">
              <Target lang={lang}>{face.example}</Target>
              {face.exampleEn && <span className="block text-faint">{face.exampleEn}</span>}
            </p>
          )}

          {face.note && (
            <p className="mx-auto mt-4 max-w-md rounded-xl bg-brand-soft/50 p-3 text-sm text-muted">
              {face.note}
            </p>
          )}
        </div>
      ) : (
        <button className="text-sm text-faint hover:text-brand" onClick={onShow}>
          Say it out loud first, then reveal.
        </button>
      )}
    </article>
  );
}

interface Face {
  label: string;
  front: string;
  back: string;
  /** Dictation: play it before you read it, or listening is not being tested. */
  hideFront?: boolean;
  reading?: string;
  pronounced?: string;
  example?: string;
  exampleEn?: string;
  note?: string;
}

function faceOf(item: ReviewItem): Face {
  const c = (item.content ?? {}) as Record<string, string>;
  switch (item.card.item_type) {
    case "script_unit":
      return {
        label: "Writing system",
        front: c.unit ?? "",
        back: c.transliteration || c.name || "",
        reading: c.name,
      };
    case "grammar":
      return {
        label: "Grammar",
        front: c.name_native || c.name || "",
        back: c.meaning ?? "",
        note: c.simple,
      };
    default: {
      const shared = {
        reading: c.reading || c.transliteration,
        pronounced: c.pronunciation,
        example: c.example_native,
        exampleEn: c.example_en,
        note: c.notes,
      };
      // The mode turns the card round. Meaning-first is production and is
      // genuinely harder than term-first, which is why it is only used on
      // cards the learner has already met several times.
      switch (item.ask?.mode) {
        case "recall":
          return { label: "Produce it", front: c.meaning ?? "",
                   back: c.term ?? "", ...shared };
        case "speak":
          return { label: "Say it out loud", front: c.meaning ?? "",
                   back: c.term ?? "", ...shared };
        case "listen":
          return { label: "Listen first", front: c.term ?? "",
                   back: c.meaning ?? "", hideFront: true, ...shared };
        default:
          return { label: "Vocabulary", front: c.term ?? "",
                   back: c.meaning ?? "", ...shared };
      }
    }
  }
}

function Forecast({
  summary,
}: {
  summary: { by_state: Record<string, number>; forecast: { date: string; count: number }[] } | null;
}) {
  if (!summary) return null;
  const states = Object.entries(summary.by_state).filter(([, n]) => n > 0);
  const days = summary.forecast.slice(0, 14);
  const peak = Math.max(1, ...days.map((d) => d.count));

  return (
    <>
      {states.length > 0 && (
        <Section title="Your cards">
          <div className="card flex flex-wrap gap-6 p-5">
            {states.map(([state, n]) => (
              <div key={state}>
                <p className="text-2xl font-bold">{n}</p>
                <p className="text-xs capitalize text-faint">{state}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="The next two weeks" hint="What the scheduler has planned">
        <div className="card flex items-end gap-1 p-5" style={{ height: 140 }}>
          {days.map((d) => (
            <div key={d.date} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-brand/70"
                style={{ height: `${(d.count / peak) * 90}px` }}
                title={`${d.count} on ${d.date}`}
              />
              <span className="text-[0.6rem] text-faint">{d.date.slice(8)}</span>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}
