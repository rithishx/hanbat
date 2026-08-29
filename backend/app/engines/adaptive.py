"""
Adaptive layer: what does this learner not know, and what should happen next.

Three jobs:

  1. Turn a stream of graded attempts into a picture of the learner — per
     skill, per topic, and per *confusion pair*, because most learner mistakes
     are not "wrong" but "picked the wrong one of two".
  2. Decide what to serve next, and say why in words the learner can read.
  3. When a confusion becomes chronic, assemble a targeted mini-course for it
     instead of waiting for the curriculum to circle back.

Everything here is language-neutral. The engine never knows what language it
is looking at — it takes a language code, asks the registry for that language's
confusion pairs and level ladder, and works with whatever comes back. A
language that has registered neither still gets full skill and item tracking.

Mini-courses are assembled from real authored content in the language module,
not generated on the fly: a learner who keeps mixing up 은/는 and 이/가 needs
the actual explanation, not a rephrasing of the exercise they just failed.
"""

from __future__ import annotations

import importlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Literal, Optional

from ..languages import registry

Skill = Literal["reading", "listening", "writing", "speaking", "grammar", "vocabulary", "pronunciation"]
SKILLS: tuple[Skill, ...] = (
    "reading", "listening", "writing", "speaking", "grammar", "vocabulary", "pronunciation",
)

SKILL_NAMES_EN = {
    "reading": "Reading", "listening": "Listening", "writing": "Writing",
    "speaking": "Speaking", "grammar": "Grammar", "vocabulary": "Vocabulary",
    "pronunciation": "Pronunciation",
}


def native_skill_names(language: str) -> dict[str, str]:
    """What this language calls the four skills, for the progress screen.

    Korean shows 읽기/듣기/쓰기/말하기, Japanese 読む/聞く/書く/話す, Mandarin
    阅读/听力/写作/口语. A language that has not supplied them falls back to
    English rather than showing another language's words.
    """
    spec = registry.try_get(language)
    if spec is None or not spec.levels_module:
        return dict(SKILL_NAMES_EN)
    try:
        module = importlib.import_module(spec.levels_module)
    except ModuleNotFoundError:
        return dict(SKILL_NAMES_EN)
    names = getattr(module, "SKILL_NAMES", None) or {}
    return {s: names.get(s, SKILL_NAMES_EN[s]) for s in SKILLS}

#: There is deliberately no shared level ladder here. Korean, Japanese and
#: Mandarin band progress on different scales (CEFR/TOPIK, JLPT, HSK) with
#: vocabulary thresholds that differ by a factor of three. Each language module
#: owns its ladder; this engine asks the registry for it.


# ==========================================================================
# Attempt records
# ==========================================================================

@dataclass
class Attempt:
    """One graded interaction. Everything downstream is built from these."""

    skill: Skill
    correct: bool
    #: Which language this attempt belongs to. Attempts never mix across
    #: languages — a Korean mistake must not affect a Japanese score.
    language: str = ""
    item_type: str = ""          # vocab | grammar | script | sentence | ...
    item_id: str = ""
    expected: str = ""           # the right answer
    given: str = ""              # what the learner produced
    lesson_id: str = ""
    topic: str = ""
    level: str = ""
    response_ms: int = 0
    at: Optional[datetime] = None

    def __post_init__(self):
        if self.at is None:
            self.at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["at"] = self.at.isoformat() if self.at else None
        return d


# ==========================================================================
# Known confusion pairs, with their remedies
# ==========================================================================

def identify_confusion(language: str, expected: str, given: str) -> Optional[str]:
    """Map a wrong answer onto a known confusion for `language`, if it is one.

    Returns None when the language has registered no confusions, which is the
    normal state for a language whose module is still being built. The caller
    degrades to generic per-item weakness tracking rather than failing.
    """
    if not expected or not given or expected == given:
        return None
    spec = registry.try_get(language)
    if spec is None:
        return None
    try:
        module = importlib.import_module(spec.confusions_module) if spec.confusions_module else None
    except ModuleNotFoundError:
        return None
    index = getattr(module, "PAIR_INDEX", None) if module else None
    if not index:
        return None
    return index.get(frozenset((expected.strip(), given.strip())))


def confusions_for(language: str) -> dict:
    """Every confusion this language has registered, keyed by id."""
    spec = registry.try_get(language)
    if spec is None:
        return {}
    try:
        return spec.confusions
    except ModuleNotFoundError:
        return {}


# ==========================================================================
# Learner model
# ==========================================================================

#: Attempts older than this contribute less. Recent evidence matters more,
#: but old evidence is never thrown away entirely.
HALF_LIFE_DAYS = 21.0

#: How many times a confusion must recur before it earns its own mini-course.
MINI_COURSE_THRESHOLD = 3


def _weight(at: datetime, now: datetime) -> float:
    age_days = max(0.0, (now - at).total_seconds() / 86400)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


@dataclass
class SkillScore:
    skill: Skill
    name: str                  # English label
    native_name: str           # what the target language calls this skill
    score: float               # 0-100
    attempts: int
    confidence: float          # 0-1, how much evidence backs the score

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LearnerModel:
    skills: dict[str, SkillScore] = field(default_factory=dict)
    weak_items: list[dict] = field(default_factory=list)
    strong_items: list[dict] = field(default_factory=list)
    confusions: list[dict] = field(default_factory=list)
    topics: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    estimated_level: str = "unknown"
    total_attempts: int = 0

    def to_dict(self) -> dict:
        return {
            "skills": {k: v.to_dict() for k, v in self.skills.items()},
            "weak_items": self.weak_items,
            "strong_items": self.strong_items,
            "confusions": self.confusions,
            "topics": self.topics,
            "overall": self.overall,
            "estimated_level": self.estimated_level,
            "total_attempts": self.total_attempts,
        }


def build_model(
    attempts: Iterable[Attempt],
    language: str,
    now: Optional[datetime] = None,
    script_mastery: float = 0.0,
    vocab_known: int = 0,
    grammar_known: int = 0,
) -> LearnerModel:
    """Turn a history of attempts into a picture of the learner.

    `script_mastery` is 0-1 across whatever writing systems this language
    gates on: Hangul for Korean, kana for Japanese, pinyin for Mandarin.
    Attempts belonging to other languages are ignored rather than trusted,
    so a caller passing an unfiltered history cannot silently corrupt a score.
    """
    now = now or datetime.now(timezone.utc)
    attempts = [a for a in attempts if not a.language or a.language == language]

    skill_hit: dict[str, float] = defaultdict(float)
    skill_tot: dict[str, float] = defaultdict(float)
    skill_n: Counter = Counter()

    item_hit: dict[tuple, float] = defaultdict(float)
    item_tot: dict[tuple, float] = defaultdict(float)
    item_n: Counter = Counter()

    topic_hit: dict[str, float] = defaultdict(float)
    topic_tot: dict[str, float] = defaultdict(float)

    confusion_n: Counter = Counter()
    confusion_last: dict[str, datetime] = {}

    for a in attempts:
        w = _weight(a.at, now)
        skill_tot[a.skill] += w
        skill_n[a.skill] += 1
        if a.correct:
            skill_hit[a.skill] += w

        if a.item_id:
            key = (a.item_type, a.item_id)
            item_tot[key] += w
            item_n[key] += 1
            if a.correct:
                item_hit[key] += w

        if a.topic:
            topic_tot[a.topic] += w
            if a.correct:
                topic_hit[a.topic] += w

        if not a.correct:
            cid = identify_confusion(language, a.expected, a.given)
            if cid:
                confusion_n[cid] += 1
                confusion_last[cid] = max(confusion_last.get(cid, a.at), a.at)

    native = native_skill_names(language)
    skills: dict[str, SkillScore] = {}
    for s in SKILLS:
        tot = skill_tot.get(s, 0.0)
        score = 100.0 * (skill_hit.get(s, 0.0) / tot) if tot else 0.0
        n = skill_n.get(s, 0)
        skills[s] = SkillScore(
            skill=s,
            name=SKILL_NAMES_EN[s],
            native_name=native[s],
            score=round(score, 1),
            attempts=n,
            # Confidence saturates around 30 attempts; below that the score is
            # shown but labelled provisional in the UI.
            confidence=round(min(1.0, n / 30.0), 2),
        )

    def item_rows(ascending: bool) -> list[dict]:
        rows = []
        for key, tot in item_tot.items():
            if item_n[key] < 2:      # one data point is noise, not a weakness
                continue
            acc = item_hit[key] / tot if tot else 0.0
            rows.append({
                "item_type": key[0], "item_id": key[1],
                "accuracy": round(acc, 3), "attempts": item_n[key],
            })
        rows.sort(key=lambda r: r["accuracy"], reverse=not ascending)
        return rows

    weak = [r for r in item_rows(ascending=True) if r["accuracy"] < 0.7][:20]
    strong = [r for r in item_rows(ascending=False) if r["accuracy"] >= 0.9][:20]

    registered = confusions_for(language)
    confusions = []
    for cid, n in confusion_n.most_common():
        if cid not in registered:
            continue
        c = registered[cid]
        confusions.append({
            "id": cid,
            "language": language,
            "title": c.title,
            "one_line": c.one_line,
            "count": n,
            "last_seen": confusion_last[cid].isoformat(),
            "warrants_mini_course": n >= MINI_COURSE_THRESHOLD,
        })

    topics = {
        t: round(topic_hit[t] / tot, 3)
        for t, tot in topic_tot.items() if tot
    }

    graded = [s for s in skills.values() if s.attempts]
    overall = round(sum(s.score for s in graded) / len(graded), 1) if graded else 0.0

    return LearnerModel(
        skills=skills,
        weak_items=weak,
        strong_items=strong,
        confusions=confusions,
        topics=topics,
        overall=overall,
        estimated_level=estimate_level(language, script_mastery, vocab_known, grammar_known, overall),
        total_attempts=len(attempts),
    )


def estimate_level(
    language: str,
    script_mastery: float,
    vocab_known: int,
    grammar_known: int,
    accuracy: float,
) -> str:
    """Ask the language's own ladder where this learner sits.

    There is no shared banding here on purpose. Korean bands on CEFR/TOPIK,
    Japanese on JLPT N5-N1, Mandarin on HSK 1-6, and the vocabulary each band
    implies differs enormously — HSK 4 is around 1,200 words while JLPT N3 is
    around 3,700. A single shared scale would be wrong for at least two of the
    three languages, and "wrong" here means sending someone into material they
    cannot read.
    """
    spec = registry.try_get(language)
    if spec is None or not spec.levels_module:
        return "unknown"
    try:
        ladder = spec.levels
    except ModuleNotFoundError:
        return "unknown"
    if ladder is None:
        return "unknown"
    return ladder.estimate(script_mastery, vocab_known, grammar_known, accuracy)


def level_ladder(language: str) -> Optional[Any]:
    """The ordered level scheme for one language, or None if not registered."""
    spec = registry.try_get(language)
    if spec is None or not spec.levels_module:
        return None
    try:
        return spec.levels
    except ModuleNotFoundError:
        return None


# ==========================================================================
# What next?
# ==========================================================================

@dataclass
class Recommendation:
    kind: str                # review | mini_course | lesson | drill | rest
    title: str
    reason: str              # shown to the learner, in plain language
    payload: dict = field(default_factory=dict)
    priority: int = 0        # higher runs first

    def to_dict(self) -> dict:
        return asdict(self)


def recommend(
    model: LearnerModel,
    due_count: int = 0,
    minutes_available: int = 15,
    completed_lesson_ids: Optional[set[str]] = None,
    next_lesson: Optional[dict] = None,
    studied_today_minutes: int = 0,
) -> list[Recommendation]:
    """Answer the three questions the app must always be able to answer:
    what should I learn next, what do I need to review, and why do I keep
    making this mistake."""
    out: list[Recommendation] = []

    # 1. Chronic confusions come first — they block everything downstream.
    for c in model.confusions:
        if c["warrants_mini_course"]:
            out.append(Recommendation(
                kind="mini_course",
                title=c["title"],
                reason=(
                    f"You've mixed these up {c['count']} times. "
                    "Let's stop and sort it out properly — it will keep costing "
                    "you marks until you do."
                ),
                payload={"confusion_id": c["id"], "language": c.get("language", "")},
                priority=100 - c["count"],
            ))

    # 2. Overdue reviews.
    if due_count:
        out.append(Recommendation(
            kind="review",
            title=f"{due_count} card{'s' if due_count != 1 else ''} to review",
            reason=(
                "These are due today. Reviewing on the day something is due is "
                "what makes it stick — a day late roughly halves the benefit."
            ),
            payload={"count": due_count},
            priority=90 if due_count > 20 else 70,
        ))

    # 3. Weakest skill, if there is enough evidence to say so.
    graded = [s for s in model.skills.values() if s.attempts >= 10]
    if graded:
        worst = min(graded, key=lambda s: s.score)
        best = max(graded, key=lambda s: s.score)
        if best.score - worst.score >= 15:
            out.append(Recommendation(
                kind="drill",
                title=f"{worst.native_name} practice",
                reason=(
                    f"Your {worst.skill} is sitting at {worst.score:.0f}% while "
                    f"your {best.skill} is at {best.score:.0f}%. Lopsided skills "
                    "get harder to fix the longer you leave them."
                ),
                payload={"skill": worst.skill},
                priority=60,
            ))

    # 4. The next lesson in the path.
    if next_lesson:
        out.append(Recommendation(
            kind="lesson",
            title=next_lesson.get("title", "Next lesson"),
            reason="This is the next step on your path.",
            payload={"lesson_id": next_lesson.get("id")},
            priority=50,
        ))

    # 5. Honesty about diminishing returns.
    if studied_today_minutes >= 90:
        out.append(Recommendation(
            kind="rest",
            title="Call it a day",
            reason=(
                f"You've done {studied_today_minutes} minutes today. Past about "
                "an hour and a half, retention per minute drops off sharply. "
                "Tomorrow's session will be worth more than another twenty "
                "minutes now."
            ),
            priority=110,
        ))

    out.sort(key=lambda r: -r.priority)
    return out


def build_mini_course(language: str, confusion_id: str) -> dict:
    """Assemble a focused lesson for one chronic confusion."""
    c = confusions_for(language).get(confusion_id)
    if c is None:
        raise KeyError(
            f"{language!r} has no confusion registered under {confusion_id!r}"
        )

    return {
        "id": f"{language}-mini-{c.id}",
        "language": language,
        "generated": True,
        "title": c.title,
        "level": "adaptive",
        "why_you_are_seeing_this": (
            "You keep choosing one of these where the other belongs. This "
            "mini-course exists only for that."
        ),
        "steps": [
            {"step": "understand", "heading": "The one-line version",
             "body": c.one_line},
            {"step": "learn", "heading": "Said simply",
             "body": c.simple},
            {"step": "examples", "heading": "See it working",
             "examples": c.examples},
            {"step": "practice", "heading": "Your turn",
             "instruction": c.drill_prompt,
             "generator": {"type": "confusion_drill", "confusion_id": c.id}},
            {"step": "recall", "heading": "No hints this time",
             "generator": {"type": "confusion_drill", "confusion_id": c.id,
                           "hints": False, "count": 8}},
            {"step": "summary", "heading": "The rule, properly stated",
             "body": c.rule},
        ],
        "mastery_requires": {
            "correct_in_a_row": 8,
            "note": "and the same again in a review session two days from now",
        },
    }


def next_difficulty(recent: Iterable[Attempt], current: float = 0.5) -> float:
    """Nudge difficulty toward the band where the learner gets ~80% right.

    Too easy and nothing is learned; too hard and the session stops being
    survivable. 80% is roughly where effortful-but-successful recall lives.
    """
    recent = list(recent)[-20:]
    if len(recent) < 5:
        return current
    acc = sum(1 for a in recent if a.correct) / len(recent)
    if acc > 0.9:
        return min(1.0, current + 0.1)
    if acc < 0.65:
        return max(0.0, current - 0.1)
    return current
