"""
The language registry — the one place that knows which languages exist.

Everything else in the shared core takes a language code (`"ko"`, `"ja"`,
`"zh"`) and asks the registry for what it needs. Nothing in `app/engines/`,
`app/api/` or the frontend should ever contain the string "Korean".

Engines are loaded lazily. Importing this module does not import the Korean
phonology tables, and a learner who only studies Japanese never pays for
Mandarin's character data. That matters on the 8 GB machine the project
targets.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field, asdict
from functools import cached_property
from typing import Any, Optional

from .protocols import check_capabilities

#: ISO 639-1 where one exists. Mandarin uses "zh" (with "cmn" available in the
#: spec below for when Cantonese arrives and the distinction starts to matter).
LanguageCode = str


@dataclass(frozen=True)
class WritingSystemSpec:
    """Declared metadata for one script. The engine itself is loaded lazily."""

    id: str
    name: str
    native_name: str
    has_stroke_order: bool = False
    is_closed_inventory: bool = True
    #: Roughly how many units a learner must master. None for open inventories.
    unit_count: Optional[int] = None
    #: Taught in this order; the first is the gate for the rest.
    teaching_order: int = 0
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LanguageSpec:
    """Everything the shared core needs to know about one language.

    The `*_module` fields are dotted paths resolved on first use, so that a
    language can be registered without its engines being importable yet — which
    is what makes it possible to add Japanese in stages rather than all at once.
    """

    code: LanguageCode
    name: str
    native_name: str
    flag: str
    #: ISO 639-3, for the day "zh" is not specific enough.
    iso3: str = ""

    writing_systems: tuple[WritingSystemSpec, ...] = ()
    capabilities: frozenset[str] = frozenset()

    #: Dotted module paths. Each is expected to expose a module-level `ENGINE`.
    writing_module: str = ""
    pronunciation_module: str = ""
    transliteration_module: str = ""
    grammar_module: str = ""
    levels_module: str = ""
    confusions_module: str = ""

    #: Where this language's JSON content lives, relative to CONTENT_DIR.
    content_dir: str = ""

    #: How complete this language is right now. Shown in the UI so a learner is
    #: never surprised by an empty curriculum. One of:
    #: "complete" | "foundation" | "in_progress" | "planned"
    status: str = "planned"
    status_note: str = ""

    #: Text direction and whether the script normally uses spaces between words.
    #: Korean does, Japanese and Mandarin do not — which changes how the
    #: reading exercises segment text.
    uses_spaces: bool = True

    def __post_init__(self):
        check_capabilities(self.capabilities)

    # -- lazy engine access -------------------------------------------------

    def _load(self, dotted: str) -> Any:
        if not dotted:
            return None
        module = importlib.import_module(dotted)
        engine = getattr(module, "ENGINE", None)
        if engine is None:
            raise AttributeError(
                f"{dotted} is registered for {self.code} but exposes no ENGINE"
            )
        return engine

    @cached_property
    def writing(self) -> Any:
        return self._load(self.writing_module)

    @cached_property
    def pronunciation(self) -> Any:
        return self._load(self.pronunciation_module)

    @cached_property
    def transliteration(self) -> Any:
        return self._load(self.transliteration_module)

    @cached_property
    def grammar(self) -> Any:
        return self._load(self.grammar_module)

    @cached_property
    def levels(self) -> Any:
        return self._load(self.levels_module)

    @cached_property
    def confusions(self) -> dict:
        """Known confusion pairs for this language, keyed by id.

        Returns {} for a language that has not registered any yet, so the
        adaptive engine degrades to generic weakness tracking rather than
        failing.
        """
        if not self.confusions_module:
            return {}
        try:
            module = importlib.import_module(self.confusions_module)
        except ModuleNotFoundError:
            # Unlike the engines, confusions are genuinely optional: a language
            # is perfectly usable before anyone has catalogued its classic
            # mistakes. The adaptive engine falls back to per-item weakness
            # tracking. The engines above deliberately do NOT swallow this —
            # a missing grammar engine is a bug, not a soft state.
            return {}
        return getattr(module, "CONFUSIONS", {})

    # -- introspection ------------------------------------------------------

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    @property
    def is_usable(self) -> bool:
        """Is there enough here for a learner to actually study?"""
        return self.status in ("complete", "foundation", "in_progress")

    def writing_system(self, ws_id: str) -> Optional[WritingSystemSpec]:
        for ws in self.writing_systems:
            if ws.id == ws_id:
                return ws
        return None

    def to_dict(self, include_engines: bool = False) -> dict:
        d = {
            "code": self.code,
            "name": self.name,
            "native_name": self.native_name,
            "flag": self.flag,
            "iso3": self.iso3,
            "writing_systems": [w.to_dict() for w in self.writing_systems],
            "capabilities": sorted(self.capabilities),
            "status": self.status,
            "status_note": self.status_note,
            "uses_spaces": self.uses_spaces,
            "content_dir": self.content_dir,
        }
        if include_engines:
            ladder = self.levels
            d["levels"] = list(ladder.levels) if ladder else []
            d["level_scheme"] = ladder.scheme if ladder else ""
            tl = self.transliteration
            d["transliteration"] = (
                {"scheme": tl.scheme_name, "fully_removable": tl.fully_removable}
                if tl else None
            )
        return d


# ==========================================================================
# The registry
# ==========================================================================

_REGISTRY: dict[LanguageCode, LanguageSpec] = {}


def register(spec: LanguageSpec) -> LanguageSpec:
    if spec.code in _REGISTRY:
        raise ValueError(f"language {spec.code!r} is already registered")
    _REGISTRY[spec.code] = spec
    return spec


def get(code: LanguageCode) -> LanguageSpec:
    try:
        return _REGISTRY[code]
    except KeyError:
        raise UnknownLanguage(code) from None


def try_get(code: LanguageCode) -> Optional[LanguageSpec]:
    return _REGISTRY.get(code)


def all_languages(usable_only: bool = False) -> list[LanguageSpec]:
    out = list(_REGISTRY.values())
    if usable_only:
        out = [s for s in out if s.is_usable]
    return sorted(out, key=lambda s: (s.status != "complete", s.name))


def codes() -> list[LanguageCode]:
    return [s.code for s in all_languages()]


def is_registered(code: LanguageCode) -> bool:
    return code in _REGISTRY


class UnknownLanguage(KeyError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(
            f"no language registered under {code!r}; "
            f"known codes are {sorted(_REGISTRY)}"
        )


# ==========================================================================
# Built-in languages
# ==========================================================================

KOREAN = register(LanguageSpec(
    code="ko",
    name="Korean",
    native_name="한국어",
    flag="🇰🇷",
    iso3="kor",
    writing_systems=(
        WritingSystemSpec(
            id="hangul", name="Hangul", native_name="한글",
            has_stroke_order=True, is_closed_inventory=True, unit_count=40,
            teaching_order=0,
            description="An alphabet of 24 basic letters, grouped into syllable blocks.",
        ),
    ),
    capabilities=frozenset({
        "conjugation", "particles", "honorifics", "speech_levels",
        "syllable_blocks", "stroke_order", "counters",
    }),
    writing_module="app.languages.korean.writing",
    pronunciation_module="app.languages.korean.pronunciation",
    transliteration_module="app.languages.korean.transliteration",
    grammar_module="app.languages.korean.grammar",
    levels_module="app.languages.korean.levels",
    confusions_module="app.languages.korean.confusions",
    content_dir="ko",
    status="in_progress",
    status_note="Hangul curriculum complete and tested. Beginner grammar and the lesson runtime are still being built.",
    uses_spaces=True,
))

JAPANESE = register(LanguageSpec(
    code="ja",
    name="Japanese",
    native_name="日本語",
    flag="🇯🇵",
    iso3="jpn",
    writing_systems=(
        WritingSystemSpec(
            id="hiragana", name="Hiragana", native_name="ひらがな",
            has_stroke_order=True, is_closed_inventory=True, unit_count=104,
            teaching_order=0,
            description="The core syllabary. Learned first, and used for grammar.",
        ),
        WritingSystemSpec(
            id="katakana", name="Katakana", native_name="カタカナ",
            has_stroke_order=True, is_closed_inventory=True, unit_count=104,
            teaching_order=1,
            description="The same sounds in a second set of shapes, for loanwords.",
        ),
        WritingSystemSpec(
            id="kanji", name="Kanji", native_name="漢字",
            has_stroke_order=True, is_closed_inventory=False, unit_count=None,
            teaching_order=2,
            description="Chinese-derived characters, each with several readings. Taught by frequency, never exhaustively.",
        ),
    ),
    capabilities=frozenset({
        "conjugation", "particles", "honorifics", "keigo", "counters",
        "pitch_accent", "stroke_order", "mora_timing",
    }),
    writing_module="app.languages.japanese.writing",
    pronunciation_module="app.languages.japanese.pronunciation",
    transliteration_module="app.languages.japanese.transliteration",
    grammar_module="app.languages.japanese.grammar",
    levels_module="app.languages.japanese.levels",
    confusions_module="app.languages.japanese.confusions",
    content_dir="ja",
    status="foundation",
    status_note=(
        "Kana, mora timing, verb conjugation and N5 grammar are in place. "
        "Kanji content and the N4+ curriculum are still to come."
    ),
    uses_spaces=False,
))

MANDARIN = register(LanguageSpec(
    code="zh",
    name="Mandarin Chinese",
    native_name="普通话",
    flag="🇨🇳",
    iso3="cmn",
    writing_systems=(
        WritingSystemSpec(
            id="pinyin", name="Pinyin", native_name="拼音",
            has_stroke_order=False, is_closed_inventory=True, unit_count=None,
            teaching_order=0,
            description="The romanisation, learned first as a pronunciation system in its own right.",
        ),
        WritingSystemSpec(
            id="hanzi", name="Chinese characters", native_name="汉字",
            has_stroke_order=True, is_closed_inventory=False, unit_count=None,
            teaching_order=1,
            description="Taught by frequency and by shared components, never exhaustively.",
        ),
    ),
    capabilities=frozenset({
        "tone_sandhi", "measure_words", "aspect_particles",
        "character_components", "stroke_order",
    }),
    writing_module="app.languages.mandarin.writing",
    pronunciation_module="app.languages.mandarin.pronunciation",
    transliteration_module="app.languages.mandarin.transliteration",
    grammar_module="app.languages.mandarin.grammar",
    levels_module="app.languages.mandarin.levels",
    confusions_module="app.languages.mandarin.confusions",
    content_dir="zh",
    status="foundation",
    status_note=(
        "Pinyin, the four tones, tone sandhi, measure words, aspect and HSK1 "
        "grammar are in place. Character content beyond the first words, and "
        "the HSK2+ curriculum, are still to come."
    ),
    uses_spaces=False,
))

DEFAULT_LANGUAGE = "ko"
