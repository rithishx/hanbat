/**
 * The grammar reference.
 *
 * Every point carries two explanations and shows the plain one first. The
 * terminology is behind a click, never in front of it — that ordering is the
 * whole teaching philosophy, and putting "the polite copula attaches to
 * nominals" at the top of the card would undo it.
 *
 * Mistakes are shown as wrong→right pairs with the reason, because the way
 * most people learn a grammar point is by seeing the error they were about to
 * make.
 */

import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/app-context";
import { useAsync } from "../lib/hooks";
import {
  AudioButton, Empty, ErrorState, NotReady, PageHeader, Skeleton, Target, TwoLevel,
} from "../components/ui";
import type { GrammarPoint } from "../lib/types";

export default function Grammar() {
  const { pointId } = useParams();
  const { lang, language } = useApp();
  const [openId, setOpenId] = useState<string | null>(pointId ?? null);
  const [category, setCategory] = useState("");

  const points = useAsync(() => api.grammar(lang), [lang]);

  const categories = useMemo(() => {
    const set = new Set((points.data?.points ?? []).map((p) => p.category).filter(Boolean));
    return [...set].sort();
  }, [points.data]);

  const list = (points.data?.points ?? []).filter(
    (p) => !category || p.category === category,
  );

  if (points.notReady) return <NotReady notReady={points.notReady} />;
  if (points.error) return <ErrorState error={points.error} onRetry={points.reload} />;

  return (
    <>
      <PageHeader
        title="Grammar"
        native={language?.native_name}
        subtitle={
          points.data
            ? `${points.data.points.length} points, in the order they are taught`
            : undefined
        }
      />

      {categories.length > 1 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            className={`chip ${!category ? "!border-brand !text-brand" : ""}`}
            onClick={() => setCategory("")}
          >
            All
          </button>
          {categories.map((c) => (
            <button
              key={c}
              className={`chip capitalize ${category === c ? "!border-brand !text-brand" : ""}`}
              onClick={() => setCategory(c)}
            >
              {c.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      )}

      {points.loading ? (
        <Skeleton rows={5} />
      ) : list.length === 0 ? (
        <Empty
          title="No grammar points yet"
          body="The curriculum for this language has not reached grammar. The writing system comes first."
          action={{ to: "/writing", label: "Writing system" }}
        />
      ) : (
        <ul className="space-y-2">
          {list.map((p) => (
            <li key={p.id}>
              <Point
                point={p}
                lang={lang}
                open={openId === p.id}
                onToggle={() => setOpenId(openId === p.id ? null : p.id)}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Point({
  point,
  lang,
  open,
  onToggle,
}: {
  point: GrammarPoint;
  lang: string;
  open: boolean;
  onToggle: () => void;
}) {
  const detail = useAsync(
    () => (open ? api.grammarPoint(point.id, lang) : Promise.resolve(null)),
    [open, point.id, lang],
  );
  const p = detail.data ?? point;

  return (
    <div className="card overflow-hidden">
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-brand-soft/40"
      >
        <span className="w-8 shrink-0 text-sm text-faint">{point.ordinal}</span>
        <span className="min-w-0 flex-1">
          <Target lang={lang} size="md" className="font-semibold">
            {point.name_native || point.name}
          </Target>
          <span className="ml-2 text-sm text-muted">{point.meaning}</span>
        </span>
        {point.level && <span className="chip shrink-0">{point.level}</span>}
        <span aria-hidden className="text-faint">
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open && (
        <div className="animate-fade-up border-t border-line p-5">
          {p.structure && (
            <p className="mb-4 rounded-xl bg-paper p-3 font-mono text-sm">
              <Target lang={lang}>{p.structure}</Target>
            </p>
          )}

          <TwoLevel simple={p.simple} technical={p.technical} />

          {p.formality && (
            <p className="mt-3 text-sm text-muted">
              <span className="label">Formality: </span>
              {p.formality}
            </p>
          )}

          {p.examples?.length > 0 && (
            <div className="mt-5">
              <p className="label mb-2">Examples</p>
              <ul className="space-y-2.5">
                {p.examples.map((ex, i) => (
                  <li key={i} className="border-l-2 border-line pl-3">
                    <span className="flex flex-wrap items-center gap-2">
                      <Target lang={lang} size="md">
                        {ex.target}
                      </Target>
                      {ex.target && <AudioButton text={ex.target} lang={lang} className="!py-1 !px-2" />}
                    </span>
                    {ex.pinyin && (
                      <span className="block text-xs text-faint">{ex.pinyin}</span>
                    )}
                    <span className="block text-sm text-muted">{ex.english}</span>
                    {ex.note && (
                      <span className="block text-xs text-faint">{ex.note}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {p.mistakes?.length > 0 && (
            <div className="mt-5">
              <p className="label mb-2">What people get wrong</p>
              <ul className="space-y-2">
                {p.mistakes.map((m, i) => (
                  <li key={i} className="rounded-xl bg-bad/5 p-3 text-sm">
                    <span className="block">
                      <span className="text-bad line-through">
                        <Target lang={lang}>{m.wrong}</Target>
                      </span>
                      <span className="mx-2 text-faint" aria-hidden>→</span>
                      <span className="text-good">
                        <Target lang={lang}>{m.right}</Target>
                      </span>
                    </span>
                    <span className="mt-1 block text-muted">{m.why}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(p.contrast_points?.length ?? 0) > 0 && (
            <div className="mt-5">
              <p className="label mb-2">Often confused with</p>
              <div className="flex flex-wrap gap-2">
                {p.contrast_points!.map((c) => (
                  <span key={c.id} className="chip">
                    <Target lang={lang}>{c.name_native || c.name}</Target> — {c.meaning}
                  </span>
                ))}
              </div>
            </div>
          )}

          <button
            className="btn-ghost mt-5 !py-1.5 text-xs"
            onClick={() =>
              void api.enqueue(lang, [{ item_type: "grammar", item_id: p.id }])
            }
          >
            Add to review
          </button>
        </div>
      )}
    </div>
  );
}
