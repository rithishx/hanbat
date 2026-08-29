"""Language registry endpoints: what exists, and which one is active."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import store
from ..languages import registry
from .deps import Lang, Learner

router = APIRouter(prefix="/languages", tags=["languages"])


class SwitchRequest(BaseModel):
    language: str


@router.get("")
def list_languages(learner: Learner) -> dict:
    """Every registered language, with this learner's progress in each.

    Feeds both the language switcher and the 'My Languages' panel. Languages
    whose modules are unfinished appear with an honest status rather than
    being hidden — a learner should be able to see what is coming.
    """
    progress = {p["language"]: p for p in store.learner_languages(learner["id"])}
    out = []
    for spec in registry.all_languages():
        p = progress.get(spec.code, {})
        out.append({
            **spec.to_dict(),
            "started": bool(p),
            "level": p.get("level", ""),
            "xp": p.get("xp", 0),
            "script_mastery": p.get("script_mastery", 0.0),
            "known_items": p.get("known_items", 0),
            "due_now": p.get("due_now", 0),
            "last_studied": p.get("last_studied"),
            "is_active": spec.code == learner.get("active_language"),
        })
    return {"languages": out, "active": learner.get("active_language")}


@router.get("/active")
def active(learner: Learner, spec: Lang) -> dict:
    return spec.to_dict(include_engines=spec.is_usable)


@router.post("/active")
def switch(req: SwitchRequest, learner: Learner) -> dict:
    """Switch the active language.

    This changes curriculum, vocabulary, grammar, writing system, exercises,
    progress and recommendations in one move. It does not touch any stored
    progress — each language's data was always separate.
    """
    spec = registry.try_get(req.language)
    if spec is None:
        raise registry.UnknownLanguage(req.language)
    store.update_learner(learner["id"], active_language=spec.code)
    store.get_learner_language(learner["id"], spec.code)
    return {
        "active": spec.code,
        "language": spec.to_dict(include_engines=spec.is_usable),
        "usable": spec.is_usable,
    }


@router.get("/{code}")
def one(code: str) -> dict:
    spec = registry.try_get(code)
    if spec is None:
        raise registry.UnknownLanguage(code)
    d = spec.to_dict(include_engines=spec.is_usable)
    if spec.is_usable:
        try:
            ladder = spec.levels
            d["level_details"] = [ladder.describe(l) for l in ladder.levels]
        except ModuleNotFoundError:
            pass
        try:
            d["pronunciation_difficulties"] = spec.pronunciation.difficulty_points()
        except ModuleNotFoundError:
            pass
    return d


@router.get("/{code}/writing-systems")
def writing_systems(code: str) -> dict:
    spec = registry.try_get(code)
    if spec is None:
        raise registry.UnknownLanguage(code)
    return {"language": code,
            "writing_systems": [w.to_dict() for w in spec.writing_systems]}
