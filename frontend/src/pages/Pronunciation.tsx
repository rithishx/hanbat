/**
 * The pronunciation laboratory.
 *
 * Three panels over one idea: spelling and sound come apart, and there is
 * always a reason. Type anything and see what it really sounds like with the
 * rules that changed it; browse every rule the language has, each explained
 * plainly first and technically second; and drill any rule from its own
 * examples.
 *
 * The rules and examples come from the language's engine, computed at request
 * time. Korean returns sound changes, Japanese returns timing rules, Mandarin
 * returns tone changes — genuinely different material rendered through one
 * shape, which is the architecture visible from the outside.
 */

import { useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync, useLocalState } from "../lib/hooks";
import { Recorder, recordingAvailable, scoreRecording } from "../lib/speech";
import {
  AudioButton, ErrorState, NotReady, PageHeader, Section, Skeleton, Target,
  TwoLevel,
} from "../components/ui";
import type { PitchAccent, PitchContour, PronunciationRule } from "../lib/types";

const SAMPLES: Record<string, string[]> = {
  ko: ["한국어", "먹고 싶어요", "좋아요", "학교", "감사합니다", "읽는다"],
  ja: ["きょう", "がっこう", "きって", "コーヒー", "せんせい", "べんきょう"],
  zh: ["nǐ hǎo", "wǒ hěn hǎo", "bù shì", "yī gè", "Zhōngguó", "xièxie"],
};

type Tab = "explain" | "rules" | "pitch" | "difficulties";

export default function Pronunciation() {
  const { lang, language } = useApp();
  const [tab, setTab] = useLocalState<Tab>(`pron.tab.${lang}`, "explain");
  const lab = useAsync(() => api.pronunciationLab(lang), [lang]);

  if (lab.notReady) return <NotReady notReady={lab.notReady} />;
  if (lab.error) return <ErrorState error={lab.error} onRetry={lab.reload} />;

  const pitch = lab.data?.pitch_accent;

  const tabs: [Tab, string][] = [
    ["explain", "Say anything"],
    ["rules", `Rules${lab.data ? ` (${lab.data.rules.length})` : ""}`],
    // Only for a language that has pitch accent. A tab that opens onto "this
    // language does not do that" is worse than no tab.
    ...(pitch ? ([["pitch", "Pitch accent"]] as [Tab, string][]) : []),
    ["difficulties", "What is hard"],
  ];

  // Switching to a language without the tab must not leave it selected.
  const active: Tab = tab === "pitch" && !pitch ? "explain" : tab;

  return (
    <>
      <PageHeader
        title="Pronunciation lab"
        native={language?.native_name}
        subtitle="What it sounds like, and the rule that made it sound that way."
      />

      <div className="mb-6 flex gap-2 overflow-x-auto pb-1" role="tablist">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={active === id}
            onClick={() => setTab(id)}
            className={`shrink-0 rounded-xl border px-4 py-2 text-sm transition-colors ${
              active === id
                ? "border-brand bg-brand-soft font-semibold text-brand"
                : "border-line bg-raised text-muted hover:bg-brand-soft/50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {lab.loading && <Skeleton rows={4} />}

      {active === "explain" && <Explain lang={lang} />}
      {active === "rules" && lab.data && (
        <RuleIndex rules={lab.data.rules} lang={lang} note={lab.data.note}
                   ruleDerived={lab.data.rule_derived} />
      )}
      {active === "pitch" && pitch && <Pitch pitch={pitch} lang={lang} />}
      {active === "difficulties" && lab.data && (
        <Difficulties lab={lab.data} lang={lang} />
      )}
    </>
  );
}

// ==========================================================================

function Explain({ lang }: { lang: string }) {
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [casual, setCasual] = useState(false);
  const result = useAsync(
    () => (submitted ? api.pronounce(submitted, lang, casual) : Promise.resolve(null)),
    [submitted, lang, casual],
  );
  const samples = SAMPLES[lang] ?? [];

  return (
    <>
      <form
        className="mb-4 flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(text.trim());
        }}
      >
        <input
          className="field flex-1"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={samples[0] ? `e.g. ${samples[0]}` : "Type something"}
          lang={lang}
          aria-label="Text to analyse"
        />
        <button className="btn-primary" type="submit" disabled={!text.trim()}>
          Explain
        </button>
      </form>

      <div className="mb-6 flex flex-wrap items-center gap-2">
        {samples.map((s) => (
          <button
            key={s}
            className="chip hover:!border-brand hover:!text-brand"
            onClick={() => {
              setText(s);
              setSubmitted(s);
            }}
          >
            <Target lang={lang}>{s}</Target>
          </button>
        ))}
        {lang === "ko" && (
          <label className="ml-auto flex items-center gap-2 text-xs text-muted">
            <input
              type="checkbox"
              checked={casual}
              onChange={(e) => setCasual(e.target.checked)}
            />
            Casual speech
          </label>
        )}
      </div>

      {result.error && <ErrorState error={result.error} onRetry={result.reload} />}
      {result.loading && <Skeleton rows={2} />}
      {result.data && <Trace lang={lang} result={result.data} fallback={submitted} />}

      <RecordPanel lang={lang} target={submitted || samples[0] || ""} />
    </>
  );
}

function Trace({
  lang,
  result,
  fallback,
}: {
  lang: string;
  result: { written?: string; spoken: string; summary?: string; steps: {
    rule_id: string; rule_name: string; child_explanation: string;
    linguistic_explanation: string; before?: string; after?: string }[] };
  fallback: string;
}) {
  return (
    <div className="card mb-8 animate-fade-up p-5">
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <div>
          <p className="label">Written</p>
          <Target lang={lang} size="lg">{result.written ?? fallback}</Target>
        </div>
        <span aria-hidden className="text-2xl text-faint">→</span>
        <div>
          <p className="label">Said</p>
          <Target lang={lang} size="lg" className="font-semibold text-brand">
            {result.spoken}
          </Target>
        </div>
        <AudioButton text={result.spoken} lang={lang} className="ml-auto" />
      </div>

      {result.summary && <p className="mb-3 text-sm text-muted">{result.summary}</p>}

      {result.steps?.length ? (
        <ol className="space-y-3">
          {result.steps.map((s, i) => (
            <li key={i} className="rounded-xl border border-line p-3">
              <p className="mb-1 text-sm font-semibold">
                {s.rule_name}
                {s.before && s.after && (
                  <span className="ml-2 font-normal text-faint">
                    <Target lang={lang}>{s.before}</Target> →{" "}
                    <Target lang={lang}>{s.after}</Target>
                  </span>
                )}
              </p>
              <TwoLevel simple={s.child_explanation} technical={s.linguistic_explanation} />
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-sm text-muted">
          Nothing changes here — it is said exactly as it is written.
        </p>
      )}
    </div>
  );
}

// ==========================================================================

function RuleIndex({
  rules,
  lang,
  note,
  ruleDerived,
}: {
  rules: PronunciationRule[];
  lang: string;
  note: string;
  ruleDerived: boolean;
}) {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <>
      <p className="card mb-4 p-4 text-sm leading-relaxed text-muted">
        {note}
        {!ruleDerived && (
          <span className="mt-2 block text-xs text-faint">
            Readings in this language come from the vocabulary entry rather than
            being computed from the spelling — so the app can tell you the rules,
            but cannot derive an unfamiliar word's reading for you.
          </span>
        )}
      </p>

      <div className="space-y-2">
        {rules.map((r) => (
          <article key={r.id} className="card overflow-hidden">
            <button
              className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-brand-soft/40"
              onClick={() => setOpen(open === r.id ? null : r.id)}
              aria-expanded={open === r.id}
            >
              <span className="min-w-0 flex-1">
                <span className="font-medium">{r.name}</span>
                <Target lang={lang} className="ml-2 text-muted">
                  {r.native_name}
                </Target>
              </span>
              <span aria-hidden className="text-faint">
                {open === r.id ? "▴" : "▾"}
              </span>
            </button>

            {open === r.id && (
              <div className="animate-fade-up border-t border-line p-5">
                <TwoLevel simple={r.simple} technical={r.technical} />

                <div className="mt-4 space-y-2">
                  {r.examples.map((ex) => (
                    <div
                      key={ex.written}
                      className="flex flex-wrap items-center gap-3 rounded-xl bg-paper p-3"
                    >
                      <Target lang={lang} size="md">{ex.written}</Target>
                      <span aria-hidden className="text-faint">→</span>
                      <Target lang={lang} size="md" className="font-semibold text-brand">
                        {ex.spoken}
                      </Target>
                      {typeof ex.beats === "number" && (
                        <span className="chip">{ex.beats} beats</span>
                      )}
                      {ex.shows_the_limit && (
                        <span className="chip !border-warn/40 !text-warn">
                          where it stops
                        </span>
                      )}
                      {ex.verified === false && !ex.shows_the_limit && (
                        <span className="chip !border-bad/40 !text-bad" title="This example no longer triggers its own rule — a bug, surfaced rather than hidden.">
                          unverified
                        </span>
                      )}
                      <AudioButton text={ex.spoken} lang={lang} />
                      <span className="w-full text-xs leading-relaxed text-muted">
                        {ex.note}
                      </span>
                    </div>
                  ))}
                </div>

                <RuleDrill rule={r.id} lang={lang} />
              </div>
            )}
          </article>
        ))}
      </div>
    </>
  );
}

function RuleDrill({ rule, lang }: { rule: string; lang: string }) {
  const [open, setOpen] = useState(false);
  const drill = useAsync(
    () => (open ? api.pronunciationDrill(lang, rule) : Promise.resolve(null)),
    [open, rule, lang],
  );

  if (!open) {
    return (
      <button
        className="btn-ghost mt-4 !py-1.5 text-xs"
        onClick={() => setOpen(true)}
      >
        Practise this rule
      </button>
    );
  }
  if (drill.loading) return <Skeleton rows={1} />;
  if (!drill.data) return null;

  return (
    <div className="mt-4 space-y-2">
      {drill.data.items.map((item) => (
        <div key={item.written} className="rounded-xl border border-line p-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Target lang={lang} size="md">{item.written}</Target>
            <AudioButton text={item.spoken} lang={lang} />
          </div>
          <ol className="space-y-1 text-sm text-muted">
            {(item.explained?.steps ?? []).map((s, i) => (
              <li key={i}>
                <strong className="text-ink">{s.rule_name}: </strong>
                {s.child_explanation}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}

// ==========================================================================

/**
 * Pitch accent, drawn rather than described.
 *
 * The staircase is the point: two words made of the same beats, sitting at
 * different heights. And the honest boundary is stated on the page rather than
 * buried in a docs file — the app computes any contour you give it a number
 * for, and ships numbers only for the pairs where the pitch *is* the lesson.
 */
function Pitch({ pitch, lang }: { pitch: PitchAccent; lang: string }) {
  return (
    <>
      <div className="card mb-6 border-l-4 !border-l-brand p-4">
        <p className="text-sm leading-relaxed">{pitch.computed}</p>
        <p className="mt-2 text-sm leading-relaxed text-muted">{pitch.not_stored}</p>
      </div>

      <Section title="The four shapes" hint="Every word in Tokyo Japanese is one of these">
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(pitch.kinds).map(([id, info]) => (
            <div key={id} className="card p-4">
              <h3 className="mb-2 font-semibold">{info.name}</h3>
              <TwoLevel simple={info.simple} technical={info.technical} />
            </div>
          ))}
        </div>
      </Section>

      <Section
        title={`Where pitch changes the meaning (${pitch.documented_sets} sets)`}
        hint="Same beats, different heights, different word"
      >
        <div className="grid gap-3">
          {pitch.pairs.map((set) => (
            <article key={set.reading} className="card p-5">
              <div className="mb-3 flex items-baseline gap-3">
                <Target lang={lang} size="lg" className="font-semibold">
                  {set.reading}
                </Target>
                <span className="text-xs text-faint">{set.mora} beats</span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {set.senses.map((s) => (
                  <div key={s.word} className="rounded-xl border border-line p-3">
                    <div className="mb-2 flex items-baseline justify-between gap-2">
                      <Target lang={lang} className="font-semibold">{s.word}</Target>
                      <span className="text-xs text-muted">{s.meaning}</span>
                    </div>
                    <Staircase contour={s.contour} lang={lang} />
                    <p className="mt-2 text-xs text-faint">
                      [{s.accent}] {s.contour.kind_name} · with a particle:{" "}
                      <span className="font-mono">{s.contour.with_particle}</span>
                    </p>
                    <div className="mt-2">
                      <AudioButton text={s.word} lang={lang} label="Hear it" />
                    </div>
                  </div>
                ))}
              </div>

              {set.note && (
                <p className="mt-3 text-sm leading-relaxed text-muted">{set.note}</p>
              )}
            </article>
          ))}
        </div>
      </Section>

      <p className="mt-6 text-xs leading-relaxed text-faint">
        Browser voices do not reliably reproduce pitch accent, so the audio
        button is a rough guide rather than a model. The contour above is
        computed and is correct; the synthesis may not be.
      </p>
    </>
  );
}

/** The contour as a two-row staircase — high beats on top, low beats below. */
function Staircase({ contour, lang }: { contour: PitchContour; lang: string }) {
  return (
    <div
      className="flex items-end gap-0.5"
      role="img"
      aria-label={`Pitch pattern ${contour.shape}, ${contour.kind_name}`}
    >
      {contour.mora.map((m, i) => (
        <div key={i} className="flex-1 text-center">
          <div
            className={`mb-0.5 h-8 rounded-md ${
              m.pitch === "high"
                ? "bg-brand-soft border-t-2 border-brand"
                : "mt-6 h-2 border-b-2 border-line bg-transparent"
            }`}
          />
          <Target lang={lang} className="text-sm">{m.text}</Target>
        </div>
      ))}
      {/* The trailing particle slot: for odaka it is the only place the fall
          is audible at all, so leaving it out would hide the contrast. */}
      <div className="flex-1 text-center opacity-60">
        <div
          className={`mb-0.5 h-8 rounded-md border-dashed ${
            contour.particle === "high"
              ? "bg-brand-soft/50 border-t-2 border-brand/50"
              : "mt-6 h-2 border-b-2 border-line"
          }`}
        />
        <span className="text-sm text-faint">が</span>
      </div>
    </div>
  );
}

// ==========================================================================

function Difficulties({
  lab,
  lang,
}: {
  lab: { difficulties: { id: string; title: string; contrast: string[];
    why_hard: string; fix: string; severity: string;
    minimal_pairs?: string[][] }[];
    minimal_pairs: { syllable?: string; note?: string;
      set?: { pinyin: string; hanzi?: string; meaning: string }[];
      pair?: string[]; meanings?: string[] }[] };
  lang: string;
}) {
  return (
    <>
      <Section
        title="What is hard about this language"
        hint="Ranked by how much it stops you being understood"
      >
        <div className="space-y-2">
          {lab.difficulties.map((d) => (
            <div key={d.id} className="card p-4">
              <div className="mb-1.5 flex flex-wrap items-center gap-2">
                <span className="font-semibold">{d.title}</span>
                {d.severity === "high" && (
                  <span className="chip !border-bad/40 !text-bad">high</span>
                )}
                {d.contrast?.map((c) => (
                  <Target key={c} lang={lang} className="chip">{c}</Target>
                ))}
              </div>
              <p className="mb-1.5 text-sm text-muted">{d.why_hard}</p>
              <p className="text-sm">
                <strong className="text-good">Fix: </strong>
                {d.fix}
              </p>
              {d.minimal_pairs?.length ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {d.minimal_pairs.map((pair, i) => (
                    <span key={i} className="chip">
                      {pair.map((w) => (
                        <span key={w} className="flex items-center gap-1">
                          <Target lang={lang}>{w}</Target>
                          <AudioButton
                            text={w}
                            lang={lang}
                            className="!border-0 !px-1 !py-0.5"
                          />
                        </span>
                      ))}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Section>

      {lab.minimal_pairs.length > 0 && (
        <Section
          title="Words that differ by one thing"
          hint="The fastest way to train an ear is to hear the contrast, not more speech"
        >
          <div className="grid gap-2 sm:grid-cols-2">
            {lab.minimal_pairs.map((g, i) => (
              <div key={i} className="card p-4">
                <div className="flex flex-wrap gap-3">
                  {(g.set ?? []).map((m) => (
                    <span key={m.pinyin} className="flex items-center gap-1.5">
                      <Target lang={lang} size="md">{m.hanzi || m.pinyin}</Target>
                      <span className="text-xs text-faint">{m.meaning}</span>
                      <AudioButton text={m.pinyin} lang={lang} className="!border-0 !px-1 !py-0.5" />
                    </span>
                  ))}
                  {(g.pair ?? []).map((w, j) => (
                    <span key={w} className="flex items-center gap-1.5">
                      <Target lang={lang} size="md">{w}</Target>
                      {g.meanings?.[j] && (
                        <span className="text-xs text-faint">{g.meanings[j]}</span>
                      )}
                      <AudioButton text={w} lang={lang} className="!border-0 !px-1 !py-0.5" />
                    </span>
                  ))}
                </div>
                {g.note && (
                  <p className="mt-2 text-xs leading-relaxed text-muted">{g.note}</p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

function RecordPanel({ lang, target }: { lang: string; target: string }) {
  const [recorder] = useState(() => new Recorder());
  const [recording, setRecording] = useState(false);
  const [clip, setClip] = useState<string | null>(null);
  const [error, setError] = useState("");
  const capabilities = useAsync(() => api.speechCapabilities(lang), [lang]);

  if (!recordingAvailable()) return null;

  // The backend knows whether a local speech engine is actually installed.
  // Saying "scoring is impossible" when whisper is present would be as
  // dishonest as inventing a score when it is not.
  const scoring = scoreRecording(capabilities.data?.stt.scoring_available);

  return (
    <Section title="Record yourself" hint="Compare by ear, side by side">
      <div className="card p-5">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          {target && (
            <>
              <Target lang={lang} size="md" className="font-semibold">{target}</Target>
              <AudioButton text={target} lang={lang} label="Model" />
            </>
          )}
          {!recording ? (
            <button
              className="btn-ghost"
              onClick={async () => {
                try {
                  await recorder.start();
                  setRecording(true);
                  setError("");
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Microphone unavailable.");
                }
              }}
            >
              ● Record
            </button>
          ) : (
            <button
              className="btn-primary"
              onClick={async () => {
                const rec = await recorder.stop();
                setClip(rec.url);
                setRecording(false);
              }}
            >
              ■ Stop
            </button>
          )}
          {clip && <audio src={clip} controls className="h-9" />}
        </div>
        {error && <p className="mb-2 text-sm text-bad">{error}</p>}
        <p className="text-xs leading-relaxed text-muted">{scoring.reason}</p>
      </div>
    </Section>
  );
}
