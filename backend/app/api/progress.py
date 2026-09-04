"""
Dashboard and progress.

The dashboard exists to answer three questions and it should answer all three
above the fold: what should I learn today, what am I forgetting, and why do I
keep making this mistake.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter

from .. import store
from ..db import get_connection, query
from ..engines import (adaptive, diagnosis, remediation,
                       session as session_engine, srs)
from ..languages import registry
from .deps import Learner, UsableLang

router = APIRouter(tags=["progress"])


def _model(learner_id: int, language: str, conn) -> adaptive.LearnerModel:
    known = store.known_counts(learner_id, language, conn)
    return adaptive.build_model(
        store.attempts(learner_id, language, conn=conn),
        language=language,
        script_mastery=store.script_mastery(learner_id, language, conn),
        vocab_known=known["vocab"],
        grammar_known=known["grammar"],
    )


def _next_lesson(learner_id: int, language: str) -> Optional[dict]:
    """The next unfinished lesson whose prerequisites are met.

    Shared by the dashboard and the session planner deliberately: two
    implementations of "what comes next" would eventually disagree, and the
    learner would see one lesson recommended and a different one planned.
    """
    progress = store.lesson_progress(learner_id, language)
    done = {k for k, v in progress.items() if v["status"] == "completed"}
    for L in store.lessons(language):
        if L["id"] in done:
            continue
        if set(L.get("prerequisites") or []) - done:
            continue
        return {"id": L["id"], "title": L["title"],
                "title_native": L["title_native"],
                "est_minutes": L["est_minutes"], "unit": L["unit"]}
    return None


@router.get("/dashboard")
def dashboard(spec: UsableLang, learner: Learner) -> dict:
    """Everything the home screen needs, in one call."""
    conn = get_connection()
    lid, lang = learner["id"], spec.code

    ll = store.get_learner_language(lid, lang, conn)
    cards = store.cards(lid, lang, conn)
    summary = srs.queue_summary(cards)
    model = _model(lid, lang, conn)
    known = store.known_counts(lid, lang, conn)
    minutes = store.study_minutes_today(lid, conn=conn)
    goal_minutes = int(learner["settings"].get("daily_goal_minutes", 15))

    next_lesson = _next_lesson(lid, lang)

    reasons = store.mistakes_by_reason(lid, lang, conn)
    recs = adaptive.recommend(
        model, due_count=summary["due_now"],
        minutes_available=max(0, goal_minutes - minutes),
        next_lesson=next_lesson,
        studied_today_minutes=minutes,
    )

    try:
        ladder = spec.levels
        level_details = ladder.describe(ll.get("level") or ladder.levels[0])
    except ModuleNotFoundError:
        level_details = {}

    return {
        "language": {"code": spec.code, "name": spec.name,
                     "native_name": spec.native_name, "flag": spec.flag},
        "greeting": {"native": _greeting(spec.code), "english": "Today's study"},
        "level": ll.get("level", ""),
        "level_details": level_details,
        "estimated_level": model.estimated_level,
        "xp": ll.get("xp", 0),
        "streak": store.get_streak(lid),
        "today": {
            "minutes_done": minutes,
            "goal_minutes": goal_minutes,
            "percent": min(100, round(100 * minutes / goal_minutes)) if goal_minutes else 0,
            "reviews_due": summary["due_now"],
            "new_available": summary["by_state"]["new"],
        },
        "srs": summary,
        "known": known,
        "script_mastery": store.script_mastery(lid, lang, conn),
        "skills": {k: v.to_dict() for k, v in model.skills.items()},
        "weak_skills": [f.to_dict() for f in
                        adaptive.weakest(model, reasons, limit=3)],
        "mistake_reasons": reasons,
        "mistake_summary": diagnosis.summarise(
            [r for r, n in reasons.items() for _ in range(n)
             if r in diagnosis.REASON_INFO]),
        # One level below "weak skills": the specific rules and points that
        # keep failing. This is what turns "pronunciation is weak" into
        # something the learner can actually go and do.
        "weak_point": _top_weak_point(lid, lang, conn),
        "weak_areas": model.weak_items[:5],
        "strong_areas": model.strong_items[:5],
        "confusions": model.confusions[:5],
        "next_lesson": next_lesson,
        "recommendations": [r.to_dict() for r in recs],
    }


_GREETINGS = {"ko": "오늘의 한국어", "ja": "今日の日本語", "zh": "今天的中文"}


def _greeting(code: str) -> str:
    return _GREETINGS.get(code, "Today")


@router.get("/progress")
def progress(spec: UsableLang, learner: Learner) -> dict:
    """The detailed progress screen for one language."""
    conn = get_connection()
    lid, lang = learner["id"], spec.code
    cards = store.cards(lid, lang, conn)
    model = _model(lid, lang, conn)

    lessons = store.lessons(lang)
    lp = store.lesson_progress(lid, lang)
    completed = sum(1 for L in lessons if lp.get(L["id"], {}).get("status") == "completed")

    try:
        ladder = spec.levels
        ladder_out = [ladder.describe(l) for l in ladder.levels]
        scheme = ladder.scheme
    except ModuleNotFoundError:
        ladder_out, scheme = [], ""

    return {
        "language": spec.code,
        "level_scheme": scheme,
        "ladder": ladder_out,
        "current_level": store.get_learner_language(lid, lang, conn).get("level"),
        "estimated_level": model.estimated_level,
        "overall": model.overall,
        "skills": {k: v.to_dict() for k, v in model.skills.items()},
        "srs": srs.queue_summary(cards),
        "forecast": srs.retention_forecast(cards, days=30),
        "lessons": {"completed": completed, "total": len(lessons)},
        "known": store.known_counts(lid, lang, conn),
        "script_mastery": store.script_mastery(lid, lang, conn),
        "weak_items": model.weak_items,
        "strong_items": model.strong_items,
        "confusions": model.confusions,
        "topics": model.topics,
        "activity": _activity(lid, lang, conn),
    }


def _activity(learner_id: int, language: str, conn, days: int = 90) -> list[dict]:
    """Attempts per day, for the heatmap."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = query(
        "SELECT substr(at,1,10) AS day, COUNT(*) AS n, "
        "       SUM(correct) AS correct "
        "FROM attempt WHERE learner_id=? AND language=? AND at>=? "
        "GROUP BY day ORDER BY day", (learner_id, language, since), conn)
    return [{"date": r["day"], "count": r["n"],
             "accuracy": round(r["correct"] / r["n"], 3) if r["n"] else None}
            for r in rows]


@router.get("/progress/all")
def all_languages(learner: Learner) -> dict:
    """Cross-language summary for the 'My Languages' panel.

    Aggregates for display only. The underlying schedules and scores stay
    entirely separate — this endpoint reads each language's numbers and puts
    them side by side.
    """
    conn = get_connection()
    out = []
    for spec in registry.all_languages(usable_only=False):
        ll = store.get_learner_language(learner["id"], spec.code, conn) \
            if spec.is_usable else {}
        if not spec.is_usable:
            out.append({"code": spec.code, "name": spec.name, "flag": spec.flag,
                        "native_name": spec.native_name, "status": spec.status,
                        "status_note": spec.status_note, "started": False})
            continue
        summary = store.srs_counts(learner["id"], spec.code, conn)
        known = store.known_counts(learner["id"], spec.code, conn)
        out.append({
            "code": spec.code, "name": spec.name, "flag": spec.flag,
            "native_name": spec.native_name, "status": spec.status,
            "started": bool(ll.get("xp") or known["all"]),
            "level": ll.get("level", ""),
            "xp": ll.get("xp", 0),
            "known": known,
            "due_now": summary["due_now"],
            "script_mastery": store.script_mastery(learner["id"], spec.code, conn),
        })
    return {"languages": out, "streak": store.get_streak(learner["id"]),
            "minutes_today": store.study_minutes_today(learner["id"], conn=conn)}


@router.get("/recommendations")
def recommendations(spec: UsableLang, learner: Learner) -> dict:
    conn = get_connection()
    model = _model(learner["id"], spec.code, conn)
    summary = store.srs_counts(learner["id"], spec.code, conn)
    recs = adaptive.recommend(
        model, due_count=summary["due_now"],
        studied_today_minutes=store.study_minutes_today(learner["id"], conn=conn))
    return {"language": spec.code, "recommendations": [r.to_dict() for r in recs]}


# ==========================================================================
# Today's session
# ==========================================================================

@router.get("/session/plan")
def session_plan(spec: UsableLang, learner: Learner,
                 minutes: Optional[int] = None, seed: Optional[int] = None) -> dict:
    """One ordered plan for today, built from what is genuinely due.

    Everything the planner receives describes what actually exists — the real
    due count, whether this language really has a next lesson — so a block can
    never point at content that is not there. A learner with nothing due gets a
    short session and a sentence explaining why, rather than filler.
    """
    conn = get_connection()
    lid, lang = learner["id"], spec.code

    cards = store.cards(lid, lang, conn)
    summary = srs.queue_summary(cards)
    model = _model(lid, lang, conn)
    goal = minutes or int(learner["settings"].get("daily_goal_minutes", 15))

    plan = session_engine.build(
        language=lang,
        model=model,
        due_now=summary["due_now"],
        minutes=goal,
        mistake_reasons=store.mistakes_by_reason(lid, lang, conn),
        next_lesson=_next_lesson(lid, lang),
        new_vocab=summary["by_state"].get("new", 0),
        has_grammar=bool(store.grammar(lang)),
        has_sentences=bool(store.sentences(lang, limit=1, conn=conn)),
        weak_point=_top_weak_point(lid, lang, conn),
        studied_today=store.study_minutes_today(lid, conn=conn),
        seed=seed,
    )
    return plan.to_dict()


def _top_weak_point(lid: int, lang: str, conn) -> Optional[dict]:
    """The one specific point worth a targeted block today, or None.

    Only the top one. A session with three remediation blocks in it is a
    session that never gets to anything new, and a learner who is failing three
    rules is best served by fixing one properly.
    """
    points = remediation.catalogue(lang, store.grammar(lang, conn=conn))
    weak = remediation.weak_points(
        points, store.mistakes_by_focus(lid, lang, conn), limit=1)
    if not weak or not weak[0].warrants_remediation:
        return None

    w = weak[0]
    plan = remediation.plan(
        w.point, has_sentences=bool(store.sentences(lang, limit=1, conn=conn)))
    return {"id": w.point.id, "title": w.point.title, "skill": w.point.skill,
            "failures": w.failures, "minutes": plan.minutes}
