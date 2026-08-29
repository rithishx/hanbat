/**
 * Conjugation — for the languages that have it.
 *
 * This route is not rendered at all for Mandarin: the nav filters on the
 * `conjugation` capability, and the API returns 409 with a reason if you reach
 * it anyway. That is the visible payoff of the language modules declaring what
 * they can do rather than every language pretending to do everything.
 *
 * The table's grouping is the language's own — Korean groups by speech level,
 * Japanese by politeness register — and only the two neutral keys `form` and
 * `label_native` are read here.
 */

import { useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import {
  AudioButton, Empty, ErrorState, PageHeader, Skeleton, Target, TwoLevel,
} from "../components/ui";

const EXAMPLES: Record<string, string[]> = {
  ko: ["먹다", "춥다", "듣다", "걷다", "하다", "이다", "예쁘다", "돕다"],
  ja: ["食べる", "飲む", "行く", "する", "来る", "話す", "高い", "静か"],
};

interface FormRow {
  id: string;
  form: string;
  label_en: string;
  label_native: string;
  category: string;
  note?: string;
  speech_level?: string;
  politeness?: string;
}

interface Table {
  dictionary_form: string;
  stem: string;
  part_of_speech: string;
  confident: boolean;
  note: string;
  categories: Record<string, FormRow[]>;
  irregular?: string;
  irregular_explained?: { name: string; simple: string; technical: string; example: string };
  verb_class?: string;
  class_explained?: { name: string; simple: string; technical: string; example: string };
  bases?: Record<string, unknown>;
  stems?: Record<string, string>;
}

export default function Conjugation() {
  const { lang, language } = useApp();
  const [word, setWord] = useState("");
  const [submitted, setSubmitted] = useState("");

  const table = useAsync<Table | null>(
    () =>
      submitted
        ? (api.conjugate(submitted, lang) as unknown as Promise<Table>)
        : Promise.resolve(null),
    [submitted, lang],
  );

  if (!language?.capabilities?.includes("conjugation")) {
    return (
      <>
        <PageHeader title="Conjugation" native={language?.native_name} />
        <Empty
          title={`${language?.name ?? "This language"} has no conjugation`}
          body="Verbs do not change shape here. Time comes from time words and aspect particles instead, which is a different system rather than a simpler one — the grammar reference covers it."
          action={{ to: "/grammar", label: "Grammar reference" }}
        />
      </>
    );
  }

  const examples = EXAMPLES[lang] ?? [];
  const t = table.data;
  const explained = t?.irregular_explained ?? t?.class_explained;

  return (
    <>
      <PageHeader
        title="Conjugation"
        native={language?.native_name}
        subtitle="Type a dictionary form and see every form it takes, with the class that decides them."
      />

      <form
        className="mb-4 flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(word.trim());
        }}
      >
        <input
          className="field flex-1"
          value={word}
          onChange={(e) => setWord(e.target.value)}
          placeholder={examples[0] ? `e.g. ${examples[0]}` : "Dictionary form"}
          lang={lang}
          aria-label="Dictionary form"
        />
        <button className="btn-primary" type="submit" disabled={!word.trim()}>
          Conjugate
        </button>
      </form>

      <div className="mb-6 flex flex-wrap gap-2">
        {examples.map((e) => (
          <button
            key={e}
            className="chip hover:!border-brand hover:!text-brand"
            onClick={() => {
              setWord(e);
              setSubmitted(e);
            }}
          >
            <Target lang={lang}>{e}</Target>
          </button>
        ))}
      </div>

      {table.error && <ErrorState error={table.error} onRetry={table.reload} />}
      {table.loading && <Skeleton rows={4} />}

      {t && (
        <div className="animate-fade-up">
          <div className="card mb-5 p-5">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <Target lang={lang} size="lg" className="font-semibold">
                {t.dictionary_form}
              </Target>
              <span className="chip">{t.part_of_speech}</span>
              {(t.irregular || t.verb_class) && (
                <span className="chip !border-brand/40 !text-brand">
                  {t.irregular && t.irregular !== "regular"
                    ? `${t.irregular} irregular`
                    : t.verb_class}
                </span>
              )}
              {!t.confident && (
                <span className="chip !border-warn/40 !text-warn" title={t.note}>
                  not certain
                </span>
              )}
            </div>

            {!t.confident && t.note && (
              <p className="mb-3 rounded-xl bg-warn/5 p-3 text-sm leading-relaxed text-muted">
                <strong className="text-warn">Careful: </strong>
                {t.note}
              </p>
            )}

            {explained && (
              <TwoLevel simple={explained.simple} technical={explained.technical} />
            )}
            {explained?.example && (
              <p className="mt-2 text-sm text-muted">
                <Target lang={lang}>{explained.example}</Target>
              </p>
            )}
          </div>

          {Object.entries(t.categories).map(([category, forms]) => (
            <section key={category} className="mb-5">
              <h2 className="label mb-2 capitalize">{category}</h2>
              <ul className="card divide-y divide-line">
                {forms.map((f) => (
                  <li key={f.id} className="flex items-center gap-3 p-3">
                    <Target lang={lang} size="md" className="w-40 shrink-0 font-semibold">
                      {f.form}
                    </Target>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm">{f.label_en}</span>
                      <Target lang={lang} className="block text-xs text-faint">
                        {f.label_native}
                      </Target>
                      {f.note && (
                        <span className="block text-xs text-muted">{f.note}</span>
                      )}
                    </span>
                    <AudioButton text={f.form} lang={lang} />
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
