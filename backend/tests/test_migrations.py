"""
Migration tests.

These start from a real version-1 database containing real Korean learner
data, run the migration, and assert that every row survived and landed in the
right language. A migration that silently drops a learner's two-year review
history is the worst bug this project could ship, so the test asserts on row
counts and on specific values, not just on the schema shape.

The v1 schema is pinned here as a literal rather than imported, because the
point of the test is to migrate from what v1 *was*, not from whatever db.py
happens to say today.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import db, migrations

# --------------------------------------------------------------------------
# The version-1 schema, frozen. Do not edit to match later changes.
# --------------------------------------------------------------------------

V1_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE learner (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL,
    level          TEXT    NOT NULL DEFAULT 'pre-A1',
    start_level    TEXT    NOT NULL DEFAULT 'pre-A1',
    goal           TEXT    NOT NULL DEFAULT '',
    daily_minutes  INTEGER NOT NULL DEFAULT 15,
    onboarded      INTEGER NOT NULL DEFAULT 0,
    settings_json  TEXT    NOT NULL DEFAULT '{}',
    xp             INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE streak (
    learner_id       INTEGER PRIMARY KEY REFERENCES learner(id) ON DELETE CASCADE,
    current          INTEGER NOT NULL DEFAULT 0,
    longest          INTEGER NOT NULL DEFAULT 0,
    last_active_date TEXT,
    freezes          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE vocab (
    id      TEXT PRIMARY KEY,
    korean  TEXT NOT NULL,
    meaning TEXT NOT NULL,
    pos     TEXT NOT NULL DEFAULT '',
    topic   TEXT NOT NULL DEFAULT '',
    level   TEXT NOT NULL DEFAULT 'A1'
);

CREATE TABLE slang (
    id      TEXT PRIMARY KEY,
    korean  TEXT NOT NULL,
    literal TEXT NOT NULL DEFAULT '',
    actual  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE lesson (
    id    TEXT PRIMARY KEY,
    level TEXT NOT NULL,
    unit  TEXT NOT NULL DEFAULT '',
    ordinal INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL
);

CREATE TABLE srs_card (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id        INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
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
    UNIQUE(learner_id, item_type, item_id)
);

CREATE TABLE attempt (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
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

CREATE TABLE lesson_progress (
    learner_id   INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    lesson_id    TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'not_started',
    step         TEXT    NOT NULL DEFAULT 'warmup',
    score        REAL    NOT NULL DEFAULT 0,
    attempts     INTEGER NOT NULL DEFAULT 0,
    started_at   TEXT,
    completed_at TEXT,
    PRIMARY KEY (learner_id, lesson_id)
);

CREATE TABLE mistake (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id   INTEGER NOT NULL REFERENCES learner(id) ON DELETE CASCADE,
    at           TEXT    NOT NULL,
    category     TEXT    NOT NULL,
    expected     TEXT    NOT NULL DEFAULT '',
    given        TEXT    NOT NULL DEFAULT '',
    confusion_id TEXT    NOT NULL DEFAULT '',
    resolved     INTEGER NOT NULL DEFAULT 0,
    times_seen   INTEGER NOT NULL DEFAULT 1
);

CREATE VIRTUAL TABLE search_index USING fts5(
    ref UNINDEXED, kind UNINDEXED, korean, english, extra
);
"""


@pytest.fixture
def v1_db(tmp_path: Path):
    """A version-1 database holding a real Korean learner's data."""
    path = tmp_path / "hanbat.sqlite3"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(V1_SCHEMA)
    conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', '1')")

    conn.execute(
        "INSERT INTO learner(id, name, created_at, level, start_level, goal, "
        "daily_minutes, onboarded, xp) VALUES (1, ?, ?, ?, ?, ?, ?, 1, ?)",
        ("Rithish", "2026-01-04T09:00:00Z", "A2", "pre-A1",
         "Move to Seoul", 20, 4820),
    )
    conn.execute(
        "INSERT INTO streak(learner_id, current, longest, last_active_date) "
        "VALUES (1, 47, 61, '2026-08-26')"
    )
    conn.executemany(
        "INSERT INTO vocab(id, korean, meaning, pos, topic, level) VALUES (?,?,?,?,?,?)",
        [("v-0081", "밥", "cooked rice; a meal", "noun", "food", "A1"),
         ("v-0302", "먹다", "to eat", "verb", "food", "A1"),
         ("v-0371", "춥다", "to be cold", "adjective", "weather", "A1")],
    )
    conn.execute("INSERT INTO slang(id, korean, literal, actual) VALUES "
                 "('s-001', '대박', 'big hit', 'wow / amazing')")
    conn.executemany(
        "INSERT INTO lesson(id, level, unit, ordinal, title) VALUES (?,?,?,?,?)",
        [("hangul-000", "level0", "level0-hangul", 0, "What is Korean?"),
         ("batchim-003", "level0", "level0-hangul", 12, "연음")],
    )
    # A mature card with real review history — the thing that must not be lost.
    conn.executemany(
        "INSERT INTO srs_card(learner_id, item_type, item_id, state, ease, "
        "interval_days, repetitions, lapses, streak, due_at, total_reviews, "
        "total_correct) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(1, "vocab", "v-0081", "mastered", 2.7, 92.4, 11, 1, 6,
          "2026-11-01T09:00:00Z", 14, 13),
         (1, "vocab", "v-0371", "difficult", 1.8, 3.0, 2, 4, 0,
          "2026-08-27T09:00:00Z", 19, 9),
         (1, "hangul", "ko-jamo-ㅓ", "review", 2.4, 21.0, 6, 0, 4,
          "2026-09-10T09:00:00Z", 8, 7)],
    )
    conn.executemany(
        "INSERT INTO attempt(learner_id, at, skill, correct, item_type, item_id, "
        "expected, given) VALUES (?,?,?,?,?,?,?,?)",
        [(1, "2026-08-20T10:00:00Z", "grammar", 0, "grammar", "g-particles", "이", "은"),
         (1, "2026-08-21T10:00:00Z", "grammar", 0, "grammar", "g-particles", "가", "는"),
         (1, "2026-08-22T10:00:00Z", "reading", 1, "vocab", "v-0081", "", "")],
    )
    conn.execute(
        "INSERT INTO lesson_progress(learner_id, lesson_id, status, score, "
        "completed_at) VALUES (1, 'hangul-000', 'completed', 100.0, '2026-01-05T10:00:00Z')"
    )
    conn.execute(
        "INSERT INTO mistake(learner_id, at, category, expected, given, "
        "confusion_id, times_seen) VALUES "
        "(1, '2026-08-21T10:00:00Z', 'grammar', '이', '은', 'topic_vs_subject', 3)"
    )
    conn.commit()
    return path, conn


# ==========================================================================

def test_starts_at_version_1(v1_db):
    path, conn = v1_db
    assert migrations.current_version(conn) == 1


def test_migration_reaches_version_2(v1_db):
    path, conn = v1_db
    result = migrations.migrate(conn, 2, path, verbose=False)
    assert result["migrated"] is True
    assert result["from"] == 1 and result["to"] == 2
    assert migrations.current_version(conn) == 2


def test_migration_takes_a_backup(v1_db):
    path, conn = v1_db
    result = migrations.migrate(conn, 2, path, verbose=False)
    backup = Path(result["backup"])
    assert backup.exists()
    # and the backup is still readable at version 1
    old = sqlite3.connect(str(backup))
    assert migrations.current_version(old) == 1
    assert old.execute("SELECT COUNT(*) FROM srs_card").fetchone()[0] == 3


def test_no_learner_rows_are_lost(v1_db):
    path, conn = v1_db
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("learner", "srs_card", "attempt", "lesson_progress",
                        "mistake", "streak")}
    migrations.migrate(conn, 2, path, verbose=False)
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in before}
    assert after == before


def test_srs_history_survives_intact(v1_db):
    """The mature card keeps every field. This is the row that matters most."""
    path, conn = v1_db
    conn.row_factory = sqlite3.Row
    migrations.migrate(conn, 2, path, verbose=False)

    row = conn.execute(
        "SELECT * FROM srs_card WHERE item_id = 'v-0081'"
    ).fetchone()
    assert row["language"] == "ko"
    assert row["state"] == "mastered"
    assert row["ease"] == pytest.approx(2.7)
    assert row["interval_days"] == pytest.approx(92.4)
    assert row["repetitions"] == 11
    assert row["lapses"] == 1
    assert row["total_reviews"] == 14
    assert row["total_correct"] == 13
    assert row["due_at"] == "2026-11-01T09:00:00Z"


def test_everything_is_stamped_korean(v1_db):
    path, conn = v1_db
    migrations.migrate(conn, 2, path, verbose=False)
    for table in ("vocab", "slang", "lesson", "srs_card", "attempt",
                  "lesson_progress", "mistake"):
        rows = conn.execute(f"SELECT DISTINCT language FROM {table}").fetchall()
        assert [r[0] for r in rows] == ["ko"], f"{table} was not stamped"


def test_korean_column_becomes_term(v1_db):
    path, conn = v1_db
    conn.row_factory = sqlite3.Row
    migrations.migrate(conn, 2, path, verbose=False)
    row = conn.execute("SELECT * FROM vocab WHERE id = 'v-0081'").fetchone()
    assert row["term"] == "밥"
    assert "korean" not in row.keys()
    row = conn.execute("SELECT * FROM slang WHERE id = 's-001'").fetchone()
    assert row["term"] == "대박"


def test_learner_language_row_is_created_from_learner(v1_db):
    path, conn = v1_db
    conn.row_factory = sqlite3.Row
    migrations.migrate(conn, 2, path, verbose=False)
    row = conn.execute(
        "SELECT * FROM learner_language WHERE learner_id = 1 AND language = 'ko'"
    ).fetchone()
    assert row is not None
    assert row["level"] == "A2"
    assert row["start_level"] == "pre-A1"
    assert row["goal"] == "Move to Seoul"
    assert row["xp"] == 4820


def test_streak_stays_global(v1_db):
    """The daily streak measures the habit, not progress in one language."""
    path, conn = v1_db
    conn.row_factory = sqlite3.Row
    migrations.migrate(conn, 2, path, verbose=False)
    row = conn.execute("SELECT * FROM streak WHERE learner_id = 1").fetchone()
    assert row["current"] == 47
    assert row["longest"] == 61
    assert "language" not in row.keys()


def test_srs_uniqueness_now_includes_language(v1_db):
    """The whole point: the same item id in two languages stays two cards."""
    path, conn = v1_db
    migrations.migrate(conn, 2, path, verbose=False)

    conn.execute(
        "INSERT INTO srs_card(learner_id, language, item_type, item_id, state) "
        "VALUES (1, 'ja', 'vocab', 'v-0081', 'new')"
    )
    conn.commit()
    rows = conn.execute(
        "SELECT language, state FROM srs_card WHERE item_id = 'v-0081' "
        "ORDER BY language"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("ja", "new"), ("ko", "mastered")]

    # and the old constraint still holds within one language
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO srs_card(learner_id, language, item_type, item_id) "
            "VALUES (1, 'ko', 'vocab', 'v-0081')"
        )
    conn.rollback()


def test_lesson_progress_is_keyed_by_language(v1_db):
    path, conn = v1_db
    migrations.migrate(conn, 2, path, verbose=False)
    conn.execute(
        "INSERT INTO lesson_progress(learner_id, language, lesson_id, status) "
        "VALUES (1, 'ja', 'hangul-000', 'not_started')"
    )
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM lesson_progress WHERE lesson_id = 'hangul-000'"
    ).fetchone()[0]
    assert n == 2


def test_migration_is_idempotent(v1_db):
    path, conn = v1_db
    migrations.migrate(conn, 2, path, verbose=False)
    second = migrations.migrate(conn, 2, path, verbose=False)
    assert second["migrated"] is False
    assert conn.execute("SELECT COUNT(*) FROM srs_card").fetchone()[0] == 3


def test_fresh_database_skips_migration_entirely(tmp_path):
    path = tmp_path / "fresh.sqlite3"
    conn = db.connect(path)
    db.init_db(conn, path)
    assert migrations.current_version(conn) == db.SCHEMA_VERSION
    # no backup should have been written for a database that did not exist
    assert not list(tmp_path.glob("*.backup-*"))


def test_backup_of_missing_file_is_none(tmp_path):
    assert migrations.backup(tmp_path / "nope.sqlite3") is None


# ==========================================================================
# Concurrency
# ==========================================================================

def test_concurrent_writers_wait_instead_of_failing(tmp_path):
    """Two connections writing at once must not raise "database is locked".

    This is a regression test for a real failure: the dashboard fires several
    requests at once and FastAPI answers them on a thread pool, so a read and
    a write overlap on the very first screen. SQLite's default busy timeout is
    zero, which turns that overlap into an immediate error rather than a
    wait — onboarding failed with a spinner stuck on "Setting up…".
    """
    import threading

    path = tmp_path / "busy.sqlite3"
    setup = db.connect(path)
    db.init_db(setup, path)
    setup.execute("INSERT INTO learner(id, name, created_at) "
                  "VALUES (1, 'R', '2026-01-01T00:00:00Z')")
    setup.commit()

    errors: list[Exception] = []

    def hammer(tag: str) -> None:
        conn = db.connect(path)
        try:
            for i in range(40):
                conn.execute("UPDATE learner SET name = ? WHERE id = 1", (f"{tag}{i}",))
                conn.commit()
        except Exception as e:                      # noqa: BLE001 - recorded
            errors.append(e)
        finally:
            conn.close()

    threads = [threading.Thread(target=hammer, args=(t,)) for t in "abcd"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent writes failed: {errors[0]}"


def test_connections_are_configured_for_concurrent_use(tmp_path):
    conn = db.connect(tmp_path / "pragmas.sqlite3")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000


# ==========================================================================
# v3 — why a mistake happened
# ==========================================================================

def test_v1_migrates_all_the_way_to_v3_without_losing_anything(v1_db):
    """A learner two versions behind must arrive intact, not be rebuilt."""
    path, conn = v1_db
    before = conn.execute("SELECT COUNT(*) FROM mistake").fetchone()[0]
    xp_before = conn.execute("SELECT xp FROM learner WHERE id = 1").fetchone()[0]

    result = migrations.migrate(conn, 3, path, verbose=False)

    assert result["migrated"] is True
    assert result["to"] == 3
    assert conn.execute("SELECT COUNT(*) FROM mistake").fetchone()[0] == before
    assert conn.execute(
        "SELECT xp FROM learner_language WHERE learner_id=1 AND language='ko'"
    ).fetchone()[0] == xp_before


def test_v3_adds_the_reason_columns(v1_db):
    path, conn = v1_db
    migrations.migrate(conn, 3, path, verbose=False)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(mistake)")}
    assert {"reason", "reason_why", "confidence", "response_ms"} <= columns


def test_old_mistakes_are_not_given_an_invented_reason(v1_db):
    """The signals that classify a mistake were not recorded at the time.

    Back-filling a plausible-looking reason would put a fabricated diagnosis in
    front of the learner, which is exactly the kind of confident nonsense this
    project refuses elsewhere. They stay blank and the UI says so.
    """
    path, conn = v1_db
    migrations.migrate(conn, 3, path, verbose=False)
    reasons = [r[0] for r in conn.execute("SELECT reason FROM mistake")]
    assert reasons and all(r == "" for r in reasons)


def test_v3_is_idempotent(v1_db):
    path, conn = v1_db
    migrations.migrate(conn, 3, path, verbose=False)
    again = migrations.migrate(conn, 3, path, verbose=False)
    assert again["migrated"] is False
