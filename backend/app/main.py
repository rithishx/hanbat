"""
The application.

Binds to loopback only. Everything a learner does — their vocabulary, their
mistakes, their recordings — stays on their machine, and the one way that
stops being true is a server listening on 0.0.0.0. Overriding the bind address
is possible but logs a warning that says exactly what it exposes.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import (
    AUDIO_DIR, DEV_ORIGINS, FRONTEND_DIST, HOST, NETWORK_FEATURES, PORT,
    RuntimeInfo,
)
from .content import loader
from .engines import exercises
from .languages import registry

log = logging.getLogger("hanbat")

VERSION = "0.2.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-7s %(name)s  %(message)s",
    )
    log.info("Hanbat %s starting", VERSION)

    conn = db.get_connection()
    db.init_db(conn, verbose=True)
    log.info("database ready at %s (schema v%s)", db.DB_PATH, db.SCHEMA_VERSION)

    report = loader.load_all(conn)
    for line in report.summary().splitlines():
        log.info("content:%s", line)
    for w in report.warnings:
        log.warning("content: %s", w)
    for e in report.errors:
        log.error("content: %s", e)

    for spec in registry.all_languages():
        n = exercises.load_language_generators(spec.code)
        if n:
            log.info("%s: %d exercise generators", spec.code, n)

    if HOST not in ("127.0.0.1", "localhost", "::1"):
        log.warning(
            "Bound to %s, not loopback. Every device on this network can now read "
            "this learner's study history and reach any configured local AI model.",
            HOST,
        )

    app.state.report = report
    yield
    log.info("shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hanbat — East Asian Language Learning",
        version=VERSION,
        description="A local, offline-first language school. Korean, Japanese and Mandarin.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .api import ai, content, data, languages, learner, progress, speech, study

    for router in (languages.router, learner.router, content.router, study.router,
                   progress.router, ai.router, data.router, speech.router):
        app.include_router(router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        conn = db.get_connection()
        counts = {}
        for spec in registry.all_languages():
            row = conn.execute(
                "SELECT (SELECT COUNT(*) FROM lesson WHERE language=?) AS lessons,"
                "       (SELECT COUNT(*) FROM vocab  WHERE language=?) AS vocab,"
                "       (SELECT COUNT(*) FROM grammar WHERE language=?) AS grammar",
                (spec.code, spec.code, spec.code)).fetchone()
            counts[spec.code] = dict(row)
        return {
            "ok": True,
            "version": VERSION,
            "schema_version": db.SCHEMA_VERSION,
            "offline": True,
            "languages": counts,
            "content_errors": getattr(app.state, "report", None).errors
                              if hasattr(app.state, "report") else [],
        }

    @app.get("/api/runtime")
    def runtime() -> dict:
        """What this installation can actually do right now.

        Every capability that needs something the learner may not have — a
        local model, a speech engine, an audio pack — is reported here rather
        than assumed, so the UI can hide what does not work instead of
        offering buttons that fail.
        """
        from .engines.ai import base as ai_base

        providers = ai_base.probe_all()
        info = RuntimeInfo(version=VERSION)
        info.ai_available = any(p.available and p.models for p in providers)
        info.ai_models = [m for p in providers if p.available for m in p.models]
        return {
            **info.to_dict(),
            "ai_providers": [p.to_dict() for p in providers],
            "audio_files": len(list(Path(AUDIO_DIR).glob("**/*"))) if AUDIO_DIR.exists() else 0,
            "network_features": [
                {"id": f.id, "name": f.name, "what_it_sends": f.what_it_sends,
                 "where": f.where, "enabled_by_default": f.default_on}
                for f in NETWORK_FEATURES
            ],
            "note": "Local AI runs on this machine over loopback. It is not internet access.",
        }

    @app.exception_handler(registry.UnknownLanguage)
    async def unknown_language(request: Request, exc: registry.UnknownLanguage):
        return JSONResponse(
            status_code=404,
            content={"error": "unknown_language", "code": exc.code,
                     "known": registry.codes()},
        )

    # Audio the learner has imported, served locally.
    if AUDIO_DIR.exists():
        app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

    # The built frontend, if it has been built. Absent during `npm run dev`,
    # which proxies to this server instead.
    if FRONTEND_DIST.exists():
        app.mount("/assets",
                  StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:
        @app.get("/")
        def not_built() -> dict:
            return {
                "message": "The API is running, but the frontend has not been built.",
                "next": "cd frontend && npm install && npm run build",
                "api_docs": f"http://{HOST}:{PORT}/docs",
            }

    return app


app = create_app()


def main() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload="--reload" in sys.argv)


if __name__ == "__main__":
    main()
