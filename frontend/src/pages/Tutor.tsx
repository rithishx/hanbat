/**
 * The AI tutor — entirely optional, and honest when it is not there.
 *
 * With no provider configured this screen does not show a chat box that
 * silently fails, and it does not show canned answers pretending to be a
 * model. It shows what is missing and how to fix it, and every other part of
 * the app keeps working without it.
 *
 * Ollama, LM Studio and llama.cpp run on the learner's own machine, so using
 * them is a loopback request rather than internet access. A remote provider is
 * possible and is labelled as a network feature wherever it appears.
 */

import { useRef, useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import {
  ErrorState, PageHeader, Section, Skeleton, Target,
} from "../components/ui";

interface Turn {
  role: "you" | "tutor";
  text: string;
  /** The backend flags a reply that handed over the answer too fast. */
  gaveAway?: boolean;
}

export default function Tutor() {
  const { lang, language, settings, updateSettings } = useApp();
  const status = useAsync(() => api.aiStatus(), []);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  if (status.loading) return <Skeleton rows={4} />;
  if (status.error) return <ErrorState error={status.error} onRetry={status.reload} />;

  const s = status.data!;

  const ask = async () => {
    const q = question.trim();
    if (!q) return;
    setTurns((t) => [...t, { role: "you", text: q }]);
    setQuestion("");
    setBusy(true);
    setFailure("");
    try {
      const history = turns.map((t) => ({
        role: t.role === "you" ? "user" : "assistant",
        content: t.text,
      }));
      const res = await api.ask(lang, { message: q, history });
      if (res.available && res.text) {
        setTurns((t) => [
          ...t,
          { role: "tutor", text: res.text, gaveAway: res.collapse_answer },
        ]);
      } else {
        setFailure(res.reason ?? res.error ?? "The model did not answer.");
      }
    } catch (e) {
      setFailure(e instanceof Error ? e.message : "The request failed.");
    } finally {
      setBusy(false);
      requestAnimationFrame(() => bottom.current?.scrollIntoView({ behavior: "smooth" }));
    }
  };

  return (
    <>
      <PageHeader
        title="Tutor"
        native={language?.native_name}
        subtitle="Optional. Everything else in the app works without it."
      />

      {!s.available ? (
        <NoProvider status={s} />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="chip !border-good/40 !text-good">
              {s.selected_provider} · {s.selected_model || "default model"}
            </span>
            <label className="ml-auto flex items-center gap-2">
              <input
                type="checkbox"
                checked={settings?.ai_socratic ?? true}
                onChange={(e) => void updateSettings({ ai_socratic: e.target.checked })}
              />
              Make me work for it (Socratic)
            </label>
          </div>

          <div className="card mb-4 max-h-[55vh] space-y-4 overflow-y-auto p-5">
            {turns.length === 0 && (
              <div className="text-sm leading-relaxed text-muted">
                <p className="mb-2">
                  Ask about anything you are stuck on. With Socratic mode on, the
                  tutor will push you towards the answer instead of handing it
                  over — which is slower and works better.
                </p>
                <ul className="list-inside list-disc space-y-1 text-faint">
                  <li>Why is this sentence wrong?</li>
                  <li>What is the difference between these two?</li>
                  <li>Give me three sentences using this pattern.</li>
                </ul>
              </div>
            )}
            {turns.map((t, i) => (
              <div
                key={i}
                className={`rounded-2xl p-3.5 text-sm leading-relaxed ${
                  t.role === "you"
                    ? "ml-8 bg-brand-soft"
                    : "mr-8 border border-line bg-paper"
                }`}
              >
                <p className="label mb-1">{t.role === "you" ? "You" : "Tutor"}</p>
                {t.gaveAway ? (
                  <details>
                    <summary className="cursor-pointer text-xs font-semibold text-warn">
                      This reply gives the answer away — open it if you want it
                    </summary>
                    <Target lang={lang} className="mt-2 block whitespace-pre-line !text-[1em]">
                      {t.text}
                    </Target>
                  </details>
                ) : (
                  <Target lang={lang} className="whitespace-pre-line !text-[1em]">
                    {t.text}
                  </Target>
                )}
              </div>
            ))}
            {busy && (
              <p className="text-sm text-faint">
                Thinking — a local model on a laptop takes a few seconds.
              </p>
            )}
            {failure && (
              <p className="rounded-xl bg-bad/5 p-3 text-sm text-bad">{failure}</p>
            )}
            <div ref={bottom} />
          </div>

          <form
            className="flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void ask();
            }}
          >
            <input
              className="field flex-1"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask something"
              aria-label="Your question"
            />
            <button className="btn-primary" disabled={busy || !question.trim()}>
              Ask
            </button>
          </form>
        </>
      )}
    </>
  );
}

function NoProvider({ status }: { status: { providers: { id: string; name: string; available: boolean; base_url: string; error: string; hint: string }[] } }) {
  return (
    <>
      <div className="card mb-6 p-6">
        <h2 className="mb-2 text-lg font-semibold">No model is running</h2>
        <p className="mb-4 text-sm leading-relaxed text-muted">
          The tutor needs a language model on this machine. There is deliberately
          no fallback: a canned answer dressed up as a tutor would be worse than
          no tutor, because you could not tell which one you were reading.
        </p>
        <p className="text-sm leading-relaxed text-muted">
          Everything else — lessons, review, pronunciation, grammar — works
          exactly the same without this.
        </p>
      </div>

      <Section title="What was checked" hint="All on this machine, over loopback">
        <div className="space-y-2">
          {status.providers.map((p) => (
            <div key={p.id} className="card p-4">
              <div className="mb-1 flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full ${p.available ? "bg-good" : "bg-faint"}`}
                  aria-hidden
                />
                <span className="font-semibold">{p.name}</span>
                <span className="font-mono text-xs text-faint">{p.base_url}</span>
              </div>
              {p.hint && <p className="text-sm leading-relaxed text-muted">{p.hint}</p>}
              {p.error && (
                <p className="mt-1 font-mono text-xs text-faint">{p.error}</p>
              )}
            </div>
          ))}
        </div>
      </Section>

      <p className="rounded-2xl border border-line p-4 text-xs leading-relaxed text-muted">
        Once one of these is running, choose it in{" "}
        <a className="font-semibold text-brand hover:underline" href="/settings">
          Settings
        </a>
        . A remote, non-local provider can also be configured there — it is the
        one part of this application that sends anything over the network, and
        it is off unless you turn it on.
      </p>
    </>
  );
}
