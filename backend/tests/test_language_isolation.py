"""
Progress must not leak between languages.

This is the correctness property the whole refactor exists to protect. A
learner who is B1 in Korean and has never opened Mandarin must not see a
Mandarin level of B1, must not get Korean cards in a Mandarin review session,
and must not have a bad week of Mandarin tone drills drag down their Korean
listening score.

Tested at both levels it can break: the adaptive engine in memory, and the
database on disk.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.engines import adaptive as A
from app.engines import srs

NOW = datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc)


def attempt(language, skill, correct, item_id="", expected="", given="", days_ago=1):
    return A.Attempt(
        skill=skill, correct=correct, language=language,
        item_type="vocab", item_id=item_id,
        expected=expected, given=given,
        at=NOW - timedelta(days=days_ago),
    )


# ==========================================================================
# The adaptive engine
# ==========================================================================

def test_scores_ignore_other_languages():
    """A perfect Korean record must not lift a poor Mandarin score."""
    history = (
        [attempt("ko", "listening", True, f"ko-v-{i}") for i in range(20)]
        + [attempt("zh", "listening", False, f"zh-v-{i}") for i in range(10)]
    )
    ko = A.build_model(history, language="ko", now=NOW)
    zh = A.build_model(history, language="zh", now=NOW)

    assert ko.skills["listening"].score == 100.0
    assert zh.skills["listening"].score == 0.0
    assert ko.total_attempts == 20
    assert zh.total_attempts == 10


def test_weak_items_do_not_cross_over():
    history = (
        [attempt("ko", "vocabulary", False, "shared-id") for _ in range(4)]
        + [attempt("ja", "vocabulary", True, "shared-id") for _ in range(4)]
    )
    ko = A.build_model(history, language="ko", now=NOW)
    ja = A.build_model(history, language="ja", now=NOW)

    assert any(w["item_id"] == "shared-id" for w in ko.weak_items)
    assert not any(w["item_id"] == "shared-id" for w in ja.weak_items)


def test_unlabelled_attempts_are_accepted_for_backwards_compatibility():
    """Attempts recorded before languages existed carry no language. They are
    trusted rather than discarded, because throwing away a learner's history
    is worse than attributing it to the language they are asking about."""
    legacy = [A.Attempt(skill="reading", correct=True, at=NOW - timedelta(days=1))]
    model = A.build_model(legacy, language="ko", now=NOW)
    assert model.total_attempts == 1


def test_confusions_are_resolved_per_language():
    """The same wrong answer means different things in different languages."""
    history = [attempt("ko", "grammar", False, "g1", "이", "은") for _ in range(4)]
    ko = A.build_model(history, language="ko", now=NOW)
    assert ko.confusions
    assert ko.confusions[0]["id"] == "topic_vs_subject"
    assert ko.confusions[0]["language"] == "ko"
    assert ko.confusions[0]["warrants_mini_course"] is True

    # The identical attempts, read as Japanese, produce no confusion — Japanese
    # has not registered 은/는 because it does not have it.
    ja_history = [attempt("ja", "grammar", False, "g1", "이", "은") for _ in range(4)]
    ja = A.build_model(ja_history, language="ja", now=NOW)
    assert ja.confusions == []


def test_mini_course_is_scoped_to_its_language():
    course = A.build_mini_course("ko", "topic_vs_subject")
    assert course["id"] == "ko-mini-topic_vs_subject"
    assert course["language"] == "ko"
    assert course["steps"][1]["body"]           # the patient-teacher explanation

    with pytest.raises(KeyError, match="'ja' has no confusion"):
        A.build_mini_course("ja", "topic_vs_subject")


def test_level_estimates_use_each_languages_own_ladder():
    """The same learner profile lands on different bands, because CEFR and
    JLPT are different scales with different vocabulary thresholds."""
    profile = dict(script_mastery=1.0, vocab_known=1600,
                   grammar_known=60, accuracy=85)
    # The same learner, read against three ladders, lands in three different
    # places. 1,600 words and 60 grammar points is solidly B1 on CEFR; only N5
    # on JLPT, which wants 65 grammar points before N4; and HSK3 on HSK, where
    # the vocabulary is far past HSK4's 1,200 but the grammar count is the
    # binding constraint. Three scales, three answers, and no way to convert
    # between them — which is why there is no shared ladder.
    assert A.estimate_level("ko", **profile) == "B1"
    assert A.estimate_level("ja", **profile) == "N5"
    assert A.estimate_level("zh", **profile) == "HSK3"
    assert len({A.estimate_level(c, **profile) for c in ("ko", "ja", "zh")}) == 3

    # A language with no ladder module says so rather than guessing.
    assert A.estimate_level("fr", 1.0, 5000, 200, 99) == "unknown"


def test_level_ladders_do_not_share_a_scale():
    ko = A.level_ladder("ko")
    ja = A.level_ladder("ja")
    assert ko.scheme.startswith("CEFR")
    assert ja.scheme == "JLPT"
    assert set(ko.levels) & set(ja.levels) == set(), \
        "the two ladders must not share level names"


def test_korean_ladder_gates_on_reading_hangul():
    """Vocabulary is worthless if you cannot read. The ladder enforces it."""
    assert A.estimate_level("ko", 0.4, 5000, 200, 95) == "pre-A1"
    assert A.estimate_level("ko", 0.95, 5000, 200, 95) == "C1"


def test_native_skill_names_come_from_each_language():
    ko = A.native_skill_names("ko")
    ja = A.native_skill_names("ja")
    zh = A.native_skill_names("zh")
    assert ko["reading"] == "읽기"
    assert ja["reading"] == "読む"
    assert zh["reading"] == "阅读"
    assert "읽기" not in ja.values(), "Japanese must never show Korean labels"
    assert "読む" not in zh.values(), "Mandarin must never show Japanese labels"


def test_skill_names_fall_back_to_english_rather_than_borrowing():
    """A language with no SKILL_NAMES must show English, never another
    language's labels. Checked against a code that is not registered at all,
    so the test keeps meaning something as languages get finished."""
    unknown = A.native_skill_names("fr")
    assert unknown["reading"] == "Reading"
    assert not ({"읽기", "読む", "阅读"} & set(unknown.values()))


# ==========================================================================
# The database
# ==========================================================================

@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "t.sqlite3"
    c = db.connect(path)
    db.init_db(c, path)
    c.execute("INSERT INTO learner(id, name, created_at) VALUES (1,'R','2026-01-01T00:00:00Z')")
    for lang, level in (("ko", "A2"), ("ja", "pre-A1"), ("zh", "")):
        c.execute(
            "INSERT INTO learner_language(learner_id, language, level, started_at) "
            "VALUES (1, ?, ?, '2026-01-01T00:00:00Z')", (lang, level))
    c.commit()
    return c


def test_same_item_id_in_two_languages_is_two_cards(conn):
    for lang, state in (("ko", "mastered"), ("ja", "new")):
        conn.execute(
            "INSERT INTO srs_card(learner_id, language, item_type, item_id, state) "
            "VALUES (1, ?, 'vocab', 'v-0001', ?)", (lang, state))
    conn.commit()
    rows = conn.execute(
        "SELECT language, state FROM srs_card WHERE item_id='v-0001' ORDER BY language"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("ja", "new"), ("ko", "mastered")]


def test_duplicate_within_one_language_is_still_rejected(conn):
    conn.execute("INSERT INTO srs_card(learner_id, language, item_type, item_id) "
                 "VALUES (1,'ko','vocab','v-1')")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO srs_card(learner_id, language, item_type, item_id) "
                     "VALUES (1,'ko','vocab','v-1')")
    conn.rollback()


def test_due_queue_is_scoped_by_language(conn):
    due = "2026-08-01T00:00:00Z"
    later = "2027-01-01T00:00:00Z"
    rows = [("ko", "a", due), ("ko", "b", due), ("ja", "c", due), ("zh", "d", later)]
    for lang, item, when in rows:
        conn.execute(
            "INSERT INTO srs_card(learner_id, language, item_type, item_id, state, due_at) "
            "VALUES (1, ?, 'vocab', ?, 'review', ?)", (lang, item, when))
    conn.commit()

    def due_count(lang):
        return conn.execute(
            "SELECT COUNT(*) FROM srs_card WHERE learner_id=1 AND language=? "
            "AND state != 'new' AND due_at <= ?", (lang, "2026-08-27T09:00:00Z")
        ).fetchone()[0]

    assert due_count("ko") == 2
    assert due_count("ja") == 1
    assert due_count("zh") == 0


def test_levels_are_stored_per_language(conn):
    levels = dict(conn.execute(
        "SELECT language, level FROM learner_language WHERE learner_id=1"
    ).fetchall())
    assert levels == {"ko": "A2", "ja": "pre-A1", "zh": ""}


def test_lesson_progress_does_not_collide_across_languages(conn):
    for lang in ("ko", "ja"):
        conn.execute(
            "INSERT INTO lesson_progress(learner_id, language, lesson_id, status) "
            "VALUES (1, ?, 'lesson-001', ?)",
            (lang, "completed" if lang == "ko" else "not_started"))
    conn.commit()
    got = dict(conn.execute(
        "SELECT language, status FROM lesson_progress WHERE lesson_id='lesson-001'"
    ).fetchall())
    assert got == {"ko": "completed", "ja": "not_started"}


def test_streak_is_shared_because_it_measures_the_habit(conn):
    """Deliberate design choice: the daily streak is global.

    Level and XP are per language because they measure progress in that
    language. The streak measures whether you sat down to study at all, and
    splitting it would punish a learner for spending Tuesday on Japanese.
    """
    cols = [r[1] for r in conn.execute("PRAGMA table_info(streak)")]
    assert "language" not in cols
    assert "learner_id" in cols


# ==========================================================================
# The SRS engine itself is language-agnostic
# ==========================================================================

def test_srs_scheduler_has_no_language_opinion():
    """The scheduler never sees a language — isolation is enforced by the
    queries that feed it, which is the right place for it."""
    card = srs.Card(item_type="vocab", item_id="anything")
    out = srs.review(card, "good", now=NOW)
    assert out.card.state in ("learning", "review")
    assert not hasattr(card, "language")


def test_queues_built_from_separate_card_sets_stay_separate():
    ko_cards = [srs.Card(item_type="vocab", item_id=f"ko-{i}") for i in range(5)]
    ja_cards = [srs.Card(item_type="vocab", item_id=f"ja-{i}") for i in range(5)]
    ko_queue = srs.build_queue(ko_cards, now=NOW)
    assert all(c.item_id.startswith("ko-") for c in ko_queue)
    ja_queue = srs.build_queue(ja_cards, now=NOW)
    assert all(c.item_id.startswith("ja-") for c in ja_queue)
