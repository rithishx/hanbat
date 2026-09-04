"""
Content loading: JSON files on disk -> the SQLite content cache.

The files are the source of truth. The database is a queryable index of them,
rebuilt whenever they change, and never edited by hand. That split is what
makes it possible to add thousands of lessons by dropping in JSON without
touching a line of application code.

Loading is language-scoped and convention-driven: for each registered language
the loader walks `content/<code>/` and dispatches each file by the directory it
sits in. A new language becomes loadable by creating its directory — no
registration of individual files, no code change here.

Derived fields are computed at load time rather than stored in the JSON.
Korean pronunciation and romanisation come from the phonology engine, so a
correction to a sound-change rule propagates to every example sentence on the
next reload instead of leaving 300 hand-written strings quietly wrong.
"""

from __future__ import annotations

import importlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from ..config import CONTENT_DIR
from ..db import execute, get_connection, now_iso
from ..engines import exercises
from ..languages import registry


@dataclass
class LoadReport:
    """What a reload actually did, per language and per kind."""

    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    skipped_languages: list[str] = field(default_factory=list)

    def add(self, language: str, kind: str, n: int) -> None:
        self.counts.setdefault(language, {})
        self.counts[language][kind] = self.counts[language].get(kind, 0) + n

    @property
    def total(self) -> int:
        return sum(sum(k.values()) for k in self.counts.values())

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "total": self.total,
            "counts": self.counts,
            "warnings": self.warnings,
            "errors": self.errors,
            "files_read": self.files_read,
            "skipped_languages": self.skipped_languages,
        }

    def summary(self) -> str:
        lines = []
        for lang, kinds in sorted(self.counts.items()):
            parts = ", ".join(f"{n} {k}" for k, n in sorted(kinds.items()))
            lines.append(f"  {lang}: {parts}")
        if self.warnings:
            lines.append(f"  {len(self.warnings)} warning(s)")
        if self.errors:
            lines.append(f"  {len(self.errors)} ERROR(s)")
        return "\n".join(lines) or "  (nothing loaded)"


# ==========================================================================
# Helpers
# ==========================================================================

def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _expand_columnar(doc: dict) -> list[dict]:
    """Turn the {"fields": [...], "words": [[...]]} format into dicts.

    Large vocabularies are authored columnar because 300 rows of repeated key
    names is unreadable and un-diffable. Anything needing more than the shared
    columns carries a `detail` entry, merged in here.
    """
    fields = doc.get("fields") or []
    rows = doc.get("words") or doc.get("rows") or []
    detail = doc.get("detail") or {}
    out: list[dict] = []
    for row in rows:
        entry = dict(zip(fields, row))
        extra = detail.get(entry.get("id"))
        if extra:
            entry = {**entry, **extra}
        out.append(entry)
    return out


def _entries(doc: Any, *keys: str) -> list[dict]:
    """Pull a list of records out of a document, whatever shape it uses."""
    if isinstance(doc, list):
        return doc
    if not isinstance(doc, dict):
        return []
    if "fields" in doc and ("words" in doc or "rows" in doc):
        return _expand_columnar(doc)
    for k in keys:
        v = doc.get(k)
        if isinstance(v, list):
            return v
    return []


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


# ==========================================================================
# Per-kind loaders
# ==========================================================================

def load_vocab(lang: str, doc: Any, source: str, report: LoadReport,
               conn: sqlite3.Connection) -> int:
    spec = registry.get(lang)
    try:
        translit = spec.transliteration
        pron = spec.pronunciation
    except ModuleNotFoundError:
        translit = pron = None

    rows = []
    for e in _entries(doc, "words", "vocab", "entries"):
        term = (e.get("term") or e.get("target") or e.get("word")
                or e.get("korean") or "").strip()
        if not term:
            report.warnings.append(f"{source}: entry {e.get('id')!r} has no term; skipped")
            continue
        if not e.get("meaning"):
            report.warnings.append(f"{source}: {e.get('id')!r} ({term}) has no meaning; skipped")
            continue

        # Derived where it *can* be derived, and recomputed on every reload so
        # a rule fix cannot leave stale strings behind. Where it cannot be —
        # Mandarin pinyin needs a dictionary, because 行 is xíng or háng
        # depending on the word — the file's authored value is used instead.
        # Authored always wins, so a language that can compute it never has to
        # write it out, and one that cannot is never silently blank.
        pronunciation = ""
        transliteration = ""
        if pron is not None:
            try:
                pronunciation = pron.pronounce(term).get("spoken", "")
            except Exception:                       # a bad term must not stop the load
                pronunciation = ""
        if translit is not None:
            try:
                transliteration = translit.transliterate(term)
            except Exception:
                transliteration = ""

        rows.append({
            "id": e["id"], "language": lang, "term": term,
            "meaning": e.get("meaning", ""), "pos": e.get("pos", ""),
            "topic": e.get("topic", ""), "level": e.get("level", ""),
            "band": e.get("band", "beginner"),
            "frequency_rank": e.get("freq") or e.get("frequency_rank"),
            "reading": e.get("reading", ""),
            "transliteration": (e.get("transliteration") or e.get("pinyin")
                                or transliteration),
            "pronunciation": e.get("pronunciation") or pronunciation,
            "example_native": e.get("example_ko") or e.get("example_native", ""),
            "example_en": e.get("example_en", ""),
            "counter": e.get("counter", ""), "irregular": e.get("irregular", ""),
            "register": e.get("register", "neutral"),
            "synonyms": _json(e.get("synonyms")), "antonyms": _json(e.get("antonyms")),
            "related": _json(e.get("related")), "collocations": _json(e.get("collocations")),
            "notes": e.get("note") or e.get("notes", ""),
            "audio_id": e.get("audio_id", ""),
            "extra": _json({k: v for k, v in e.items() if k.startswith("note_")}),
        })
    _bulk_upsert(conn, "vocab", rows)
    return len(rows)


def load_grammar(lang: str, doc: Any, source: str, report: LoadReport,
                 conn: sqlite3.Connection) -> int:
    rows = []
    for e in _entries(doc, "points", "grammar"):
        if not e.get("id"):
            report.warnings.append(f"{source}: a grammar point has no id; skipped")
            continue
        rows.append({
            "id": e["id"], "language": lang, "name": e.get("name", ""),
            "name_native": e.get("name_native", ""),
            "level": e.get("level") or (doc.get("level") if isinstance(doc, dict) else ""),
            "category": e.get("category", ""), "ordinal": e.get("ordinal", 0),
            "meaning": e.get("meaning", ""), "structure": e.get("structure", ""),
            "formality": e.get("formality", ""), "attaches_to": e.get("attaches_to", ""),
            "simple": e.get("simple", ""), "technical": e.get("technical", ""),
            "examples": _json(e.get("examples")), "mistakes": _json(e.get("mistakes")),
            "similar": _json(e.get("similar")), "contrast": _json(e.get("contrast")),
            "tags": _json(e.get("tags")),
        })
    _bulk_upsert(conn, "grammar", rows)
    return len(rows)


def load_lessons(lang: str, doc: Any, source: str, report: LoadReport,
                 conn: sqlite3.Connection) -> int:
    unit = doc.get("unit", {}) if isinstance(doc, dict) else {}
    rows, exercises = [], []
    for e in _entries(doc, "lessons"):
        if not e.get("id"):
            report.warnings.append(f"{source}: a lesson has no id; skipped")
            continue
        rows.append({
            "id": e["id"], "language": lang,
            "level": e.get("level") or unit.get("level", ""),
            "unit": e.get("unit") or unit.get("id", ""),
            "ordinal": e.get("ordinal", 0),
            "title": e.get("title", ""), "title_native": e.get("title_ko") or e.get("title_native", ""),
            "summary": e.get("summary", ""),
            "objectives": _json(e.get("objectives")),
            "prerequisites": _json(e.get("prerequisites")),
            "vocabulary": _json(e.get("vocabulary")),
            "grammar": _json(e.get("grammar")),
            "est_minutes": e.get("est_minutes", 10),
            "tags": _json(e.get("tags")),
            # The whole lesson body is stored verbatim. The runtime reads the
            # steps straight from here, so a new step type needs no migration.
            "body": _json({k: v for k, v in e.items()
                           if k in ("steps", "introduces", "is_gate",
                                    "difficulty_warning", "importance")}),
            "source_file": source,
        })
        exercises.extend(_lesson_exercises(lang, e))
    _bulk_upsert(conn, "lesson", rows)
    _bulk_upsert(conn, "exercise", exercises)
    if exercises:
        report.add(lang, "exercises", len(exercises))
    return len(rows)


def _lesson_exercises(lang: str, lesson: dict) -> list[dict]:
    """Register each generator spec as an exercise row.

    The rows are *specs*, not materialised questions. Expanding them at
    request time means a jamo drill draws fresh items every session instead of
    the learner memorising question 4's position.
    """
    out = []
    for i, step in enumerate(lesson.get("steps", [])):
        gen = step.get("generator")
        if not gen and step.get("type") not in ("pronounce", "read_aloud", "word_read"):
            continue
        kind = (gen or {}).get("type") or step.get("type", "")
        out.append({
            "id": f"{lesson['id']}-s{i:02d}",
            "language": lang, "lesson_id": lesson["id"],
            "step": step.get("step", "practice"),
            "kind": kind,
            "skill": step.get("skill") or exercises.skill_for(lang, kind),
            "level": lesson.get("level", ""),
            "difficulty": 0.5,
            "prompt": step.get("instruction") or step.get("heading", ""),
            "prompt_native": "",
            "data": _json(gen or {k: v for k, v in step.items() if k != "step"}),
            "answer": _json({}),
            "explain": _json({"note": step.get("note", "")}),
            "tags": _json(lesson.get("tags")),
        })
    return out


def load_script_units(lang: str, doc: Any, source: str, report: LoadReport,
                      conn: sqlite3.Connection) -> int:
    """Jamo, kana, characters — whatever this language's writing system teaches.

    The units come from the language's own writing engine rather than being
    parsed here, because only that engine knows what an "atom" is for its
    script. Korean returns jamo; Japanese will return mora; Mandarin will
    return characters by frequency band.
    """
    spec = registry.get(lang)
    try:
        module = importlib.import_module(spec.writing_module) if spec.writing_module else None
    except ModuleNotFoundError:
        module = None
    if module is None:
        report.warnings.append(f"{lang}: no writing engine yet; script units skipped")
        return 0

    # A language may have several scripts. Japanese registers three and they
    # are learned separately, so all of them must be loaded — reading only the
    # default ENGINE would silently leave katakana and kanji at zero units and
    # make the progress bars lie.
    engines = getattr(module, "BY_ID", None) or {}
    if not engines:
        default = getattr(module, "ENGINE", None)
        if default is None:
            return 0
        engines = {getattr(default, "id", ""): default}

    rows = []
    for ws_id, engine in engines.items():
        try:
            units = engine.units()
        except Exception as e:
            report.warnings.append(f"{lang}/{ws_id}: could not load units: {e}")
            continue
        if not units and not engine.is_closed_inventory:
            # An open inventory with no authored content yet is expected, not
            # an error: nobody has written the kanji frequency bands.
            report.warnings.append(
                f"{lang}/{ws_id}: no content authored yet (open inventory)")
        for u in units:
            rows.append({
                "id": u["id"], "language": lang, "writing_system": ws_id,
                "unit": u["unit"], "kind": u.get("kind", ""),
                "name": u.get("name", ""),
                "transliteration": u.get("romanization") or u.get("transliteration", ""),
                "teaching_stage": u.get("teaching_stage", 99),
                "data": _json(u),
            })
    _bulk_upsert(conn, "script_unit", rows)
    return len(rows)


def load_sentences(lang: str, doc: Any, source: str, report: LoadReport,
                   conn: sqlite3.Connection) -> int:
    """Real sentences, with their pronunciation derived the same way vocab is.

    A sentence carries the ids of the words and grammar points it uses, so a
    drill can be built around a point the learner has just met — which is what
    turns "learn this word" into "use this word".
    """
    spec = registry.get(lang)
    try:
        translit = spec.transliteration
        pron = spec.pronunciation
    except ModuleNotFoundError:
        translit = pron = None

    rows = []
    for e in _entries(doc, "sentences", "items"):
        target = (e.get("target") or e.get("term") or "").strip()
        if not e.get("id") or not target:
            report.warnings.append(f"{source}: a sentence has no id or text; skipped")
            continue

        pronunciation = transliteration = ""
        if pron is not None:
            try:
                pronunciation = pron.pronounce(target).get("spoken", "")
            except Exception:
                pronunciation = ""
        if translit is not None:
            try:
                transliteration = translit.transliterate(target)
            except Exception:
                transliteration = ""

        rows.append({
            "id": e["id"], "language": lang, "target": target,
            "english": e.get("english", ""),
            "transliteration": e.get("transliteration") or transliteration,
            "pronunciation": e.get("pronunciation") or pronunciation,
            "level": e.get("level") or (doc.get("level", "") if isinstance(doc, dict) else ""),
            "topic": e.get("topic", ""),
            "register": e.get("register", "neutral"),
            "vocab_ids": _json(e.get("vocab")),
            "grammar_ids": _json(e.get("grammar")),
            "chunks": _json(e.get("chunks")),
            "blanks": _json(e.get("blanks")),
            "transforms": _json(e.get("transforms")),
            "note": e.get("note", ""),
            "audio_id": e.get("audio_id", ""),
        })
    _bulk_upsert(conn, "sentence", rows)
    return len(rows)


def load_culture(lang: str, doc: Any, source: str, report: LoadReport,
                 conn: sqlite3.Connection) -> int:
    rows = [{
        "id": e["id"], "language": lang, "title": e.get("title", ""),
        "category": e.get("category", ""), "level": e.get("level", ""),
        "body": e.get("body", ""), "examples": _json(e.get("examples")),
        "warnings": _json(e.get("warnings")),
    } for e in _entries(doc, "notes", "culture") if e.get("id")]
    _bulk_upsert(conn, "culture_note", rows)
    return len(rows)


def load_slang(lang: str, doc: Any, source: str, report: LoadReport,
               conn: sqlite3.Connection) -> int:
    rows = [{
        "id": e["id"], "language": lang,
        "term": e.get("term") or e.get("target") or e.get("korean", ""),
        "literal": e.get("literal", ""), "actual": e.get("actual", ""),
        "tone": e.get("tone", ""), "context": e.get("context", ""),
        "who_can_use": e.get("who_can_use", ""), "avoid_when": e.get("avoid_when", ""),
        "register": e.get("register", "casual"), "example": e.get("example", ""),
    } for e in _entries(doc, "entries", "slang") if e.get("id")]
    _bulk_upsert(conn, "slang", rows)
    return len(rows)


def load_scenarios(lang: str, doc: Any, source: str, report: LoadReport,
                   conn: sqlite3.Connection) -> int:
    rows = [{
        "id": e["id"], "language": lang, "title": e.get("title", ""),
        "title_native": e.get("title_ko") or e.get("title_native", ""),
        "level": e.get("level", ""), "setting": e.get("setting", ""),
        "roles": _json(e.get("roles")), "script": _json(e.get("script")),
        "vocabulary": _json(e.get("vocabulary")), "goals": _json(e.get("goals")),
        "culture": e.get("culture", ""),
    } for e in _entries(doc, "scenarios", "conversations") if e.get("id")]
    _bulk_upsert(conn, "scenario", rows)
    return len(rows)


#: Directory name -> loader. This is the whole dispatch table; a new content
#: kind is a new directory plus one function.
LOADERS: dict[str, Callable] = {
    "vocab": load_vocab,
    "grammar": load_grammar,
    "lessons": load_lessons,
    "sentences": load_sentences,
    "culture": load_culture,
    "slang": load_slang,
    "conversations": load_scenarios,
}

#: Directories holding writing-system reference data. Their teachable units
#: come from the language's writing engine, not from parsing the files.
SCRIPT_DIRS = {"hangul", "writing", "kana", "hanzi", "script"}


def _bulk_upsert(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0])
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "id")
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT(id) DO UPDATE SET {updates}")
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])


# ==========================================================================
# Search index
# ==========================================================================

def rebuild_search_index(conn: sqlite3.Connection, language: Optional[str] = None) -> int:
    """Rebuild the FTS index over everything currently in the content cache."""
    if language:
        conn.execute("DELETE FROM search_index WHERE language = ?", (language,))
    else:
        conn.execute("DELETE FROM search_index")

    where = "WHERE language = ?" if language else ""
    args = (language,) if language else ()
    n = 0

    for sql, kind in (
        (f"SELECT id, language, term, meaning, "
         f"       COALESCE(example_native,'')||' '||COALESCE(topic,'')||' '||COALESCE(pos,'') "
         f"FROM vocab {where}", "vocab"),
        (f"SELECT id, language, name_native, name||' '||meaning, "
         f"       COALESCE(structure,'')||' '||COALESCE(simple,'') "
         f"FROM grammar {where}", "grammar"),
        (f"SELECT id, language, title_native, title||' '||summary, "
         f"       COALESCE(level,'') FROM lesson {where}", "lesson"),
        (f"SELECT id, language, unit, name, COALESCE(transliteration,'') "
         f"FROM script_unit {where}", "script_unit"),
        (f"SELECT id, language, term, actual, "
         f"       COALESCE(literal,'')||' '||COALESCE(context,'') FROM slang {where}", "slang"),
        (f"SELECT id, language, target, english, COALESCE(topic,'') "
         f"FROM sentence {where}", "sentence"),
    ):
        try:
            rows = conn.execute(sql, args).fetchall()
        except sqlite3.OperationalError:
            continue
        conn.executemany(
            "INSERT INTO search_index(ref, kind, language, term, english, extra) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(r[0], kind, r[1], r[2] or "", r[3] or "", r[4] or "") for r in rows],
        )
        n += len(rows)
    conn.commit()
    return n


# ==========================================================================
# Entry points
# ==========================================================================

def load_language(
    lang: str,
    conn: Optional[sqlite3.Connection] = None,
    report: Optional[LoadReport] = None,
    base: Optional[Path] = None,
) -> LoadReport:
    """Load everything under `content/<lang>/`."""
    conn = conn or get_connection()
    report = report or LoadReport()
    spec = registry.try_get(lang)
    if spec is None:
        report.errors.append(f"{lang}: not a registered language")
        return report

    root = Path(base or CONTENT_DIR) / (spec.content_dir or lang)
    if not root.exists():
        report.skipped_languages.append(lang)
        return report

    # Before reading any lesson: import this language's generators, so that
    # `skill_for` can classify its exercise kinds. Without this, a Mandarin
    # tone drill loaded on a cold start would be filed under "grammar" and
    # quietly corrupt the four-skill tracker.
    exercises.load_language_generators(lang)

    # Script units first: lessons reference them.
    if any((root / d).exists() for d in SCRIPT_DIRS):
        try:
            n = load_script_units(lang, None, str(root), report, conn)
            if n:
                report.add(lang, "script_units", n)
        except Exception as e:
            report.errors.append(f"{lang}: script units failed: {e}")

    for sub, loader in LOADERS.items():
        d = root / sub
        if not d.exists():
            continue
        for path in sorted(d.glob("*.json")):
            rel = str(path.relative_to(Path(base or CONTENT_DIR)))
            try:
                doc = _read(path)
            except json.JSONDecodeError as e:
                report.errors.append(f"{rel}: invalid JSON — {e}")
                continue

            declared = doc.get("language") if isinstance(doc, dict) else None
            if declared and declared != lang:
                report.errors.append(
                    f"{rel}: declares language {declared!r} but sits under {lang}/"
                )
                continue

            try:
                n = loader(lang, doc, rel, report, conn)
            except Exception as e:
                report.errors.append(f"{rel}: {type(e).__name__}: {e}")
                continue
            report.files_read.append(rel)
            if n:
                report.add(lang, sub, n)

    conn.commit()
    return report


def load_all(
    conn: Optional[sqlite3.Connection] = None,
    base: Optional[Path] = None,
    rebuild_index: bool = True,
) -> LoadReport:
    """Load every registered language that has content on disk."""
    conn = conn or get_connection()
    report = LoadReport()
    for spec in registry.all_languages():
        load_language(spec.code, conn, report, base)
    if rebuild_index and report.ok:
        rebuild_search_index(conn)
    return report


def clear_language(lang: str, conn: Optional[sqlite3.Connection] = None) -> None:
    """Drop one language's cached content. Learner progress is untouched."""
    conn = conn or get_connection()
    for table in ("lesson", "vocab", "grammar", "exercise", "scenario",
                  "culture_note", "slang", "script_unit", "sentence",
                  "search_index"):
        try:
            conn.execute(f"DELETE FROM {table} WHERE language = ?", (lang,))
        except sqlite3.OperationalError:
            pass
    conn.commit()
