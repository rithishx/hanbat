/**
 * First run.
 *
 * The questions come from the API rather than being hard-coded here, because
 * which languages are offered — and which of them are ready — is the
 * registry's business, not the UI's. A language whose status is "planned"
 * arrives with `enabled: false` and an explanation, so a learner is told it is
 * coming instead of picking it and finding an empty curriculum.
 *
 * There are four questions and no account. Nothing here leaves the machine.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import { ErrorState, Loading, Target } from "../components/ui";

export default function Onboarding() {
  const nav = useNavigate();
  const { refresh } = useApp();
  const { data, loading, error, reload } = useAsync(() => api.onboardingQuestions(), []);
  const [answers, setAnswers] = useState<Record<string, string | number>>({});
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState("");

  if (loading) return <FullPage><Loading /></FullPage>;
  if (error) return <FullPage><ErrorState error={error} onRetry={reload} /></FullPage>;
  if (!data) return null;

  const questions = data.questions;
  const total = questions.length + 1;          // + the intro
  const current = step === 0 ? null : questions[step - 1];

  const submit = async () => {
    setSubmitting(true);
    setFailure("");
    try {
      const res = await api.onboard({
        language: String(answers.language),
        experience: String(answers.experience ?? "none"),
        goal: answers.goal ? String(answers.goal) : undefined,
        minutes: answers.minutes ? Number(answers.minutes) : undefined,
        name: name.trim() || undefined,
      });
      await refresh();
      nav(res.needs_placement ? "/placement" : "/", { replace: true });
    } catch (e) {
      setFailure(e instanceof Error ? e.message : "Could not save that.");
      setSubmitting(false);
    }
  };

  return (
    <FullPage>
      <div className="mb-8">
        <div className="mb-6 flex gap-1.5" aria-hidden>
          {Array.from({ length: total }).map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full ${i <= step ? "bg-brand" : "bg-line"}`}
            />
          ))}
        </div>

        {step === 0 ? (
          <div className="animate-fade-up">
            <Target size="lg" className="mb-2 block font-semibold">
              {data.greeting.native}
            </Target>
            <h1 className="mb-3 text-3xl font-bold tracking-tight">
              {data.greeting.english}
            </h1>
            <p className="mb-6 leading-relaxed text-muted">
              Four questions, then you start. There is no account and no sign-up —
              everything you do stays in a file on this computer, and the app works
              with the network switched off.
            </p>
            <label className="mb-6 block">
              <span className="label mb-1.5 block">What should I call you? (optional)</span>
              <input
                className="field"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
              />
            </label>
            <button className="btn-primary w-full sm:w-auto" onClick={() => setStep(1)}>
              Start →
            </button>
          </div>
        ) : (
          current && (
            <div className="animate-fade-up" key={current.id}>
              <h1 className="mb-6 text-2xl font-bold tracking-tight sm:text-3xl">
                {current.question}
              </h1>
              <div className="grid gap-2.5">
                {current.options.map((o) => {
                  const disabled = o.enabled === false;
                  const picked = answers[current.id] === o.value;
                  return (
                    <button
                      key={String(o.value)}
                      disabled={disabled}
                      onClick={() => {
                        const next = { ...answers, [current.id]: o.value };
                        setAnswers(next);
                        if (step < questions.length) setStep(step + 1);
                      }}
                      className={`card flex items-center justify-between gap-3 p-4 text-left transition-colors ${
                        picked ? "!border-brand bg-brand-soft" : "hover:bg-brand-soft/50"
                      } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
                    >
                      <span>
                        <span className="font-medium">{o.label}</span>
                        {o.native && (
                          <Target className="ml-2 text-muted">{o.native}</Target>
                        )}
                        {o.note && (
                          <span className="mt-0.5 block text-xs text-faint">{o.note}</span>
                        )}
                        {disabled && (
                          <span className="mt-0.5 block text-xs text-warn">
                            Not ready yet
                          </span>
                        )}
                      </span>
                      <span aria-hidden className="text-faint">→</span>
                    </button>
                  );
                })}
              </div>

              <div className="mt-6 flex items-center justify-between">
                <button className="btn-quiet" onClick={() => setStep(step - 1)}>
                  ← Back
                </button>
                {step === questions.length && (
                  <button
                    className="btn-primary"
                    disabled={!answers.language || submitting}
                    onClick={() => void submit()}
                  >
                    {submitting ? "Setting up…" : "Finish"}
                  </button>
                )}
              </div>
              {failure && <p className="mt-3 text-sm text-bad">{failure}</p>}
            </div>
          )
        )}
      </div>
    </FullPage>
  );
}

function FullPage({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh place-items-center bg-paper p-5">
      <div className="w-full max-w-lg">{children}</div>
    </div>
  );
}
