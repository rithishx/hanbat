"""
Configuration. Everything defaults to local-only; nothing reaches the network
unless the user turns it on and is told so.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_DIR = BASE_DIR.parent                              # repo root
CONTENT_DIR = Path(os.environ.get("HANBAT_CONTENT_DIR", BASE_DIR / "content"))
DATA_DIR = Path(os.environ.get("HANBAT_DATA_DIR", PROJECT_DIR / "data"))
AUDIO_DIR = Path(os.environ.get("HANBAT_AUDIO_DIR", DATA_DIR / "audio"))
RECORDING_DIR = Path(os.environ.get("HANBAT_RECORDING_DIR", DATA_DIR / "recordings"))
DB_PATH = Path(os.environ.get("HANBAT_DB", DATA_DIR / "hanbat.sqlite3"))
FRONTEND_DIST = Path(os.environ.get("HANBAT_FRONTEND", PROJECT_DIR / "frontend" / "dist"))

for d in (DATA_DIR, AUDIO_DIR, RECORDING_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------

#: Loopback only. Binding to 0.0.0.0 would expose a learner's entire study
#: history — and any local AI model — to every device on their network.
#: Overridable, but the override is deliberately noisy in the logs.
HOST = os.environ.get("HANBAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("HANBAT_PORT", "8756"))

#: The dev server origin, allowed through CORS only while developing.
DEV_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}",
]


# --------------------------------------------------------------------------
# Features that touch the network — every one is off by default
# --------------------------------------------------------------------------

@dataclass
class NetworkFeature:
    """A capability that cannot work offline. Declared so the Settings screen
    can list them honestly rather than surprising the learner."""

    id: str
    name: str
    what_it_sends: str
    where: str
    default_on: bool = False


NETWORK_FEATURES: list[NetworkFeature] = [
    NetworkFeature(
        id="ai_tutor_remote",
        name="AI tutor via a non-local provider",
        what_it_sends="Your questions and the sentences you write.",
        where="Whatever base URL you configure.",
    ),
    NetworkFeature(
        id="audio_download",
        name="Downloading an audio pack",
        what_it_sends="Nothing about you — only a request for the file.",
        where="The URL you paste.",
    ),
    NetworkFeature(
        id="tts_model_download",
        name="Downloading a local TTS or STT model",
        what_it_sends="Nothing about you — only a request for the model.",
        where="The model host you choose.",
    ),
]

#: Ollama and LM Studio run on the learner's own machine. Talking to them is a
#: loopback request, not internet access, so they are not listed above.
LOCAL_AI_ENDPOINTS = {
    "ollama": "http://127.0.0.1:11434",
    "lmstudio": "http://127.0.0.1:1234/v1",
    "llamacpp": "http://127.0.0.1:8080",
}


# --------------------------------------------------------------------------
# Default learner settings
# --------------------------------------------------------------------------

DEFAULT_SETTINGS: dict = {
    # Language and display
    # "target" means explain in the language being learned, whichever that is.
    "explanation_language": "en",        # en | target | both
    "native_ui": False,                  # label the interface in the target language
    "romanization": "auto",              # always | auto | never
    "romanization_level": 1.0,           # 1.0 = full; the app lowers it as you improve
    "show_translations": True,
    "font_size": "medium",               # small | medium | large | xlarge
    "theme": "system",                   # light | dark | system
    "dyslexia_font": False,
    "high_contrast": False,
    "reduce_motion": False,

    # Study
    "daily_goal_minutes": 15,
    "new_cards_per_day": 10,
    "reviews_per_day": 100,
    "difficulty": "adaptive",            # gentle | adaptive | hard
    "audio_autoplay": True,
    "playback_rate": 1.0,
    "require_typing": False,             # type the answer instead of choosing

    # Speech
    "tts_engine": "browser",             # browser | piper | none
    "tts_voice": "",
    "stt_engine": "browser",             # browser | whisper | none
    "microphone_enabled": True,

    # AI
    "ai_provider": "disabled",           # ollama | lmstudio | llamacpp | disabled
    "ai_model": "",
    "ai_temperature": 0.6,
    "ai_context_length": 4096,
    "ai_base_url": "",
    "ai_socratic": True,                 # never hand over the answer first

    # Privacy
    "allow_network": False,
}

#: Settings whose value the UI must never silently change.
#: `romanization` is on this list for a specific reason: the app fades
#: romanisation as a learner improves, and that automatic fade must never
#: override a learner who has explicitly asked to keep it or switch it off.
LEARNER_OWNED = frozenset({"romanization", "ai_provider", "allow_network",
                           "microphone_enabled", "daily_goal_minutes"})


@dataclass
class RuntimeInfo:
    """What the app can actually do right now, given what is installed."""

    version: str = "0.2.0"
    db_path: str = str(DB_PATH)
    content_dir: str = str(CONTENT_DIR)
    audio_dir: str = str(AUDIO_DIR)
    offline_capable: bool = True
    ai_available: bool = False
    ai_provider: str = "disabled"
    ai_models: list[str] = field(default_factory=list)
    network_features: list[dict] = field(default_factory=lambda: [asdict(f) for f in NETWORK_FEATURES])

    def to_dict(self) -> dict:
        return asdict(self)


def load_settings(raw: str | None) -> dict:
    """Merge stored settings over the defaults, dropping unknown keys."""
    settings = dict(DEFAULT_SETTINGS)
    if raw:
        try:
            stored = json.loads(raw)
        except (TypeError, ValueError):
            return settings
        for k, v in stored.items():
            if k in DEFAULT_SETTINGS:
                settings[k] = v
    return settings
