"""
Data access.

One place for the SQL, so the routers stay readable and — more importantly —
so the language filter cannot be forgotten. Every function that touches
learner data takes a `language` and applies it. That is the whole defence
against progress leaking between languages, and it lives here rather than
being repeated at twenty call sites.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from .config import DEFAULT_SETTINGS, load_settings
from .db import get_connection, now_iso, query, query_one
from .engines import srs
from .engines.adaptive import Attempt
from .languages import registry

JSON_COLUMNS = {
    "lesson": ("objectives", "prerequisites", "vocabulary", "grammar", "tags", "body"),
    "vocab": ("synonyms", "antonyms", "related", "collocations", "extra"),
    "grammar": ("examples", "mistakes", "similar", "contrast", "tags"),
    "exercise": ("data", "answer", "explain", "tags"),
    "script_unit": ("data",),
    "scenario": ("roles", "script", "vocabulary", "goals"),
    "culture_note": ("examples", "warnings"),
}


def _decode(table: str, row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    out = dict(row)
    for col in JSON_COLUMNS.get(table, ()):
        raw = out.get(col)
        if isinstance(raw, str):
            try:
                out[col] = json.loads(raw)
            except (TypeError, ValueError):
                pass
    return out


def _decode_all(table: str, rows: list[dict]) -> list[dict]:
    return [_decode(table, r) for r in rows]


# ==========================================================================
# Learner
# ==========================================================================

def get_or_create_learner(conn: Optional[sqlite3.Connection] = None) -> dict:
    """Single-profile by default. The schema supports several; the UI does not
    expose them yet, so this returns the one profile and makes it if absent."""
    conn = conn or get_connection()
    row = query_one("SELECT * FROM learner ORDER BY id LIMIT 1", conn=conn)
    if row is None:
        conn.execute(
            "INSERT INTO learner(name, created_at, active_language) VALUES ('', ?, ?)",
            (now_iso(), registry.DEFAULT_LANGUAGE),
        )
        conn.execute(
            "INSERT INTO streak(learner_id, current, longest) "
            "SELECT id, 0, 0 FROM learner ORDER BY id LIMIT 1")
        conn.commit()
        row = query_one("SELECT * FROM learner ORDER BY id LIMIT 1", conn=conn)
    row["settings"] = load_settings(row.get("settings_json"))
    return row


def update_learner(learner_id: int, conn: Optional[sqlite3.Connection] = None, **fields) -> dict:
    conn = conn or get_connection()
    allowed = {"name", "active_language", "onboarded", "settings_json"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if sets:
        clause = ", ".join(f"{k} = ?" for k in sets)
        conn.execute(f"UPDATE learner SET {clause} WHERE id = ?",
                     (*sets.values(), learner_id))
        conn.commit()
    return get_or_create_learner(conn)


def save_settings(learner_id: int, patch: dict,
                  conn: Optional[sqlite3.Connection] = None) -> dict:
    conn = conn or get_connection()
    row = query_one("SELECT settings_json FROM learner WHERE id = ?", (learner_id,), conn)
    current = load_settings(row["settings_json"] if row else None)
    for k, v in (patch or {}).items():
        if k in DEFAULT_SETTINGS:
            current[k] = v
    conn.execute("UPDATE learner SET settings_json = ? WHERE id = ?",
                 (json.dumps(current, ensure_ascii=False), learner_id))
    conn.commit()
    return current


def get_learner_language(learner_id: int, language: str,
                         conn: Optional[sqlite3.Connection] = None) -> dict:
    conn = conn or get_connection()
    row = query_one(
        "SELECT * FROM learner_language WHERE learner_id = ? AND language = ?",
        (learner_id, language), conn)
    if row is None:
        conn.execute(
            "INSERT INTO learner_language(learner_id, language, started_at) VALUES (?, ?, ?)",
            (learner_id, language, now_iso()))
        conn.commit()
        row = query_one(
            "SELECT * FROM learner_language WHERE learner_id = ? AND language = ?",
            (learner_id, language), conn)
    return row


def update_learner_language(learner_id: int, language: str,
                            conn: Optional[sqlite3.Connection] = None, **fields) -> dict:
    conn = conn or get_connection()
    get_learner_language(learner_id, language, conn)
    allowed = {"level", "start_level", "goal", "xp", "script_mastery",
               "last_studied", "is_active", "settings_json"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if sets:
        clause = ", ".join(f"{k} = ?" for k in sets)
        conn.execute(
            f"UPDATE learner_language SET {clause} WHERE learner_id = ? AND language = ?",
            (*sets.values(), learner_id, language))
        conn.commit()
    return get_learner_language(learner_id, language, conn)


def add_xp(learner_id: int, language: str, amount: int,
           conn: Optional[sqlite3.Connection] = None) -> int:
    conn = conn or get_connection()
    get_learner_language(learner_id, language, conn)
    conn.execute(
        "UPDATE learner_language SET xp = xp + ?, last_studied = ? "
        "WHERE learner_id = ? AND language = ?",
        (amount, now_iso(), learner_id, language))
    conn.commit()
    row = query_one("SELECT xp FROM learner_language WHERE learner_id = ? AND language = ?",
                    (learner_id, language), conn)
    return row["xp"] if row else 0


def learner_languages(learner_id: int, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    """Every language this learner has touched, with progress. Feeds the
    'My Languages' panel on the dashboard."""
    conn = conn or get_connection()
    rows = query("SELECT * FROM learner_language WHERE learner_id = ? ORDER BY language",
                 (learner_id,), conn)
    out = []
    for r in rows:
        spec = registry.try_get(r["language"])
        if spec is None:
            continue
        counts = srs_counts(learner_id, r["language"], conn)
        out.append({
            **r,
            "name": spec.name, "native_name": spec.native_name, "flag": spec.flag,
            "status": spec.status,
            "known_items": counts["known"], "due_now": counts["due_now"],
        })
    return out


# ==========================================================================
# Streak
# ==========================================================================

def touch_streak(learner_id: int, conn: Optional[sqlite3.Connection] = None,
                 today: Optional[date] = None) -> dict:
    """Record that the learner studied today, in any language."""
    conn = conn or get_connection()
    today = today or datetime.now(timezone.utc).date()
    row = query_one("SELECT * FROM streak WHERE learner_id = ?", (learner_id,), conn)
    if row is None:
        conn.execute("INSERT INTO streak(learner_id, current, longest, last_active_date) "
                     "VALUES (?, 1, 1, ?)", (learner_id, today.isoformat()))
        conn.commit()
        return {"current": 1, "longest": 1, "last_active_date": today.isoformat()}

    last = row["last_active_date"]
    if last == today.isoformat():
        return row
    current = 1
    if last:
        try:
            gap = (today - date.fromisoformat(last)).days
            current = row["current"] + 1 if gap == 1 else 1
        except ValueError:
            current = 1
    longest = max(row["longest"], current)
    conn.execute("UPDATE streak SET current = ?, longest = ?, last_active_date = ? "
                 "WHERE learner_id = ?", (current, longest, today.isoformat(), learner_id))
    conn.commit()
    return {"current": current, "longest": longest, "last_active_date": today.isoformat()}


def get_streak(learner_id: int, conn: Optional[sqlite3.Connection] = None) -> dict:
    conn = conn or get_connection()
    return query_one("SELECT * FROM streak WHERE learner_id = ?", (learner_id,), conn) or {
        "current": 0, "longest": 0, "last_active_date": None}


# ==========================================================================
# Content
# ==========================================================================

def lessons(language: str, level: Optional[str] = None, unit: Optional[str] = None,
            conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    sql = "SELECT * FROM lesson WHERE language = ?"
    args: list = [language]
    if level:
        sql += " AND level = ?"; args.append(level)
    if unit:
        sql += " AND unit = ?"; args.append(unit)
    sql += " ORDER BY unit, ordinal"
    return _decode_all("lesson", query(sql, args, conn))


def lesson(lesson_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    return _decode("lesson", query_one("SELECT * FROM lesson WHERE id = ?", (lesson_id,), conn))


def vocab(language: str, topic: Optional[str] = None, level: Optional[str] = None,
          limit: int = 200, offset: int = 0,
          conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    sql = "SELECT * FROM vocab WHERE language = ?"
    args: list = [language]
    if topic:
        sql += " AND topic = ?"; args.append(topic)
    if level:
        sql += " AND level = ?"; args.append(level)
    sql += " ORDER BY COALESCE(frequency_rank, 99999), term LIMIT ? OFFSET ?"
    args += [limit, offset]
    return _decode_all("vocab", query(sql, args, conn))


def vocab_one(vocab_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    return _decode("vocab", query_one("SELECT * FROM vocab WHERE id = ?", (vocab_id,), conn))


def vocab_topics(language: str, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    return query(
        "SELECT topic, COUNT(*) AS n FROM vocab WHERE language = ? AND topic != '' "
        "GROUP BY topic ORDER BY n DESC", (language,), conn)


def grammar(language: str, level: Optional[str] = None,
            conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    sql = "SELECT * FROM grammar WHERE language = ?"
    args: list = [language]
    if level:
        sql += " AND level = ?"; args.append(level)
    sql += " ORDER BY level, ordinal"
    return _decode_all("grammar", query(sql, args, conn))


def grammar_one(grammar_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    return _decode("grammar", query_one("SELECT * FROM grammar WHERE id = ?", (grammar_id,), conn))


def script_units(language: str, writing_system: Optional[str] = None,
                 conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    sql = "SELECT * FROM script_unit WHERE language = ?"
    args: list = [language]
    if writing_system:
        sql += " AND writing_system = ?"; args.append(writing_system)
    sql += " ORDER BY teaching_stage, id"
    return _decode_all("script_unit", query(sql, args, conn))


def exercises_for(lesson_id: str, step: Optional[str] = None,
                  conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    sql = "SELECT * FROM exercise WHERE lesson_id = ?"
    args: list = [lesson_id]
    if step:
        sql += " AND step = ?"; args.append(step)
    sql += " ORDER BY id"
    return _decode_all("exercise", query(sql, args, conn))


def search(language: str, q: str, limit: int = 30,
           conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    """Full-text across vocab, grammar, lessons, script units and slang."""
    conn = conn or get_connection()
    if not q.strip():
        return []
    # FTS5 treats several characters as operators; quote the term to search literally.
    safe = '"' + q.replace('"', '""') + '"'
    try:
        rows = query(
            "SELECT ref, kind, language, term, english FROM search_index "
            "WHERE search_index MATCH ? AND language = ? LIMIT ?",
            (safe, language, limit), conn)
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        like = f"%{q}%"
        rows = query(
            "SELECT ref, kind, language, term, english FROM search_index "
            "WHERE language = ? AND (term LIKE ? OR english LIKE ?) LIMIT ?",
            (language, like, like, limit), conn)
    return rows


# ==========================================================================
# SRS
# ==========================================================================

def _row_to_card(row: dict) -> srs.Card:
    def dt(v):
        return datetime.fromisoformat(v) if v else None
    return srs.Card(
        id=row["id"], item_type=row["item_type"], item_id=row["item_id"],
        state=row["state"], ease=row["ease"], interval_days=row["interval_days"],
        repetitions=row["repetitions"], lapses=row["lapses"], streak=row["streak"],
        step_index=row["step_index"], due_at=dt(row["due_at"]),
        last_reviewed_at=dt(row["last_reviewed_at"]), introduced_at=dt(row["introduced_at"]),
        total_reviews=row["total_reviews"], total_correct=row["total_correct"],
    )


def cards(learner_id: int, language: str, conn: Optional[sqlite3.Connection] = None,
          item_type: Optional[str] = None) -> list[srs.Card]:
    sql = "SELECT * FROM srs_card WHERE learner_id = ? AND language = ?"
    args: list = [learner_id, language]
    if item_type:
        sql += " AND item_type = ?"; args.append(item_type)
    return [_row_to_card(r) for r in query(sql, args, conn)]


def ensure_card(learner_id: int, language: str, item_type: str, item_id: str,
                conn: Optional[sqlite3.Connection] = None) -> srs.Card:
    conn = conn or get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO srs_card(learner_id, language, item_type, item_id, state) "
        "VALUES (?, ?, ?, ?, 'new')", (learner_id, language, item_type, item_id))
    conn.commit()
    row = query_one(
        "SELECT * FROM srs_card WHERE learner_id = ? AND language = ? "
        "AND item_type = ? AND item_id = ?",
        (learner_id, language, item_type, item_id), conn)
    return _row_to_card(row)


def save_card(learner_id: int, language: str, card: srs.Card,
              conn: Optional[sqlite3.Connection] = None) -> None:
    conn = conn or get_connection()
    def iso(v):
        return v.isoformat() if v else None
    conn.execute("""
        INSERT INTO srs_card(learner_id, language, item_type, item_id, state, ease,
            interval_days, repetitions, lapses, streak, step_index, due_at,
            last_reviewed_at, introduced_at, total_reviews, total_correct)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(learner_id, language, item_type, item_id) DO UPDATE SET
            state=excluded.state, ease=excluded.ease, interval_days=excluded.interval_days,
            repetitions=excluded.repetitions, lapses=excluded.lapses, streak=excluded.streak,
            step_index=excluded.step_index, due_at=excluded.due_at,
            last_reviewed_at=excluded.last_reviewed_at, introduced_at=excluded.introduced_at,
            total_reviews=excluded.total_reviews, total_correct=excluded.total_correct
    """, (learner_id, language, card.item_type, card.item_id, card.state, card.ease,
          card.interval_days, card.repetitions, card.lapses, card.streak,
          card.step_index, iso(card.due_at), iso(card.last_reviewed_at),
          iso(card.introduced_at), card.total_reviews, card.total_correct))
    conn.commit()


def srs_counts(learner_id: int, language: str,
               conn: Optional[sqlite3.Connection] = None) -> dict:
    return srs.queue_summary(cards(learner_id, language, conn))


def introduced_today(learner_id: int, language: str,
                     conn: Optional[sqlite3.Connection] = None) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                               microsecond=0).isoformat()
    row = query_one(
        "SELECT COUNT(*) AS n FROM srs_card WHERE learner_id = ? AND language = ? "
        "AND introduced_at >= ?", (learner_id, language, start), conn)
    return row["n"] if row else 0


# ==========================================================================
# Attempts, mistakes, sessions
# ==========================================================================

def record_attempt(learner_id: int, language: str, a: Attempt,
                   conn: Optional[sqlite3.Connection] = None,
                   exercise_id: str = "") -> None:
    conn = conn or get_connection()
    conn.execute("""
        INSERT INTO attempt(learner_id, language, at, skill, correct, item_type,
            item_id, exercise_id, lesson_id, topic, level, expected, given, response_ms)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (learner_id, language, (a.at or datetime.now(timezone.utc)).isoformat(),
          a.skill, int(a.correct), a.item_type, a.item_id, exercise_id,
          a.lesson_id, a.topic, a.level, a.expected, a.given, a.response_ms))
    conn.commit()


def attempts(learner_id: int, language: str, days: int = 120,
             conn: Optional[sqlite3.Connection] = None) -> list[Attempt]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = query(
        "SELECT * FROM attempt WHERE learner_id = ? AND language = ? AND at >= ? "
        "ORDER BY at", (learner_id, language, since), conn)
    out = []
    for r in rows:
        try:
            at = datetime.fromisoformat(r["at"])
        except (TypeError, ValueError):
            at = datetime.now(timezone.utc)
        out.append(Attempt(
            skill=r["skill"], correct=bool(r["correct"]), language=r["language"],
            item_type=r["item_type"], item_id=r["item_id"], expected=r["expected"],
            given=r["given"], lesson_id=r["lesson_id"], topic=r["topic"],
            level=r["level"], response_ms=r["response_ms"], at=at))
    return out


def record_mistake(learner_id: int, language: str, category: str,
                   expected: str, given: str, explanation: str = "",
                   confusion_id: str = "", item_type: str = "", item_id: str = "",
                   lesson_id: str = "", conn: Optional[sqlite3.Connection] = None) -> None:
    """Store a mistake, merging repeats of the same one."""
    conn = conn or get_connection()
    existing = query_one(
        "SELECT id, times_seen FROM mistake WHERE learner_id = ? AND language = ? "
        "AND expected = ? AND given = ? AND item_id = ? AND resolved = 0",
        (learner_id, language, expected, given, item_id), conn)
    if existing:
        conn.execute("UPDATE mistake SET times_seen = ?, at = ? WHERE id = ?",
                     (existing["times_seen"] + 1, now_iso(), existing["id"]))
    else:
        conn.execute("""
            INSERT INTO mistake(learner_id, language, at, category, item_type, item_id,
                expected, given, explanation, confusion_id, lesson_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (learner_id, language, now_iso(), category, item_type, item_id,
              expected, given, explanation, confusion_id, lesson_id))
    conn.commit()


def mistakes(learner_id: int, language: str, unresolved_only: bool = True,
             limit: int = 100, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    sql = "SELECT * FROM mistake WHERE learner_id = ? AND language = ?"
    args: list = [learner_id, language]
    if unresolved_only:
        sql += " AND resolved = 0"
    sql += " ORDER BY times_seen DESC, at DESC LIMIT ?"
    args.append(limit)
    return query(sql, args, conn)


def resolve_mistake(mistake_id: int, conn: Optional[sqlite3.Connection] = None) -> None:
    conn = conn or get_connection()
    conn.execute("UPDATE mistake SET resolved = 1 WHERE id = ?", (mistake_id,))
    conn.commit()


def lesson_progress(learner_id: int, language: str,
                    conn: Optional[sqlite3.Connection] = None) -> dict[str, dict]:
    rows = query(
        "SELECT * FROM lesson_progress WHERE learner_id = ? AND language = ?",
        (learner_id, language), conn)
    return {r["lesson_id"]: r for r in rows}


def set_lesson_progress(learner_id: int, language: str, lesson_id: str,
                        status: str, step: str = "", score: float = 0.0,
                        conn: Optional[sqlite3.Connection] = None) -> None:
    conn = conn or get_connection()
    conn.execute("""
        INSERT INTO lesson_progress(learner_id, language, lesson_id, status, step,
            score, attempts, started_at, completed_at)
        VALUES (?,?,?,?,?,?,1,?,?)
        ON CONFLICT(learner_id, language, lesson_id) DO UPDATE SET
            status=excluded.status, step=excluded.step,
            score=MAX(lesson_progress.score, excluded.score),
            attempts=lesson_progress.attempts + 1,
            completed_at=COALESCE(excluded.completed_at, lesson_progress.completed_at)
    """, (learner_id, language, lesson_id, status, step, score, now_iso(),
          now_iso() if status == "completed" else None))
    conn.commit()


def study_minutes_today(learner_id: int, language: Optional[str] = None,
                        conn: Optional[sqlite3.Connection] = None) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                               microsecond=0).isoformat()
    sql = "SELECT COALESCE(SUM(seconds),0) AS s FROM study_session WHERE learner_id = ? AND started_at >= ?"
    args: list = [learner_id, start]
    if language:
        sql += " AND language = ?"; args.append(language)
    row = query_one(sql, args, conn)
    return int((row["s"] if row else 0) / 60)


def log_session(learner_id: int, language: str, seconds: int, kind: str = "mixed",
                xp: int = 0, cards_reviewed: int = 0, lessons_completed: int = 0,
                conn: Optional[sqlite3.Connection] = None) -> None:
    conn = conn or get_connection()
    conn.execute("""
        INSERT INTO study_session(learner_id, language, started_at, ended_at, seconds,
            kind, xp, cards_reviewed, lessons_completed)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (learner_id, language, now_iso(), now_iso(), seconds, kind, xp,
          cards_reviewed, lessons_completed))
    conn.commit()


def script_mastery(learner_id: int, language: str,
                   conn: Optional[sqlite3.Connection] = None) -> float:
    """Fraction of this language's script units that are genuinely known.

    Counts only cards in review or mastered state — a unit seen once this
    morning is not knowledge, and gating the curriculum on it would let
    someone into A1 material they cannot read.
    """
    conn = conn or get_connection()
    total = query_one("SELECT COUNT(*) AS n FROM script_unit WHERE language = ?",
                      (language,), conn)
    total_n = total["n"] if total else 0
    if not total_n:
        return 0.0
    known = query_one(
        "SELECT COUNT(*) AS n FROM srs_card WHERE learner_id = ? AND language = ? "
        "AND item_type = 'script_unit' AND state IN ('review','mastered')",
        (learner_id, language), conn)
    return round((known["n"] if known else 0) / total_n, 4)


def known_counts(learner_id: int, language: str,
                 conn: Optional[sqlite3.Connection] = None) -> dict:
    rows = query(
        "SELECT item_type, COUNT(*) AS n FROM srs_card WHERE learner_id = ? "
        "AND language = ? AND state IN ('review','mastered') GROUP BY item_type",
        (learner_id, language), conn)
    by_type = {r["item_type"]: r["n"] for r in rows}
    return {
        "vocab": by_type.get("vocab", 0),
        "grammar": by_type.get("grammar", 0),
        "script": by_type.get("script_unit", 0),
        "all": sum(by_type.values()),
    }
