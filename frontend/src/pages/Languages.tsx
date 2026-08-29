/**
 * Languages: what each one is, how complete it is, and what it can do.
 *
 * The capability list is not decoration. Korean declares `conjugation` and
 * `speech_levels`; Japanese declares `keigo` and `mora_timing`; Mandarin
 * declares `tone_sandhi` and `measure_words` and does *not* declare
 * conjugation, because it has none. Those declarations decide what the
 * interface offers, so showing them here explains why the app looks different
 * from one language to the next.
 */

import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import { Bar, PageHeader, Section, Skeleton, StatusDot, Target } from "../components/ui";

const CAPABILITY_LABEL: Record<string, string> = {
  conjugation: "Verbs conjugate",
  particles: "Particles",
  honorifics: "Honorifics",
  speech_levels: "Speech levels",
  keigo: "Keigo",
  tone_sandhi: "Tone changes",
  measure_words: "Measure words",
  counters: "Counters",
  aspect_particles: "Aspect particles",
  pitch_accent: "Pitch accent",
  stroke_order: "Stroke order",
  character_components: "Character components",
  syllable_blocks: "Syllable blocks",
  mora_timing: "Mora timing",
};

export default function Languages() {
  const { languages, lang, switchLanguage } = useApp();
  const progress = useAsync(() => api.progressAll(), []);
  const health = useAsync(() => api.health(), []);

  const byCode = new Map((progress.data?.languages ?? []).map((L) => [L.code, L]));

  return (
    <>
      <PageHeader
        title="Languages"
        subtitle="Three, each with its own curriculum, its own level scale and its own progress. Nothing crosses over."
      />

      <div className="grid gap-3">
        {languages.map((L) => {
          const stats = byCode.get(L.code);
          const counts = health.data?.languages?.[L.code];
          const active = L.code === lang;
          return (
            <article
              key={L.code}
              className={`card p-5 ${active ? "!border-brand" : ""}`}
            >
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <span aria-hidden className="text-3xl">{L.flag}</span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-lg font-semibold">
                    {L.name}
                    <Target lang={L.code} className="ml-2 font-normal text-muted">
                      {L.native_name}
                    </Target>
                  </h2>
                  <p className="text-xs text-faint">
                    {L.level_scheme ?? "—"} · {L.iso3}
                  </p>
                </div>
                <StatusDot status={L.status} />
                {active ? (
                  <span className="chip !border-brand/40 !text-brand">active</span>
                ) : (
                  <button
                    className="btn-ghost !py-1.5 text-xs"
                    onClick={() => void switchLanguage(L.code)}
                  >
                    Switch to this
                  </button>
                )}
              </div>

              <p className="mb-4 text-sm leading-relaxed text-muted">{L.status_note}</p>

              {stats?.started && (
                <div className="mb-4 flex flex-wrap gap-4 text-sm text-muted">
                  <span>Level <strong className="text-ink">{stats.level || "—"}</strong></span>
                  <span><strong className="text-ink">{stats.known.all}</strong> known</span>
                  <span><strong className="text-ink">{stats.xp}</strong> XP</span>
                  {stats.due_now > 0 && (
                    <span className="text-brand">{stats.due_now} due now</span>
                  )}
                </div>
              )}

              <div className="mb-4">
                <p className="label mb-2">Writing systems</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {L.writing_systems.map((w) => (
                    <div key={w.id} className="rounded-xl border border-line p-3">
                      <div className="mb-1 flex items-baseline justify-between gap-2">
                        <span className="text-sm font-medium">{w.name}</span>
                        <Target lang={L.code} className="text-xs text-faint">
                          {w.native_name}
                        </Target>
                      </div>
                      {w.is_closed_inventory ? (
                        <>
                          <Bar percent={(w.mastery ?? 0) * 100} />
                          <p className="mt-1 text-xs text-faint">
                            {w.unit_count ?? "—"} units
                          </p>
                        </>
                      ) : (
                        <p className="text-xs text-faint">
                          Open set — no fixed number to finish.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="mb-4">
                <p className="label mb-2">What this language does</p>
                <div className="flex flex-wrap gap-1.5">
                  {L.capabilities.length === 0 ? (
                    <span className="text-xs text-faint">Nothing declared yet.</span>
                  ) : (
                    L.capabilities.map((c) => (
                      <span key={c} className="chip">
                        {CAPABILITY_LABEL[c] ?? c.replace(/_/g, " ")}
                      </span>
                    ))
                  )}
                </div>
                {!L.capabilities.includes("conjugation") && L.status !== "planned" && (
                  <p className="mt-2 text-xs leading-relaxed text-faint">
                    No conjugation is declared, so the app does not show a
                    conjugation view for {L.name} — there would be nothing in it.
                  </p>
                )}
              </div>

              {counts && (
                <div className="flex flex-wrap gap-3 text-xs text-faint">
                  {Object.entries(counts).map(([k, n]) => (
                    <span key={k}>
                      <strong className="text-muted">{n}</strong> {k}
                    </span>
                  ))}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {progress.loading && <Skeleton rows={2} />}

      <Section title="Adding a fourth">
        <p className="card p-5 text-sm leading-relaxed text-muted">
          A language is a directory of six modules plus a curriculum of JSON —
          nothing in the shared engine changes. The step-by-step guide is in{" "}
          <span className="font-mono text-xs">docs/LANGUAGE_MODULES.md</span>.
          The hardest part is not the code: it is knowing which three things a
          learner of that language gets wrong invisibly for months, because that
          is what the module has to be built around.
        </p>
      </Section>
    </>
  );
}
