/**
 * The writing system.
 *
 * A language may have several, and they are learned separately — Japanese
 * registers hiragana, katakana and kanji, and a learner who has finished the
 * first two has not started the third. Each is a tab with its own progress.
 *
 * An *open* inventory (kanji, hanzi) cannot be enumerated. It says so, with a
 * count of what has been authored, rather than showing a progress bar that
 * could never reach 100% and would read as a stalled download.
 */

import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync, useLocalState } from "../lib/hooks";
import {
  AudioButton, Bar, ErrorState, NotReady, PageHeader, Skeleton, Target,
} from "../components/ui";
import type { ScriptUnit } from "../lib/types";

export default function Writing() {
  const { lang, language } = useApp();
  const systems = useAsync(() => api.writingSystems(lang), [lang]);
  const [active, setActive] = useLocalState<string>(`writing.${lang}`, "");
  const [selected, setSelected] = useState<ScriptUnit | null>(null);

  const list = systems.data?.writing_systems ?? [];
  const current = list.find((w) => w.id === active) ?? list[0];

  useEffect(() => setSelected(null), [active, lang]);

  const units = useAsync(
    () => (current ? api.scriptUnits(current.id, lang) : Promise.resolve({ units: [], writing_system: "" })),
    [current?.id, lang],
  );

  if (systems.notReady) return <NotReady notReady={systems.notReady} />;
  if (systems.error) return <ErrorState error={systems.error} onRetry={systems.reload} />;
  if (systems.loading) return <Skeleton rows={4} />;

  return (
    <>
      <PageHeader
        title="Writing system"
        native={language?.native_name}
        subtitle="Everything else waits on this. Learn to read before you learn to say."
      />

      {list.length > 1 && (
        <div className="mb-6 flex gap-2 overflow-x-auto pb-1" role="tablist">
          {list.map((w) => (
            <button
              key={w.id}
              role="tab"
              aria-selected={w.id === current?.id}
              onClick={() => setActive(w.id)}
              className={`shrink-0 rounded-xl border px-4 py-2 text-sm transition-colors ${
                w.id === current?.id
                  ? "border-brand bg-brand-soft font-semibold text-brand"
                  : "border-line bg-raised text-muted hover:bg-brand-soft/50"
              }`}
            >
              {w.name}
              <Target lang={lang} className="ml-2 opacity-60">
                {w.native_name}
              </Target>
            </button>
          ))}
        </div>
      )}

      {current && (
        <div className="card mb-6 p-5">
          <p className="mb-3 text-sm leading-relaxed text-muted">{current.description}</p>
          {current.is_closed_inventory ? (
            <Bar
              percent={(current.mastery ?? 0) * 100}
              label={`${current.known ?? 0} of ${current.units_loaded ?? current.unit_count ?? 0} learned`}
              tone={(current.mastery ?? 0) >= 0.9 ? "good" : "brand"}
            />
          ) : (
            <p className="rounded-xl bg-warn/5 p-3 text-sm leading-relaxed text-muted">
              <strong className="text-warn">An open set.</strong> There is no
              fixed number of these to learn, so there is no percentage to show.
              They are taught by frequency and by the parts they share.
              {(current.units_loaded ?? 0) === 0 &&
                " No content is authored for it yet — that is a gap in the curriculum, not something you have missed."}
            </p>
          )}
        </div>
      )}

      {units.loading ? (
        <Skeleton rows={3} />
      ) : units.data?.units.length ? (
        <UnitGrid
          units={units.data.units}
          lang={lang}
          selected={selected}
          onSelect={setSelected}
        />
      ) : null}

      {selected && <UnitDetail unit={selected} lang={lang} onClose={() => setSelected(null)} />}

      {current?.has_stroke_order && (
        <p className="mt-6 text-xs leading-relaxed text-faint">
          Stroke order is not animated here. Copying a character by hand, in the
          right order, is what makes it stick — the app cannot do that part for
          you, and watching an animation instead is the most common way learners
          convince themselves they have practised.
        </p>
      )}
    </>
  );
}

function UnitGrid({
  units,
  lang,
  selected,
  onSelect,
}: {
  units: ScriptUnit[];
  lang: string;
  selected: ScriptUnit | null;
  onSelect: (u: ScriptUnit) => void;
}) {
  const groups = useMemo(() => {
    const m = new Map<string, ScriptUnit[]>();
    for (const u of units) {
      const key = (u.data?.group as string) || u.kind || "other";
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(u);
    }
    return [...m.entries()];
  }, [units]);

  return (
    <>
      {groups.map(([group, items]) => (
        <section key={group} className="mb-6">
          <h2 className="label mb-2 capitalize">{group.replace(/_/g, " ")}</h2>
          <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8">
            {items.map((u) => (
              <button
                key={u.id}
                onClick={() => onSelect(u)}
                aria-pressed={selected?.id === u.id}
                className={`card grid aspect-square place-items-center transition-colors hover:bg-brand-soft ${
                  selected?.id === u.id ? "!border-brand bg-brand-soft" : ""
                } ${u.known ? "!border-good/40" : ""}`}
              >
                <Target lang={lang} size="lg" className="font-semibold">
                  {u.unit}
                </Target>
                <span className="text-[0.65rem] text-faint">{u.transliteration}</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}

function UnitDetail({
  unit,
  lang,
  onClose,
}: {
  unit: ScriptUnit;
  lang: string;
  onClose: () => void;
}) {
  const d = unit.data as Record<string, unknown>;
  const sound = d.sound as Record<string, string> | undefined;
  const shape = d.shape as Record<string, string> | undefined;

  return (
    <div className="sticky bottom-20 z-20 lg:bottom-4">
      <div className="card animate-fade-up p-5 shadow-lg">
        <div className="mb-3 flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <Target lang={lang} size="hero" className="font-semibold">
              {unit.unit}
            </Target>
            <div>
              <p className="font-semibold">{unit.name}</p>
              <p className="text-sm text-muted">{unit.transliteration}</p>
              <AudioButton text={unit.name || unit.unit} lang={lang} className="mt-2" />
            </div>
          </div>
          <button className="btn-quiet !px-2" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {sound?.english_hint && (
          <p className="mb-2 text-sm leading-relaxed">{sound.english_hint}</p>
        )}
        {sound?.common_error && (
          <p className="mb-2 rounded-xl bg-warn/5 p-3 text-sm text-muted">
            <strong className="text-warn">Watch out: </strong>
            {sound.common_error}
          </p>
        )}
        {Boolean(shape?.mnemonic || d.note) && (
          <p className="text-sm leading-relaxed text-muted">
            {String(shape?.mnemonic ?? d.note ?? "")}
          </p>
        )}
        {sound?.final && (
          <p className="mt-2 text-sm text-muted">
            At the end of a block it becomes{" "}
            <span className="font-semibold">{sound.final}</span>.
          </p>
        )}
      </div>
    </div>
  );
}
