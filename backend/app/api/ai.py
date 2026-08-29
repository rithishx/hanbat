"""
The optional AI tutor.

Every endpoint here works when no model is installed — it returns
`available: false` with a reason the UI can show, and the UI hides the tutor
rather than offering a button that fails. Nothing in this file ever fabricates
a tutor reply.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import store
from ..db import get_connection, now_iso, query, query_one
from ..engines.ai import base as ai_base
from ..engines.ai import tutor as ai_tutor
from .deps import Learner, UsableLang

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def status(learner: Learner) -> dict:
    """What is installed, and what is selected."""
    settings = learner["settings"]
    providers = ai_base.probe_all()
    selected = settings.get("ai_provider", "disabled")
    current = next((p for p in providers if p.id == selected), None)
    return {
        "selected_provider": selected,
        "selected_model": settings.get("ai_model", ""),
        "enabled": selected != "disabled",
        "available": bool(current and current.available and current.models),
        "providers": [p.to_dict() for p in providers],
        "note": ("The tutor is optional. Lessons, drills, reviews, progress and "
                 "the whole curriculum work without it."),
    }


def _context(learner: dict, spec, conn) -> ai_tutor.LearnerContext:
    lid, lang = learner["id"], spec.code
    ll = store.get_learner_language(lid, lang, conn)
    known_vocab = [r["term"] for r in query(
        "SELECT v.term FROM srs_card c JOIN vocab v ON v.id = c.item_id "
        "WHERE c.learner_id=? AND c.language=? AND c.item_type='vocab' "
        "AND c.state IN ('review','mastered','learning') LIMIT 120",
        (lid, lang), conn)]
    known_grammar = [r["name"] for r in query(
        "SELECT g.name FROM srs_card c JOIN grammar g ON g.id = c.item_id "
        "WHERE c.learner_id=? AND c.language=? AND c.item_type='grammar' LIMIT 60",
        (lid, lang), conn)]
    settings = learner["settings"]
    return ai_tutor.LearnerContext(
        language=lang,
        level=ll.get("level", ""),
        goal=ll.get("goal", ""),
        known_vocab=known_vocab,
        known_grammar=known_grammar,
        recent_mistakes=store.mistakes(lid, lang, True, 8, conn),
        explanation_language=settings.get("explanation_language", "en"),
        romanization=settings.get("romanization") != "never",
    )


class AskRequest(BaseModel):
    message: str
    history: list[dict] = []
    mode: str = "auto"          # auto | correct | explain
    conversation_id: Optional[int] = None


@router.post("/ask")
def ask(req: AskRequest, spec: UsableLang, learner: Learner) -> dict:
    conn = get_connection()
    provider = ai_base.build(learner["settings"])
    if provider.id == "disabled":
        return {"available": False,
                "reason": "The AI tutor is switched off in Settings.",
                "text": ""}

    ctx = _context(learner, spec, conn)
    result = ai_tutor.ask(provider, ctx, req.history, req.message,
                          socratic=bool(learner["settings"].get("ai_socratic", True)),
                          mode=req.mode)
    if not result.available:
        st = provider.status()
        return {"available": False, "reason": st.hint or result.error,
                "error": result.error, "text": ""}

    giveaway = ai_tutor.looks_like_a_giveaway(result.text)
    out = {
        **result.to_dict(),
        "gave_away_the_answer": giveaway,
        "collapse_answer": giveaway and bool(learner["settings"].get("ai_socratic", True)),
    }

    if req.conversation_id:
        _append(conn, req.conversation_id, req.message, result.text)
    return out


class ConversationStart(BaseModel):
    scenario_id: Optional[str] = None


@router.post("/conversation")
def start_conversation(req: ConversationStart, spec: UsableLang, learner: Learner) -> dict:
    """Begin a roleplay. Returns the scenario even when no model is installed,
    so the learner can still read and practise the scripted version."""
    conn = get_connection()
    scenario = None
    if req.scenario_id:
        scenario = query_one("SELECT * FROM scenario WHERE id = ?", (req.scenario_id,), conn)
        if scenario is None:
            raise HTTPException(404, f"no scenario {req.scenario_id!r}")
        for k in ("roles", "script", "vocabulary", "goals"):
            if isinstance(scenario.get(k), str):
                scenario[k] = json.loads(scenario[k])

    ll = store.get_learner_language(learner["id"], spec.code, conn)
    provider = ai_base.build(learner["settings"])
    cur = conn.execute(
        "INSERT INTO conversation(learner_id, language, scenario_id, started_at, "
        "level, provider, model, transcript) VALUES (?,?,?,?,?,?,?,'[]')",
        (learner["id"], spec.code, req.scenario_id or "", now_iso(),
         ll.get("level", ""), provider.id, learner["settings"].get("ai_model", "")))
    conn.commit()

    return {
        "conversation_id": cur.lastrowid,
        "language": spec.code,
        "scenario": scenario,
        "ai_available": provider.id != "disabled",
        "opener": ai_tutor.conversation_opener(spec.code, ll.get("level", "A1"), scenario),
        "note": ("No model is configured, so the scripted dialogue is shown instead "
                 "of a live partner." if provider.id == "disabled" else ""),
    }


def _append(conn, conversation_id: int, user: str, assistant: str) -> None:
    row = query_one("SELECT transcript FROM conversation WHERE id = ?",
                    (conversation_id,), conn)
    if row is None:
        return
    try:
        t = json.loads(row["transcript"])
    except (TypeError, ValueError):
        t = []
    t.append({"role": "user", "content": user})
    t.append({"role": "assistant", "content": assistant})
    conn.execute("UPDATE conversation SET transcript = ? WHERE id = ?",
                 (json.dumps(t, ensure_ascii=False), conversation_id))
    conn.commit()


@router.get("/conversations")
def conversations(spec: UsableLang, learner: Learner, limit: int = 20) -> dict:
    rows = query(
        "SELECT id, scenario_id, started_at, level, provider, model "
        "FROM conversation WHERE learner_id=? AND language=? "
        "ORDER BY started_at DESC LIMIT ?",
        (learner["id"], spec.code, limit))
    return {"language": spec.code, "conversations": rows}


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: int) -> dict:
    row = query_one("SELECT * FROM conversation WHERE id = ?", (conversation_id,))
    if row is None:
        raise HTTPException(404, "no such conversation")
    try:
        row["transcript"] = json.loads(row["transcript"])
    except (TypeError, ValueError):
        row["transcript"] = []
    return row


@router.get("/scenarios")
def scenarios(spec: UsableLang, level: Optional[str] = None) -> dict:
    sql = "SELECT id, title, title_native, level, setting FROM scenario WHERE language = ?"
    args: list = [spec.code]
    if level:
        sql += " AND level = ?"; args.append(level)
    return {"language": spec.code, "scenarios": query(sql, args)}
