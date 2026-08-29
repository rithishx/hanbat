"""
Versioned schema migrations.

Every migration is a numbered step that knows how to move the database from
version N-1 to version N. The runner takes a backup first, applies the steps
in order inside a transaction, and verifies the result before committing.

SQLite cannot alter a primary key or a UNIQUE constraint in place, so the
migrations that change them follow the standard rebuild dance: create the new
table under a temporary name, copy the rows across with any new columns filled
in, drop the original, rename. This is why each migration is written out longhand
rather than generated — the copy step is where data is silently lost if it is
done carelessly, and it deserves to be readable.

Adding a migration:
    1. Append a function to MIGRATIONS with the next version number.
    2. Bump SCHEMA_VERSION in db.py.
    3. Add a test in tests/test_migrations.py that starts from real data at
       the previous version and asserts the rows survive.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

#: Tables holding learner data. These are irreplaceable and must never be
#: dropped without copying their rows forward first.
LEARNER_TABLES = (
    "learner", "streak", "srs_card", "attempt", "lesson_progress", "mistake",
    "study_session", "daily_goal", "achievement", "conversation", "recording",
)

#: Tables that cache content loaded from JSON files. Safe to drop and rebuild.
CONTENT_TABLES = (
    "lesson", "vocab", "grammar", "exercise", "scenario", "culture_note",
    "slang", "audio_asset",
)


def current_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row else 0


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


def backup(db_path: Path) -> Optional[Path]:
    """Copy the database beside itself before touching it.

    Returns None when there is nothing to back up (a database that has never
    been created). WAL and shm files are copied too — a backup missing the
    write-ahead log can be missing the most recent writes.
    """
    if not db_path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = db_path.with_name(f"{db_path.stem}.backup-{stamp}{db_path.suffix}")
    shutil.copy2(db_path, dest)
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            shutil.copy2(side, Path(str(dest) + suffix))
    return dest


def _row_counts(conn: sqlite3.Connection, tables) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tables:
        try:
            out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.OperationalError:
            out[t] = -1          # table does not exist at this version
    return out


# ==========================================================================
# 001 -> 002 : make everything language-aware
# ==========================================================================

def migrate_002_multilanguage(conn: sqlite3.Connection) -> None:
    """Introduce languages.

    Before this migration the database assumed one language. Every content and
    progress row now carries a `language` column, and the uniqueness rules
    change so that a Korean card and a Japanese card can share an item id
    without colliding.

    Existing rows are stamped 'ko', because that is what they were: the schema
    at version 1 had columns literally named `korean`.
    """
    cur = conn.cursor()

    # -- 1. learner: remember which language is selected -------------------
    _add_column(cur, "learner", "active_language", "TEXT NOT NULL DEFAULT 'ko'")

    # -- 2. per-language learner state ------------------------------------
    # Level, XP and goal are per language: someone can be B1 in Korean and a
    # complete beginner in Mandarin, and showing one number for both would be
    # meaningless. The daily streak stays on `learner` because it measures the
    # habit of studying at all, not progress in any one language.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS learner_language (
            learner_id     INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
            language       TEXT    NOT NULL,
            level          TEXT    NOT NULL DEFAULT '',
            start_level    TEXT    NOT NULL DEFAULT '',
            goal           TEXT    NOT NULL DEFAULT '',
            xp             INTEGER NOT NULL DEFAULT 0,
            script_mastery REAL    NOT NULL DEFAULT 0,
            started_at     TEXT    NOT NULL,
            last_studied   TEXT,
            is_active      INTEGER NOT NULL DEFAULT 1,
            settings_json  TEXT    NOT NULL DEFAULT '{}',
            PRIMARY KEY (learner_id, language)
        )
    """)

    # Carry each existing learner's Korean progress into the new table.
    cur.execute("""
        INSERT OR IGNORE INTO learner_language
            (learner_id, language, level, start_level, goal, xp, started_at)
        SELECT id, 'ko', level, start_level, goal, xp, created_at FROM learner
    """)

    # -- 3. stamp language onto content and progress tables ---------------
    for table in ("lesson", "vocab", "grammar", "exercise", "scenario",
                  "culture_note", "slang", "attempt", "mistake",
                  "study_session", "conversation", "audio_asset", "recording"):
        if _table_exists(cur, table):
            _add_column(cur, table, "language", "TEXT NOT NULL DEFAULT 'ko'")

    # -- 4. neutral column names ------------------------------------------
    # `korean` was fine when there was one language. `term` is what it always
    # meant: the headword in the language being learned.
    for table in ("vocab", "slang"):
        if _table_exists(cur, table) and _has_column(cur, table, "korean"):
            cur.execute(f"ALTER TABLE {table} RENAME COLUMN korean TO term")

    # -- 5. rebuild the tables whose uniqueness rules change --------------
    _rebuild_srs_card(cur)
    _rebuild_lesson_progress(cur)

    # -- 6. rebuild the FTS index -----------------------------------------
    cur.execute("DROP TABLE IF EXISTS search_index")
    cur.execute("""
        CREATE VIRTUAL TABLE search_index USING fts5(
            ref UNINDEXED, kind UNINDEXED, language UNINDEXED,
            term, english, extra,
            tokenize = 'unicode61 remove_diacritics 2'
        )
    """)

    # -- 7. indexes --------------------------------------------------------
    # Each is guarded on the table existing. A database created by an early
    # build may be missing tables that were added later, and a migration that
    # assumes a complete schema will abort partway through on exactly the
    # databases that most need migrating. init_db() runs SCHEMA afterwards to
    # create anything still absent, along with its indexes.
    for table, stmt in (
        ("lesson",   "CREATE INDEX IF NOT EXISTS idx_lesson_lang   ON lesson(language, level, unit, ordinal)"),
        ("vocab",    "CREATE INDEX IF NOT EXISTS idx_vocab_lang    ON vocab(language, term)"),
        ("vocab",    "CREATE INDEX IF NOT EXISTS idx_vocab_topic   ON vocab(language, topic, level)"),
        ("grammar",  "CREATE INDEX IF NOT EXISTS idx_grammar_lang  ON grammar(language, level, ordinal)"),
        ("exercise", "CREATE INDEX IF NOT EXISTS idx_exercise_lang ON exercise(language, skill, level)"),
        ("attempt",  "CREATE INDEX IF NOT EXISTS idx_attempt_lang  ON attempt(learner_id, language, at)"),
        ("mistake",  "CREATE INDEX IF NOT EXISTS idx_mistake_lang  ON mistake(learner_id, language, resolved, at)"),
    ):
        if _table_exists(cur, table):
            cur.execute(stmt)


def _rebuild_srs_card(cur: sqlite3.Cursor) -> None:
    """srs_card gains `language` in its UNIQUE key.

    This is the change that keeps the three schedules genuinely separate. Under
    the old key, a Korean vocab card and a Japanese vocab card that happened to
    share an item id would collide and overwrite each other's review history.
    """
    if not _table_exists(cur, "srs_card"):
        return
    if _has_column(cur, "srs_card", "language"):
        return

    cur.execute("ALTER TABLE srs_card RENAME TO srs_card_old")
    cur.execute("""
        CREATE TABLE srs_card (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            learner_id        INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
            language          TEXT    NOT NULL,
            item_type         TEXT    NOT NULL,
            item_id           TEXT    NOT NULL,
            state             TEXT    NOT NULL DEFAULT 'new',
            ease              REAL    NOT NULL DEFAULT 2.5,
            interval_days     REAL    NOT NULL DEFAULT 0,
            repetitions       INTEGER NOT NULL DEFAULT 0,
            lapses            INTEGER NOT NULL DEFAULT 0,
            streak            INTEGER NOT NULL DEFAULT 0,
            step_index        INTEGER NOT NULL DEFAULT 0,
            due_at            TEXT,
            last_reviewed_at  TEXT,
            introduced_at     TEXT,
            total_reviews     INTEGER NOT NULL DEFAULT 0,
            total_correct     INTEGER NOT NULL DEFAULT 0,
            UNIQUE(learner_id, language, item_type, item_id)
        )
    """)
    cur.execute("""
        INSERT INTO srs_card
            (id, learner_id, language, item_type, item_id, state, ease,
             interval_days, repetitions, lapses, streak, step_index, due_at,
             last_reviewed_at, introduced_at, total_reviews, total_correct)
        SELECT id, learner_id, 'ko', item_type, item_id, state, ease,
               interval_days, repetitions, lapses, streak, step_index, due_at,
               last_reviewed_at, introduced_at, total_reviews, total_correct
        FROM srs_card_old
    """)
    cur.execute("DROP TABLE srs_card_old")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_card_due ON srs_card(learner_id, language, due_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_card_state ON srs_card(learner_id, language, state)")


def _rebuild_lesson_progress(cur: sqlite3.Cursor) -> None:
    """lesson_progress gains `language` in its primary key."""
    if not _table_exists(cur, "lesson_progress"):
        return
    if _has_column(cur, "lesson_progress", "language"):
        return

    cur.execute("ALTER TABLE lesson_progress RENAME TO lesson_progress_old")
    cur.execute("""
        CREATE TABLE lesson_progress (
            learner_id   INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
            language     TEXT    NOT NULL,
            lesson_id    TEXT    NOT NULL,
            status       TEXT    NOT NULL DEFAULT 'not_started',
            step         TEXT    NOT NULL DEFAULT 'warmup',
            score        REAL    NOT NULL DEFAULT 0,
            attempts     INTEGER NOT NULL DEFAULT 0,
            started_at   TEXT,
            completed_at TEXT,
            PRIMARY KEY (learner_id, language, lesson_id)
        )
    """)
    cur.execute("""
        INSERT INTO lesson_progress
            (learner_id, language, lesson_id, status, step, score, attempts,
             started_at, completed_at)
        SELECT learner_id, 'ko', lesson_id, status, step, score, attempts,
               started_at, completed_at
        FROM lesson_progress_old
    """)
    cur.execute("DROP TABLE lesson_progress_old")


# ==========================================================================
# Runner
# ==========================================================================

MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    2: migrate_002_multilanguage,
}


def migrate(
    conn: sqlite3.Connection,
    target: int,
    db_path: Optional[Path] = None,
    verbose: bool = True,
) -> dict:
    """Bring `conn` up to `target`, backing up and verifying along the way."""
    version = current_version(conn)
    if version >= target:
        return {"migrated": False, "from": version, "to": version, "backup": None}

    before = _row_counts(conn, LEARNER_TABLES)
    backup_path = backup(db_path) if db_path else None

    applied: list[int] = []
    try:
        conn.execute("PRAGMA foreign_keys = OFF")   # table rebuilds move rows
        for v in range(version + 1, target + 1):
            step = MIGRATIONS.get(v)
            if step is None:
                continue
            if verbose:
                print(f"  applying migration {v:03d}: {step.__name__}")
            step(conn)
            _set_version(conn, v)
            applied.append(v)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    after = _row_counts(conn, LEARNER_TABLES)
    lost = {
        t: (before[t], after[t])
        for t in LEARNER_TABLES
        if before.get(t, -1) > 0 and after.get(t, -1) < before[t]
    }
    if lost:
        raise MigrationDataLoss(
            f"migration lost learner rows: {lost}. "
            f"The database has been left as-is; restore from {backup_path}."
        )

    return {
        "migrated": True,
        "from": version,
        "to": target,
        "applied": applied,
        "backup": str(backup_path) if backup_path else None,
        "rows_before": before,
        "rows_after": after,
    }


class MigrationDataLoss(RuntimeError):
    """Raised when a migration finishes with fewer learner rows than it started."""


# ==========================================================================
# SQLite introspection helpers
# ==========================================================================

def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _has_column(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    if not _table_exists(cur, table):
        return False
    return any(r[1] == column for r in cur.execute(f"PRAGMA table_info({table})"))


def _add_column(cur: sqlite3.Cursor, table: str, column: str, decl: str) -> None:
    if _table_exists(cur, table) and not _has_column(cur, table, column):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
