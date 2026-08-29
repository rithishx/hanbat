"""
Import and export. The learner owns their data.

Export produces a single JSON file containing every row of learner progress —
every card, every attempt, every mistake, in every language. It is complete
enough to restore onto a fresh install, and readable enough to inspect in a
text editor. Content is deliberately excluded: it is regenerated from the JSON
files, and including it would triple the file size for nothing.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import store
from ..db import SCHEMA_VERSION, get_connection, query
from ..languages import registry
from .deps import Lang, Learner

router = APIRouter(prefix="/data", tags=["data"])

EXPORT_VERSION = 1

#: Learner-owned tables, in dependency order for restore.
PROGRESS_TABLES = (
    "learner", "learner_language", "streak", "srs_card", "attempt",
    "lesson_progress", "mistake", "study_session", "daily_goal",
    "achievement", "conversation", "recording",
)


@router.get("/export")
def export_progress(learner: Learner, language: Optional[str] = None) -> dict:
    """Everything, or one language's slice of it."""
    conn = get_connection()
    payload: dict = {
        "format": "hanbat-progress",
        "export_version": EXPORT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "language_filter": language,
        "tables": {},
    }
    for table in PROGRESS_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if not cols:
            continue
        sql = f"SELECT * FROM {table}"
        args: list = []
        wheres = []
        if "learner_id" in cols:
            wheres.append("learner_id = ?"); args.append(learner["id"])
        elif table == "learner":
            wheres.append("id = ?"); args.append(learner["id"])
        if language and "language" in cols:
            wheres.append("language = ?"); args.append(language)
        if wheres:
            sql += " WHERE " + " AND ".join(wheres)
        payload["tables"][table] = query(sql, args, conn)

    payload["counts"] = {t: len(rows) for t, rows in payload["tables"].items()}
    return payload


@router.get("/export/file")
def export_file(learner: Learner, language: Optional[str] = None):
    payload = export_progress(learner, language)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    name = f"hanbat-progress-{language or 'all'}-{stamp}.json"
    return StreamingResponse(
        io.BytesIO(body.encode("utf-8")), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


class ImportRequest(BaseModel):
    payload: dict
    #: "merge" keeps existing rows and adds missing ones. "replace" wipes this
    #: learner's progress first. Merge is the default because the destructive
    #: option should never be the one you get by accident.
    mode: str = "merge"


@router.post("/import")
def import_progress(req: ImportRequest, learner: Learner) -> dict:
    payload = req.payload
    if payload.get("format") != "hanbat-progress":
        raise HTTPException(400, "not a Hanbat progress export")
    if payload.get("export_version", 0) > EXPORT_VERSION:
        raise HTTPException(
            400, f"this file was written by a newer version "
                 f"(export_version {payload['export_version']}); upgrade first")

    conn = get_connection()
    lid = learner["id"]
    restored: dict[str, int] = {}
    skipped: dict[str, int] = {}

    if req.mode == "replace":
        for table in reversed(PROGRESS_TABLES):
            if table == "learner":
                continue
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            if "learner_id" in cols:
                conn.execute(f"DELETE FROM {table} WHERE learner_id = ?", (lid,))
        conn.commit()

    for table, rows in (payload.get("tables") or {}).items():
        if table not in PROGRESS_TABLES or table == "learner":
            continue
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if not cols or not rows:
            continue
        n = 0
        for row in rows:
            data = {k: v for k, v in row.items() if k in cols}
            if "learner_id" in cols:
                data["learner_id"] = lid          # always land on this profile
            data.pop("id", None)                  # let autoincrement reassign
            if not data:
                continue
            placeholders = ", ".join("?" for _ in data)
            try:
                conn.execute(
                    f"INSERT OR IGNORE INTO {table} ({', '.join(data)}) "
                    f"VALUES ({placeholders})", tuple(data.values()))
                n += 1
            except Exception:
                skipped[table] = skipped.get(table, 0) + 1
        restored[table] = n
    conn.commit()

    return {"imported": True, "mode": req.mode, "restored": restored,
            "skipped": skipped,
            "note": "Content was not imported — it is rebuilt from the JSON files."}


@router.post("/import/file")
async def import_file(file: UploadFile = File(...), mode: str = "merge",
                      learner: dict = None) -> dict:
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(400, f"could not read that file: {e}")
    return import_progress(ImportRequest(payload=payload, mode=mode),
                           learner or store.get_or_create_learner())


# ==========================================================================
# Vocabulary export
# ==========================================================================

@router.get("/export/vocab.csv")
def export_vocab_csv(spec: Lang, learner: Learner, known_only: bool = False):
    """Vocabulary as CSV, with the learner's own progress attached."""
    conn = get_connection()
    sql = """
        SELECT v.term, v.meaning, v.pos, v.topic, v.level, v.transliteration,
               v.pronunciation, v.example_native, v.example_en,
               COALESCE(c.state,'') AS srs_state,
               COALESCE(c.total_reviews,0) AS reviews,
               COALESCE(c.due_at,'') AS due_at
        FROM vocab v
        LEFT JOIN srs_card c ON c.item_id = v.id AND c.item_type='vocab'
             AND c.learner_id = ? AND c.language = v.language
        WHERE v.language = ?
    """
    args: list = [learner["id"], spec.code]
    if known_only:
        sql += " AND c.state IN ('review','mastered')"
    sql += " ORDER BY COALESCE(v.frequency_rank, 99999)"

    rows = query(sql, args, conn)
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")), media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="hanbat-vocab-{spec.code}-{stamp}.csv"'})


@router.get("/export/anki.txt")
def export_anki(spec: Lang, learner: Learner, known_only: bool = False):
    """Anki-compatible tab-separated import.

    Plain text rather than a .apkg: the tab-separated format imports cleanly
    into Anki without a dependency on their package library, and the learner
    can see exactly what they are getting.
    """
    conn = get_connection()
    sql = """
        SELECT v.term, v.meaning, v.transliteration, v.example_native,
               v.example_en, v.topic, v.level
        FROM vocab v
        LEFT JOIN srs_card c ON c.item_id = v.id AND c.item_type='vocab'
             AND c.learner_id = ? AND c.language = v.language
        WHERE v.language = ?
    """
    args: list = [learner["id"], spec.code]
    if known_only:
        sql += " AND c.state IN ('review','mastered')"
    rows = query(sql, args, conn)

    lines = ["#separator:tab", "#html:false",
             f"#tags column:7", "#notetype column:0"]
    for r in rows:
        back = r["meaning"]
        if r["example_native"]:
            back += f"<br><br>{r['example_native']}"
            if r["example_en"]:
                back += f"<br>{r['example_en']}"
        tags = " ".join(t for t in (spec.code, r["topic"], r["level"]) if t)
        lines.append("\t".join([r["term"], back, r["transliteration"] or "",
                                "", "", "", tags]))
    body = "\n".join(lines)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return StreamingResponse(
        io.BytesIO(body.encode("utf-8")), media_type="text/plain",
        headers={"Content-Disposition":
                 f'attachment; filename="hanbat-anki-{spec.code}-{stamp}.txt"'})


@router.get("/backup/list")
def backups() -> dict:
    """Database backups the migration runner has taken."""
    from ..config import DB_PATH
    parent = DB_PATH.parent
    found = sorted(parent.glob(f"{DB_PATH.stem}.backup-*"), reverse=True)
    return {"backups": [
        {"path": str(p), "name": p.name, "bytes": p.stat().st_size,
         "modified": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()}
        for p in found]}
