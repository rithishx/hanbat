/**
 * The vocabulary list.
 *
 * Filterable by topic and level, searchable, and every row expands into the
 * word's full entry — pronunciation with its reasoning, the forms worth
 * drilling, an example sentence. The forms come from the language's own
 * grammar engine, so a Korean noun shows its particles, a Japanese verb shows
 * its て-form, and a Mandarin noun shows its measure word. None of that logic
 * lives here.
 */

import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync, useLocalState } from "../lib/hooks";
import {
  AudioButton, Empty, ErrorState, NotReady, PageHeader, Skeleton, Target,
} from "../components/ui";
import type { VocabWord } from "../lib/types";

export default function Vocabulary() {
  const { lang, language } = useApp();
  const [topic, setTopic] = useLocalState<string>(`vocab.topic.${lang}`, "");
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

  const topics = useAsync(() => api.vocabTopics(lang), [lang]);
  const words = useAsync(
    () => api.vocab(lang, { topic: topic || undefined, limit: 600 }),
    [lang, topic],
  );

  const filtered = useMemo(() => {
    const rows = words.data?.words ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (w) =>
        w.term.includes(query) ||
        w.meaning.toLowerCase().includes(q) ||
        (w.transliteration ?? "").toLowerCase().includes(q) ||
        (w.reading ?? "").includes(query),
    );
  }, [words.data, query]);

  if (words.notReady) return <NotReady notReady={words.notReady} />;
  if (words.error) return <ErrorState error={words.error} onRetry={words.reload} />;

  return (
    <>
      <PageHeader
        title="Vocabulary"
        native={language?.native_name}
        subtitle={
          words.data ? `${words.data.count} words in the curriculum` : undefined
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          className="field flex-1 !py-2 sm:max-w-xs"
          placeholder="Search words or meanings"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search vocabulary"
        />
        <select
          className="field !w-auto !py-2"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          aria-label="Filter by topic"
        >
          <option value="">All topics</option>
          {(topics.data?.topics ?? []).map((t) => (
            <option key={t.topic} value={t.topic}>
              {t.topic} ({t.count})
            </option>
          ))}
        </select>
      </div>

      {words.loading ? (
        <Skeleton rows={6} />
      ) : filtered.length === 0 ? (
        <Empty
          title="Nothing matches"
          body="Try a different search, or clear the topic filter."
        />
      ) : (
        <ul className="card divide-y divide-line">
          {filtered.map((w) => (
            <li key={w.id}>
              <Row
                word={w}
                lang={lang}
                open={openId === w.id}
                onToggle={() => setOpenId(openId === w.id ? null : w.id)}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Row({
  word,
  lang,
  open,
  onToggle,
}: {
  word: VocabWord;
  lang: string;
  open: boolean;
  onToggle: () => void;
}) {
  const detail = useAsync(
    () => (open ? api.vocabWord(word.id, lang) : Promise.resolve(null)),
    [open, word.id, lang],
  );
  const full = detail.data ?? word;

  return (
    <div>
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 p-3.5 text-left transition-colors hover:bg-brand-soft/40"
      >
        <Target lang={lang} size="md" className="w-32 shrink-0 font-semibold">
          {word.term}
        </Target>
        <span className="min-w-0 flex-1">
          <span className="block truncate">{word.meaning}</span>
          {(word.reading || word.transliteration) && (
            <span className="block truncate text-xs text-faint">
              {word.reading || word.transliteration}
            </span>
          )}
        </span>
        {word.level && <span className="chip shrink-0">{word.level}</span>}
        <span aria-hidden className="text-faint">
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open && (
        <div className="animate-fade-up border-t border-line bg-paper/60 p-4">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <AudioButton text={word.term} lang={lang} />
            {full.pronunciation && full.pronunciation !== word.term && (
              <span className="text-sm text-muted">
                said <Target lang={lang} className="font-semibold">{full.pronunciation}</Target>
              </span>
            )}
            {full.pos && <span className="chip">{full.pos}</span>}
            {full.counter && (
              <span className="chip">
                measure word <Target lang={lang}>{full.counter}</Target>
              </span>
            )}
          </div>

          {full.pronunciation_explained?.steps?.length ? (
            <details className="mb-3">
              <summary className="cursor-pointer text-xs font-semibold text-brand">
                Why it sounds different from how it is spelled
              </summary>
              <ul className="mt-2 space-y-1.5 text-sm text-muted">
                {full.pronunciation_explained.steps.map((s, i) => (
                  <li key={i}>
                    <strong>{s.rule_name}: </strong>
                    {s.child_explanation}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          {full.example_native && (
            <p className="mb-3 text-sm">
              <Target lang={lang}>{full.example_native}</Target>
              <AudioButton text={full.example_native} lang={lang} className="ml-2 !py-1 !px-2" />
              {full.example_en && (
                <span className="block text-muted">{full.example_en}</span>
              )}
            </p>
          )}

          {full.notes && (
            <p className="mb-3 rounded-xl bg-brand-soft/50 p-3 text-sm text-muted">
              {full.notes}
            </p>
          )}

          {(full.drill_forms?.length ?? 0) > 0 && (
            <div>
              <p className="label mb-1.5">Worth practising</p>
              <div className="flex flex-wrap gap-2">
                {full.drill_forms!.map((f) => (
                  <span key={f.form_id} className="card px-3 py-1.5 text-sm">
                    <Target lang={lang} className="font-semibold">
                      {f.form}
                    </Target>
                    <span className="ml-2 text-xs text-faint">{f.label}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          <button
            className="btn-ghost mt-4 !py-1.5 text-xs"
            onClick={() =>
              void api.enqueue(lang, [{ item_type: "vocab", item_id: word.id }])
            }
          >
            Add to review
          </button>
        </div>
      )}
    </div>
  );
}
