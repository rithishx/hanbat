"""
Speech: audio out, recordings in, and an honest account of what is scored.

The default engines are the browser's own — `speechSynthesis` for playback and
`MediaRecorder` for capture — which need no install and work offline on macOS
and Windows. That means most of the work happens client-side, and this router
exists to (a) tell the frontend what is available, (b) store recordings, and
(c) serve any audio the learner has imported.

Pronunciation *scoring* is the part that must not be faked. A score requires a
speech-to-text engine that can transcribe the target language; when none is
configured, the endpoint says so and returns the recording for self-comparison
instead of inventing a number. Comparing your own voice against a model is
genuinely useful; a fabricated "82%" is not.
"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import AUDIO_DIR, RECORDING_DIR
from ..db import get_connection, now_iso, query, query_one
from .deps import Learner, UsableLang

router = APIRouter(prefix="/speech", tags=["speech"])

MAX_RECORDING_BYTES = 10 * 1024 * 1024


@router.get("/capabilities")
def capabilities(spec: UsableLang, learner: Learner) -> dict:
    """What this installation can actually do with speech, right now."""
    settings = learner["settings"]
    imported = list(AUDIO_DIR.glob("**/*")) if AUDIO_DIR.exists() else []
    audio_files = [p for p in imported if p.is_file()]

    return {
        "language": spec.code,
        "tts": {
            "engine": settings.get("tts_engine", "browser"),
            "browser_available": True,
            "note": ("Playback uses your operating system's built-in voices via the "
                     "browser. On macOS and Windows a Korean voice is usually "
                     "installed already; on Linux you may need to add one. "
                     "No audio is sent anywhere."),
            "local_engines": [
                {"id": "piper", "name": "Piper", "installed": _has("piper"),
                 "note": "Higher quality offline TTS. Requires downloading a voice model."},
            ],
        },
        "stt": {
            "engine": settings.get("stt_engine", "browser"),
            "browser_available": True,
            "browser_caveat": ("Browser speech recognition quality varies by "
                               "platform and some implementations send audio to a "
                               "cloud service. Check before relying on it offline."),
            "local_engines": [
                {"id": "whisper", "name": "faster-whisper", "installed": _has_module("faster_whisper"),
                 "note": "Fully offline transcription. Requires downloading a model."},
            ],
        },
        "scoring": {
            "available": _scoring_available(settings),
            "requires": "a speech-to-text engine that transcribes this language",
            "note": ("Without one, recordings are stored so you can listen back "
                     "against the model pronunciation. No score is invented."),
        },
        "imported_audio_files": len(audio_files),
        "recordings_stored": _recording_count(learner["id"], spec.code),
    }


def _has(binary: str) -> bool:
    return shutil.which(binary) is not None


def _has_module(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


def _scoring_available(settings: dict) -> bool:
    engine = settings.get("stt_engine", "browser")
    if engine == "whisper":
        return _has_module("faster_whisper")
    return False


def _recording_count(learner_id: int, language: str) -> int:
    row = query_one("SELECT COUNT(*) AS n FROM recording WHERE learner_id=? AND language=?",
                    (learner_id, language))
    return row["n"] if row else 0


# ==========================================================================
# Audio out
# ==========================================================================

@router.get("/audio")
def audio_for(spec: UsableLang, text: str) -> dict:
    """Find pre-recorded audio for a string, if the learner has imported any.

    Returns a URL when a file exists, and otherwise tells the client to
    synthesise it. There is no server-side TTS by default — the browser does
    it, which keeps the whole path offline and adds no install step.
    """
    row = query_one(
        "SELECT * FROM audio_asset WHERE language=? AND text=? LIMIT 1",
        (spec.code, text))
    if row:
        return {"text": text, "source": "file", "url": f"/audio/{row['path']}",
                "voice": row["voice"], "license": row["license"]}
    return {
        "text": text, "source": "synthesize", "url": None,
        "hint": {"lang": _bcp47(spec.code),
                 "note": "Use the browser's speechSynthesis with this language tag."},
    }


_BCP47 = {"ko": "ko-KR", "ja": "ja-JP", "zh": "zh-CN"}


def _bcp47(code: str) -> str:
    return _BCP47.get(code, code)


@router.post("/audio/import")
async def import_audio(spec: UsableLang, text: str = Form(...),
                       license: str = Form(""), voice: str = Form(""),
                       file: UploadFile = File(...)) -> dict:
    """Import an audio file for a word or phrase.

    Recording a native speaker, or using an openly-licensed clip, beats
    synthesis for anything the learner will drill repeatedly. The licence
    field is stored so the origin of every clip stays traceable.
    """
    ext = Path(file.filename or "clip.mp3").suffix or ".mp3"
    if ext.lower() not in (".mp3", ".ogg", ".wav", ".m4a", ".webm", ".flac"):
        raise HTTPException(400, f"unsupported audio format {ext}")

    dest_dir = AUDIO_DIR / spec.code
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    dest = dest_dir / name
    dest.write_bytes(await file.read())

    conn = get_connection()
    asset_id = f"{spec.code}-audio-{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO audio_asset(id, language, text, path, voice, engine, source, "
        "license, created_at) VALUES (?,?,?,?,?,?,'import',?,?)",
        (asset_id, spec.code, text, f"{spec.code}/{name}", voice, "", license, now_iso()))
    conn.commit()
    return {"id": asset_id, "text": text, "url": f"/audio/{spec.code}/{name}"}


# ==========================================================================
# Recordings in
# ==========================================================================

@router.post("/record")
async def record(spec: UsableLang, learner: Learner,
                 target: str = Form(...), item_type: str = Form(""),
                 item_id: str = Form(""), file: UploadFile = File(...)) -> dict:
    """Store a recording and score it if — and only if — an engine can.

    When no transcriber is configured the response says so explicitly and
    returns both audio URLs so the learner can compare. This is the honest
    version of a pronunciation trainer: real feedback where it exists,
    a mirror where it does not.
    """
    raw = await file.read()
    if len(raw) > MAX_RECORDING_BYTES:
        raise HTTPException(413, "recording too large")

    RECORDING_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "rec.webm").suffix or ".webm"
    name = f"{uuid.uuid4().hex}{ext}"
    (RECORDING_DIR / name).write_bytes(raw)

    settings = learner["settings"]
    analysis: dict = {}
    score = None
    heard = ""

    if _scoring_available(settings):
        try:
            heard, score, analysis = _transcribe_and_score(
                RECORDING_DIR / name, target, spec)
        except Exception as e:
            analysis = {"error": f"transcription failed: {e}"}
    else:
        analysis = {
            "scored": False,
            "why": ("No offline speech-to-text engine is configured, so there is "
                    "nothing that can honestly score this. Listen to both and "
                    "compare — that is what a teacher would have you do anyway."),
            "how_to_enable": ("pip install faster-whisper, then set the speech "
                              "engine to whisper in Settings."),
        }
        # Point at the specific sounds this language's learners struggle with,
        # which is useful advice even without a score.
        try:
            points = spec.pronunciation.difficulty_points()
            relevant = [p for p in points
                        if any(c in target for c in "".join(p.get("contrast", [])))]
            if relevant:
                analysis["watch_for"] = [
                    {"title": p["title"], "fix": p["fix"]} for p in relevant[:2]]
        except ModuleNotFoundError:
            pass

    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO recording(learner_id, language, at, item_type, item_id, "
        "target, heard, path, score, analysis) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (learner["id"], spec.code, now_iso(), item_type, item_id, target,
         heard, name, score, __import__("json").dumps(analysis, ensure_ascii=False)))
    conn.commit()

    return {
        "id": cur.lastrowid,
        "target": target,
        "heard": heard,
        "score": score,
        "scored": score is not None,
        "analysis": analysis,
        "your_recording": f"/api/speech/recording/{cur.lastrowid}",
        "model_audio": audio_for(spec, target),
    }


def _transcribe_and_score(path: Path, target: str, spec) -> tuple[str, float, dict]:
    """Transcribe with faster-whisper and compare against the target.

    The comparison is done on the *pronounced* form, not the spelling: a
    learner saying 한구거 for 한국어 is correct, and marking it wrong because
    the transcript does not match the spelling would be teaching the opposite
    of what the 받침 module teaches.
    """
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(path), language=spec.code)
    heard = "".join(s.text for s in segments).strip()

    expected = target
    try:
        expected = spec.pronunciation.pronounce(target).get("spoken", target)
        heard_norm = spec.pronunciation.pronounce(heard).get("spoken", heard)
    except ModuleNotFoundError:
        heard_norm = heard

    score = _similarity(expected, heard_norm)
    analysis: dict = {
        "scored": True,
        "expected_written": target,
        "expected_spoken": expected,
        "heard": heard,
        "heard_normalised": heard_norm,
        "engine": "faster-whisper (small, local)",
    }

    if score < 0.9:
        diffs = _differing_units(expected, heard_norm, spec)
        if diffs:
            analysis["problem_sounds"] = diffs
    return heard, round(score * 100, 1), analysis


def _similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def _differing_units(expected: str, heard: str, spec) -> list[dict]:
    """Which written units differ, with this language's advice for each."""
    try:
        engine = spec.writing
        exp = [u.get("char") or u.get("unit") for u in engine.decompose(expected)]
        got = [u.get("char") or u.get("unit") for u in engine.decompose(heard)]
    except (ModuleNotFoundError, AttributeError):
        return []

    points = []
    try:
        difficulty = spec.pronunciation.difficulty_points()
    except ModuleNotFoundError:
        difficulty = []

    for i, e in enumerate(exp):
        g = got[i] if i < len(got) else None
        if g == e:
            continue
        advice = next((d["fix"] for d in difficulty
                       if e and any(e in c for c in d.get("contrast", []))), "")
        points.append({"position": i, "expected": e, "heard": g, "advice": advice})
    return points[:5]


@router.get("/recording/{recording_id}")
def get_recording(recording_id: int):
    row = query_one("SELECT * FROM recording WHERE id = ?", (recording_id,))
    if row is None:
        raise HTTPException(404, "no such recording")
    path = RECORDING_DIR / row["path"]
    if not path.exists():
        raise HTTPException(404, "the audio file is missing")
    return FileResponse(path)


@router.get("/recordings")
def recordings(spec: UsableLang, learner: Learner, limit: int = 50) -> dict:
    rows = query(
        "SELECT id, at, target, heard, score, item_type, item_id FROM recording "
        "WHERE learner_id=? AND language=? ORDER BY at DESC LIMIT ?",
        (learner["id"], spec.code, limit))
    return {"language": spec.code, "recordings": rows}


@router.get("/difficulties")
def difficulties(spec: UsableLang) -> dict:
    """The sounds learners of this language reliably struggle with."""
    try:
        return {"language": spec.code,
                "difficulties": spec.pronunciation.difficulty_points()}
    except ModuleNotFoundError:
        raise HTTPException(409, f"{spec.code} has no pronunciation engine yet")
