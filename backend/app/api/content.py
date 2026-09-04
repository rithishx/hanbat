"""Content: lessons, vocabulary, grammar, writing systems, search, dictionary."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import store
from ..content import loader
from ..db import get_connection
from .deps import Lang, Learner, UsableLang

router = APIRouter(tags=["content"])


# ==========================================================================
# Lessons
# ==========================================================================

@router.get("/lessons")
def list_lessons(spec: UsableLang, learner: Learner,
                 level: Optional[str] = None, unit: Optional[str] = None) -> dict:
    rows = store.lessons(spec.code, level, unit)
    progress = store.lesson_progress(learner["id"], spec.code)
    done = {lid for lid, p in progress.items() if p["status"] == "completed"}

    out = []
    for L in rows:
        prereqs = L.get("prerequisites") or []
        p = progress.get(L["id"], {})
        out.append({
            **L,
            "status": p.get("status", "not_started"),
            "score": p.get("score", 0),
            "locked": bool(set(prereqs) - done),
            "blocked_by": sorted(set(prereqs) - done),
        })
    return {"language": spec.code, "lessons": out,
            "completed": len(done), "total": len(rows)}


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: str, learner: Learner) -> dict:
    L = store.lesson(lesson_id)
    if L is None:
        raise HTTPException(404, f"no lesson {lesson_id!r}")
    p = store.lesson_progress(learner["id"], L["language"]).get(lesson_id, {})
    body = L.get("body") or {}
    return {**L, "steps": body.get("steps", []),
            "introduces": body.get("introduces", {}),
            "is_gate": body.get("is_gate", False),
            "difficulty_warning": body.get("difficulty_warning", ""),
            "progress": p or {"status": "not_started"}}


@router.get("/units")
def units(spec: UsableLang, learner: Learner) -> dict:
    """The visible roadmap: units in order, with completion."""
    rows = store.lessons(spec.code)
    progress = store.lesson_progress(learner["id"], spec.code)
    by_unit: dict[str, dict] = {}
    for L in rows:
        u = by_unit.setdefault(L["unit"], {
            "id": L["unit"], "level": L["level"], "lessons": 0, "completed": 0})
        u["lessons"] += 1
        if progress.get(L["id"], {}).get("status") == "completed":
            u["completed"] += 1
    for u in by_unit.values():
        u["percent"] = round(100 * u["completed"] / u["lessons"]) if u["lessons"] else 0
    return {"language": spec.code, "units": list(by_unit.values())}


# ==========================================================================
# Vocabulary
# ==========================================================================

@router.get("/vocab")
def list_vocab(spec: UsableLang, topic: Optional[str] = None,
               level: Optional[str] = None, limit: int = 100, offset: int = 0) -> dict:
    rows = store.vocab(spec.code, topic, level, limit, offset)
    return {"language": spec.code, "count": len(rows), "words": rows}


@router.get("/vocab/topics")
def topics(spec: UsableLang) -> dict:
    return {"language": spec.code, "topics": store.vocab_topics(spec.code)}


@router.get("/vocab/{vocab_id}")
def get_vocab(vocab_id: str) -> dict:
    row = store.vocab_one(vocab_id)
    if row is None:
        raise HTTPException(404, f"no vocabulary entry {vocab_id!r}")
    from ..languages import registry
    spec = registry.get(row["language"])

    out = dict(row)
    try:
        out["pronunciation_explained"] = spec.pronunciation.explain(row["term"])
    except ModuleNotFoundError:
        pass
    # The whole row is handed over rather than a hand-picked subset, because
    # each language reaches for different columns: Korean wants `irregular`,
    # Japanese wants `reading`, and Mandarin wants `counter` (the measure word)
    # and `transliteration` (the pinyin, which it cannot derive itself).
    # Picking fields here meant 水 came back as 一个水 instead of 一杯水.
    try:
        out["drill_forms"] = spec.grammar.drill_forms(dict(row))
    except ModuleNotFoundError:
        out["drill_forms"] = []
    return out


# ==========================================================================
# Grammar
# ==========================================================================

@router.get("/grammar")
def list_grammar(spec: UsableLang, level: Optional[str] = None) -> dict:
    return {"language": spec.code, "points": store.grammar(spec.code, level)}


@router.get("/grammar/{grammar_id}")
def get_grammar(grammar_id: str) -> dict:
    row = store.grammar_one(grammar_id)
    if row is None:
        raise HTTPException(404, f"no grammar point {grammar_id!r}")
    # Resolve cross-references so the UI can render them without extra calls.
    row["similar_points"] = [store.grammar_one(i) for i in (row.get("similar") or [])]
    row["contrast_points"] = [store.grammar_one(i) for i in (row.get("contrast") or [])]
    row["similar_points"] = [p for p in row["similar_points"] if p]
    row["contrast_points"] = [p for p in row["contrast_points"] if p]
    return row


# ==========================================================================
# Writing systems
# ==========================================================================

@router.get("/writing")
def writing_overview(spec: UsableLang, learner: Learner) -> dict:
    """Every script this language uses, with the learner's mastery of each."""
    conn = get_connection()
    out = []
    for ws in spec.writing_systems:
        total = conn.execute(
            "SELECT COUNT(*) FROM script_unit WHERE language=? AND writing_system=?",
            (spec.code, ws.id)).fetchone()[0]
        known = conn.execute(
            "SELECT COUNT(*) FROM srs_card c JOIN script_unit s ON s.id = c.item_id "
            "WHERE c.learner_id=? AND c.language=? AND s.writing_system=? "
            "AND c.state IN ('review','mastered')",
            (learner["id"], spec.code, ws.id)).fetchone()[0]
        out.append({**ws.to_dict(), "units_loaded": total, "known": known,
                    "mastery": round(known / total, 3) if total else 0.0})
    return {"language": spec.code, "writing_systems": out}


@router.get("/writing/{writing_system}/units")
def units_for_script(writing_system: str, spec: UsableLang) -> dict:
    rows = store.script_units(spec.code, writing_system)
    return {"language": spec.code, "writing_system": writing_system,
            "count": len(rows), "units": rows}


@router.get("/writing/compose")
def compose(spec: UsableLang, parts: str = Query(..., description="Comma-separated parts")) -> dict:
    """Assemble written units into a written form.

    Korean composes jamo into a syllable block; other scripts will answer this
    differently or not at all. The endpoint reports which, rather than
    pretending every script composes.
    """
    try:
        engine = spec.writing
    except ModuleNotFoundError:
        raise HTTPException(409, f"{spec.code} has no writing engine yet")
    if not hasattr(engine, "compose"):
        raise HTTPException(
            409, f"{spec.name}'s writing system does not compose units into blocks")
    items = [p.strip() for p in parts.split(",") if p.strip()]
    try:
        result = engine.compose(items)
    except ValueError as e:
        raise HTTPException(400, str(e))
    detail = engine.decompose(result)[0]
    return {"parts": items, "result": result, "detail": detail}


@router.get("/writing/decompose")
def decompose(spec: UsableLang, text: str) -> dict:
    try:
        engine = spec.writing
    except ModuleNotFoundError:
        raise HTTPException(409, f"{spec.code} has no writing engine yet")
    return {"text": text, "parts": engine.decompose(text)}


# ==========================================================================
# Pronunciation
# ==========================================================================

@router.get("/pronounce")
def pronounce(spec: UsableLang, text: str, casual: bool = False) -> dict:
    """Written form to spoken form, with the reasons."""
    try:
        engine = spec.pronunciation
    except ModuleNotFoundError:
        raise HTTPException(409, f"{spec.code} has no pronunciation engine yet")
    hints = {"casual": casual} if casual else None
    return engine.explain(text, hints=hints)


@router.get("/transliterate")
def transliterate(spec: UsableLang, text: str, level: float = 1.0) -> dict:
    try:
        engine = spec.transliteration
    except ModuleNotFoundError:
        raise HTTPException(409, f"{spec.code} has no transliteration engine yet")
    return {
        "text": text,
        "scheme": engine.scheme_name,
        "full": engine.transliterate(text),
        "faded": engine.fade(text, level),
        "fully_removable": engine.fully_removable,
        "warnings": engine.ambiguity_warnings(text)
                    if hasattr(engine, "ambiguity_warnings") else [],
    }


# ==========================================================================
# Conjugation (only for languages that have it)
# ==========================================================================

@router.get("/conjugate")
def conjugate(spec: UsableLang, word: str, pos: Optional[str] = None) -> dict:
    if not spec.supports("conjugation"):
        raise HTTPException(
            409,
            {"error": "not_applicable",
             "message": f"{spec.name} has no conjugation. "
                        f"There is nothing to show here, which is why the app "
                        f"does not offer a conjugation view for it."})
    try:
        engine = spec.grammar
    except ModuleNotFoundError:
        raise HTTPException(409, f"{spec.code} has no grammar engine yet")
    try:
        return engine.conjugation_table(word, pos)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ==========================================================================
# Search
# ==========================================================================

@router.get("/search")
def search(spec: UsableLang, q: str, limit: int = 30) -> dict:
    """One box, everything in this language.

    Results carry their kind so the UI can group them, and a term that looks
    like a conjugated verb also returns the dictionary form it came from.
    """
    rows = store.search(spec.code, q, limit)
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r["kind"], []).append(r)

    extra = {}
    if spec.supports("conjugation") and q.strip().endswith("다"):
        try:
            extra["conjugation"] = spec.grammar.conjugation_table(q.strip())
        except (ValueError, ModuleNotFoundError):
            pass
    if spec.is_usable:
        try:
            extra["pronunciation"] = spec.pronunciation.pronounce(q)
        except ModuleNotFoundError:
            pass

    return {"language": spec.code, "query": q, "total": len(rows),
            "results": grouped, **extra}


# ==========================================================================
# Reloading content from disk
# ==========================================================================

@router.post("/content/reload")
def reload_content(spec: Lang) -> dict:
    """Re-read this language's JSON files. Learner progress is never touched."""
    conn = get_connection()
    loader.clear_language(spec.code, conn)
    report = loader.load_language(spec.code, conn)
    loader.rebuild_search_index(conn, spec.code)
    return report.to_dict()


# ==========================================================================
# The pronunciation lab
# ==========================================================================

@router.get("/pronunciation/lab")
def pronunciation_lab(spec: UsableLang) -> dict:
    """Everything this language's pronunciation engine knows, browsable.

    The three languages fill this with genuinely different material — Korean
    with sound-change rules, Japanese with timing rules, Mandarin with tone
    changes — and the lab renders all three the same way because the *shape* is
    shared even though the content is not. Each rule carries the plain-words
    explanation first and the terminology behind it, and every worked example
    is computed by the engine at request time rather than authored, so the lab
    cannot drift out of step with the rules it documents.
    """
    try:
        engine = spec.pronunciation
    except ModuleNotFoundError:
        raise HTTPException(409, f"{spec.code} has no pronunciation engine yet")

    rules = engine.rules() if hasattr(engine, "rules") else []
    minimal_pairs = (engine.minimal_pairs()
                     if hasattr(engine, "minimal_pairs") else [])

    out = {
        "language": spec.code,
        "name": getattr(engine, "name", ""),
        # Korean derives pronunciation from rules; Japanese cannot, because
        # kanji readings are lexical. Saying which is the difference between
        # "the app computed this" and "someone typed this in".
        "rule_derived": bool(getattr(engine, "is_rule_derived", False)),
        "rules": rules,
        "difficulties": engine.difficulty_points(),
        "minimal_pairs": minimal_pairs,
        "note": _lab_note(spec.code, rules, minimal_pairs),
    }

    # An optional extra section, present only for a language whose engine has
    # something real to put in it. Korean and Mandarin have no pitch accent, so
    # the key is absent for them and the page renders one section fewer —
    # rather than an empty panel explaining what the language does not have.
    if hasattr(engine, "pitch_accent"):
        out["pitch_accent"] = engine.pitch_accent()
    return out


def _lab_note(code: str, rules: list, pairs: list) -> str:
    if not rules:
        return ("This language's pronunciation engine does not publish a rule "
                "index yet. The explanations on individual words still work.")
    return (f"{len(rules)} rules, each with a worked example checked against "
            f"the engine when this page was built. If an example ever "
            f"contradicts the rule it illustrates, it is marked rather than "
            f"hidden.")


@router.get("/pronunciation/drill")
def pronunciation_drill(spec: UsableLang, rule: str) -> dict:
    """The examples for one rule, ready to practise.

    Answers the question a rule index always raises next: "fine, let me try
    it." The examples come from the rule itself, so a learner drills the exact
    thing they just read about.
    """
    try:
        engine = spec.pronunciation
    except ModuleNotFoundError:
        raise HTTPException(409, f"{spec.code} has no pronunciation engine yet")
    if not hasattr(engine, "rules"):
        raise HTTPException(409, f"{spec.code} publishes no rule index")

    found = next((r for r in engine.rules() if r["id"] == rule), None)
    if found is None:
        raise HTTPException(404, f"no pronunciation rule {rule!r} in {spec.code}")

    items = []
    for ex in found["examples"]:
        detail = {}
        try:
            detail = engine.explain(ex["written"], hints=ex.get("hints") or None)
        except TypeError:
            detail = engine.explain(ex["written"])
        except Exception:
            detail = {}
        items.append({**ex, "explained": detail})

    return {"language": spec.code, "rule": found, "items": items}
