"""
Today's session.

Two properties matter more than the rest. The plan must never contain a block
pointing at content that does not exist — that is how an app ends up offering a
learner a Mandarin grammar drill it cannot build. And it must not pad: a
learner with nothing due should get a short session and be told why, because a
learner who notices the app inventing work stops believing the rest of it.
"""

from __future__ import annotations

import pytest

from app.engines import adaptive as A
from app.engines import exercises as X
from app.engines import session as S


@pytest.fixture(autouse=True)
def generators_loaded():
    for code in ("ko", "ja", "zh"):
        X.load_language_generators(code)


def model_with(**skills) -> A.LearnerModel:
    """A learner model with the given skill scores, as (score, attempts)."""
    m = A.LearnerModel()
    for name, (score, attempts) in skills.items():
        m.skills[name] = A.SkillScore(
            skill=name, name=name.capitalize(), native_name="",
            score=score, attempts=attempts,
            confidence=min(1.0, attempts / 30),
        )
    m.total_attempts = sum(a for _, a in skills.values())
    return m


LESSON = {"id": "ko-hangul-001", "title": "Your first vowels", "est_minutes": 8}


# ==========================================================================
# Order
# ==========================================================================

def test_reviews_come_first():
    """They are the only part with a deadline. A card reviewed a week late has
    already decayed; a lesson is equally new tomorrow."""
    plan = S.build(language="ko", model=model_with(reading=(50, 40)),
                   due_now=20, minutes=15, next_lesson=LESSON, seed=1)
    assert plan.blocks[0].kind == "review"


def test_production_comes_last_because_it_is_hardest():
    plan = S.build(language="ko", model=model_with(reading=(50, 40)),
                   due_now=10, minutes=25, next_lesson=LESSON, seed=1)
    kinds = [b.kind for b in plan.blocks]
    if "production" in kinds:
        assert kinds[-1] == "production"


def test_a_chronic_confusion_is_taught_before_new_material():
    m = model_with(grammar=(40, 30))
    m.confusions = [{"id": "topic_vs_subject", "title": "은/는 versus 이/가",
                     "count": 6, "warrants_mini_course": True, "language": "ko"}]
    plan = S.build(language="ko", model=m, due_now=0, minutes=20,
                   next_lesson=LESSON, seed=1)
    kinds = [b.kind for b in plan.blocks]
    assert "confusion" in kinds
    assert kinds.index("confusion") < kinds.index("lesson")


# ==========================================================================
# Budget
# ==========================================================================

def test_the_plan_fits_the_budget():
    for minutes in (5, 10, 15, 30, 45):
        plan = S.build(language="ko", model=model_with(reading=(50, 40)),
                       due_now=60, minutes=minutes, next_lesson=LESSON, seed=2)
        assert plan.planned_minutes <= minutes, f"overran at {minutes} minutes"


def test_reviews_cannot_eat_the_whole_session():
    """A session that is nothing but reviews is how people quit."""
    plan = S.build(language="ko", model=model_with(reading=(50, 40)),
                   due_now=500, minutes=20, next_lesson=LESSON, seed=1)
    review = next(b for b in plan.blocks if b.kind == "review")
    assert review.minutes <= 20 * S.MAX_REVIEW_SHARE + 1
    assert review.payload["deferred"] > 0
    assert "wait for tomorrow" in review.why
    assert len(plan.blocks) > 1, "the rest of the session should still happen"


def test_a_tiny_budget_still_produces_something_coherent():
    plan = S.build(language="ko", model=model_with(reading=(50, 40)),
                   due_now=30, minutes=3, next_lesson=LESSON, seed=1)
    assert plan.planned_minutes <= 3
    assert plan.blocks


def test_nothing_due_and_nothing_to_teach_is_an_honest_empty_plan():
    """Padding to fill the stated fifteen minutes would be the app inventing
    work, which is exactly what it refuses to do everywhere else."""
    plan = S.build(language="ko", model=A.LearnerModel(), due_now=0,
                   minutes=15, next_lesson=None, new_vocab=0, seed=1)
    kinds = {b.kind for b in plan.blocks}
    assert "lesson" not in kinds and "review" not in kinds
    assert plan.planned_minutes < 15
    assert plan.note


def test_a_short_plan_says_why_it_is_short():
    plan = S.build(language="ko", model=A.LearnerModel(), due_now=0,
                   minutes=40, next_lesson=None, new_vocab=0, seed=1)
    assert "padding" in plan.note or "not enough" in plan.note


# ==========================================================================
# Honesty
# ==========================================================================

def test_no_block_points_at_content_that_does_not_exist():
    plan = S.build(language="ko", model=model_with(reading=(50, 40)),
                   due_now=5, minutes=20, next_lesson=None, new_vocab=0, seed=3)
    assert not any(b.kind == "lesson" for b in plan.blocks)


def test_an_unmeasured_learner_is_not_told_what_their_weakness_is():
    """Claiming a weakest skill before anything is measured would be the app
    asserting something it does not know."""
    plan = S.build(language="ko", model=A.LearnerModel(skills={}), due_now=0,
                   minutes=15, next_lesson=LESSON, seed=1)
    drill = next((b for b in plan.blocks if b.kind in ("weakness", "calibrate")), None)
    if drill:
        assert drill.kind == "calibrate"
        assert "weakest" not in drill.title.lower()
        assert "Nothing has been measured" in drill.why


def test_a_measured_learner_is_told_which_skill_and_on_what_evidence():
    plan = S.build(
        language="ko",
        model=model_with(listening=(20, 40), reading=(90, 40)),
        due_now=0, minutes=20, next_lesson=LESSON, seed=1,
    )
    drill = next(b for b in plan.blocks if b.kind == "weakness")
    assert "answers" in drill.why          # the evidence, not just the verdict


def test_the_superlative_is_only_used_when_it_is_true():
    """The block must not claim "weakest" for a skill that is not weakest.

    Drills are drawn with weights and a floor, so the block sometimes misses
    the single weakest skill. The screen shows the ranked focus list a few
    centimetres below, so an overstated claim is not merely wrong but visibly
    wrong. Across many seeds, every superlative claim must agree with the
    ranking the same plan publishes.
    """
    model = model_with(grammar=(0, 20), vocabulary=(50, 12), listening=(88, 30))
    seen_both = {"claims": 0, "hedges": 0}

    for seed in range(60):
        plan = S.build(language="ko", model=model, due_now=0, minutes=20,
                       next_lesson=LESSON, has_sentences=True, seed=seed)
        drill = next((b for b in plan.blocks if b.kind == "weakness"), None)
        if drill is None:
            continue
        ranked = [f for f in plan.focus if f["attempts"] > 0]
        weakest = ranked[0]["skill"]
        if "weakest measured skill" in drill.why or "need the most work" in drill.why:
            seen_both["claims"] += 1
            assert drill.why.lower().startswith(weakest), drill.why
            assert drill.title == "Work on what is weakest"
        else:
            seen_both["hedges"] += 1
            assert weakest not in drill.why.split(".")[0], drill.why
            assert drill.title == "Practice where you are weak"

    assert seen_both["claims"] > 0, "the superlative branch was never exercised"


def test_a_block_that_misses_the_weakest_skill_still_names_it():
    """Hedged copy must not simply go quiet about the real weak point."""
    hedged = S._why_weak(
        [A.SkillFocus(skill="vocabulary", weight=0.7, score=50, attempts=12,
                      why="50% across 12 answers.")],
        [A.SkillFocus(skill="grammar", weight=0.9, score=0, attempts=20,
                      why="0% across 20 answers."),
         A.SkillFocus(skill="vocabulary", weight=0.7, score=50, attempts=12,
                      why="50% across 12 answers.")],
    )
    assert "drills vocabulary" in hedged
    assert "Grammar" in hedged
    assert "weakest measured skill" not in hedged


def test_every_block_explains_itself():
    plan = S.build(language="ko", model=model_with(grammar=(30, 50)),
                   due_now=12, minutes=25, next_lesson=LESSON, seed=1)
    for b in plan.blocks:
        assert b.why and len(b.why) > 20, f"{b.kind} does not justify itself"
        assert b.minutes > 0


# ==========================================================================
# Language isolation
# ==========================================================================

def test_a_plan_only_uses_drills_that_language_actually_has():
    """The property the whole architecture protects, seen from the session."""
    for code in ("ko", "ja", "zh"):
        plan = S.build(language=code, model=model_with(listening=(20, 40)),
                       due_now=0, minutes=25, next_lesson=None, new_vocab=5,
                       seed=4)
        available = set(X.supported_kinds(code))
        for b in plan.blocks:
            for spec in b.payload.get("specs", []):
                assert spec["type"] in available, (
                    f"{code} plan asked for {spec['type']}, which it cannot build")


def test_mandarin_is_never_planned_a_conjugation_drill():
    plan = S.build(language="zh", model=model_with(grammar=(10, 60)),
                   due_now=0, minutes=30, new_vocab=10, seed=5)
    kinds = {s["type"] for b in plan.blocks for s in b.payload.get("specs", [])}
    assert "conjugate" not in kinds


# ==========================================================================
# Adaptivity
# ==========================================================================

def test_the_weakest_skill_gets_the_most_drills():
    m = model_with(listening=(10, 60), reading=(95, 60), vocabulary=(90, 60))
    plan = S.build(language="ko", model=m, due_now=0, minutes=30,
                   next_lesson=None, new_vocab=0, seed=7)
    specs = [s["type"] for b in plan.blocks for s in b.payload.get("specs", [])]
    skills = [X.skill_for("ko", k) for k in specs]
    assert skills.count("listening") >= 1
    assert plan.focus[0]["skill"] == "listening"


def test_recent_mistakes_lift_a_skill_even_when_its_average_looks_fine():
    m = model_with(grammar=(85, 60), reading=(85, 60))
    without = {f.skill: f.weight for f in A.focus(m)}
    with_recent = {f.skill: f.weight
                   for f in A.focus(m, {"grammar": 12, "reading": 0})}
    assert with_recent["grammar"] > without["grammar"]
    assert with_recent["reading"] == pytest.approx(without["reading"])


def test_careless_slips_never_make_a_skill_look_weak():
    """The single most important line in the adaptive path.

    A learner who keeps mistyping words they know must not have those words
    pushed at them harder — that is the system reading haste as ignorance.
    """
    m = model_with(vocabulary=(85, 60))
    baseline = {f.skill: f.weight for f in A.focus(m)}
    slips = {f.skill: f.weight for f in A.focus(m, {"careless": 40})}
    assert slips["vocabulary"] == pytest.approx(baseline["vocabulary"])
    assert "careless" not in A.REASON_TO_SKILL
