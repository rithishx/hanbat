"""
Shared dependencies for the routers.

The important one is `Lang`: every endpoint that touches learner data resolves
its language through this, which validates the code and returns the spec. An
endpoint that forgets to depend on it cannot compile a query, because `store`
requires a language argument.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Query

from .. import store
from ..languages import registry
from ..languages.registry import LanguageSpec


def resolve_language(
    lang: Optional[str] = Query(
        None, description="Language code (ko, ja, zh). Defaults to the learner's active language."),
) -> LanguageSpec:
    """Resolve the target language for this request.

    Falls back to the learner's active language rather than to a hard-coded
    default, so switching language in the UI changes every screen at once.
    """
    if lang:
        spec = registry.try_get(lang)
        if spec is None:
            raise registry.UnknownLanguage(lang)
        return spec
    learner = store.get_or_create_learner()
    return registry.get(learner.get("active_language") or registry.DEFAULT_LANGUAGE)


def require_usable(spec: LanguageSpec = Depends(resolve_language)) -> LanguageSpec:
    """For endpoints that need real content, not just a registration.

    Japanese and Mandarin are registered before their curricula exist. Rather
    than returning empty lists that look like a bug, these endpoints say
    plainly that the language is not ready and what state it is in.
    """
    if not spec.is_usable:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "language_not_ready",
                "language": spec.code,
                "status": spec.status,
                "message": spec.status_note,
            },
        )
    return spec


def current_learner() -> dict:
    return store.get_or_create_learner()


Lang = Annotated[LanguageSpec, Depends(resolve_language)]
UsableLang = Annotated[LanguageSpec, Depends(require_usable)]
Learner = Annotated[dict, Depends(current_learner)]
