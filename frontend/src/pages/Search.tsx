/**
 * One box, everything in the active language.
 *
 * The backend does two extra things worth surfacing: it runs the query through
 * the pronunciation engine, so searching a word also shows how it is said; and
 * if the query looks like a dictionary form it returns the conjugation table.
 * Both are answers to questions the learner was probably about to ask next.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import {
  AudioButton, Empty, ErrorState, NotReady, PageHeader, Section, Skeleton, Target,
} from "../components/ui";

const KIND_LABEL: Record<string, string> = {
  vocab: "Vocabulary",
  grammar: "Grammar",
  lesson: "Lessons",
  script_unit: "Writing system",
  slang: "Slang",
};

const KIND_LINK: Record<string, (ref: string) => string> = {
  grammar: (ref) => `/grammar/${ref}`,
  lesson: (ref) => `/learn/${ref}`,
};

export default function Search() {
  const { lang, language } = useApp();
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");

  const results = useAsync(
    () => (query ? api.search(query, lang) : Promise.resolve(null)),
    [query, lang],
  );

  if (results.notReady) return <NotReady notReady={results.notReady} />;

  return (
    <>
      <PageHeader
        title="Search"
        native={language?.native_name}
        subtitle="Words, grammar, lessons and letters — everything in one place."
      />

      <form
        className="mb-6 flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(text.trim());
        }}
      >
        <input
          className="field flex-1"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Search in English or in the language"
          lang={lang}
          autoFocus
          aria-label="Search"
        />
        <button className="btn-primary" disabled={!text.trim()}>
          Search
        </button>
      </form>

      {results.error && <ErrorState error={results.error} onRetry={results.reload} />}
      {results.loading && <Skeleton rows={4} />}

      {results.data && (
        <>
          {results.data.pronunciation && (
            <Section title="How it sounds">
              <div className="card flex flex-wrap items-center gap-3 p-4">
                <Target lang={lang} size="md">
                  {results.data.pronunciation.written ?? query}
                </Target>
                <span aria-hidden className="text-faint">→</span>
                <Target lang={lang} size="md" className="font-semibold text-brand">
                  {results.data.pronunciation.spoken}
                </Target>
                <AudioButton text={results.data.pronunciation.spoken} lang={lang} />
                <Link className="ml-auto text-xs font-semibold text-brand hover:underline" to="/pronunciation">
                  Explain →
                </Link>
              </div>
            </Section>
          )}

          {results.data.conjugation ? (
            <Section title="It conjugates">
              <Link className="card block p-4 hover:bg-brand-soft/40" to="/conjugation">
                <p className="text-sm">
                  <Target lang={lang} className="font-semibold">
                    {String((results.data.conjugation as { dictionary_form?: string }).dictionary_form ?? query)}
                  </Target>{" "}
                  is a dictionary form — see the full table.
                </p>
              </Link>
            </Section>
          ) : null}

          {results.data.total === 0 ? (
            <Empty
              title="Nothing found"
              body={`Nothing in the ${language?.name ?? ""} curriculum matches “${query}”. The curriculum is finite — a missing word is more likely a gap than a mistake in your spelling.`}
            />
          ) : (
            Object.entries(results.data.results).map(([kind, hits]) => (
              <Section key={kind} title={KIND_LABEL[kind] ?? kind} right={<span className="text-xs text-faint">{hits.length}</span>}>
                <ul className="card divide-y divide-line">
                  {hits.map((h) => {
                    const body = (
                      <>
                        <Target lang={lang} size="md" className="w-40 shrink-0 font-semibold">
                          {h.term}
                        </Target>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate">{h.english}</span>
                          {h.extra && (
                            <span className="block truncate text-xs text-faint">{h.extra}</span>
                          )}
                        </span>
                      </>
                    );
                    const to = KIND_LINK[kind]?.(h.ref);
                    return (
                      <li key={h.ref}>
                        {to ? (
                          <Link
                            to={to}
                            className="flex items-center gap-3 p-3.5 hover:bg-brand-soft/40"
                          >
                            {body}
                          </Link>
                        ) : (
                          <div className="flex items-center gap-3 p-3.5">{body}</div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </Section>
            ))
          )}
        </>
      )}
    </>
  );
}
