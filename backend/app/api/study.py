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
from ..engines import adaptive, exercises as X, srs
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
        if confusion_id:
            c = adaptive.confusions_for(lang).get(confusion_id)
            if c:
                explanation = c.one_line
                result["confusion"] = {
                    "id": c.id, "title": c.title, "one_line": c.one_line,
                    "simple": c.simple,
                }
        store.record_mistake(
            lid, lang, category=req.skill, expected=req.expected, given=req.given,
            explanation=explanation, confusion_id=confusion_id or "",
            item_type=req.item_type, item_id=req.item_id,
            lesson_id=req.lesson_id, conn=conn)
        result["message"] = "Not quite."
        result["try_again"] = True
    else:
        store.add_xp(lid, lang, 2, conn)
        result["xp"] = 2

    return result


# ==========================================================================
# Reviews
# ==========================================================================

@router.get("/review/queue")
def review_queue(spec: UsableLang, learner: Learner, limit: int = 40) -> dict:
    """Today's review session for this language only."""
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
        items.append(item)

    return {
        "language": lang,
        "count": len(items),
        "items": items,
        "summary": srs.queue_summary(all_cards),
    }


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
def my_mistakes(spec: UsableLang, learner: Learner, include_resolved: bool = False) -> dict:
    rows = store.mistakes(learner["id"], spec.code, not include_resolved)
    confusions = adaptive.confusions_for(spec.code)
    for r in rows:
        c = confusions.get(r.get("confusion_id") or "")
        if c:
            r["confusion"] = {"title": c.title, "one_line": c.one_line}
    by_category: dict[str, list] = {}
    for r in rows:
        by_category.setdefault(r["category"], []).append(r)
    return {"language": spec.code, "total": len(rows),
            "by_category": by_category, "mistakes": rows}


@router.post("/mistakes/{mistake_id}/resolve")
def resolve(mistake_id: int) -> dict:
    store.resolve_mistake(mistake_id)
    return {"resolved": True}


@router.get("/mini-course/{confusion_id}")
def mini_course(confusion_id: str, spec: UsableLang) -> dict:
    """The targeted lesson for one chronic confusion."""
    try:
        return adaptive.build_mini_course(spec.code, confusion_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
