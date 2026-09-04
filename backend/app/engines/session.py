"""
Today's session: one plan, composed rather than chosen.

The application could already answer "what should I do next" — it had a review
queue, a lesson list, a practice screen and a recommendation feed. What it
could not do was answer it *once*. A learner opening the app had to decide how
much reviewing was enough, whether to do a lesson or drill their weak skill,
and when to stop. That decision is made badly by everyone, every day, and
making it is not what they came for.

So this builds a single ordered plan out of the things that are actually due,
inside the minute budget the learner set, in the order that teaches best:

    1. Reviews         — what is already scheduled, and decays if skipped
    2. A confusion     — one chronic mistake, fixed properly, if there is one
    3. Weak skills     — drills chosen by the adaptive engine
    4. Something new   — the next lesson, or new words
    5. Production      — using it, which is the part everyone skips

That order is not arbitrary. Reviews come first because they are the only part
with a deadline: a card reviewed a week late has already been half-forgotten,
whereas a new lesson is equally new tomorrow. Production comes last because it
is the hardest and works best on material just refreshed.

Two things this deliberately does not do. It does not pad: a learner with
nothing due and no measured weakness gets a short session and is told why,
rather than being handed filler to fill fifteen minutes. And it never plans
around content that does not exist — a language whose grammar curriculum is
unwritten simply has no grammar block, and the plan says so.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Optional

from . import adaptive, exercises as X

#: Rough pacing, used only to fit blocks into the learner's budget. Deliberately
#: conservative: a plan that overruns its stated length is worse than one that
#: finishes early, because the learner stops trusting the number.
SECONDS_PER_REVIEW = 12
SECONDS_PER_EXERCISE = 20

#: Reviews are the only part with a deadline, but a session that is nothing but
#: reviews is how people quit. Past this share, the rest of the queue waits for
#: tomorrow and the plan says so.
MAX_REVIEW_SHARE = 0.55

#: Below this, there is no room for anything but reviews.
MIN_SESSION_MINUTES = 3


@dataclass
class Block:
    """One segment of the session."""

    id: str
    #: review | remediation | confusion | weakness | calibrate | lesson |
    #: vocabulary | production
    kind: str
    title: str
    #: Why this is here, in language a learner can disagree with.
    why: str
    minutes: int
    skill: str = ""
    #: What the runner needs to execute it. Shape depends on `kind`.
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionPlan:
    language: str
    minutes: int
    blocks: list[Block] = field(default_factory=list)
    #: An honest sentence about what this session is and is not.
    note: str = ""
    generated_at: str = ""
    #: Skills the plan is deliberately aiming at, for the dashboard to show.
    focus: list[dict] = field(default_factory=list)

    @property
    def planned_minutes(self) -> int:
        return sum(b.minutes for b in self.blocks)

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "minutes": self.minutes,
            "planned_minutes": self.planned_minutes,
            "blocks": [b.to_dict() for b in self.blocks],
            "note": self.note,
            "focus": self.focus,
            "generated_at": self.generated_at,
        }


def build(
    *,
    language: str,
    model: adaptive.LearnerModel,
    due_now: int = 0,
    minutes: int = 15,
    mistake_reasons: Optional[dict[str, int]] = None,
    next_lesson: Optional[dict] = None,
    new_vocab: int = 0,
    has_grammar: bool = False,
    #: Whether this language has a sentence bank. Without one, sentence-based
    #: drills are simply not planned — a block that would render "no sentences
    #: written yet" is worse than no block.
    has_sentences: bool = False,
    #: The single most-failed specific point, if one has crossed the
    #: remediation threshold. A dict rather than an object so this engine stays
    #: free of any dependency on how the caller found it — and `None` when
    #: nothing has failed often enough, which is the normal state for a new
    #: learner and produces no block at all.
    weak_point: Optional[dict] = None,
    studied_today: int = 0,
    seed: Optional[int] = None,
) -> SessionPlan:
    """Compose today's session.

    Every argument describes what actually exists — how many cards are really
    due, whether this language really has grammar content — so the plan can
    never contain a block pointing at nothing.
    """
    import random

    rng = random.Random(seed)
    budget = max(0, minutes)
    plan = SessionPlan(
        language=language,
        minutes=budget,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    focus_list = adaptive.focus(model, mistake_reasons)
    plan.focus = [f.to_dict() for f in focus_list[:4]]
    weights = {f.skill: f.weight for f in focus_list}

    remaining = budget

    # -- 1. reviews, first and capped ------------------------------------
    if due_now > 0 and remaining > 0:
        wanted = _minutes_for(due_now * SECONDS_PER_REVIEW)
        cap = max(1, int(budget * MAX_REVIEW_SHARE))
        take = min(wanted, cap, remaining)
        cards = min(due_now, max(1, (take * 60) // SECONDS_PER_REVIEW))
        deferred = due_now - cards
        plan.blocks.append(Block(
            id="review",
            kind="review",
            title=f"Review {cards} card{'' if cards == 1 else 's'}",
            why=("These are due now. Reviews are the only part of this with a "
                 "deadline — everything else is just as new tomorrow, and a "
                 "card left a week is half forgotten."
                 + (f" {deferred} more will wait for tomorrow so this session "
                    f"is not only reviewing." if deferred > 0 else "")),
            minutes=take,
            skill="",
            payload={"count": cards, "deferred": deferred},
        ))
        remaining -= take

    # -- 2a. one specific thing that keeps failing ------------------------
    #
    # Ahead of the generic weakness drill, and ahead of the confusion, because
    # it is the most specific thing the app knows. "You have dropped this rule
    # four times" beats "pronunciation is your weakest skill" as a use of eight
    # minutes, and it is the only block that teaches before it drills.
    if weak_point and remaining >= 4:
        take = min(remaining, max(4, int(weak_point.get("minutes") or 6)))
        plan.blocks.append(Block(
            id=f"remediation-{weak_point['id']}",
            kind="remediation",
            title=f"Fix: {weak_point['title']}",
            why=(f"This has gone wrong {weak_point['failures']} times, which is "
                 f"a pattern rather than bad luck. Repeating the same question "
                 f"would not help, so this explains it and then drills it in a "
                 f"different form."),
            minutes=take,
            skill=weak_point.get("skill", ""),
            payload={"point_id": weak_point["id"]},
        ))
        remaining -= take

    # -- 2b. one chronic confusion ----------------------------------------
    chronic = next((c for c in model.confusions if c.get("warrants_mini_course")), None)
    if chronic and remaining >= 4:
        plan.blocks.append(Block(
            id=f"confusion-{chronic['id']}",
            kind="confusion",
            title=chronic["title"],
            why=(f"You have mixed these up {chronic['count']} times. One "
                 f"explanation now costs less than the next ten mistakes."),
            minutes=4,
            skill="grammar",
            payload={"confusion_id": chronic["id"]},
        ))
        remaining -= 4

    # -- 3. weak skills, drilled with real generators --------------------
    if remaining >= 3 and weights:
        take = min(remaining, max(3, round(budget * 0.3)))
        n = max(4, (take * 60) // SECONDS_PER_EXERCISE)
        kinds = X.choose_kinds(language, weights, n, rng,
                               exclude=_unbuildable(has_sentences))
        if kinds:
            named = [f for f in focus_list if f.skill in
                     {X.skill_for(language, k) for k in kinds}][:2]
            # Before anything has been measured there is no "weakest" skill,
            # and claiming one would be the app asserting something it does not
            # know. The same block does a different, honest job instead: it
            # spreads across skills to find out where the learner stands.
            measured = [f for f in named if f.attempts > 0]
            # The full measured ranking, so the copy can tell whether this
            # block actually landed on the weakest skill or merely on a weak
            # one. Claiming the former when only the latter is true is the kind
            # of small lie a learner catches, and then stops trusting the rest.
            ranked = [f for f in focus_list if f.attempts > 0]
            plan.blocks.append(Block(
                id="weakness",
                kind="weakness" if measured else "calibrate",
                title="Work on what is weakest" if measured and
                      measured[0].skill == ranked[0].skill
                      else "Practice where you are weak" if measured
                      else "A spread, to see where you stand",
                why=_why_weak(measured, ranked) if measured else (
                    "Nothing has been measured yet, so this is a mix across "
                    "skills rather than a targeted drill. After a few sessions "
                    "the app will know where to push."),
                minutes=take,
                skill=measured[0].skill if measured else "",
                payload={"specs": _specs(kinds)},
            ))
            remaining -= take

    # -- 4. something new -------------------------------------------------
    if remaining >= 4 and next_lesson:
        take = min(remaining, max(4, int(next_lesson.get("est_minutes") or 8)))
        plan.blocks.append(Block(
            id=f"lesson-{next_lesson['id']}",
            kind="lesson",
            title=next_lesson.get("title", "Next lesson"),
            why="The next step on your path. New material goes in best after "
                "you have warmed up on things you already know.",
            minutes=take,
            payload={"lesson_id": next_lesson["id"]},
        ))
        remaining -= take
    elif remaining >= 3 and new_vocab > 0:
        take = min(remaining, 4)
        plan.blocks.append(Block(
            id="vocabulary",
            kind="vocabulary",
            title="Meet some new words",
            why="No lesson is waiting, so this is straight vocabulary. New "
                "words are introduced both ways round — recognising one is "
                "not the same as being able to say it.",
            minutes=take,
            skill="vocabulary",
            payload={"specs": _specs(["vocab_recognise", "vocab_recall"])},
        ))
        remaining -= take

    # -- 5. production, last and only if there is room --------------------
    #
    # Production is the part everyone skips and the only part that turns
    # recognition into use, so it gets its own block rather than being left to
    # chance in the weakness mix.
    if remaining >= 3:
        blocked = _unbuildable(has_sentences)
        produce = [k for k in X.kinds_by_skill(language).get("writing", [])
                   if k in ("translate_to_target", "concept_to_target",
                            "concept_to_korean", "structure_produce")
                   and k not in blocked]
        speak = [k for k in X.kinds_by_skill(language).get("speaking", [])
                 if k not in blocked]
        kinds = (produce[:1] or []) + (speak[:1] or [])
        if kinds:
            take = min(remaining, 3)
            plan.blocks.append(Block(
                id="production",
                kind="production",
                title="Use it yourself",
                why="Recognising a word and producing it are different skills, "
                    "and only the second one survives a conversation. This is "
                    "the part that is easy to skip and shouldn't be.",
                minutes=take,
                skill="writing",
                payload={"specs": _specs(kinds)},
            ))
            remaining -= take

    plan.note = _note(plan, due_now, studied_today, has_grammar, model)
    return plan


# ==========================================================================

#: Drills that need a sentence bank behind them.
SENTENCE_KINDS = frozenset({
    "translate_to_english", "translate_to_target",
    "sentence_complete", "sentence_order",
})


def _unbuildable(has_sentences: bool) -> frozenset[str]:
    return frozenset() if has_sentences else SENTENCE_KINDS


def _specs(kinds: list[str]) -> list[dict]:
    """Generator specs, deduplicated but order-preserving."""
    seen: set[str] = set()
    out = []
    for k in kinds:
        if k in seen:
            continue
        seen.add(k)
        out.append({"type": k, "count": 4})
    return out


def _minutes_for(seconds: int) -> int:
    return max(1, round(seconds / 60))


def _why_weak(named: list[adaptive.SkillFocus],
              ranked: list[adaptive.SkillFocus]) -> str:
    """Explain the block without overstating what it landed on.

    The drills are drawn with weights and a floor, not picked off the top of
    the ranking, so the block does not always include the single weakest skill.
    On the sessions where it does not, "vocabulary is your weakest skill" would
    be false — and *visibly* false, because the ranked focus list is on the same
    screen a few centimetres below. So the superlative is used only when it is
    true, and otherwise the block says plainly what it is drilling.
    """
    if not named:
        return "A mix of drills across the skills you have measured."

    top = ranked[0] if ranked else None
    a = named[0]
    leads = top is not None and a.skill == top.skill

    if len(named) == 1:
        if leads:
            return f"{a.skill.capitalize()} is your weakest measured skill. {a.why}"
        return (f"This block drills {a.skill}. {a.why}"
                + (f" {top.skill.capitalize()} scores lower and is what the app "
                   f"is aiming at overall — the draw is weighted rather than "
                   f"fixed, because hammering one skill works worse than mixing."
                   if top else ""))

    b = named[1]
    tail = ("Mixed rather than drilled one at a time, because interleaving "
            "sticks better than blocking.")
    if leads:
        return f"{a.skill.capitalize()} and {b.skill} need the most work. {a.why} {tail}"
    return f"This block drills {a.skill} and {b.skill}. {a.why} {tail}"


def _note(plan: SessionPlan, due_now: int, studied_today: int,
          has_grammar: bool, model: adaptive.LearnerModel) -> str:
    """One honest sentence about what this session is.

    In particular: when there is nothing to do, say so. Padding a session to
    fill the learner's stated fifteen minutes would be the app inventing work,
    and a learner who notices that stops believing the rest of it.
    """
    if not plan.blocks:
        return ("Nothing is due and there is no lesson waiting. That is a real "
                "answer, not an empty screen — come back tomorrow, or browse "
                "the vocabulary if you want to get ahead.")

    if plan.planned_minutes < plan.minutes - 2:
        return (f"About {plan.planned_minutes} minutes today rather than "
                f"{plan.minutes}. There is not enough genuinely due to fill "
                f"the full session, and padding it would waste your time.")

    if studied_today > 0:
        return (f"You have already done {studied_today} minutes today. This is "
                f"extra — useful, but the streak is safe either way.")

    if model.total_attempts < 10:
        return ("Early days, so this is mostly new material. The plan gets more "
                "pointed once there is enough evidence to know where you "
                "struggle.")

    if due_now == 0:
        return ("Nothing was due, so this session is all forward motion rather "
                "than maintenance.")

    return "Reviews first, then the weak spots, then something new."
