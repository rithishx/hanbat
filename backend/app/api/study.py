"""
The study loop: lessons, exercises, reviews, and what happens when you answer.

This is where the app earns its keep. Answering an exercise does four things
at once — records the attempt, schedules the SRS card, stores the mistake if
there was one, and returns an explanation that says *why* rather than "wrong".
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import store
from ..db import get_connection
from ..engines import adaptive, diagnosis, exercises as X, remediation, srs
from .deps import Learner, UsableLang

router = APIRouter(tags=["study"])


# ==========================================================================
# Building exercises
# ==========================================================================

def _context(spec, learner_id: int, seed: Optional[int] = None,
             level: str = "") -> X.GenContext:
    X.load_language_generators(spec.code)
    return X.GenContext(
        language=spec.code,
        rng=random.Random(seed) if seed is not None else random.Random(),
        vocab=store.vocab(spec.code, level=level or None, limit=500),
        script_units=store.script_units(spec.code),
        sentences=store.sentences(spec.code, level=level or None, limit=300),
        grammar=store.grammar(spec.code),
        level=level,
    )


@router.get("/lessons/{lesson_id}/exercises")
def lesson_exercises(lesson_id: str, learner: Learner,
                     step: Optional[str] = None, seed: Optional[int] = None) -> dict:
    """Expand a lesson's generator specs into concrete questions."""
    L = store.lesson(lesson_id)
    if L is None:
        raise HTTPException(404, f"no lesson {lesson_id!r}")
    from ..languages import registry
    spec = registry.get(L["language"])

    ctx = _context(spec, learner["id"], seed, L.get("level", ""))
    rows = store.exercises_for(lesson_id, step)

    out = []
    for r in rows:
        built = X.generate(r["data"] or {}, ctx)
        for e in built:
            d = e.to_dict()
            d["exercise_id"] = r["id"]
            d["step"] = r["step"]
            out.append(d)
    return {"lesson_id": lesson_id, "language": spec.code,
            "step": step, "count": len(out), "exercises": out}


class PracticeRequest(BaseModel):
    spec: dict = Field(..., description="A generator spec, e.g. {'type':'conjugate','count':8}")
    seed: Optional[int] = None
    level: str = ""


@router.post("/practice")
def practice(req: PracticeRequest, spec: UsableLang, learner: Learner) -> dict:
    """Build a drill on demand, outside any lesson."""
    ctx = _context(spec, learner["id"], req.seed, req.level)
    built = X.generate(req.spec, ctx)
    return {"language": spec.code, "count": len(built),
            "exercises": [e.to_dict() for e in built]}


@router.get("/practice/kinds")
def practice_kinds(spec: UsableLang) -> dict:
    X.load_language_generators(spec.code)
    return {"language": spec.code, "kinds": X.supported_kinds(spec.code)}


# ==========================================================================
# Answering
# ==========================================================================

class AnswerRequest(BaseModel):
    correct: bool
    skill: str = "grammar"
    item_type: str = ""
    item_id: str = ""
    expected: str = ""
    given: str = ""
    lesson_id: str = ""
    exercise_id: str = ""
    topic: str = ""
    level: str = ""
    response_ms: int = 0
    #: Whether the exercise offered options. A wrong pick from a list is a
    #: decision, not a typo, so it can never be diagnosed as careless.
    had_options: bool = False
    #: SRS grade. Omit and it is inferred from `correct`.
    grade: Optional[str] = None


@router.post("/answer")
def answer(req: AnswerRequest, spec: UsableLang, learner: Learner) -> dict:
    """Record one answer and schedule what follows.

    The response never says only "wrong". When the mistake matches a known
    confusion for this language, the explanation is the authored one for that
    confusion — the same text the mini-course uses — so the learner meets a
    consistent account of their own error rather than a fresh paraphrase each
    time.
    """
    conn = get_connection()
    lid, lang = learner["id"], spec.code

    attempt = adaptive.Attempt(
        skill=req.skill, correct=req.correct, language=lang,
        item_type=req.item_type, item_id=req.item_id,
        expected=req.expected, given=req.given, lesson_id=req.lesson_id,
        topic=req.topic, level=req.level, response_ms=req.response_ms,
    )
    store.record_attempt(lid, lang, attempt, conn, req.exercise_id)
    store.touch_streak(lid, conn)

    result: dict[str, Any] = {"correct": req.correct}

    # -- schedule the card -------------------------------------------------
    if req.item_type and req.item_id:
        card = store.ensure_card(lid, lang, req.item_type, req.item_id, conn)
        grade = req.grade or ("good" if req.correct else "again")
        outcome = srs.review(card, grade)
        store.save_card(lid, lang, outcome.card, conn)
        result["srs"] = {
            "state": outcome.card.state,
            "next_due_in": outcome.next_due_in,
            "graduated": outcome.graduated,
            "lapsed": outcome.lapsed,
            "mastered": outcome.mastered,
        }

    # -- explain, rather than mark ----------------------------------------
    if not req.correct:
        confusion_id = adaptive.identify_confusion(lang, req.expected, req.given)
        explanation = ""
        tags: tuple[str, ...] = ()
        if confusion_id:
            c = adaptive.confusions_for(lang).get(confusion_id)
            if c:
                explanation = c.one_line
                tags = tuple(c.tags)
                result["confusion"] = {
                    "id": c.id, "title": c.title, "one_line": c.one_line,
                    "simple": c.simple,
                }

        # Why it was wrong, not only where. A slip on something already known
        # is diagnosed as careless and deliberately does not become a weakness
        # — see engines/diagnosis.py.
        history = store.item_history(lid, lang, req.item_type, req.item_id,
                                     skill=req.skill, conn=conn)
        verdict = diagnosis.diagnose(
            skill=req.skill,
            expected=req.expected,
            given=req.given,
            response_ms=req.response_ms,
            history=diagnosis.ItemHistory(**history),
            confusion_tags=tags,
            had_options=req.had_options,
        )

        # And *which specific thing* it was about — one rule, one grammar
        # point — so that repeated failures can be remediated rather than only
        # counted. Careless slips are attributed too: knowing which rule a
        # learner keeps fumbling is useful even when they know it.
        got = remediation.attribute(
            lang, skill=req.skill, item_type=req.item_type, item_id=req.item_id,
            expected=req.expected, given=req.given,
            confusion_id=confusion_id or "",
            points=remediation.catalogue(lang, store.grammar(lang, conn=conn)),
        )

        store.record_mistake(
            lid, lang, category=req.skill, expected=req.expected, given=req.given,
            explanation=explanation, confusion_id=confusion_id or "",
            item_type=req.item_type, item_id=req.item_id,
            lesson_id=req.lesson_id, reason=verdict.reason,
            reason_why=verdict.because, confidence=verdict.confidence,
            response_ms=req.response_ms, focus=got.focus, focus_why=got.why,
            conn=conn)

        if got.attributed:
            result["focus"] = {"id": got.focus, "why": got.why}

        result["diagnosis"] = verdict.to_dict()
        result["message"] = (
            "You knew this one." if verdict.reason == "careless" else "Not quite."
        )
        result["try_again"] = True
    else:
        store.add_xp(lid, lang, 2, conn)
        result["xp"] = 2

    return result


# ==========================================================================
# Reviews
# ==========================================================================

@router.get("/review/queue")
def review_queue(spec: UsableLang, learner: Learner, limit: int = 40,
                 seed: Optional[int] = None) -> dict:
    """Today's review session for this language only.

    The scheduler decides which cards; the adaptive model decides *how each one
    is asked*. A learner weak at listening meets some of their due vocabulary as
    dictation, one weak at production meets it meaning-first. Same cards, same
    intervals, a question aimed at the half they are actually losing.

    Cards still being learned are never made harder this way — you cannot
    recall what you met four minutes ago, and a card that fails for that reason
    would be misread by the scheduler as forgetting.
    """
    conn = get_connection()
    lid, lang = learner["id"], spec.code
    settings = learner["settings"]

    all_cards = store.cards(lid, lang, conn)
    limits = srs.QueueLimits(
        new_per_day=int(settings.get("new_cards_per_day", 10)),
        reviews_per_day=int(settings.get("reviews_per_day", 100)),
    )
    queue = srs.build_queue(
        all_cards, limits=limits,
        introduced_today=store.introduced_today(lid, lang, conn))[:limit]

    weights = _review_weights(lid, lang, conn)
    rng = random.Random(seed) if seed is not None else random.Random()

    items = []
    for c in queue:
        item = {"card": c.to_dict(), "preview": srs.preview_intervals(c)}
        if c.item_type == "vocab":
            item["content"] = store.vocab_one(c.item_id)
        elif c.item_type == "grammar":
            item["content"] = store.grammar_one(c.item_id)
        elif c.item_type == "script_unit":
            row = next((s for s in store.script_units(lang) if s["id"] == c.item_id), None)
            item["content"] = row
        item["ask"] = adaptive.review_mode(
            state=c.state, item_type=c.item_type, weights=weights, rng=rng)
        items.append(item)

    asked = {}
    for i in items:
        asked[i["ask"]["mode"]] = asked.get(i["ask"]["mode"], 0) + 1

    return {
        "language": lang,
        "count": len(items),
        "items": items,
        "summary": srs.queue_summary(all_cards),
        "modes": asked,
    }


def _review_weights(lid: int, lang: str, conn) -> dict[str, float]:
    """The learner's skill weights, or nothing if there is no evidence yet.

    An empty dict means every card is asked the ordinary way, which is the
    right default: varying the question format before knowing anything about
    the learner is variety for its own sake.
    """
    model = adaptive.build_model(
        store.attempts(lid, lang, conn=conn), language=lang)
    if model.total_attempts < 10:
        return {}
    return {f.skill: f.weight
            for f in adaptive.focus(model, store.mistakes_by_reason(lid, lang, conn))}


@router.get("/review/summary")
def review_summary(spec: UsableLang, learner: Learner) -> dict:
    cards = store.cards(learner["id"], spec.code)
    return {"language": spec.code, **srs.queue_summary(cards),
            "forecast": srs.retention_forecast(cards, days=30)}


class GradeRequest(BaseModel):
    item_type: str
    item_id: str
    grade: str


@router.post("/review/grade")
def grade(req: GradeRequest, spec: UsableLang, learner: Learner) -> dict:
    conn = get_connection()
    lid, lang = learner["id"], spec.code
    card = store.ensure_card(lid, lang, req.item_type, req.item_id, conn)
    try:
        outcome = srs.review(card, req.grade)
    except ValueError as e:
        raise HTTPException(400, str(e))
    store.save_card(lid, lang, outcome.card, conn)
    store.touch_streak(lid, conn)
    store.add_xp(lid, lang, 1 if req.grade != "again" else 0, conn)
    return outcome.to_dict()


class EnqueueRequest(BaseModel):
    items: list[dict] = Field(..., description="[{item_type, item_id}, ...]")


@router.post("/review/enqueue")
def enqueue(req: EnqueueRequest, spec: UsableLang, learner: Learner) -> dict:
    """Add items to the review queue — what a lesson's `srs_enqueue` step does."""
    conn = get_connection()
    n = 0
    for it in req.items:
        if it.get("item_type") and it.get("item_id"):
            store.ensure_card(learner["id"], spec.code,
                              it["item_type"], it["item_id"], conn)
            n += 1
    return {"language": spec.code, "enqueued": n}


# ==========================================================================
# Lesson progress
# ==========================================================================

class ProgressRequest(BaseModel):
    status: str = "in_progress"
    step: str = ""
    score: float = 0.0


@router.post("/lessons/{lesson_id}/progress")
def set_progress(lesson_id: str, req: ProgressRequest, learner: Learner) -> dict:
    L = store.lesson(lesson_id)
    if L is None:
        raise HTTPException(404, f"no lesson {lesson_id!r}")
    lang = L["language"]
    store.set_lesson_progress(learner["id"], lang, lesson_id,
                              req.status, req.step, req.score)
    if req.status == "completed":
        store.add_xp(learner["id"], lang, 20)
        store.touch_streak(learner["id"])
        # Enqueue whatever the lesson said to review.
        for step in (L.get("body") or {}).get("steps", []):
            if step.get("type") == "srs_enqueue":
                for item in step.get("items", []):
                    store.ensure_card(learner["id"], lang, "sentence", item)
    return {"lesson_id": lesson_id, "status": req.status}


class SessionRequest(BaseModel):
    seconds: int
    kind: str = "mixed"
    cards_reviewed: int = 0
    lessons_completed: int = 0


@router.post("/session")
def log_session(req: SessionRequest, spec: UsableLang, learner: Learner) -> dict:
    store.log_session(learner["id"], spec.code, req.seconds, req.kind,
                      cards_reviewed=req.cards_reviewed,
                      lessons_completed=req.lessons_completed)
    return {"logged": True, "minutes_today": store.study_minutes_today(learner["id"])}


# ==========================================================================
# Mistakes
# ==========================================================================

@router.get("/mistakes")
def my_mistakes(spec: UsableLang, learner: Learner, include_resolved: bool = False,
                reason: Optional[str] = None) -> dict:
    """Every mistake, grouped by *why* it happened.

    `by_category` is kept for the skill breakdown, but `by_reason` is the one
    worth reading: it separates "you have not learned this" from "you knew it
    and slipped", which are different problems and should not be studied the
    same way.
    """
    rows = store.mistakes(learner["id"], spec.code, not include_resolved)
    confusions = adaptive.confusions_for(spec.code)
    for r in rows:
        c = confusions.get(r.get("confusion_id") or "")
        if c:
            r["confusion"] = {"title": c.title, "one_line": c.one_line}

    if reason:
        rows = [r for r in rows if (r.get("reason") or "unknown") == reason]

    by_category: dict[str, list] = {}
    by_reason: dict[str, list] = {}
    for r in rows:
        by_category.setdefault(r["category"], []).append(r)
        # Rows recorded before v3 have no diagnosis, and are not given an
        # invented one — they group under "unknown" and the UI says why.
        by_reason.setdefault(r.get("reason") or "unknown", []).append(r)

    diagnosed = [r["reason"] for r in rows if r.get("reason")]

    # What each group of mistakes should lead to. A list of errors with no next
    # action is a scoreboard; the whole value of grouping by reason is that
    # each reason has a different answer to "so what do I do about it".
    next_steps = {
        key: _next_step(key, len(group))
        for key, group in by_reason.items() if key in diagnosis.REASON_INFO
    }

    conn = get_connection()
    points = remediation.catalogue(spec.code, store.grammar(spec.code, conn=conn))
    weak = remediation.weak_points(
        points, store.mistakes_by_focus(learner["id"], spec.code, conn),
        store.mistake_samples(learner["id"], spec.code, conn=conn))

    return {
        "language": spec.code,
        "total": len(rows),
        "by_category": by_category,
        "by_reason": by_reason,
        "reasons": {
            key: diagnosis.REASON_INFO[key]
            for key in by_reason if key in diagnosis.REASON_INFO
        },
        "next_steps": next_steps,
        "summary": diagnosis.summarise(diagnosed),
        "undiagnosed": len(rows) - len(diagnosed),
        "weak_points": [w.to_dict() for w in weak],
        "weak_point_summary": remediation.summarise(weak),
        "mistakes": rows,
    }


#: What to do about each kind of mistake, and — as importantly — what not to.
#: Written as instructions a learner can follow today, not as descriptions of
#: the category, which they can already read above it.
_NEXT_STEP = {
    "vocabulary": ("Practise these as recall, not recognition — meaning first, "
                   "then produce the word. Recognising them again proves "
                   "nothing.", "vocab_recall"),
    "grammar": ("Drill the point rather than the sentence. The wrong-versus-"
                "right pairs in the curriculum are the fastest way in.",
                "spot_the_error"),
    "pronunciation": ("Take the rule apart in the pronunciation lab, then say "
                      "the examples out loud. Reading the rule is not enough.",
                      "pronounce"),
    "listening": ("Dictation on the same items. Hearing is a separate skill "
                  "and only improves by being practised on its own.",
                  "listen_type"),
    "reading": ("Read them again in a sentence rather than alone — most "
                "reading mistakes are about context, not the word.",
                "translate_to_english"),
    "writing": ("Rewrite them from the English. Producing the form is what "
                "went wrong, so producing it is what fixes it.",
                "fix_the_sentence"),
    "careless": ("Nothing. These are not scheduled on purpose — you knew them. "
                 "If there are a lot, slow down rather than practise more.", ""),
}


def _next_step(reason: str, count: int) -> dict:
    advice, kind = _NEXT_STEP.get(reason, ("", ""))
    return {"advice": advice, "drill": kind, "count": count,
            "practisable": bool(kind)}


@router.post("/mistakes/{mistake_id}/resolve")
def resolve(mistake_id: int) -> dict:
    store.resolve_mistake(mistake_id)
    return {"resolved": True}


class MistakePracticeRequest(BaseModel):
    #: Narrow to one diagnosis reason, one specific point, or neither.
    reason: str = ""
    focus: str = ""
    count: int = 8
    seed: Optional[int] = None


@router.post("/mistakes/practice")
def practice_my_mistakes(req: MistakePracticeRequest, spec: UsableLang,
                         learner: Learner) -> dict:
    """A drill built from the learner's own recorded mistakes.

    Not a generated drill that happens to cover a weak skill — these are the
    exact items this learner got wrong, asked again in the direction that
    proves they have fixed it. A vocabulary gap comes back as recall, because
    recognising the word again proves nothing; a listening mistake comes back
    as dictation; a pronunciation one comes back to be said out loud.

    Careless slips are excluded by default and the response says so. Drilling
    someone on thirty words they already know, because they mistyped them, is
    exactly the busywork this app is built to avoid.
    """
    conn = get_connection()
    lid, lang = learner["id"], spec.code
    rows = store.mistakes(lid, lang, unresolved_only=True, limit=200, conn=conn)

    if req.reason:
        rows = [r for r in rows if (r.get("reason") or "unknown") == req.reason]
    else:
        rows = [r for r in rows if (r.get("reason") or "") != "careless"]
    if req.focus:
        rows = [r for r in rows if r.get("focus") == req.focus]

    # Keep only what can honestly be asked again: an item with no expected
    # answer is a mistake we recorded but cannot re-pose.
    rows = [r for r in rows if r.get("expected")]

    ctx = _context(spec, lid, req.seed)
    built: list[dict] = []
    for row in rows[: max(1, req.count)]:
        ex = _reask(row, ctx)
        if ex is not None:
            built.append(ex)

    return {
        "language": lang,
        "count": len(built),
        "exercises": built,
        "from_mistakes": len(rows),
        "excluded_careless": not req.reason,
        "note": _practice_note(len(built), bool(req.reason or req.focus)),
    }


#: How each diagnosis comes back. The direction matters more than the format:
#: a gap has to be re-asked productively or the learner only proves they can
#: still recognise it.
_REASK = {
    "vocabulary": ("vocab_recall", "vocabulary"),
    "listening": ("listen_type", "listening"),
    "pronunciation": ("pronounce", "speaking"),
    "writing": ("fix_the_sentence", "writing"),
    "grammar": ("spot_the_error", "grammar"),
    "reading": ("word_read", "reading"),
    "careless": ("vocab_recall", "vocabulary"),
}


def _reask(row: dict, ctx: X.GenContext) -> Optional[dict]:
    """Turn one recorded mistake back into a question.

    Built directly rather than through a generator: the point is to ask about
    *this* item, and every generator samples from a pool. The explanation is
    the one already stored on the mistake, so the learner meets the same
    account of their error they met the first time.
    """
    expected = row["expected"]
    kind, skill = _REASK.get(row.get("reason") or "", ("vocab_recall", "vocabulary"))

    if kind == "listen_type":
        prompt, audio, options = "Type what you hear.", expected, []
    elif kind == "pronounce":
        prompt, audio, options = f"Say: {expected}", expected, []
    elif kind == "fix_the_sentence":
        prompt = f"You wrote this. Write it correctly:\n{row.get('given') or '—'}"
        audio, options = expected, []
    elif kind == "spot_the_error":
        prompt, audio = "Which one is correct?", expected
        options = [expected, row.get("given") or ""]
        options = [o for o in options if o]
        if len(options) < 2:
            prompt, options = f"Write it correctly: {row.get('explanation') or ''}", []
    else:
        prompt = row.get("explanation") or "What was the correct answer here?"
        if row.get("given"):
            prompt = f"You answered {row['given']}. What should it have been?"
        audio, options = expected, []

    return X.Exercise(
        kind=kind, skill=skill, prompt=prompt, answer=expected,
        options=options, audio=audio,
        explain=row.get("explanation") or row.get("reason_why") or "",
        data={"from_mistake": row["id"], "seen": row.get("times_seen", 1),
              "reason": row.get("reason") or "", "focus": row.get("focus") or ""},
        item_type=row.get("item_type") or "", item_id=row.get("item_id") or "",
    ).to_dict()


def _practice_note(built: int, narrowed: bool) -> str:
    if built == 0:
        return ("Nothing to practise here — either you have no unresolved "
                "mistakes of this kind, or the ones you have cannot be asked "
                "again as a question.")
    scope = "this group" if narrowed else "your open mistakes"
    return (f"{built} question{'' if built == 1 else 's'} from {scope}, asked in "
            f"the direction that proves you have fixed them rather than the one "
            f"you originally met them in.")


@router.get("/mini-course/{confusion_id}")
def mini_course(confusion_id: str, spec: UsableLang) -> dict:
    """The targeted lesson for one chronic confusion."""
    try:
        return adaptive.build_mini_course(spec.code, confusion_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
