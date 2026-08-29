"""
The local-AI provider abstraction.

Four providers, one interface, and a `disabled` provider that is a first-class
citizen rather than an error path. The application must be fully usable with no
model installed — every lesson, every drill, every review works without AI —
so `disabled` returns a clear "not available" result and the UI hides the tutor
rather than showing a broken one.

Nothing here ever fabricates a reply. If a provider is unreachable, the caller
gets `available=False` and a reason it can show the learner. A language app
that invents a tutor's grammar correction is worse than one with no tutor.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Optional

#: Requests to a local model are loopback traffic, not internet access, so they
#: are allowed even with `allow_network` off. The timeout is generous because a
#: 7B model on CPU can genuinely take this long for a first token.
DEFAULT_TIMEOUT = 120
PROBE_TIMEOUT = 3


@dataclass
class Message:
    role: str            # system | user | assistant
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResult:
    text: str = ""
    available: bool = True
    error: str = ""
    provider: str = ""
    model: str = ""
    #: Round-trip in milliseconds, so the UI can warn about a slow model.
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProviderStatus:
    id: str
    name: str
    available: bool
    models: list[str] = field(default_factory=list)
    base_url: str = ""
    error: str = ""
    #: How to fix it, in words a non-developer can act on.
    hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _post_json(url: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, timeout: int = PROBE_TIMEOUT) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class Provider:
    """Base class. Subclasses override `chat` and `status`."""

    id = "base"
    name = "Base"
    default_base_url = ""

    def __init__(self, base_url: str = "", model: str = "",
                 temperature: float = 0.6, context_length: int = 4096):
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.model = model
        self.temperature = temperature
        self.context_length = context_length

    def chat(self, messages: list[Message], **kw) -> ChatResult:  # pragma: no cover
        raise NotImplementedError

    def status(self) -> ProviderStatus:  # pragma: no cover
        raise NotImplementedError

    def _unavailable(self, err: Exception, hint: str) -> ChatResult:
        return ChatResult(
            available=False, provider=self.id, model=self.model,
            error=f"{type(err).__name__}: {err}",
            text="", elapsed_ms=0,
        )


# ==========================================================================
# Ollama
# ==========================================================================

class OllamaProvider(Provider):
    id = "ollama"
    name = "Ollama"
    default_base_url = "http://127.0.0.1:11434"

    def status(self) -> ProviderStatus:
        try:
            data = _get_json(f"{self.base_url}/api/tags")
            models = [m["name"] for m in data.get("models", [])]
            return ProviderStatus(
                self.id, self.name, True, models, self.base_url,
                hint="" if models else
                     "Ollama is running but has no models. Try: ollama pull qwen2.5:7b")
        except Exception as e:
            return ProviderStatus(
                self.id, self.name, False, [], self.base_url, str(e),
                hint="Ollama does not appear to be running. Install it from ollama.com, "
                     "then run: ollama pull qwen2.5:7b")

    def chat(self, messages: list[Message], **kw) -> ChatResult:
        import time
        t0 = time.time()
        try:
            data = _post_json(f"{self.base_url}/api/chat", {
                "model": kw.get("model") or self.model,
                "messages": [m.to_dict() for m in messages],
                "stream": False,
                "options": {
                    "temperature": kw.get("temperature", self.temperature),
                    "num_ctx": kw.get("context_length", self.context_length),
                },
            }, timeout=kw.get("timeout", DEFAULT_TIMEOUT))
            return ChatResult(
                text=(data.get("message") or {}).get("content", "").strip(),
                provider=self.id, model=kw.get("model") or self.model,
                elapsed_ms=int((time.time() - t0) * 1000))
        except Exception as e:
            return self._unavailable(e, "Is Ollama running?")


# ==========================================================================
# LM Studio and llama.cpp — both speak the OpenAI chat format
# ==========================================================================

class OpenAICompatibleProvider(Provider):
    """LM Studio and llama.cpp's server both expose /v1/chat/completions."""

    def status(self) -> ProviderStatus:
        try:
            data = _get_json(f"{self.base_url}/models")
            models = [m["id"] for m in data.get("data", [])]
            return ProviderStatus(self.id, self.name, True, models, self.base_url)
        except Exception as e:
            return ProviderStatus(self.id, self.name, False, [], self.base_url,
                                  str(e), hint=self.start_hint)

    start_hint = ""

    def chat(self, messages: list[Message], **kw) -> ChatResult:
        import time
        t0 = time.time()
        try:
            data = _post_json(f"{self.base_url}/chat/completions", {
                "model": kw.get("model") or self.model or "local-model",
                "messages": [m.to_dict() for m in messages],
                "temperature": kw.get("temperature", self.temperature),
                "max_tokens": kw.get("max_tokens", 800),
                "stream": False,
            }, timeout=kw.get("timeout", DEFAULT_TIMEOUT))
            choices = data.get("choices") or []
            text = (choices[0].get("message", {}).get("content", "") if choices else "")
            return ChatResult(text=text.strip(), provider=self.id,
                              model=kw.get("model") or self.model,
                              elapsed_ms=int((time.time() - t0) * 1000))
        except Exception as e:
            return self._unavailable(e, self.start_hint)


class LMStudioProvider(OpenAICompatibleProvider):
    id = "lmstudio"
    name = "LM Studio"
    default_base_url = "http://127.0.0.1:1234/v1"
    start_hint = ("Open LM Studio, load a model, and start the local server "
                  "from the Developer tab.")


class LlamaCppProvider(OpenAICompatibleProvider):
    id = "llamacpp"
    name = "llama.cpp"
    default_base_url = "http://127.0.0.1:8080/v1"
    start_hint = ("Start llama.cpp's server, for example: "
                  "llama-server -m model.gguf --port 8080")


# ==========================================================================
# Disabled — the honest default
# ==========================================================================

class DisabledProvider(Provider):
    id = "disabled"
    name = "No AI"

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            self.id, self.name, False, [], "",
            hint="The AI tutor is switched off. Everything else works without it — "
                 "lessons, drills, reviews and progress are all local and need no model.")

    def chat(self, messages: list[Message], **kw) -> ChatResult:
        return ChatResult(
            available=False, provider=self.id,
            error="AI is disabled",
            text="")


PROVIDERS: dict[str, type[Provider]] = {
    "ollama": OllamaProvider,
    "lmstudio": LMStudioProvider,
    "llamacpp": LlamaCppProvider,
    "disabled": DisabledProvider,
}


def build(settings: dict) -> Provider:
    """Construct the provider named in the learner's settings."""
    cls = PROVIDERS.get(settings.get("ai_provider", "disabled"), DisabledProvider)
    return cls(
        base_url=settings.get("ai_base_url", ""),
        model=settings.get("ai_model", ""),
        temperature=float(settings.get("ai_temperature", 0.6)),
        context_length=int(settings.get("ai_context_length", 4096)),
    )


def probe_all() -> list[ProviderStatus]:
    """Which local runtimes are actually up right now.

    Used by the settings screen so the learner picks from what is installed
    rather than typing a provider name and hoping.
    """
    out = []
    for pid, cls in PROVIDERS.items():
        if pid == "disabled":
            continue
        out.append(cls().status())
    return out
