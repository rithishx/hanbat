"""Profile, first-run onboarding, placement, and settings."""

from __future__ import annotations

import random
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import store
from ..config import DEFAULT_SETTINGS, LEARNER_OWNED
from ..db import get_connection
from ..engines import exercises as X
from ..languages import registry
from .deps import Lang, Learner, UsableLang

router = APIRouter(tags=["learner"])


@router.get("/me")
def me(learner: Learner) -> dict:
    langs = store.learner_languages(learner["id"])
    return {
        "id": learner["id"], "name": learner["name"],
        "active_language": learner["active_language"],
        "onboarded": bool(learner["onboarded"]),
        "settings": learner["settings"],
        "streak": store.get_streak(learner["id"]),
        "languages": langs,
    }


# ==========================================================================
# First run
# ==========================================================================

@router.get("/onboarding/questions")
def onboarding_questions() -> dict:
    """The five first-run questions, as data so the UI does not hard-code them."""
    return {
        "greeting": {"native": "안녕하세요! 🇰🇷", "english": "Let's learn a language."},
        "questions": [
            {"id": "language", "question": "Which language do you want to learn?",
             "type": "single",
             "options": [
                 {"value": s.code, "label": f"{s.flag} {s.name}", "native": s.native_name,
                  "note": s.status_note if not s.is_usable else "",
                  "enabled": s.is_usable}
                 for s in registry.all_languages()]},
            {"id": "experience", "question": "Have you studied it before?",
             "type": "single",
             "options": [
                 {"value": "none", "label": "Never — complete beginner"},
                 {"value": "script", "label": "I can read the writing system"},
                 {"value": "beginner", "label": "A bit — some words and phrases"},
                 {"value": "intermediate", "label": "I can hold a simple conversation"},
                 {"value": "advanced", "label": "I'm fairly comfortable"}]},
            {"id": "goal", "question": "Why are you learning it?",
             "type": "single",
             "options": [
                 {"value": "travel", "label": "Travel"},
                 {"value": "living", "label": "I live there, or plan to"},
                 {"value": "media", "label": "Films, music, games, books"},
                 {"value": "people", "label": "Family, friends or a partner"},
                 {"value": "work", "label": "Work or study"},
                 {"value": "interest", "label": "Curiosity — I just want to"}]},
            {"id": "minutes", "question": "How much time can you give it most days?",
             "type": "single",
             "options": [
                 {"value": 5, "label": "5 minutes"},
                 {"value": 15, "label": "15 minutes"},
                 {"value": 30, "label": "30 minutes"},
                 {"value": 60, "label": "An hour or more"}],
             "note": "Be honest rather than ambitious. A streak you can keep beats one you break."},
        ],
    }


class OnboardRequest(BaseModel):
    language: str
    experience: str = "none"
    goal: str = ""
    minutes: int = 15
    name: str = ""


@router.post("/onboarding")
def onboard(req: OnboardRequest, learner: Learner) -> dict:
    """Build the learner's starting point from their answers."""
    spec = registry.try_get(req.language)
    if spec is None:
        raise registry.UnknownLanguage(req.language)
    if not spec.is_usable:
        raise HTTPException(409, {"error": "language_not_ready",
                                  "message": spec.status_note})

    conn = get_connection()
    store.update_learner(learner["id"], conn, name=req.name,
                         active_language=spec.code, onboarded=1)
    store.save_settings(learner["id"], {"daily_goal_minutes": req.minutes}, conn)

    start = {"none": "pre-A1", "script": "pre-A1", "beginner": "A1",
             "intermediate": "A2", "advanced": "B1"}.get(req.experience, "pre-A1")
    store.update_learner_language(learner["id"], spec.code, conn,
                                  level=start, start_level=start, goal=req.goal)

    needs_placement = req.experience not in ("none",)
    return {
        "language": spec.code,
        "starting_level": start,
        "needs_placement": needs_placement,
        "next": ("placement" if needs_placement else "first_lesson"),
        "message": (
            "Starting from the very beginning — the writing system first."
            if req.experience == "none" else
            "A short placement test will find the right starting point."),
    }


# ==========================================================================
# Placement
# ==========================================================================

@router.get("/placement")
def placement(spec: UsableLang, learner: Learner, seed: Optional[int] = None) -> dict:
    """An adaptive placement test built from real content.

    Sections run easiest-first and the UI stops when the learner starts
    failing, so a beginner answers a handful of questions rather than ploughing
    through advanced grammar to prove they cannot do it.
    """
    X.load_language_generators(spec.code)
    ctx = X.GenContext(language=spec.code,
                       rng=random.Random(seed) if seed is not None else random.Random(),
                       vocab=store.vocab(spec.code, limit=500),
                       script_units=store.script_units(spec.code))

    sections = []
    plan = [
        ("script", "Reading the writing system",
         {"type": "jamo_recognition", "count": 6, "hints": True}),
        ("reading", "Reading words",
         {"type": "syllable_read", "count": 6}),
        ("vocabulary", "Vocabulary",
         {"type": "vocab_recognise", "count": 8}),
        ("grammar", "Grammar",
         {"type": "particle_choice", "options": ["은", "는", "이", "가"], "count": 6}),
        ("listening", "Listening",
         {"type": "listen_type", "count": 5}),
    ]
    for key, title, gen in plan:
        built = X.generate(gen, ctx)
        if built and built[0].kind not in ("unsupported", "error"):
            sections.append({"id": key, "title": title,
                             "exercises": [e.to_dict() for e in built]})

    return {
        "language": spec.code,
        "sections": sections,
        "instructions": "Answer what you can. Skipping is fine — it tells us just as much.",
        "adaptive": True,
        "stop_rule": "Stop a section after three wrong in a row and move on.",
    }


class PlacementResult(BaseModel):
    scores: dict[str, float] = Field(..., description="section id -> 0..1")


@router.post("/placement")
def submit_placement(req: PlacementResult, spec: UsableLang, learner: Learner) -> dict:
    """Turn section scores into a starting level.

    The estimate is deliberately pessimistic: it uses the *weakest* section
    rather than the average, because a learner who scores well on vocabulary
    and badly on reading cannot use the vocabulary yet.
    """
    scores = req.scores or {}
    script = scores.get("script", 0.0)
    weakest = min(scores.values()) if scores else 0.0
    average = sum(scores.values()) / len(scores) if scores else 0.0

    try:
        ladder = spec.levels
    except ModuleNotFoundError:
        ladder = None

    if script < 0.85:
        level = ladder.levels[0] if ladder else "pre-A1"
        reason = ("You are not fully fluent with the writing system yet, so we start "
                  "there. Everything else is built on it.")
    else:
        # Map the weakest section onto the ladder, one band below the average.
        bands = list(ladder.levels) if ladder else ["pre-A1", "A1", "A2", "B1"]
        idx = min(len(bands) - 1, max(1, int(weakest * (len(bands) - 1))))
        level = bands[idx]
        reason = (f"Your strongest areas scored around {average:.0%}, but the weakest "
                  f"was {weakest:.0%}. We start at the level you can use everywhere, "
                  f"not the one you can reach on a good day.")

    conn = get_connection()
    store.update_learner_language(learner["id"], spec.code, conn,
                                  level=level, start_level=level,
                                  script_mastery=script)
    described = ladder.describe(level) if ladder else {"level": level}
    return {"language": spec.code, "level": level, "reason": reason,
            "details": described}


# ==========================================================================
# Settings
# ==========================================================================

@router.get("/settings")
def get_settings(learner: Learner) -> dict:
    return {
        "settings": learner["settings"],
        "defaults": DEFAULT_SETTINGS,
        "learner_owned": sorted(LEARNER_OWNED),
        "note": ("Settings marked learner-owned are never changed automatically. "
                 "Everything else the app may adapt as you improve — romanisation "
                 "fades on its own unless you pin it."),
    }


class SettingsPatch(BaseModel):
    settings: dict


@router.patch("/settings")
def patch_settings(req: SettingsPatch, learner: Learner) -> dict:
    unknown = set(req.settings) - set(DEFAULT_SETTINGS)
    if unknown:
        raise HTTPException(400, f"unknown settings: {sorted(unknown)}")
    return {"settings": store.save_settings(learner["id"], req.settings)}
