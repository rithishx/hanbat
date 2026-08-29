/**
 * Pronunciation.
 *
 * Type anything and see what it actually sounds like, with the rule that
 * changed it. The shape of the answer is language-defined — Korean returns a
 * chain of sound changes, Japanese a mora breakdown, Mandarin a tone trace —
 * so this screen renders the *steps* generically and lets each language decide
 * what a step is. That is the protocol boundary, seen from the UI side.
 *
 * The recorder records and nothing scores it, which is stated rather than
 * papered over with a made-up percentage.
 */

import { useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import { Recorder, recordingAvailable, scoreRecording } from "../lib/speech";
import {
  AudioButton, ErrorState, NotReady, PageHeader, Section, Skeleton, Target,
} from "../components/ui";

const SAMPLES: Record<string, string[]> = {
  ko: ["한국어", "먹고 싶어요", "좋아요", "학교", "감사합니다", "읽는다"],
  ja: ["きょう", "がっこう", "きって", "コーヒー", "せんせい", "べんきょう"],
  zh: ["nǐ hǎo", "wǒ hěn hǎo", "bù shì", "yī gè", "Zhōngguó", "xièxie"],
};

export default function Pronunciation() {
  const { lang, language } = useApp();
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [casual, setCasual] = useState(false);

  const result = useAsync(
    () => (submitted ? api.pronounce(submitted, lang, casual) : Promise.resolve(null)),
    [submitted, lang, casual],
  );
  const difficulties = useAsync(() => api.speechDifficulties(lang), [lang]);
  const capabilities = useAsync(() => api.speechCapabilities(lang), [lang]);

  if (difficulties.notReady) return <NotReady notReady={difficulties.notReady} />;

  const samples = SAMPLES[lang] ?? [];

  return (
    <>
      <PageHeader
        title="Pronunciation"
        native={language?.native_name}
        subtitle="What it sounds like, and the rule that made it sound that way."
      />

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
        {language?.code === "ko" && (
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

      {result.data && (
        <div className="card mb-8 animate-fade-up p-5">
          <div className="mb-4 flex flex-wrap items-center gap-4">
            <div>
              <p className="label">Written</p>
              <Target lang={lang} size="lg">
                {result.data.written ?? submitted}
              </Target>
            </div>
            <span aria-hidden className="text-2xl text-faint">→</span>
            <div>
              <p className="label">Said</p>
              <Target lang={lang} size="lg" className="font-semibold text-brand">
                {result.data.spoken}
              </Target>
            </div>
            <AudioButton text={result.data.spoken} lang={lang} className="ml-auto" />
          </div>

          {result.data.summary && (
            <p className="mb-3 text-sm text-muted">{result.data.summary}</p>
          )}

          {result.data.steps?.length ? (
            <ol className="space-y-3">
              {result.data.steps.map((s, i) => (
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
                  <p className="text-sm leading-relaxed">{s.child_explanation}</p>
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-xs font-semibold text-brand">
                      The precise version
                    </summary>
                    <p className="mt-1 text-sm text-muted">{s.linguistic_explanation}</p>
                  </details>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-muted">
              Nothing changes here — it is said exactly as it is written.
            </p>
          )}
        </div>
      )}

      <RecordPanel lang={lang} target={submitted || samples[0] || ""} />

      <Section
        title="What is hard about this language"
        hint="Ranked by how much it stops you being understood"
      >
        {difficulties.loading ? (
          <Skeleton rows={3} />
        ) : (
          <div className="space-y-2">
            {(difficulties.data?.difficulties ?? []).map((d) => (
              <div key={d.id} className="card p-4">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{d.title}</span>
                  {d.severity === "high" && (
                    <span className="chip !border-bad/40 !text-bad">high</span>
                  )}
                  {d.contrast?.map((c) => (
                    <Target key={c} lang={lang} className="chip">
                      {c}
                    </Target>
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
                            <AudioButton text={w} lang={lang} className="!border-0 !px-1 !py-0.5" />
                          </span>
                        ))}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Section>

      {capabilities.data && (
        <p className="rounded-2xl border border-line p-4 text-xs leading-relaxed text-muted">
          <strong>Audio: </strong>
          {capabilities.data.tts.note}
        </p>
      )}
    </>
  );
}

function RecordPanel({ lang, target }: { lang: string; target: string }) {
  const [recorder] = useState(() => new Recorder());
  const [recording, setRecording] = useState(false);
  const [clip, setClip] = useState<string | null>(null);
  const [error, setError] = useState("");
  const scoring = scoreRecording();

  if (!recordingAvailable()) return null;

  return (
    <Section title="Record yourself" hint="Compare by ear, side by side">
      <div className="card p-5">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          {target && (
            <>
              <Target lang={lang} size="md" className="font-semibold">
                {target}
              </Target>
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
