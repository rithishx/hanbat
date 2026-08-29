"""
Spaced repetition scheduler.

An SM-2 derivative with explicit learning steps, a relearning path, and the
five card states the curriculum tracks. It is deliberately conservative about
the word "mastered": a card only earns it after several successful *delayed*
recalls, never after a good run inside one session. Recognising a word ten
times in a row this afternoon is not the same as remembering it next month,
and a learning app that conflates the two lies to its user about their level.

The scheduler is pure: it takes a card plus a grade and returns a new card. No
clock is read unless one is not supplied, so every path is deterministically
testable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace, asdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal, Optional

Grade = Literal["again", "hard", "good", "easy"]
State = Literal["new", "learning", "review", "difficult", "mastered"]

GRADES: tuple[Grade, ...] = ("again", "hard", "good", "easy")

#: Minutes between the first few sightings of a brand-new card.
LEARNING_STEPS_MIN = (1.0, 10.0)
#: Where a lapsed card restarts.
RELEARNING_STEPS_MIN = (10.0,)

GRADUATING_INTERVAL_DAYS = 1.0
EASY_INTERVAL_DAYS = 4.0

MIN_EASE = 1.3
MAX_EASE = 3.2
START_EASE = 2.5

#: A card is only called mastered once all of these hold.
MASTERY_INTERVAL_DAYS = 45.0
MASTERY_REPETITIONS = 5
MASTERY_STREAK = 3

#: A card is flagged difficult once it has been forgotten this often, or once
#: its ease has sunk this low. Difficult cards are what the adaptive engine
#: builds targeted mini-lessons from.
DIFFICULT_LAPSES = 3
DIFFICULT_EASE = 1.9

MAX_INTERVAL_DAYS = 365.0 * 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Card:
    """One schedulable item. `item_type` lets one queue serve every module."""

    id: Optional[int] = None
    item_type: str = "vocab"           # vocab | grammar | hangul | sentence | pronunciation | listening
    item_id: str = ""
    state: State = "new"
    ease: float = START_EASE
    interval_days: float = 0.0
    repetitions: int = 0
    lapses: int = 0
    streak: int = 0
    step_index: int = 0
    due_at: Optional[datetime] = None
    last_reviewed_at: Optional[datetime] = None
    introduced_at: Optional[datetime] = None
    total_reviews: int = 0
    total_correct: int = 0

    @property
    def accuracy(self) -> Optional[float]:
        if not self.total_reviews:
            return None
        return self.total_correct / self.total_reviews

    @property
    def is_due(self) -> bool:
        return self.due_at is None or self.due_at <= _now()

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("due_at", "last_reviewed_at", "introduced_at"):
            if d[k] is not None:
                d[k] = d[k].isoformat()
        d["accuracy"] = self.accuracy
        return d


@dataclass(frozen=True)
class ReviewOutcome:
    card: Card
    previous_state: State
    next_due_in: str          # human-readable: "10 minutes", "3 days"
    graduated: bool = False
    lapsed: bool = False
    mastered: bool = False

    def to_dict(self) -> dict:
        return {
            "card": self.card.to_dict(),
            "previous_state": self.previous_state,
            "next_due_in": self.next_due_in,
            "graduated": self.graduated,
            "lapsed": self.lapsed,
            "mastered": self.mastered,
        }


def _humanise(delta: timedelta) -> str:
    mins = delta.total_seconds() / 60
    if mins < 60:
        return f"{round(mins)} minute{'s' if round(mins) != 1 else ''}"
    hours = mins / 60
    if hours < 24:
        return f"{round(hours)} hour{'s' if round(hours) != 1 else ''}"
    days = hours / 24
    if days < 30:
        return f"{round(days)} day{'s' if round(days) != 1 else ''}"
    months = days / 30.44
    if months < 12:
        return f"{months:.1f} months"
    return f"{days / 365.25:.1f} years"


def _fuzz(days: float, rng: Optional[random.Random]) -> float:
    """Spread long intervals by a few percent so reviews do not clump into
    one brutal day months from now."""
    if rng is None or days < 2.5:
        return days
    spread = max(1.0, days * 0.05)
    return max(1.0, days + rng.uniform(-spread, spread))


def _classify(card: Card, now: Optional[datetime] = None) -> State:
    """Derive the display state from the card's history.

    Mastery deliberately requires four things at once, including one that
    cannot be faked in a single sitting: the card must have *existed* for at
    least as long as the interval it claims. Without that clause, pressing
    "easy" ten times in one afternoon compounds the interval past the mastery
    threshold and the app reports a word as mastered that the learner first
    saw twenty minutes ago. Elapsed calendar time is the only evidence that
    someone remembered something rather than recognised it.
    """
    if card.state in ("new", "learning"):
        return card.state
    if card.lapses >= DIFFICULT_LAPSES or card.ease <= DIFFICULT_EASE:
        return "difficult"

    old_enough = True
    if card.introduced_at is not None:
        age_days = ((now or _now()) - card.introduced_at).total_seconds() / 86400
        old_enough = age_days >= MASTERY_INTERVAL_DAYS

    if (
        old_enough
        and card.interval_days >= MASTERY_INTERVAL_DAYS
        and card.repetitions >= MASTERY_REPETITIONS
        and card.streak >= MASTERY_STREAK
    ):
        return "mastered"
    return "review"


def review(
    card: Card,
    grade: Grade,
    now: Optional[datetime] = None,
    rng: Optional[random.Random] = None,
) -> ReviewOutcome:
    """Schedule the next sighting of `card` given how the learner just did."""
    if grade not in GRADES:
        raise ValueError(f"unknown grade {grade!r}; expected one of {GRADES}")

    now = now or _now()
    prev_state = card.state
    correct = grade != "again"

    c = replace(
        card,
        total_reviews=card.total_reviews + 1,
        total_correct=card.total_correct + (1 if correct else 0),
        last_reviewed_at=now,
        introduced_at=card.introduced_at or now,
        streak=card.streak + 1 if correct else 0,
    )

    graduated = lapsed = False

    # ---- brand new, or still inside the learning steps -------------------
    if c.state in ("new", "learning"):
        steps = LEARNING_STEPS_MIN
        if grade == "again":
            c = replace(c, state="learning", step_index=0)
            delay = timedelta(minutes=steps[0])
        elif grade == "easy":
            c = replace(c, state="review", step_index=0,
                        interval_days=EASY_INTERVAL_DAYS, repetitions=c.repetitions + 1)
            delay = timedelta(days=EASY_INTERVAL_DAYS)
            graduated = True
        else:
            step = c.step_index + (1 if grade == "good" else 0)
            if step >= len(steps):
                interval = GRADUATING_INTERVAL_DAYS
                c = replace(c, state="review", step_index=0,
                            interval_days=interval, repetitions=c.repetitions + 1)
                delay = timedelta(days=interval)
                graduated = True
            else:
                c = replace(c, state="learning", step_index=step)
                delay = timedelta(minutes=steps[step])

    # ---- a card the learner had already graduated -------------------------
    else:
        if grade == "again":
            lapsed = True
            new_ease = max(MIN_EASE, c.ease - 0.20)
            c = replace(
                c,
                state="learning",
                step_index=0,
                lapses=c.lapses + 1,
                ease=new_ease,
                # Keep some of the earned interval — a lapse is a wobble, not
                # amnesia, and resetting to zero makes mature cards punishing.
                interval_days=max(1.0, c.interval_days * 0.4),
                repetitions=0,
            )
            delay = timedelta(minutes=RELEARNING_STEPS_MIN[0])
        else:
            ease_delta = {"hard": -0.15, "good": 0.0, "easy": 0.15}[grade]
            new_ease = min(MAX_EASE, max(MIN_EASE, c.ease + ease_delta))
            factor = {"hard": 1.2, "good": new_ease, "easy": new_ease * 1.3}[grade]
            interval = min(MAX_INTERVAL_DAYS, max(1.0, c.interval_days * factor))
            interval = _fuzz(interval, rng)

            # Reviewing a card early — because the learner is cramming, or
            # drilling ahead of an exam — must not compound the interval.
            # Recalling something a day after you last saw it is no evidence
            # that you will recall it in three months, so an early review
            # reschedules without growing the interval.
            if card.due_at is not None and now < card.due_at:
                interval = min(interval, max(1.0, card.interval_days))
            c = replace(
                c,
                ease=new_ease,
                interval_days=interval,
                repetitions=c.repetitions + 1,
                state="review",
            )
            delay = timedelta(days=interval)

    c = replace(c, due_at=now + delay)
    c = replace(c, state=_classify(c, now))

    return ReviewOutcome(
        card=c,
        previous_state=prev_state,
        next_due_in=_humanise(delay),
        graduated=graduated,
        lapsed=lapsed,
        mastered=c.state == "mastered" and prev_state != "mastered",
    )


def preview_intervals(card: Card, now: Optional[datetime] = None) -> dict[Grade, str]:
    """What each button would do — shown on the answer screen."""
    now = now or _now()
    return {g: review(card, g, now=now).next_due_in for g in GRADES}


# ==========================================================================
# Queue building
# ==========================================================================

@dataclass
class QueueLimits:
    new_per_day: int = 10
    reviews_per_day: int = 100
    #: Difficult cards are interleaved rather than dumped at the front, so a
    #: session does not open with a wall of the learner's worst items.
    difficult_share: float = 0.25


def build_queue(
    cards: Iterable[Card],
    limits: Optional[QueueLimits] = None,
    now: Optional[datetime] = None,
    introduced_today: int = 0,
    rng: Optional[random.Random] = None,
) -> list[Card]:
    """Order today's session: overdue first, new cards spread through it.

    Ordering rules, in priority order:
      1. Cards in a learning step that are due right now (finish what you started).
      2. Overdue review cards, most overdue first.
      3. New cards, up to the daily allowance, interleaved rather than blocked.
    """
    now = now or _now()
    limits = limits or QueueLimits()
    cards = list(cards)

    def due(c: Card) -> bool:
        return c.due_at is None or c.due_at <= now

    learning = [c for c in cards if c.state == "learning" and due(c)]
    difficult = [c for c in cards if c.state == "difficult" and due(c)]
    reviews = [c for c in cards if c.state in ("review", "mastered") and due(c)]
    new = [c for c in cards if c.state == "new"]

    learning.sort(key=lambda c: c.due_at or now)
    difficult.sort(key=lambda c: c.due_at or now)
    reviews.sort(key=lambda c: c.due_at or now)

    review_budget = max(0, limits.reviews_per_day)
    n_difficult = min(len(difficult), int(review_budget * limits.difficult_share))
    body = difficult[:n_difficult] + reviews[: review_budget - n_difficult]
    if rng is not None:
        rng.shuffle(body)

    new_budget = max(0, limits.new_per_day - introduced_today)
    picked_new = new[:new_budget]

    # Interleave new cards evenly through the review body rather than
    # front-loading them: meeting ten unknown words in a row is the fastest
    # way to make someone quit.
    if picked_new and body:
        out: list[Card] = []
        gap = max(1, len(body) // (len(picked_new) + 1))
        ni = 0
        for i, c in enumerate(body):
            out.append(c)
            if ni < len(picked_new) and (i + 1) % gap == 0:
                out.append(picked_new[ni])
                ni += 1
        out.extend(picked_new[ni:])
    else:
        out = body + picked_new

    return learning + out


def queue_summary(cards: Iterable[Card], now: Optional[datetime] = None) -> dict:
    """Counts for the dashboard, by state and by what is due."""
    now = now or _now()
    cards = list(cards)
    by_state: dict[str, int] = {s: 0 for s in
                                ("new", "learning", "review", "difficult", "mastered")}
    due_now = 0
    for c in cards:
        by_state[c.state] = by_state.get(c.state, 0) + 1
        if c.state != "new" and (c.due_at is None or c.due_at <= now):
            due_now += 1

    tomorrow = now + timedelta(days=1)
    due_tomorrow = sum(
        1 for c in cards
        if c.state != "new" and c.due_at is not None and now < c.due_at <= tomorrow
    )

    reviewed = [c for c in cards if c.total_reviews]
    accuracy = (
        sum(c.total_correct for c in reviewed) / sum(c.total_reviews for c in reviewed)
        if reviewed else None
    )

    return {
        "total": len(cards),
        "by_state": by_state,
        "due_now": due_now,
        "due_tomorrow": due_tomorrow,
        "accuracy": accuracy,
        "known": by_state["review"] + by_state["mastered"],
    }


def retention_forecast(cards: Iterable[Card], days: int = 30,
                       now: Optional[datetime] = None) -> list[dict]:
    """How many reviews fall on each of the next `days` days."""
    now = now or _now()
    buckets = [0] * days
    for c in cards:
        if c.state == "new" or c.due_at is None:
            continue
        offset = (c.due_at - now).days
        if 0 <= offset < days:
            buckets[offset] += 1
        elif offset < 0:
            buckets[0] += 1
    start = now.date()
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "count": n}
        for i, n in enumerate(buckets)
    ]
