"""
Why an answer was wrong — not just that it was.

The application already recorded *which skill* a mistake happened in. That is
not the same question. "You got a listening question wrong" tells a learner
nothing they did not already know; "you heard it correctly and mistyped it" and
"you have never met this word" are different problems with different fixes, and
lumping them together makes the mistake list a scoreboard instead of a study
plan.

So every wrong answer is classified into one of seven reasons:

    vocabulary · grammar · pronunciation · listening · writing · reading
    · careless

Six of those come from what the exercise was actually testing, which the
generator already declares. The seventh — careless — is the interesting one,
because it is the only reason that should *not* schedule extra study. A learner
who knows 먹어요 and typed 먹여요 at speed does not need the word re-taught; they
need to slow down. Treating that as a vocabulary gap wastes their time and,
worse, teaches the adaptive engine that a word they know is a weakness.

Everything here is deterministic. No model is consulted, and none is needed:
the signals are prior performance on the same item, response time against the
learner's own baseline, and how close the wrong answer was to the right one.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional

#: The seven reasons. Ordered roughly from "needs teaching" to "needs care".
REASONS: tuple[str, ...] = (
    "vocabulary", "grammar", "pronunciation", "listening",
    "reading", "writing", "careless",
)

#: What each reason means, in the learner's terms, and what to do about it.
#: This is what the My Mistakes screen shows above each group, so it is written
#: to be read by someone who is mildly annoyed at having got something wrong.
REASON_INFO: dict[str, dict[str, str]] = {
    "vocabulary": {
        "name": "Vocabulary",
        "simple": "You did not know the word, or knew it in one direction only.",
        "advice": "These come back as reviews. Recognising a word is not the "
                  "same as being able to produce it, so the drills will ask "
                  "you both ways.",
    },
    "grammar": {
        "name": "Grammar",
        "simple": "You knew the words but joined them the wrong way.",
        "advice": "Usually one rule, not many separate errors. Look for the "
                  "pattern below — fixing the rule fixes all of them at once.",
    },
    "pronunciation": {
        "name": "Pronunciation",
        "simple": "The sounds, or the way spelling and sound come apart.",
        "advice": "The pronunciation lab shows the rule that changed the "
                  "sound. Hearing it once with the reason attached is worth "
                  "more than ten repetitions without.",
    },
    "listening": {
        "name": "Listening",
        "simple": "You could not catch it at speed.",
        "advice": "The most common cause is a sound contrast your ear has not "
                  "separated yet. Minimal pairs fix that faster than more "
                  "listening practice does.",
    },
    "reading": {
        "name": "Reading",
        "simple": "The writing system itself — a letter, a character, or how "
                  "they combine.",
        "advice": "Worth going back to the writing system module. Everything "
                  "else is slower while reading is effortful.",
    },
    "writing": {
        "name": "Writing and production",
        "simple": "You could not build it yourself, even though you would "
                  "recognise it.",
        "advice": "This is normal and it is the last thing to arrive. "
                  "Production drills are the only thing that moves it.",
    },
    "careless": {
        "name": "Careless slips",
        "simple": "You knew this. It was a typo, or you answered too fast.",
        "advice": "Deliberately not scheduled for extra study — you do not "
                  "need the word retaught. If there are a lot of these, slow "
                  "down rather than practise more.",
    },
}

#: Exercise skill -> reason. Six of the seven map straight across, because the
#: generator already declares what it exercises. Speaking is reported as
#: pronunciation: a learner who mispronounces does not experience it as a
#: separate "speaking" problem, and the fix is the same either way.
_SKILL_TO_REASON: dict[str, str] = {
    "vocabulary": "vocabulary",
    "grammar": "grammar",
    "pronunciation": "pronunciation",
    "speaking": "pronunciation",
    "listening": "listening",
    "reading": "reading",
    "writing": "writing",
}

#: Confusion tags that mean the pair is about sound rather than structure.
#: Every language module already tags its own confusions; this reads those tags
#: rather than knowing anything about any particular language.
_SOUND_TAGS = frozenset({"pronunciation", "tones", "sounds", "vowels", "hangul"})


@dataclass
class ItemHistory:
    """What this learner has done with this exact item before.

    Supplied by the caller from the attempt log. Empty history is the normal
    case for a first encounter and never produces a careless verdict — you
    cannot be careless with something you have never seen.
    """

    seen: int = 0
    correct: int = 0
    last_was_correct: bool = False
    #: The learner's own median response time for this kind of exercise, in
    #: milliseconds. Compared against, rather than a fixed threshold, because
    #: "fast" means something different for a beginner and for someone at B2.
    median_response_ms: int = 0

    @property
    def ever_correct(self) -> bool:
        return self.correct > 0


@dataclass
class Diagnosis:
    reason: str
    #: 0-1. Below `UNCERTAIN` the UI says "probably" rather than asserting.
    confidence: float
    #: Why this verdict, in one sentence the learner can check against memory.
    because: str
    evidence: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return REASON_INFO[self.reason]["name"]

    @property
    def counts_as_weakness(self) -> bool:
        """Careless slips must not feed the adaptive engine.

        This is the whole reason the taxonomy exists. A learner who keeps
        mistyping a word they know should not have that word pushed at them
        more often — that is the system misreading haste as ignorance.
        """
        return self.reason != "careless"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["name"] = self.name
        d["counts_as_weakness"] = self.counts_as_weakness
        d.update({k: v for k, v in REASON_INFO[self.reason].items() if k != "name"})
        return d


UNCERTAIN = 0.6

#: A typed answer this close to the right one was a slip, not a gap.
NEAR_MISS_DISTANCE = 1

#: ...but only when the answer is long enough for "one character out" to mean
#: anything. On a one-character answer, distance 1 is not a near miss — it is a
#: completely different answer. 은 and 는 differ by one character and are the
#: single most consequential particle distinction in Korean; excusing that as a
#: typo would hide the exact confusion the adaptive engine exists to catch.
NEAR_MISS_MIN_LENGTH = 3

#: Faster than this fraction of the learner's own median means they did not
#: really read the question.
RUSHED_FRACTION = 0.45

#: Below this, a response time is not evidence of anything — it is a
#: double-click or a stuck key.
MIN_MEANINGFUL_MS = 250


# ==========================================================================

def diagnose(
    *,
    skill: str,
    expected: str = "",
    given: str = "",
    response_ms: int = 0,
    history: Optional[ItemHistory] = None,
    confusion_tags: tuple[str, ...] = (),
    had_options: bool = False,
) -> Diagnosis:
    """Classify one wrong answer.

    `skill` is what the generator declared it was exercising, so this stays
    language-neutral: it never inspects the text for Korean particles or
    Mandarin tones, it asks what the exercise was for.
    """
    h = history or ItemHistory()

    # -- careless, checked first because it overrides everything ----------
    #
    # Order matters. A near-miss on a word you have had right before is a slip
    # whatever skill the exercise claimed to test, and calling it a vocabulary
    # gap would be the system arguing with evidence it already holds.
    slip = _careless(expected, given, response_ms, h, had_options)
    if slip is not None:
        return slip

    # -- a matched confusion knows better than the skill label ------------
    if confusion_tags:
        if _SOUND_TAGS & set(confusion_tags):
            return Diagnosis(
                "pronunciation", 0.85,
                "This pair is a sound distinction, not a spelling one.",
                {"confusion_tags": list(confusion_tags)},
            )
        return Diagnosis(
            "grammar", 0.85,
            "This is a known pair that learners mix up — a rule, not a slip.",
            {"confusion_tags": list(confusion_tags)},
        )

    # -- otherwise, what the exercise was testing -------------------------
    reason = _SKILL_TO_REASON.get(skill, "grammar")
    because = {
        "vocabulary": "You were being asked for a word.",
        "grammar": "You were being asked to build or choose a form.",
        "pronunciation": "You were being asked how it sounds.",
        "listening": "You were being asked what you heard.",
        "reading": "You were being asked to read it.",
        "writing": "You were being asked to produce it yourself.",
    }[reason]

    # An empty answer is a gap, and a confident one: the learner did not
    # attempt it. Explicitly *not* careless, whatever the response time says.
    if not given.strip():
        return Diagnosis(reason, 0.9, "You left it blank, so this is something "
                                      "to learn rather than a slip.",
                         {"blank": True})

    return Diagnosis(reason, 0.75 if h.seen else 0.65, because,
                     {"seen_before": h.seen})


def _careless(
    expected: str,
    given: str,
    response_ms: int,
    h: ItemHistory,
    had_options: bool,
) -> Optional[Diagnosis]:
    """Was this a slip rather than a gap?

    Three signals, and the first is close to necessary: a learner must have had
    this item right before. Without that, a near-miss is just as likely to be a
    half-learned word, and calling it carelessness would let real gaps hide.
    """
    if not given.strip() or not expected.strip():
        return None
    if not h.ever_correct:
        return None

    # A multiple-choice answer cannot be a typo. Picking the wrong option is a
    # decision, and treating it as a slip would excuse a real confusion.
    target = _normalise(expected)
    if not had_options and len(target) >= NEAR_MISS_MIN_LENGTH:
        distance = edit_distance(target, _normalise(given))
        if 0 < distance <= NEAR_MISS_DISTANCE:
            return Diagnosis(
                "careless", 0.9,
                f"One character out of “{expected}”, on something you have had "
                f"right before.",
                {"edit_distance": distance, "previously_correct": h.correct},
            )

    rushed = (
        h.median_response_ms > MIN_MEANINGFUL_MS
        and MIN_MEANINGFUL_MS < response_ms < h.median_response_ms * RUSHED_FRACTION
    )
    if rushed and h.last_was_correct:
        return Diagnosis(
            "careless", 0.7,
            "Answered much faster than you usually do, on something you had "
            "right last time.",
            {"response_ms": response_ms, "your_median_ms": h.median_response_ms},
        )
    return None


# ==========================================================================
# Text comparison
# ==========================================================================

def _normalise(s: str) -> str:
    return "".join(ch for ch in s.strip().lower() if not ch.isspace())


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance, iterative, two rows.

    Written out rather than pulled from a dependency because it is fifteen
    lines and this project ships without optional packages by default.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,          # deletion
                current[j - 1] + 1,       # insertion
                previous[j - 1] + (ca != cb),   # substitution
            ))
        previous = current
    return previous[-1]


def summarise(reasons: list[str]) -> dict:
    """Group a learner's mistake reasons into something worth acting on.

    Returns the counts, the dominant reason, and — deliberately — the count of
    careless slips kept separate from everything else, because a learner with
    thirty careless slips and two real gaps has a completely different problem
    from one with thirty vocabulary gaps.
    """
    counts = {r: reasons.count(r) for r in REASONS if r in reasons}
    real = {r: n for r, n in counts.items() if r != "careless"}
    dominant = max(real, key=lambda r: real[r]) if real else None
    total_real = sum(real.values())
    careless = counts.get("careless", 0)

    note = ""
    if careless and total_real and careless >= total_real:
        note = ("Most of your mistakes are slips rather than gaps. Slowing "
                "down will do more for you than more practice.")
    elif dominant and total_real:
        share = real[dominant] / total_real
        if share >= 0.5:
            note = (f"{REASON_INFO[dominant]['name']} accounts for most of "
                    f"them. That is one thing to fix, not many.")

    return {
        "counts": counts,
        "dominant": dominant,
        "real_total": total_real,
        "careless_total": careless,
        "note": note,
    }
