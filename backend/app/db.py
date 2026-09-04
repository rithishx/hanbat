"""
SQLite storage.

Plain `sqlite3` rather than an ORM: the schema is the interesting part, an
extra dependency is one more thing that can fail to install on a learner's
machine, and a learner who wants to open their own data in a SQLite browser
should find something legible in there.

The schema separates two kinds of table:

  * **content** tables (lesson, vocab, grammar, exercise) are a *cache* of the
    JSON content files. They can be dropped and rebuilt at any time.
  * **learner** tables (srs_card, attempt, mistake, ...) are the irreplaceable
    ones. Nothing in the reload path touches them, and they are what
    export/import moves.

Every content and progress row carries a `language` column. The uniqueness
rules include it, so the three languages' SRS schedules cannot interfere:
a Korean card and a Japanese card may share an item id and remain separate
rows with separate review histories. Per-language level and XP live in
`learner_language`, because someone can be B1 in Korean and a complete
beginner in Mandarin. The daily streak stays on `learner`, since it measures
the habit of studying at all rather than progress in any one language.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from .config import DB_PATH

SCHEMA_VERSION = 4

_local = threading.local()


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ====================================================================
-- Learner
-- ====================================================================

CREATE TABLE IF NOT EXISTS learner (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL,
    active_language TEXT    NOT NULL DEFAULT 'ko',
    onboarded       INTEGER NOT NULL DEFAULT 0,
    settings_json   TEXT    NOT NULL DEFAULT '{}'
);

-- One row per language this learner studies. Level, XP and goal are per
-- language; mixing them would make both numbers meaningless.
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
);

-- The habit metric: did you study anything today, in any language.
CREATE TABLE IF NOT EXISTS streak (
    learner_id       INTEGER PRIMARY KEY REFERENCES learner(id) ON DELETE CASCADE,
    current          INTEGER NOT NULL DEFAULT 0,
    longest          INTEGER NOT NULL DEFAULT 0,
    last_active_date TEXT,
    freezes          INTEGER NOT NULL DEFAULT 0
);

-- ====================================================================
-- Content cache — rebuilt from files, never authoritative
-- ====================================================================

CREATE TABLE IF NOT EXISTS lesson (
    id             TEXT PRIMARY KEY,
    language       TEXT NOT NULL,
    level          TEXT NOT NULL,
    unit           TEXT NOT NULL DEFAULT '',
    ordinal        INTEGER NOT NULL DEFAULT 0,
    title          TEXT NOT NULL,
    title_native   TEXT NOT NULL DEFAULT '',
    summary        TEXT NOT NULL DEFAULT '',
    objectives     TEXT NOT NULL DEFAULT '[]',
    prerequisites  TEXT NOT NULL DEFAULT '[]',
    vocabulary     TEXT NOT NULL DEFAULT '[]',
    grammar        TEXT NOT NULL DEFAULT '[]',
    est_minutes    INTEGER NOT NULL DEFAULT 10,
    tags           TEXT NOT NULL DEFAULT '[]',
    body           TEXT NOT NULL DEFAULT '{}',
    source_file    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_lesson_lang ON lesson(language, level, unit, ordinal);

CREATE TABLE IF NOT EXISTS vocab (
    id             TEXT PRIMARY KEY,
    language       TEXT NOT NULL,
    term           TEXT NOT NULL,
    meaning        TEXT NOT NULL,
    pos            TEXT NOT NULL DEFAULT '',
    topic          TEXT NOT NULL DEFAULT '',
    level          TEXT NOT NULL DEFAULT '',
    band           TEXT NOT NULL DEFAULT 'beginner',
    frequency_rank INTEGER,
    reading        TEXT NOT NULL DEFAULT '',
    transliteration TEXT NOT NULL DEFAULT '',
    pronunciation  TEXT NOT NULL DEFAULT '',
    example_native TEXT NOT NULL DEFAULT '',
    example_en     TEXT NOT NULL DEFAULT '',
    counter        TEXT NOT NULL DEFAULT '',
    irregular      TEXT NOT NULL DEFAULT '',
    register       TEXT NOT NULL DEFAULT 'neutral',
    synonyms       TEXT NOT NULL DEFAULT '[]',
    antonyms       TEXT NOT NULL DEFAULT '[]',
    related        TEXT NOT NULL DEFAULT '[]',
    collocations   TEXT NOT NULL DEFAULT '[]',
    notes          TEXT NOT NULL DEFAULT '',
    audio_id       TEXT NOT NULL DEFAULT '',
    extra          TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_vocab_lang  ON vocab(language, term);
CREATE INDEX IF NOT EXISTS idx_vocab_topic ON vocab(language, topic, level);
CREATE INDEX IF NOT EXISTS idx_vocab_freq  ON vocab(language, frequency_rank);

CREATE TABLE IF NOT EXISTS grammar (
    id            TEXT PRIMARY KEY,
    language      TEXT NOT NULL,
    name          TEXT NOT NULL,
    name_native   TEXT NOT NULL DEFAULT '',
    level         TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT '',
    ordinal       INTEGER NOT NULL DEFAULT 0,
    meaning       TEXT NOT NULL DEFAULT '',
    structure     TEXT NOT NULL DEFAULT '',
    formality     TEXT NOT NULL DEFAULT '',
    attaches_to   TEXT NOT NULL DEFAULT '',
    simple        TEXT NOT NULL DEFAULT '',
    technical     TEXT NOT NULL DEFAULT '',
    examples      TEXT NOT NULL DEFAULT '[]',
    mistakes      TEXT NOT NULL DEFAULT '[]',
    similar       TEXT NOT NULL DEFAULT '[]',
    contrast      TEXT NOT NULL DEFAULT '[]',
    tags          TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_grammar_lang ON grammar(language, level, ordinal);

CREATE TABLE IF NOT EXISTS exercise (
    id          TEXT PRIMARY KEY,
    language    TEXT NOT NULL,
    lesson_id   TEXT NOT NULL DEFAULT '',
    step        TEXT NOT NULL DEFAULT 'practice',
    kind        TEXT NOT NULL,
    skill       TEXT NOT NULL DEFAULT 'grammar',
    level       TEXT NOT NULL DEFAULT '',
    difficulty  REAL NOT NULL DEFAULT 0.5,
    prompt      TEXT NOT NULL DEFAULT '',
    prompt_native TEXT NOT NULL DEFAULT '',
    data        TEXT NOT NULL DEFAULT '{}',
    answer      TEXT NOT NULL DEFAULT '{}',
    explain     TEXT NOT NULL DEFAULT '{}',
    tags        TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_exercise_lesson ON exercise(language, lesson_id, step);
CREATE INDEX IF NOT EXISTS idx_exercise_skill  ON exercise(language, skill, level);

-- Real sentences, so vocabulary and grammar can be practised in context
-- rather than only as isolated flashcards. A sentence knows which words and
-- which grammar points it uses, which is what lets a drill be built around a
-- point the learner has just met — or just got wrong.
CREATE TABLE IF NOT EXISTS sentence (
    id           TEXT PRIMARY KEY,
    language     TEXT NOT NULL,
    target       TEXT NOT NULL,
    english      TEXT NOT NULL DEFAULT '',
    transliteration TEXT NOT NULL DEFAULT '',
    pronunciation TEXT NOT NULL DEFAULT '',
    level        TEXT NOT NULL DEFAULT '',
    topic        TEXT NOT NULL DEFAULT '',
    register     TEXT NOT NULL DEFAULT 'neutral',
    vocab_ids    TEXT NOT NULL DEFAULT '[]',
    grammar_ids  TEXT NOT NULL DEFAULT '[]',
    chunks       TEXT NOT NULL DEFAULT '[]',
    blanks       TEXT NOT NULL DEFAULT '[]',
    transforms   TEXT NOT NULL DEFAULT '[]',
    note         TEXT NOT NULL DEFAULT '',
    audio_id     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sentence_lang  ON sentence(language, level);
CREATE INDEX IF NOT EXISTS idx_sentence_topic ON sentence(language, topic);

CREATE TABLE IF NOT EXISTS scenario (
    id          TEXT PRIMARY KEY,
    language    TEXT NOT NULL,
    title       TEXT NOT NULL,
    title_native TEXT NOT NULL DEFAULT '',
    level       TEXT NOT NULL DEFAULT '',
    setting     TEXT NOT NULL DEFAULT '',
    roles       TEXT NOT NULL DEFAULT '[]',
    script      TEXT NOT NULL DEFAULT '[]',
    vocabulary  TEXT NOT NULL DEFAULT '[]',
    goals       TEXT NOT NULL DEFAULT '[]',
    culture     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS culture_note (
    id       TEXT PRIMARY KEY,
    language TEXT NOT NULL,
    title    TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    level    TEXT NOT NULL DEFAULT '',
    body     TEXT NOT NULL DEFAULT '',
    examples TEXT NOT NULL DEFAULT '[]',
    warnings TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS slang (
    id          TEXT PRIMARY KEY,
    language    TEXT NOT NULL,
    term        TEXT NOT NULL,
    literal     TEXT NOT NULL DEFAULT '',
    actual      TEXT NOT NULL DEFAULT '',
    tone        TEXT NOT NULL DEFAULT '',
    context     TEXT NOT NULL DEFAULT '',
    who_can_use TEXT NOT NULL DEFAULT '',
    avoid_when  TEXT NOT NULL DEFAULT '',
    register    TEXT NOT NULL DEFAULT 'casual',
    example     TEXT NOT NULL DEFAULT ''
);

-- Writing-system units: jamo, kana, characters. One row per teachable atom,
-- so the SRS can schedule them exactly like vocabulary.
CREATE TABLE IF NOT EXISTS script_unit (
    id             TEXT PRIMARY KEY,
    language       TEXT NOT NULL,
    writing_system TEXT NOT NULL,
    unit           TEXT NOT NULL,
    kind           TEXT NOT NULL DEFAULT '',
    name           TEXT NOT NULL DEFAULT '',
    transliteration TEXT NOT NULL DEFAULT '',
    teaching_stage INTEGER NOT NULL DEFAULT 99,
    data           TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_script_unit ON script_unit(language, writing_system, teaching_stage);

-- ====================================================================
-- Learner progress — the irreplaceable half
-- ====================================================================

CREATE TABLE IF NOT EXISTS srs_card (
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
);
CREATE INDEX IF NOT EXISTS idx_card_due   ON srs_card(learner_id, language, due_at);
CREATE INDEX IF NOT EXISTS idx_card_state ON srs_card(learner_id, language, state);

CREATE TABLE IF NOT EXISTS attempt (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    language    TEXT    NOT NULL,
    at          TEXT    NOT NULL,
    skill       TEXT    NOT NULL,
    correct     INTEGER NOT NULL,
    item_type   TEXT    NOT NULL DEFAULT '',
    item_id     TEXT    NOT NULL DEFAULT '',
    exercise_id TEXT    NOT NULL DEFAULT '',
    lesson_id   TEXT    NOT NULL DEFAULT '',
    topic       TEXT    NOT NULL DEFAULT '',
    level       TEXT    NOT NULL DEFAULT '',
    expected    TEXT    NOT NULL DEFAULT '',
    given       TEXT    NOT NULL DEFAULT '',
    response_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_attempt_learner ON attempt(learner_id, language, at);
CREATE INDEX IF NOT EXISTS idx_attempt_item    ON attempt(learner_id, language, item_type, item_id);

CREATE TABLE IF NOT EXISTS lesson_progress (
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
);

CREATE TABLE IF NOT EXISTS mistake (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id   INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    language     TEXT    NOT NULL,
    at           TEXT    NOT NULL,
    category     TEXT    NOT NULL,
    item_type    TEXT    NOT NULL DEFAULT '',
    item_id      TEXT    NOT NULL DEFAULT '',
    expected     TEXT    NOT NULL DEFAULT '',
    given        TEXT    NOT NULL DEFAULT '',
    explanation  TEXT    NOT NULL DEFAULT '',
    confusion_id TEXT    NOT NULL DEFAULT '',
    lesson_id    TEXT    NOT NULL DEFAULT '',
    resolved     INTEGER NOT NULL DEFAULT 0,
    times_seen   INTEGER NOT NULL DEFAULT 1,
    -- Why the answer was wrong, not which skill it happened in. See
    -- engines/diagnosis.py. `category` is kept as the skill for continuity.
    reason       TEXT    NOT NULL DEFAULT '',
    reason_why   TEXT    NOT NULL DEFAULT '',
    confidence   REAL    NOT NULL DEFAULT 0,
    response_ms  INTEGER NOT NULL DEFAULT 0,
    -- The specific point this mistake is about — one pronunciation rule, one
    -- grammar point, one confusion — as `kind:id`. Empty when the evidence did
    -- not isolate one, which is common and is not papered over. See
    -- engines/remediation.py.
    focus        TEXT    NOT NULL DEFAULT '',
    focus_why    TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_mistake_learner ON mistake(learner_id, language, resolved, at);
CREATE INDEX IF NOT EXISTS idx_mistake_reason  ON mistake(learner_id, language, reason, resolved);
CREATE INDEX IF NOT EXISTS idx_mistake_focus   ON mistake(learner_id, language, focus, resolved);

CREATE TABLE IF NOT EXISTS study_session (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id        INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    language          TEXT    NOT NULL,
    started_at        TEXT    NOT NULL,
    ended_at          TEXT,
    seconds           INTEGER NOT NULL DEFAULT 0,
    kind              TEXT    NOT NULL DEFAULT 'mixed',
    xp                INTEGER NOT NULL DEFAULT 0,
    cards_reviewed    INTEGER NOT NULL DEFAULT 0,
    lessons_completed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_session_learner ON study_session(learner_id, language, started_at);

CREATE TABLE IF NOT EXISTS daily_goal (
    learner_id INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    date       TEXT    NOT NULL,
    target     TEXT    NOT NULL DEFAULT '{}',
    progress   TEXT    NOT NULL DEFAULT '{}',
    per_language TEXT  NOT NULL DEFAULT '{}',
    percent    REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (learner_id, date)
);

CREATE TABLE IF NOT EXISTS achievement (
    learner_id     INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    achievement_id TEXT    NOT NULL,
    language       TEXT    NOT NULL DEFAULT '',
    earned_at      TEXT    NOT NULL,
    PRIMARY KEY (learner_id, achievement_id, language)
);

CREATE TABLE IF NOT EXISTS conversation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    language    TEXT    NOT NULL,
    scenario_id TEXT    NOT NULL DEFAULT '',
    started_at  TEXT    NOT NULL,
    level       TEXT    NOT NULL DEFAULT '',
    provider    TEXT    NOT NULL DEFAULT '',
    model       TEXT    NOT NULL DEFAULT '',
    transcript  TEXT    NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS audio_asset (
    id           TEXT PRIMARY KEY,
    language     TEXT NOT NULL,
    text         TEXT NOT NULL,
    path         TEXT NOT NULL,
    voice        TEXT NOT NULL DEFAULT '',
    engine       TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT 'user',
    license      TEXT NOT NULL DEFAULT '',
    duration_ms  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audio_text ON audio_asset(language, text);

CREATE TABLE IF NOT EXISTS recording (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    language   TEXT    NOT NULL,
    at         TEXT    NOT NULL,
    item_type  TEXT    NOT NULL DEFAULT '',
    item_id    TEXT    NOT NULL DEFAULT '',
    target     TEXT    NOT NULL DEFAULT '',
    heard      TEXT    NOT NULL DEFAULT '',
    path       TEXT    NOT NULL DEFAULT '',
    score      REAL,
    analysis   TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_recording_learner ON recording(learner_id, language, at);

-- Full-text search over the content cache, scoped by language.
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    ref UNINDEXED, kind UNINDEXED, language UNINDEXED,
    term, english, extra,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


# --------------------------------------------------------------------------
# Connection handling
# --------------------------------------------------------------------------

def _adapt(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # WAL lets readers and a writer work at the same time, which matters here
    # because one screen fires several requests at once and the server answers
    # them on a thread pool — the dashboard reads while the session tracker
    # writes.
    conn.execute("PRAGMA journal_mode = WAL")

    # And this is the one that was missing. SQLite's default busy timeout is
    # zero: a second writer does not queue, it fails immediately with
    # "database is locked". Opening the app used to be enough to trigger it,
    # because the dashboard's parallel requests include a write. Five seconds
    # is far longer than any statement here takes and turns a hard failure
    # into a wait nobody notices.
    conn.execute("PRAGMA busy_timeout = 5000")

    # The right pairing with WAL for a single-user local application: a crash
    # can lose the last transaction, never the database.
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def get_connection() -> sqlite3.Connection:
    """One connection per thread. FastAPI's threadpool reuses threads, so this
    stays a handful of connections rather than one per request."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = connect()
        _local.conn = conn
    return conn


def close_all() -> None:
    """Drop this thread's cached connection.

    Needed before the database file is replaced under a running server — a
    connection left open on the old file keeps reading it, and on some
    platforms holds a lock that stops the replacement outright. Other threads
    reopen lazily on their next call, so this is safe to call at any time.
    """
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:                   # already closed, or mid-statement
            pass
        _local.conn = None


@contextmanager
def transaction(conn: Optional[sqlite3.Connection] = None) -> Iterator[sqlite3.Connection]:
    conn = conn or get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db(
    conn: Optional[sqlite3.Connection] = None,
    path: Optional[Path] = None,
    verbose: bool = False,
) -> sqlite3.Connection:
    """Create the schema, or migrate an existing database up to it.

    A fresh database gets SCHEMA directly and is stamped at the current
    version. An existing one is handed to the migration runner, which backs it
    up first and refuses to finish if learner rows went missing.

    SCHEMA is then applied on *every* start, not only after a migration. It is
    all `CREATE TABLE IF NOT EXISTS`, so it is idempotent and cheap, and it
    means adding a new **content** table needs no migration at all — content
    tables are a rebuildable cache of the JSON files, so creating an empty one
    and reloading is the whole job. Only changes to **learner** tables, which
    hold data that exists nowhere else, need a version bump and a migration.
    Before this ran unconditionally, a database already at the current version
    never saw a newly added table and the loader failed on first use.
    """
    from . import migrations

    conn = conn or get_connection()
    existing = migrations.current_version(conn)

    if existing == 0:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
        return conn

    if existing < SCHEMA_VERSION:
        result = migrations.migrate(
            conn, SCHEMA_VERSION, path or Path(str(DB_PATH)), verbose=verbose
        )
        if verbose and result["migrated"]:
            print(f"  migrated {result['from']} -> {result['to']}; "
                  f"backup at {result['backup']}")

    conn.executescript(SCHEMA)
    conn.commit()
    return conn


# --------------------------------------------------------------------------
# Small query helpers
# --------------------------------------------------------------------------

def query(sql: str, params: Iterable = (), conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    conn = conn or get_connection()
    cur = conn.execute(sql, tuple(_adapt(p) for p in params))
    return [dict(r) for r in cur.fetchall()]


def query_one(sql: str, params: Iterable = (),
              conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    rows = query(sql, params, conn)
    return rows[0] if rows else None


def execute(sql: str, params: Iterable = (),
            conn: Optional[sqlite3.Connection] = None) -> sqlite3.Cursor:
    conn = conn or get_connection()
    cur = conn.execute(sql, tuple(_adapt(p) for p in params))
    conn.commit()
    return cur


def executemany(sql: str, rows: Iterable[Iterable],
                conn: Optional[sqlite3.Connection] = None) -> None:
    conn = conn or get_connection()
    conn.executemany(sql, [tuple(_adapt(v) for v in r) for r in rows])
    conn.commit()


def upsert(table: str, row: dict, conn: Optional[sqlite3.Connection] = None,
           key: str = "id") -> None:
    cols = list(row)
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != key)
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({key}) DO UPDATE SET {updates}"
    )
    execute(sql, [row[c] for c in cols], conn)


def json_field(row: dict, *fields: str) -> dict:
    """Decode the JSON-typed columns of a row in place."""
    out = dict(row)
    for f in fields:
        raw = out.get(f)
        if isinstance(raw, str):
            try:
                out[f] = json.loads(raw)
            except (TypeError, ValueError):
                out[f] = None
    return out


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
