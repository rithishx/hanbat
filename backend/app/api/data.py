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
import shutil
from datetime import datetime, timezone
from pathlib import Path
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
    """Every backup on disk, whoever took it.

    Migrations take one automatically before touching anything; a learner can
    take one whenever they like. Both land in the same place with the same
    naming, so restoring does not care which kind it is.
    """
    return {"backups": _list_backups(),
            "note": ("Backups sit beside the database. Copying that folder "
                     "somewhere else is a complete backup of everything the "
                     "app knows about you — there is no server copy.")}


def _list_backups() -> list[dict]:
    from ..config import DB_PATH
    found = sorted(DB_PATH.parent.glob(f"{DB_PATH.stem}.backup-*"), reverse=True)
    return [
        {"path": str(p), "name": p.name, "bytes": p.stat().st_size,
         "modified": datetime.fromtimestamp(
             p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}
        for p in found if p.suffix not in ("-wal", "-shm")
        and not p.name.endswith(("-wal", "-shm"))
    ]


@router.post("/backup")
def create_backup() -> dict:
    """Take a backup now.

    A checkpoint first, because the database runs in WAL mode: without it the
    most recent writes live in the -wal file and a copy of the main file alone
    would silently be out of date. That is the failure mode where someone
    discovers their backup was useless at the worst possible moment.
    """
    from ..config import DB_PATH
    from ..db import get_connection
    from .. import migrations

    conn = get_connection()
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:                       # not fatal — the -wal is copied too
        pass

    path = migrations.backup(Path(str(DB_PATH)))
    if path is None:
        raise HTTPException(409, "There is no database file to back up yet.")
    return {"created": True, "name": path.name, "path": str(path),
            "bytes": path.stat().st_size,
            "note": "The previous state is untouched — this is a copy, not a move."}


class RestoreRequest(BaseModel):
    name: str


@router.post("/backup/restore")
def restore_backup(req: RestoreRequest) -> dict:
    """Roll the database back to a backup.

    Two safeguards, both non-negotiable. The *current* state is backed up first,
    so restoring can itself be undone — a restore that destroys the thing it
    replaced is a trap rather than a safety net. And the candidate is opened and
    integrity-checked before anything is overwritten, so a corrupt backup is
    refused rather than installed.

    The server keeps running afterwards on the restored file; the connection
    cache is cleared so no thread keeps reading the old one.
    """
    from ..config import DB_PATH
    from .. import db as db_module
    from .. import migrations

    target = Path(str(DB_PATH))
    candidates = {b["name"]: Path(b["path"]) for b in _list_backups()}
    source = candidates.get(req.name)
    if source is None:
        raise HTTPException(404, {
            "error": "no_such_backup", "message": f"No backup named {req.name!r}.",
            "available": sorted(candidates)})

    verdict = _check_file(source)
    if not verdict["ok"]:
        raise HTTPException(422, {
            "error": "backup_is_damaged",
            "message": f"{req.name} did not pass an integrity check, so it was "
                       f"not restored. Your current data is untouched.",
            "detail": verdict})

    safety = migrations.backup(target)
    db_module.close_all()
    shutil.copy2(source, target)
    for suffix in ("-wal", "-shm"):
        side = Path(str(source) + suffix)
        dest = Path(str(target) + suffix)
        if side.exists():
            shutil.copy2(side, dest)
        elif dest.exists():
            dest.unlink()          # a stale WAL would resurrect the old data

    conn = db_module.get_connection()
    db_module.init_db(conn, target)
    return {
        "restored": req.name,
        "previous_state_saved_as": safety.name if safety else None,
        "schema_version": migrations.current_version(conn),
        "note": ("Your state before the restore was saved first, so this can "
                 "be undone the same way."),
    }


@router.get("/integrity")
def integrity() -> dict:
    """Is the database sound, and does it hold what it should?

    Runs SQLite's own integrity check, reports the schema version against the
    one this build expects, and counts the learner tables — the ones that exist
    nowhere else. Content tables are excluded on purpose: they are a rebuildable
    cache, and a low count there means "reload", not "data loss".
    """
    from ..config import DB_PATH
    from ..db import SCHEMA_VERSION, get_connection
    from .. import migrations

    conn = get_connection()
    result = _check_conn(conn)
    version = migrations.current_version(conn)
    counts = {t: _count(conn, t) for t in migrations.LEARNER_TABLES}

    return {
        **result,
        "path": str(DB_PATH),
        "bytes": Path(str(DB_PATH)).stat().st_size if Path(str(DB_PATH)).exists() else 0,
        "schema_version": version,
        "expected_schema_version": SCHEMA_VERSION,
        "up_to_date": version == SCHEMA_VERSION,
        "learner_rows": counts,
        "total_learner_rows": sum(n for n in counts.values() if n >= 0),
        "backups": len(_list_backups()),
        "note": ("Content tables are not counted here. They are a cache of the "
                 "JSON files and can be rebuilt at any time; only the learner "
                 "tables hold anything irreplaceable."),
    }


def _check_conn(conn) -> dict:
    try:
        rows = [r[0] for r in conn.execute("PRAGMA integrity_check")]
        foreign = conn.execute("PRAGMA foreign_key_check").fetchall()
    except Exception as e:                              # noqa: BLE001 - reported
        return {"ok": False, "integrity": [str(e)], "foreign_key_violations": -1}
    return {
        "ok": rows == ["ok"] and not foreign,
        "integrity": rows,
        "foreign_key_violations": len(foreign),
    }


def _check_file(path: Path) -> dict:
    import sqlite3

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        return {"ok": False, "integrity": [str(e)], "foreign_key_violations": -1}
    try:
        return _check_conn(conn)
    finally:
        conn.close()


def _count(conn, table: str) -> int:
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return -1
