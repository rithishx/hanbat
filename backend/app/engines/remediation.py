"""
From "you are weak at pronunciation" to "you keep getting 연음 wrong".

The adaptive engine works at the level of *skills* — seven of them, which is
the right granularity for deciding how to spend a session. It is the wrong
granularity for fixing anything. "Pronunciation is your weakest skill" is a
diagnosis a learner cannot act on; "you have dropped the linking rule four
times this week, here it is, now hear it, say it and use it" is.

This module is the bridge. Three things live here:

**Focus points.** The specific, teachable units a mistake can be attributed to
— one pronunciation rule, one grammar point, one confusion pair. Every one of
them is read from the language's *own* engines, so nothing here knows what a
받침 or a mora or a tone is. A language that publishes no rule index simply
contributes no pronunciation focus points, and the rest still works.

**Attribution.** Given one wrong answer, which focus point caused it. This is
deterministic — it re-runs the language's own phonology on the expected string
and looks at which rules fired — and it *refuses* when the evidence is
ambiguous. Two rules fired and the learner's answer does not isolate either?
Then the honest answer is "not attributed", not a coin flip stored as a fact.

**Remediation.** When one point has failed repeatedly, a plan that fixes it
across modalities rather than drilling the same question again: understand it,
hear it, say it, then produce it. The examples come from the point itself, so
the learner practises the exact thing they got wrong.

Everything here takes its data as arguments. No database, no I/O, so the whole
chain is testable without a learner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from ..languages import registry

#: How many times one point must fail before it earns its own remediation.
#:
#: Two is a coincidence — everyone mistypes, and everyone meets a rule on a bad
#: day. Three is a pattern, and a pattern is the thing worth spending eight
#: minutes of a session on. Set this lower and the app nags about noise; set it
#: higher and it watches a learner fail the same rule all week in silence.
REMEDIATION_THRESHOLD = 3

#: Namespaces. A focus id is `<kind>:<id>` so that a grammar point and a
#: pronunciation rule can never collide, and so the kind is readable in the
#: database without a join.
PRONUNCIATION = "pron"
GRAMMAR = "grammar"
CONFUSION = "confusion"

#: Skills whose mistakes are worth re-running through the phonology engine.
#: A vocabulary slip on a written prompt tells us nothing about sound rules.
SOUND_SKILLS = frozenset({"pronunciation", "listening", "speaking"})


@dataclass(frozen=True)
class FocusPoint:
    """One specific thing a learner can be weak at, and be taught."""

    id: str
    kind: str
    #: The skill this point belongs to, for the adaptive engine's benefit.
    skill: str
    title: str
    native_title: str = ""
    #: Patient-teacher first, terminology second. Both come from the language.
    simple: str = ""
    technical: str = ""
    #: Strings in the target language that exercise this point. These are what
    #: the drills are built from, so they are never invented here.
    examples: tuple[str, ...] = ()
    #: The id inside its own namespace, for looking the source back up.
    source_id: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "skill": self.skill,
            "title": self.title, "native_title": self.native_title,
            "simple": self.simple, "technical": self.technical,
            "examples": list(self.examples), "source_id": self.source_id,
        }


# ==========================================================================
# The catalogue
# ==========================================================================

def catalogue(language: str, grammar_rows: Iterable[dict] = ()) -> dict[str, FocusPoint]:
    """Every focus point this language currently offers, keyed by id.

    Assembled from whatever the language actually publishes. A language with no
    rule index contributes no pronunciation points; a language whose grammar
    curriculum is unwritten contributes no grammar points. Neither is an error
    and neither is papered over — the catalogue is simply smaller, and every
    consumer of it is written to cope with that.
    """
    out: dict[str, FocusPoint] = {}
    spec = registry.try_get(language)
    if spec is None:
        return out

    out.update(_pronunciation_points(spec))
    out.update(_grammar_points(grammar_rows))
    out.update(_confusion_points(spec))
    return out


def _pronunciation_points(spec) -> dict[str, FocusPoint]:
    try:
        engine = spec.pronunciation
    except ModuleNotFoundError:
        return {}
    if not hasattr(engine, "rules"):
        return {}

    out = {}
    for rule in engine.rules():
        examples = tuple(
            ex["written"] for ex in rule.get("examples", [])
            if ex.get("written") and ex.get("verified", True)
        )
        fid = f"{PRONUNCIATION}:{rule['id']}"
        out[fid] = FocusPoint(
            id=fid, kind=PRONUNCIATION, skill="pronunciation",
            title=rule.get("name", rule["id"]),
            native_title=rule.get("native_name", ""),
            simple=rule.get("simple", ""), technical=rule.get("technical", ""),
            examples=examples, source_id=rule["id"],
        )
    return out


def _grammar_points(rows: Iterable[dict]) -> dict[str, FocusPoint]:
    out = {}
    for row in rows:
        if not row.get("id"):
            continue
        examples = tuple(
            e["target"] for e in (row.get("examples") or [])
            if isinstance(e, dict) and e.get("target")
        )
        fid = f"{GRAMMAR}:{row['id']}"
        out[fid] = FocusPoint(
            id=fid, kind=GRAMMAR, skill="grammar",
            title=row.get("name") or row["id"],
            native_title=row.get("name_native", ""),
            simple=row.get("simple", ""), technical=row.get("technical", ""),
            examples=examples, source_id=row["id"],
        )
    return out


def _confusion_points(spec) -> dict[str, FocusPoint]:
    try:
        confusions = spec.confusions
    except ModuleNotFoundError:
        return {}

    out = {}
    for cid, c in confusions.items():
        fid = f"{CONFUSION}:{cid}"
        # A confusion carries its own tags, and the language decides what those
        # mean. Shared code only asks whether any of them is a sound tag.
        skill = "pronunciation" if _sounds_like_sound(c.tags) else "grammar"
        out[fid] = FocusPoint(
            id=fid, kind=CONFUSION, skill=skill,
            title=c.title, simple=c.simple, technical=c.rule,
            examples=tuple(
                e.get("target", "") for e in (c.examples or [])
                if isinstance(e, dict) and e.get("target")
            ),
            source_id=cid,
        )
    return out


#: Tags that mean "this is about sound". Read from the language's own confusion
#: tags rather than from any knowledge of scripts, which is the same trick the
#: diagnosis engine uses and for the same reason.
_SOUND_TAGS = frozenset({"pronunciation", "sounds", "tones", "vowels", "listening"})


def _sounds_like_sound(tags: Iterable[str]) -> bool:
    return bool(_SOUND_TAGS & {t.lower() for t in tags})


# ==========================================================================
# Attribution
# ==========================================================================

@dataclass(frozen=True)
class Attribution:
    """Which focus point a wrong answer belongs to, and how we decided."""

    focus: str
    why: str = ""
    #: True when the evidence pointed at exactly one thing. A false here is not
    #: a failure — it is the module declining to guess.
    certain: bool = True

    @property
    def attributed(self) -> bool:
        return bool(self.focus)


NOT_ATTRIBUTED = Attribution(focus="", why="", certain=False)


def attribute(
    language: str,
    *,
    skill: str = "",
    item_type: str = "",
    item_id: str = "",
    expected: str = "",
    given: str = "",
    confusion_id: str = "",
    points: Optional[dict[str, FocusPoint]] = None,
) -> Attribution:
    """Work out which specific point one wrong answer was about.

    In precedence order, because each step is more certain than the one after:

    1. A matched confusion. A confusion *is* a pair of specific things, and the
       confusion engine already decided this one matched.
    2. An item that is itself a teachable point — a grammar drill carries the
       grammar id, so there is nothing to infer.
    3. A sound-based answer, re-run through the language's own phonology. The
       rules that fired on the expected string are the candidates, and the
       learner's own answer is used to narrow them.

    When several rules fired and the answer does not isolate one, this returns
    `NOT_ATTRIBUTED`. That case is common and the honest handling of it is the
    whole reason this function returns a record rather than a string.
    """
    if points is None:
        points = catalogue(language)

    if confusion_id:
        fid = f"{CONFUSION}:{confusion_id}"
        if fid in points:
            return Attribution(fid, "This is one of the pairs you keep mixing up.")

    if item_type == "grammar" and item_id:
        fid = f"{GRAMMAR}:{item_id}"
        if fid in points:
            return Attribution(fid, "The exercise was about this grammar point.")

    if item_type == "pronunciation" and item_id:
        fid = f"{PRONUNCIATION}:{item_id}"
        if fid in points:
            return Attribution(fid, "The exercise was about this rule.")

    if expected and (skill in SOUND_SKILLS or item_type == "pronunciation"):
        return _from_phonology(language, expected, given, points)

    return NOT_ATTRIBUTED


def _from_phonology(language: str, expected: str, given: str,
                    points: dict[str, FocusPoint]) -> Attribution:
    """Which sound rule the learner failed, derived rather than guessed."""
    spec = registry.try_get(language)
    if spec is None:
        return NOT_ATTRIBUTED
    try:
        detail = spec.pronunciation.explain(expected)
    except Exception:
        # Deliberately broad. Attribution is a bonus on the answer path; a
        # phonology engine that chokes on an unusual string must cost the
        # learner a label, never their recorded answer.
        return NOT_ATTRIBUTED

    steps = [s for s in (detail.get("steps") or [])
             if f"{PRONUNCIATION}:{s.get('rule_id')}" in points]
    if not steps:
        return NOT_ATTRIBUTED

    spoken = detail.get("spoken") or ""
    results = [_result_of(s) for s in steps]

    # The learner's answer can only narrow this down if the answer is itself in
    # the spoken domain. It often is not: a dictation exercise asks for the
    # *written* form, so none of the spoken fragments would ever appear in a
    # perfectly good answer, and reading their absence as failure would blame
    # the first rule every time. So look for evidence first.
    in_spoken_domain = bool(given) and (
        (spoken and spoken in given) or any(r and r in given for r in results))

    if not in_spoken_domain:
        if len(steps) == 1:
            return Attribution(
                f"{PRONUNCIATION}:{steps[0]['rule_id']}",
                f"This is the only sound rule that applies to {expected}.")
        return Attribution(
            "", f"{len(steps)} sound rules apply to {expected} and the answer "
                f"does not say which one went wrong.", certain=False)

    # Rules chain: each one's output is the next one's input, so only the last
    # result survives into the final form. That makes the answer a position on
    # the chain rather than a set of independent checks — find how far the
    # learner got, and the failure is the step after it.
    reached = -1
    for i, r in enumerate(results):
        if r and r in given:
            reached = i
    if reached == len(steps) - 1:
        return Attribution(
            "", f"The sound changes in {expected} were all applied correctly; "
                f"whatever went wrong was not one of these rules.", certain=False)

    s = steps[reached + 1]
    if len(steps) == 1:
        why = f"This is the only sound rule that applies to {expected}."
    elif reached < 0:
        why = (f"{expected} needs {len(steps)} sound changes and the answer "
               f"applied none of them, so this is the first one to fix.")
    else:
        why = (f"The answer got as far as {results[reached]} and stopped, so "
               f"this is the rule that was not applied.")
    return Attribution(f"{PRONUNCIATION}:{s['rule_id']}", why)


def _result_of(step: dict) -> str:
    """The 'after' half of a step's worked fragment, if it has one."""
    shows = step.get("shows") or ""
    if "→" in shows:
        return shows.split("→")[-1].strip()
    return ""


# ==========================================================================
# Which points are actually weak
# ==========================================================================

@dataclass
class WeakPoint:
    point: FocusPoint
    failures: int
    #: The most recent evidence, for showing the learner what this is about.
    samples: list[dict] = field(default_factory=list)

    @property
    def warrants_remediation(self) -> bool:
        return self.failures >= REMEDIATION_THRESHOLD

    def to_dict(self) -> dict:
        return {**self.point.to_dict(), "failures": self.failures,
                "warrants_remediation": self.warrants_remediation,
                "samples": self.samples[:3]}


def weak_points(points: dict[str, FocusPoint], failures: dict[str, int],
                samples: Optional[dict[str, list[dict]]] = None,
                limit: int = 5) -> list[WeakPoint]:
    """Rank the points this learner keeps failing, most-failed first.

    Points the catalogue no longer contains are dropped rather than rendered as
    an id: a rule that was renamed should disappear from the learner's list,
    not appear as `pron:old_name` with no explanation attached to it.
    """
    out = []
    for fid, n in failures.items():
        p = points.get(fid)
        if p is None or n <= 0:
            continue
        out.append(WeakPoint(point=p, failures=n,
                             samples=list((samples or {}).get(fid, []))))
    out.sort(key=lambda w: (-w.failures, w.point.id))
    return out[:limit]


# ==========================================================================
# The plan
# ==========================================================================

@dataclass
class Step:
    """One stage of fixing a point."""

    id: str
    title: str
    why: str
    #: A generator spec the existing practice endpoint can build, or None for a
    #: teaching step that has no drill.
    spec: Optional[dict] = None
    teach: Optional[dict] = None

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "why": self.why,
                "spec": self.spec, "teach": self.teach}


@dataclass
class Plan:
    point: FocusPoint
    steps: list[Step] = field(default_factory=list)
    #: Steps that could not be built, and why. Rendered, not hidden — a learner
    #: is better served knowing a language has no sentence bank yet than
    #: silently getting three steps where another language gets four.
    skipped: list[dict] = field(default_factory=list)
    minutes: int = 0

    def to_dict(self) -> dict:
        return {"point": self.point.to_dict(),
                "steps": [s.to_dict() for s in self.steps],
                "skipped": self.skipped, "minutes": self.minutes}


#: Rough pacing for one remediation, matching the session planner's own numbers.
SECONDS_PER_EXERCISE = 20


def plan(point: FocusPoint, *, has_sentences: bool = False,
         count: int = 4) -> Plan:
    """Build the fix for one point: understand it, hear it, say it, use it.

    The order is the pedagogy. A learner who has failed a rule four times does
    not need a fifth attempt at the same question — they need the rule
    explained, then met in a different modality, and finally used in production,
    which is the only step that proves it stuck.

    Every drill is built from the point's *own* examples, so this cannot drift
    into practising something adjacent.
    """
    p = Plan(point=point)
    p.steps.append(Step(
        id="understand", title="What the rule actually says",
        why="You have got this wrong several times, so the first thing to do is "
            "read it once rather than guess again.",
        teach={"simple": point.simple, "technical": point.technical,
               "examples": list(point.examples)},
    ))

    if point.skill == "pronunciation":
        _sound_steps(p, count, has_sentences)
    elif point.kind == CONFUSION:
        _confusion_steps(p, count, has_sentences)
    else:
        _meaning_steps(p, count, has_sentences)

    p.minutes = max(2, round(
        sum(_count_of(s) for s in p.steps) * SECONDS_PER_EXERCISE / 60) + 1)
    return p


def _count_of(step: Step) -> int:
    return int((step.spec or {}).get("count", 0))


def _sound_steps(p: Plan, count: int, has_sentences: bool) -> None:
    examples = list(p.point.examples)
    if not examples:
        p.skipped.append({
            "id": "drills",
            "why": "This rule publishes no verified examples, so there is "
                   "nothing to drill without inventing words.",
        })
        return

    # "Which one did you hear" needs something to hear it against. Where a rule
    # publishes only one verified example there is no honest distractor, so the
    # step becomes dictation instead of quietly generating nothing.
    if len(examples) >= 2:
        hear = {"type": "listen_choose", "pool": examples,
                "count": min(count, len(examples) * 2)}
        why = ("Recognising the change by ear comes before producing it. If you "
               "cannot hear it, you cannot check yourself.")
    else:
        hear = {"type": "listen_type", "pool": examples, "count": 2}
        why = ("Only one example is written for this rule, so this is dictation "
               "rather than a choice — there is no second word to contrast it "
               "against without inventing one.")
    p.steps.append(Step(id="hear", title="Hear the difference", why=why, spec=hear))
    p.steps.append(Step(
        id="say", title="Say it yourself",
        why="The same words, out loud. Compare against the model — this is the "
            "step that moves a rule from knowing to doing.",
        spec={"type": "pronounce", "targets": examples[:count],
              "note": p.point.simple},
    ))
    if has_sentences:
        p.steps.append(Step(
            id="produce", title="Use it in a sentence",
            why="A rule you can only apply to single words has not been "
                "learned yet.",
            spec={"type": "translate_to_target", "count": max(2, count // 2)},
        ))
    else:
        p.skipped.append({
            "id": "produce",
            "why": "This language has no sentence bank yet, so there is no "
                   "production step. It is left out rather than faked.",
        })


def _confusion_steps(p: Plan, count: int, has_sentences: bool) -> None:
    """A confusion pair already has its own drill; use it rather than a copy.

    Reaching for the grammar-error drills here would ask for a `grammar_id`
    that a confusion does not have, and the learner would meet "no worked
    errors are written for this" on a point the app clearly does know about.
    """
    p.steps.append(Step(
        id="tell_apart", title="Tell them apart",
        why="The same two things, one after another, until the difference is "
            "the thing you notice rather than something you work out.",
        spec={"type": "confusion_drill", "confusion_id": p.point.source_id,
              "count": count},
    ))
    if has_sentences:
        p.steps.append(Step(
            id="produce", title="Use the right one from scratch",
            why="Choosing between two is easier than producing one. This is "
                "the step that shows whether it has actually stuck.",
            spec={"type": "sentence_complete", "count": max(2, count // 2)},
        ))
    else:
        p.skipped.append({
            "id": "produce",
            "why": "This language has no sentence bank yet, so the production "
                   "step is left out rather than faked.",
        })


def _meaning_steps(p: Plan, count: int, has_sentences: bool) -> None:
    source = p.point.source_id
    p.steps.append(Step(
        id="spot", title="Spot the mistake",
        why="The wrong versions here are the ones learners actually write. "
            "Recognising the error is the fastest way to stop making it.",
        spec={"type": "spot_the_error", "grammar_id": source, "count": count},
    ))
    p.steps.append(Step(
        id="fix", title="Fix it yourself",
        why="Now correct it rather than choosing the correction. Producing the "
            "right form is a different skill from recognising it.",
        spec={"type": "fix_the_sentence", "grammar_id": source, "count": count},
    ))
    if has_sentences:
        p.steps.append(Step(
            id="produce", title="Build it from scratch",
            why="The final test: the same point, with nothing to correct and "
                "nothing to choose from.",
            spec={"type": "sentence_complete", "grammar_id": source,
                  "count": max(2, count // 2)},
        ))
    else:
        p.skipped.append({
            "id": "produce",
            "why": "This language has no sentence bank yet, so the last step is "
                   "left out rather than faked.",
        })


def summarise(weak: list[WeakPoint]) -> str:
    """One sentence for the top of the mistakes screen."""
    ready = [w for w in weak if w.warrants_remediation]
    if not ready:
        if not weak:
            return ("Nothing has failed often enough to be a pattern yet. "
                    "Individual slips are normal and are not worth a lesson.")
        w = weak[0]
        need = REMEDIATION_THRESHOLD - w.failures
        return (f"{w.point.title} is the closest thing to a pattern so far — "
                f"{w.failures} time{'' if w.failures == 1 else 's'}. "
                f"{need} more and the app will build a targeted fix for it "
                f"rather than just showing it to you again.")
    if len(ready) == 1:
        w = ready[0]
        return (f"You have got {w.point.title} wrong {w.failures} times. That is "
                f"a pattern rather than bad luck, so there is a targeted fix "
                f"for it below.")
    return (f"{len(ready)} things have gone wrong often enough to be patterns. "
            f"Each has a targeted fix that teaches it, then drills it in a "
            f"different form — repeating the same question would not help.")
