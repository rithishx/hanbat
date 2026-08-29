"""
Spaced repetition scheduling.

The scheduler is pure — every test pins `now` — so intervals are asserted
exactly rather than approximately. The tests that matter most are the ones
about *mastery*: a scheduler that hands out "mastered" too easily lies to the
learner about their own level, which is the failure this system is most likely
to make and least likely to be caught making.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest

from app.engines import srs

NOW = datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc)
FIXED = random.Random(1234)


def new_card(**kw) -> srs.Card:
    return srs.Card(item_type="vocab", item_id="x", **kw)


def graduated(age_days: float = 200.0, **kw) -> srs.Card:
    """A card that left the learning steps a while ago.

    `introduced_at` is set to a realistic point in the past, because a card
    with a 40-day interval and five repetitions could not have been created
    this morning — and the scheduler now checks exactly that before it will
    call anything mastered.
    """
    base = dict(state="review", interval_days=10.0, repetitions=3,
                ease=2.5, streak=3, due_at=NOW,
                introduced_at=NOW - timedelta(days=age_days))
    base.update(kw)
    return new_card(**base)


# ==========================================================================
# Learning steps
# ==========================================================================

def test_new_card_starts_in_learning():
    out = srs.review(new_card(), "good", now=NOW)
    assert out.card.state == "learning"
    assert out.card.step_index == 1
    assert out.card.due_at == NOW + timedelta(minutes=10)


def test_again_resets_to_the_first_step():
    card = new_card(state="learning", step_index=1)
    out = srs.review(card, "again", now=NOW)
    assert out.card.state == "learning"
    assert out.card.step_index == 0
    assert out.card.due_at == NOW + timedelta(minutes=1)


def test_good_twice_graduates():
    card = new_card()
    card = srs.review(card, "good", now=NOW).card
    out = srs.review(card, "good", now=NOW)
    assert out.graduated is True
    assert out.card.state == "review"
    assert out.card.interval_days == srs.GRADUATING_INTERVAL_DAYS


def test_easy_graduates_immediately_with_a_longer_interval():
    out = srs.review(new_card(), "easy", now=NOW)
    assert out.graduated is True
    assert out.card.state == "review"
    assert out.card.interval_days == srs.EASY_INTERVAL_DAYS


def test_hard_repeats_the_current_step():
    card = new_card(state="learning", step_index=1)
    out = srs.review(card, "hard", now=NOW)
    assert out.card.step_index == 1


# ==========================================================================
# Review intervals
# ==========================================================================

def test_good_multiplies_by_ease():
    out = srs.review(graduated(interval_days=10.0, ease=2.5), "good", now=NOW)
    assert out.card.interval_days == pytest.approx(25.0)
    assert out.card.ease == pytest.approx(2.5)


def test_hard_shortens_the_growth_and_lowers_ease():
    out = srs.review(graduated(interval_days=10.0, ease=2.5), "hard", now=NOW)
    assert out.card.interval_days == pytest.approx(12.0)
    assert out.card.ease == pytest.approx(2.35)


def test_easy_lengthens_the_growth_and_raises_ease():
    out = srs.review(graduated(interval_days=10.0, ease=2.5), "easy", now=NOW)
    assert out.card.ease == pytest.approx(2.65)
    assert out.card.interval_days == pytest.approx(10.0 * 2.65 * 1.3)


def test_ease_is_clamped_at_both_ends():
    low = graduated(ease=srs.MIN_EASE)
    for _ in range(10):
        low = srs.review(low, "hard", now=NOW).card
    assert low.ease >= srs.MIN_EASE

    high = graduated(ease=srs.MAX_EASE)
    for _ in range(10):
        high = srs.review(high, "easy", now=NOW).card
    assert high.ease <= srs.MAX_EASE


def test_intervals_are_capped():
    card = graduated(interval_days=srs.MAX_INTERVAL_DAYS, ease=3.0)
    out = srs.review(card, "easy", now=NOW)
    assert out.card.interval_days <= srs.MAX_INTERVAL_DAYS


# ==========================================================================
# Lapses
# ==========================================================================

def test_lapse_returns_to_learning_and_records_itself():
    out = srs.review(graduated(interval_days=60.0, ease=2.5), "again", now=NOW)
    assert out.lapsed is True
    assert out.card.state == "learning"
    assert out.card.lapses == 1
    assert out.card.repetitions == 0
    assert out.card.streak == 0
    assert out.card.ease == pytest.approx(2.3)


def test_lapse_keeps_part_of_the_earned_interval():
    """Forgetting a mature card once is a wobble, not amnesia. Resetting a
    60-day card to zero makes mature cards punishing to own."""
    out = srs.review(graduated(interval_days=60.0), "again", now=NOW)
    assert out.card.interval_days == pytest.approx(24.0)


def test_repeated_lapses_mark_the_card_difficult():
    card = graduated()
    for _ in range(srs.DIFFICULT_LAPSES):
        card = srs.review(card, "again", now=NOW).card
        card = srs.review(card, "good", now=NOW).card
        card = srs.review(card, "good", now=NOW).card
    assert card.lapses >= srs.DIFFICULT_LAPSES
    assert card.state == "difficult"


def test_low_ease_alone_marks_a_card_difficult():
    card = graduated(ease=1.85, interval_days=5.0)
    out = srs.review(card, "hard", now=NOW)
    assert out.card.state == "difficult"


# ==========================================================================
# Mastery — the honesty tests
# ==========================================================================

def test_mastery_requires_a_long_interval_not_a_good_afternoon():
    """Ten correct answers in one session is recognition, not memory."""
    card = new_card()
    for _ in range(10):
        card = srs.review(card, "easy", now=NOW).card
    assert card.state != "mastered"


def test_a_young_card_cannot_be_mastered_however_good_the_numbers():
    """A card introduced last week claiming a 90-day interval is not mastered,
    it is mis-scheduled. Elapsed time is the only real evidence."""
    young = graduated(age_days=7, interval_days=90.0, repetitions=8, streak=5)
    assert srs._classify(young, NOW) == "review"
    old = graduated(age_days=200, interval_days=90.0, repetitions=8, streak=5)
    assert srs._classify(old, NOW) == "mastered"


def test_early_review_does_not_compound_the_interval():
    """Cramming ahead of an exam must not inflate the schedule."""
    card = graduated(interval_days=30.0, due_at=NOW + timedelta(days=20))
    out = srs.review(card, "good", now=NOW)
    assert out.card.interval_days <= 30.0


def test_review_on_time_does_compound():
    card = graduated(interval_days=30.0, due_at=NOW)
    out = srs.review(card, "good", now=NOW)
    assert out.card.interval_days == pytest.approx(75.0)


def test_mastery_needs_interval_repetitions_and_streak_together():
    almost = graduated(
        interval_days=srs.MASTERY_INTERVAL_DAYS + 10,
        repetitions=srs.MASTERY_REPETITIONS,
        streak=srs.MASTERY_STREAK - 1,      # one short
        ease=2.5,
    )
    assert srs._classify(almost, NOW) != "mastered"

    there = graduated(
        interval_days=srs.MASTERY_INTERVAL_DAYS + 10,
        repetitions=srs.MASTERY_REPETITIONS,
        streak=srs.MASTERY_STREAK,
        ease=2.5,
    )
    assert srs._classify(there, NOW) == "mastered"


def test_a_mastered_card_that_lapses_stops_being_mastered():
    card = graduated(interval_days=90.0, repetitions=8, streak=5)
    assert srs._classify(card, NOW) == "mastered"
    out = srs.review(card, "again", now=NOW)
    assert out.card.state == "learning"


def test_mastered_flag_only_fires_on_the_transition():
    card = graduated(interval_days=40.0, repetitions=5, streak=3, ease=2.6)
    first = srs.review(card, "good", now=NOW)
    assert first.card.state == "mastered"
    assert first.mastered is True
    second = srs.review(first.card, "good", now=NOW)
    assert second.mastered is False


# ==========================================================================
# Accounting
# ==========================================================================

def test_accuracy_tracks_every_review():
    card = new_card()
    for grade in ("good", "again", "good", "good"):
        card = srs.review(card, grade, now=NOW).card
    assert card.total_reviews == 4
    assert card.total_correct == 3
    assert card.accuracy == pytest.approx(0.75)


def test_accuracy_is_none_before_any_review():
    assert new_card().accuracy is None


def test_streak_breaks_on_again_only():
    card = new_card()
    card = srs.review(card, "good", now=NOW).card
    card = srs.review(card, "hard", now=NOW).card
    assert card.streak == 2
    card = srs.review(card, "again", now=NOW).card
    assert card.streak == 0


def test_unknown_grade_is_rejected():
    with pytest.raises(ValueError, match="unknown grade"):
        srs.review(new_card(), "brilliant", now=NOW)


def test_preview_shows_all_four_outcomes():
    p = srs.preview_intervals(graduated(), now=NOW)
    assert set(p) == set(srs.GRADES)
    assert all(isinstance(v, str) and v for v in p.values())


# ==========================================================================
# Queue building
# ==========================================================================

def test_learning_cards_come_first():
    cards = [
        srs.Card(item_id="review", state="review", due_at=NOW - timedelta(days=5)),
        srs.Card(item_id="learning", state="learning", due_at=NOW - timedelta(minutes=1)),
        srs.Card(item_id="new", state="new"),
    ]
    queue = srs.build_queue(cards, now=NOW)
    assert queue[0].item_id == "learning"


def test_new_cards_are_interleaved_not_front_loaded():
    """Meeting ten unknown words in a row is the fastest way to make someone
    quit, so new cards are spread through the session."""
    reviews = [srs.Card(item_id=f"r{i}", state="review", due_at=NOW - timedelta(days=1))
               for i in range(20)]
    news = [srs.Card(item_id=f"n{i}", state="new") for i in range(5)]
    queue = srs.build_queue(reviews + news, now=NOW,
                            limits=srs.QueueLimits(new_per_day=5, reviews_per_day=20))
    positions = [i for i, c in enumerate(queue) if c.state == "new"]
    assert len(positions) == 5
    assert positions[0] > 0, "a new card should not open the session"
    assert max(positions) - min(positions) > 5, "new cards should be spread out"


def test_daily_limits_are_respected():
    cards = ([srs.Card(item_id=f"n{i}", state="new") for i in range(50)]
             + [srs.Card(item_id=f"r{i}", state="review", due_at=NOW - timedelta(days=1))
                for i in range(50)])
    queue = srs.build_queue(cards, now=NOW,
                            limits=srs.QueueLimits(new_per_day=5, reviews_per_day=10))
    assert sum(1 for c in queue if c.state == "new") == 5
    assert sum(1 for c in queue if c.state == "review") == 10


def test_cards_introduced_today_count_against_the_new_limit():
    cards = [srs.Card(item_id=f"n{i}", state="new") for i in range(20)]
    queue = srs.build_queue(cards, now=NOW, introduced_today=8,
                            limits=srs.QueueLimits(new_per_day=10))
    assert len(queue) == 2


def test_cards_not_yet_due_are_excluded():
    cards = [srs.Card(item_id="future", state="review", due_at=NOW + timedelta(days=3))]
    assert srs.build_queue(cards, now=NOW) == []


def test_difficult_cards_are_capped_not_dumped_at_the_front():
    """A session that opens with a wall of your worst items is one you skip."""
    difficult = [srs.Card(item_id=f"d{i}", state="difficult", due_at=NOW - timedelta(days=1))
                 for i in range(40)]
    reviews = [srs.Card(item_id=f"r{i}", state="review", due_at=NOW - timedelta(days=1))
               for i in range(40)]
    queue = srs.build_queue(difficult + reviews, now=NOW,
                            limits=srs.QueueLimits(reviews_per_day=20, difficult_share=0.25))
    n_difficult = sum(1 for c in queue if c.state == "difficult")
    assert n_difficult == 5


# ==========================================================================
# Summaries
# ==========================================================================

def test_summary_counts_by_state():
    cards = [
        srs.Card(state="new"),
        srs.Card(state="learning", due_at=NOW - timedelta(minutes=1)),
        srs.Card(state="review", due_at=NOW - timedelta(days=1), total_reviews=4, total_correct=3),
        srs.Card(state="mastered", due_at=NOW + timedelta(days=40), total_reviews=10, total_correct=10),
        srs.Card(state="difficult", due_at=NOW - timedelta(days=2), total_reviews=8, total_correct=3),
    ]
    s = srs.queue_summary(cards, now=NOW)
    assert s["total"] == 5
    assert s["by_state"]["new"] == 1
    assert s["due_now"] == 3
    assert s["known"] == 2                      # review + mastered
    assert s["accuracy"] == pytest.approx(16 / 22)


def test_forecast_buckets_by_day():
    cards = [srs.Card(state="review", due_at=NOW + timedelta(days=d))
             for d in (0, 0, 1, 3, 3, 3, 40)]
    f = srs.retention_forecast(cards, days=7, now=NOW)
    assert len(f) == 7
    assert f[0]["count"] == 2
    assert f[1]["count"] == 1
    assert f[3]["count"] == 3
    assert sum(b["count"] for b in f) == 6      # the day-40 card is outside the window


def test_overdue_cards_land_in_today():
    cards = [srs.Card(state="review", due_at=NOW - timedelta(days=30))]
    f = srs.retention_forecast(cards, days=7, now=NOW)
    assert f[0]["count"] == 1


def test_fuzz_spreads_long_intervals_without_shortening_them_below_a_day():
    card = graduated(interval_days=200.0)
    seen = {srs.review(card, "good", now=NOW, rng=random.Random(s)).card.interval_days
            for s in range(20)}
    assert len(seen) > 1, "fuzz should vary long intervals"
    assert all(v >= 1.0 for v in seen)


def test_short_intervals_are_not_fuzzed():
    card = graduated(interval_days=1.0, ease=2.0)
    a = srs.review(card, "good", now=NOW, rng=random.Random(1)).card.interval_days
    b = srs.review(card, "good", now=NOW, rng=random.Random(99)).card.interval_days
    assert a == b


def test_card_serialises_to_json_safe_types():
    import json
    card = srs.review(new_card(), "good", now=NOW).card
    json.loads(json.dumps(card.to_dict()))
