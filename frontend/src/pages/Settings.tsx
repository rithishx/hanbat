/**
 * Settings.
 *
 * Grouped so the honest ones are easy to find: what the app can do without a
 * network, what it cannot, and exactly what leaves the machine if you turn a
 * network feature on. That section is not buried under "Advanced".
 *
 * Romanisation gets its own explanation because the app fades it as you
 * improve, and a setting that changes itself needs to say so.
 */

import { useState, type ReactNode } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import { loadVoices, voicesFor } from "../lib/speech";
import { ErrorState, PageHeader, Section, Skeleton } from "../components/ui";
import type { Settings as S } from "../lib/types";

export default function Settings() {
  const { settings, updateSettings, lang, language, refresh } = useApp();
  const runtime = useAsync(() => api.runtime(), []);
  const ai = useAsync(() => api.aiStatus(), []);
  const speech = useAsync(() => api.speechCapabilities(lang), [lang]);
  const [voices, setVoices] = useState<string[]>([]);
  const [notice, setNotice] = useState("");

  if (!settings) return <Skeleton rows={5} />;

  const set = <K extends keyof S,>(key: K, value: S[K]) =>
    void updateSettings({ [key]: value } as Partial<S>);

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Everything is stored in the local database. Nothing here is synced anywhere."
      />

      {/* ---------------------------------------------------------------- */}
      <Section title="Learning">
        <div className="card divide-y divide-line">
          <Row
            label="Romanisation"
            hint={
              language?.code === "zh"
                ? "Pinyin is not a crutch — it is how Chinese is typed and how dictionaries are ordered, so it never disappears entirely. It does fade from reading practice."
                : "Romanisation is scaffolding. The app lowers it as you improve, and a learner still reading it at B1 has been failed by the app. You can override that here."
            }
          >
            <Select
              value={settings.romanization}
              onChange={(v) => set("romanization", v as S["romanization"])}
              options={[
                ["auto", "Fade it as I improve"],
                ["always", "Always show it"],
                ["never", "Never show it"],
              ]}
            />
          </Row>

          <Row label="Daily goal">
            <Select
              value={String(settings.daily_goal_minutes)}
              onChange={(v) => set("daily_goal_minutes", Number(v))}
              options={[["5", "5 min"], ["10", "10 min"], ["15", "15 min"], ["30", "30 min"], ["60", "60 min"]]}
            />
          </Row>

          <Row label="New cards a day" hint="More is not better — the reviews compound.">
            <Select
              value={String(settings.new_cards_per_day)}
              onChange={(v) => set("new_cards_per_day", Number(v))}
              options={[["5", "5"], ["10", "10"], ["20", "20"], ["30", "30"]]}
            />
          </Row>

          <Row label="Difficulty">
            <Select
              value={settings.difficulty}
              onChange={(v) => set("difficulty", v as S["difficulty"])}
              options={[["gentle", "Gentle"], ["adaptive", "Adaptive"], ["hard", "Hard"]]}
            />
          </Row>

          <Row
            label="Type answers instead of choosing"
            hint="Harder, and much more effective. Multiple choice trains recognition."
          >
            <Toggle
              checked={settings.require_typing}
              onChange={(v) => set("require_typing", v)}
            />
          </Row>

          <Row label="Show English translations">
            <Toggle
              checked={settings.show_translations}
              onChange={(v) => set("show_translations", v)}
            />
          </Row>
        </div>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section title="Sound">
        <div className="card divide-y divide-line">
          <Row
            label="Voice"
            hint={speech.data?.tts.note}
          >
            <select
              className="field !w-auto !py-2"
              value={settings.tts_voice}
              onFocus={async () => {
                await loadVoices();
                setVoices(voicesFor(lang).map((v) => v.name));
              }}
              onChange={(e) => set("tts_voice", e.target.value)}
            >
              <option value="">System default</option>
              {voices.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </Row>

          <Row label="Play audio automatically">
            <Toggle
              checked={settings.audio_autoplay}
              onChange={(v) => set("audio_autoplay", v)}
            />
          </Row>

          <Row label="Playback speed">
            <Select
              value={String(settings.playback_rate)}
              onChange={(v) => set("playback_rate", Number(v))}
              options={[["0.7", "0.7×"], ["0.85", "0.85×"], ["1", "Normal"], ["1.15", "1.15×"]]}
            />
          </Row>

          <Row
            label="Microphone"
            hint="Used only to record yourself, and the recording never leaves this machine."
          >
            <Toggle
              checked={settings.microphone_enabled}
              onChange={(v) => set("microphone_enabled", v)}
            />
          </Row>
        </div>
        {speech.data?.stt.browser_caveat && (
          <p className="mt-2 rounded-xl bg-warn/5 p-3 text-xs leading-relaxed text-muted">
            <strong className="text-warn">Speech recognition: </strong>
            {speech.data.stt.browser_caveat}
          </p>
        )}
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section title="Appearance and accessibility">
        <div className="card divide-y divide-line">
          <Row label="Theme">
            <Select
              value={settings.theme}
              onChange={(v) => set("theme", v as S["theme"])}
              options={[["system", "Match my system"], ["light", "Light"], ["dark", "Dark"]]}
            />
          </Row>
          <Row label="Text size">
            <Select
              value={settings.font_size}
              onChange={(v) => set("font_size", v as S["font_size"])}
              options={[["small", "Small"], ["medium", "Medium"], ["large", "Large"], ["xlarge", "Extra large"]]}
            />
          </Row>
          <Row label="High contrast">
            <Toggle checked={settings.high_contrast} onChange={(v) => set("high_contrast", v)} />
          </Row>
          <Row
            label="Dyslexia-friendly font"
            hint="Applies to the interface. The target-language text keeps its own font, because letter shapes matter there."
          >
            <Toggle checked={settings.dyslexia_font} onChange={(v) => set("dyslexia_font", v)} />
          </Row>
          <Row label="Reduce motion">
            <Toggle checked={settings.reduce_motion} onChange={(v) => set("reduce_motion", v)} />
          </Row>
        </div>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        title="AI tutor"
        hint="Optional. The app is fully usable with this switched off."
      >
        <div className="card divide-y divide-line">
          <Row
            label="Provider"
            hint="Ollama, LM Studio and llama.cpp run on this machine. Choosing one of them does not use the network."
          >
            <Select
              value={settings.ai_provider}
              onChange={(v) => set("ai_provider", v as S["ai_provider"])}
              options={[
                ["disabled", "Off"],
                ["ollama", "Ollama (local)"],
                ["lmstudio", "LM Studio (local)"],
                ["llamacpp", "llama.cpp (local)"],
                ["openai_compatible", "Remote — needs the network"],
              ]}
            />
          </Row>

          {settings.ai_provider !== "disabled" && (
            <>
              <Row label="Model">
                <input
                  className="field !w-56 !py-2"
                  value={settings.ai_model}
                  onChange={(e) => set("ai_model", e.target.value)}
                  placeholder="qwen2.5:7b"
                />
              </Row>
              {settings.ai_provider === "openai_compatible" && (
                <Row label="Base URL" hint="This is a network feature. Requests go wherever this points.">
                  <input
                    className="field !w-56 !py-2"
                    value={settings.ai_base_url}
                    onChange={(e) => set("ai_base_url", e.target.value)}
                    placeholder="http://…"
                  />
                </Row>
              )}
              <Row
                label="Socratic mode"
                hint="Push me towards the answer instead of giving it. Slower, and it works better."
              >
                <Toggle checked={settings.ai_socratic} onChange={(v) => set("ai_socratic", v)} />
              </Row>
            </>
          )}
        </div>

        {ai.data && (
          <div className="mt-2 space-y-1 text-xs text-muted">
            {ai.data.providers.map((p) => (
              <p key={p.id}>
                <span className={p.available ? "text-good" : "text-faint"}>
                  {p.available ? "✓" : "○"}
                </span>{" "}
                <strong>{p.name}</strong> — {p.available ? "reachable" : p.hint || p.error}
              </p>
            ))}
          </div>
        )}
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section title="Network" hint="What can leave this machine, and what cannot">
        <div className="card p-5">
          <label className="mb-4 flex items-center gap-3">
            <Toggle checked={settings.allow_network} onChange={(v) => set("allow_network", v)} />
            <span>
              <span className="font-medium">Allow network features</span>
              <span className="block text-sm text-muted">
                Off by default. With this off, nothing in the app can reach the
                internet — everything below is refused rather than silently
                skipped.
              </span>
            </span>
          </label>

          <ul className="space-y-2">
            {(runtime.data?.network_features ?? []).map((f) => (
              <li key={f.id} className="rounded-xl border border-line p-3 text-sm">
                <p className="font-medium">{f.name}</p>
                <p className="text-muted">
                  <span className="label">Sends: </span>
                  {f.what_it_sends}
                </p>
                <p className="text-muted">
                  <span className="label">To: </span>
                  {f.where}
                </p>
              </li>
            ))}
          </ul>

          {runtime.data && (
            <p className="mt-4 text-xs text-faint">
              Everything else — lessons, review, pronunciation, grammar, search,
              a local AI model — works with the network switched off entirely.
            </p>
          )}
        </div>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section title="Your data" hint="It is a file. You own it.">
        <div className="card p-5">
          <div className="mb-4 flex flex-wrap gap-2">
            <a className="btn-ghost" href={api.exportUrl()} download>
              Export everything (JSON)
            </a>
            <a className="btn-ghost" href={api.exportVocabUrl(lang)} download>
              Vocabulary (CSV)
            </a>
            <a className="btn-ghost" href={api.exportAnkiUrl(lang)} download>
              Anki deck
            </a>
          </div>

          <label className="block">
            <span className="label mb-1.5 block">Import a backup</span>
            <input
              type="file"
              accept="application/json"
              className="text-sm"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  const payload = JSON.parse(await file.text());
                  const res = await api.importData(payload);
                  setNotice(
                    `Imported: ${Object.entries(res.imported)
                      .map(([k, n]) => `${n} ${k}`)
                      .join(", ")}`,
                  );
                  await refresh();
                } catch (err) {
                  setNotice(
                    err instanceof Error ? err.message : "That file could not be read.",
                  );
                }
              }}
            />
          </label>
          {notice && <p className="mt-2 text-sm text-muted">{notice}</p>}

          {runtime.data && (
            <p className="mt-4 font-mono text-xs text-faint">
              Database: {runtime.data.db_path}
            </p>
          )}
        </div>
      </Section>

      {runtime.error && <ErrorState error={runtime.error} onRetry={runtime.reload} />}

      <p className="mt-8 text-center text-xs text-faint">
        Hanbat {runtime.data?.version ?? ""} · runs on 127.0.0.1 only
      </p>
    </>
  );
}

// ==========================================================================

function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 p-4">
      <div className="min-w-0 flex-1">
        <p className="font-medium">{label}</p>
        {hint && <p className="mt-0.5 text-sm leading-relaxed text-muted">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
        checked ? "bg-brand" : "bg-line"
      }`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-[left] ${
          checked ? "left-[1.375rem]" : "left-0.5"
        }`}
      />
    </button>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <select
      className="field !w-auto !py-2"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map(([v, label]) => (
        <option key={v} value={v}>
          {label}
        </option>
      ))}
    </select>
  );
}
