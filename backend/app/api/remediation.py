"""
"You keep getting this wrong. Here is the fix."

The mistakes screen answers *what* went wrong and the dashboard answers *how
you are doing*. Neither answers the question a learner actually has after
failing the same rule for the fourth time, which is "so what do I do about it".
This router does.

Three endpoints and one idea: a weakness only earns a lesson once it is a
pattern. Below the threshold this says so plainly and offers nothing, because
building a targeted eight-minute course around a single slip would waste the
learner's time and teach them to distrust the app's judgement.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import store
from ..db import get_connection
from ..engines import remediation
from .deps import Learner, UsableLang

router = APIRouter(tags=["remediation"])


def _points(lang: str, conn) -> dict:
    return remediation.catalogue(lang, store.grammar(lang, conn=conn))


def _weak(lid: int, lang: str, conn, limit: int = 5) -> list[remediation.WeakPoint]:
    return remediation.weak_points(
        _points(lang, conn),
        store.mistakes_by_focus(lid, lang, conn),
        store.mistake_samples(lid, lang, conn=conn),
        limit=limit,
    )


@router.get("/remediation")
def my_weak_points(spec: UsableLang, learner: Learner) -> dict:
    """The specific things this learner keeps failing, most-failed first.

    Everything here is scoped to one language, like the rest of the app: a
    Korean learner's 연음 problem has nothing to say about their Japanese.
    """
    conn = get_connection()
    lid, lang = learner["id"], spec.code
    weak = _weak(lid, lang, conn)
    ready = [w for w in weak if w.warrants_remediation]

    return {
        "language": lang,
        "threshold": remediation.REMEDIATION_THRESHOLD,
        "weak_points": [w.to_dict() for w in weak],
        "ready": [w.point.id for w in ready],
        "summary": remediation.summarise(weak),
        # How many mistakes could not be pinned to any one point. Shown rather
        # than hidden: it is the honest denominator for everything above.
        "unattributed": _unattributed(lid, lang, conn),
    }


def _unattributed(lid: int, lang: str, conn) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM mistake WHERE learner_id = ? AND language = ? "
        "AND resolved = 0 AND focus = ''", (lid, lang)).fetchone()
    return row["n"] if row else 0


@router.get("/remediation/{point_id:path}")
def remediation_plan(point_id: str, spec: UsableLang, learner: Learner) -> dict:
    """The plan for one point: understand it, hear it, say it, use it.

    Available for any point in the catalogue, not only ones past the threshold
    — a learner who wants to drill a rule they have not failed yet should not
    be told to go and fail it first. What the threshold gates is whether the
    app *offers* this unprompted.
    """
    conn = get_connection()
    lid, lang = learner["id"], spec.code
    points = _points(lang, conn)

    point = points.get(point_id)
    if point is None:
        raise HTTPException(404, f"no focus point {point_id!r} in {lang}")

    has_sentences = bool(store.sentences(lang, limit=1, conn=conn))
    plan = remediation.plan(point, has_sentences=has_sentences)

    failures = store.mistakes_by_focus(lid, lang, conn).get(point_id, 0)
    samples = store.mistake_samples(lid, lang, conn=conn).get(point_id, [])

    return {
        "language": lang,
        **plan.to_dict(),
        "failures": failures,
        "your_mistakes": samples,
        "warrants_remediation": failures >= remediation.REMEDIATION_THRESHOLD,
    }


@router.post("/remediation/{point_id:path}/done")
def finish_remediation(point_id: str, spec: UsableLang, learner: Learner) -> dict:
    """Mark a plan as worked through, and clear what it was built from.

    The mistakes are resolved, not deleted — they stay in the history the
    progress page draws from. What changes is that the app stops treating this
    as an open pattern, which it should not do while the learner has just spent
    eight minutes on it.
    """
    conn = get_connection()
    lid, lang = learner["id"], spec.code
    if point_id not in _points(lang, conn):
        raise HTTPException(404, f"no focus point {point_id!r} in {lang}")

    cleared = store.resolve_mistakes_for_focus(lid, lang, point_id, conn)
    return {
        "point": point_id,
        "cleared": cleared,
        "note": ("Those are marked as dealt with. If the same rule starts "
                 "failing again it will come back — this is not a promise that "
                 "you have learned it, only that you have worked on it."),
    }
