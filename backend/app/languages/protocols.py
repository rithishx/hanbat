"""
The contracts between the shared learning core and each language module.

These are `Protocol` classes, not base classes, and that is a deliberate
design decision rather than a stylistic one.

Korean, Japanese and Mandarin do not share a grammatical model. Korean is
agglutinative with eleven irregular stem classes and a four-way speech-level
system. Japanese is agglutinative with a different verb system entirely, three
scripts, and keigo. Mandarin is isolating — it has no conjugation at all, and
instead has tone sandhi, measure words and aspect particles that the other two
have no equivalent for. Forcing them to inherit from a shared `GrammarEngine`
would mean either a base class so vague it says nothing, or three subclasses
that spend most of their code raising NotImplementedError.

So the shared core does not ask "what is this language's conjugation table?".
It asks narrower questions that all three can genuinely answer:

    "Break this text into its smallest learnable written units."
    "How is this actually pronounced, and why?"
    "Show me the transliteration for a beginner."
    "Given this word, what forms should I drill?"

A language module implements what it can and declares the rest unsupported via
`capabilities`. Mandarin has no `conjugate()`; it says so, and the UI does not
render a conjugation tab. That is better than a Mandarin conjugation engine
that returns the word unchanged.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Protocol, runtime_checkable


# ==========================================================================
# Writing systems
# ==========================================================================

@runtime_checkable
class WritingSystemEngine(Protocol):
    """One script belonging to one language.

    A language may have several: Japanese registers three (hiragana,
    katakana, kanji), Korean one, Mandarin one. Each is learned and tracked
    separately, because knowing hiragana tells you nothing about kanji.
    """

    #: Stable identifier, e.g. "hangul", "hiragana", "katakana", "kanji", "hanzi".
    id: str
    #: What the learner sees, e.g. "한글", "ひらがな", "汉字".
    native_name: str
    #: English label.
    name: str
    #: Whether this script has a fixed, teachable stroke order.
    has_stroke_order: bool
    #: Whether the full inventory is finite and small enough to enumerate.
    #: True for Hangul jamo and kana; False for kanji and hanzi, where the
    #: inventory is open-ended and taught by frequency band instead.
    is_closed_inventory: bool

    def units(self) -> list[dict]:
        """The teachable atoms of this script, in teaching order.

        Hangul returns jamo; kana returns the gojūon; kanji returns a
        frequency-ordered band, not all 50,000 characters.
        """
        ...

    def decompose(self, text: str) -> list[dict]:
        """Break text into its written parts, whatever those are for this script.

        Korean returns syllable blocks split into initial/medial/final.
        Japanese returns mora, flagging small kana and sokuon.
        Mandarin returns characters with their component radicals.

        The shapes differ on purpose — the UI renders each script's own
        structure rather than a lowest common denominator.
        """
        ...

    def is_valid(self, text: str) -> bool:
        """Is every character in `text` part of this writing system?"""
        ...


# ==========================================================================
# Pronunciation
# ==========================================================================

@runtime_checkable
class PronunciationEngine(Protocol):
    """Written form to spoken form, with reasons the learner can read.

    Every language has *some* gap between spelling and sound, but the gaps are
    of different kinds: Korean has assimilation rules across syllable
    boundaries, Japanese has mora timing and pitch accent, Mandarin has tone
    sandhi. `explain()` is the shared question; the rules behind it are not.
    """

    language: str

    def pronounce(self, text: str, **options: Any) -> dict:
        """Return at minimum {"written", "spoken", "changed"}."""
        ...

    def explain(self, text: str, **options: Any) -> dict:
        """Return the pronunciation plus an ordered list of `steps`, each with
        a child-level and a linguistic explanation."""
        ...

    def difficulty_points(self) -> list[dict]:
        """The contrasts learners of this language reliably struggle with, so
        the drill scheduler can target them: Korean's ㄱ/ㅋ/ㄲ, Japanese's
        short/long vowel pairs, Mandarin's tone 2 versus tone 3."""
        ...

    def rules(self) -> list[dict]:
        """Every rule that makes spelling and sound come apart, browsable.

        Unlike `explain()`, whose output shape is the language's own, this one
        is fixed, because the pronunciation lab renders it for all three:

            {"id", "name", "native_name", "simple", "technical",
             "examples": [{"written", "spoken", "note"}]}

        `simple` and `technical` are both required and must differ. The whole
        teaching philosophy is the plain-words version first and the
        terminology second, and a rule with only the technical account is the
        grammar reference the learner already failed to understand.

        The examples are *verified against the engine* rather than authored as
        text: each one is run through `pronounce()` when the index is built, so
        a rule change can never leave a worked example quietly wrong.
        """
        ...


# ==========================================================================
# Transliteration
# ==========================================================================

@runtime_checkable
class TransliterationEngine(Protocol):
    """Romanisation, romaji, pinyin — the training wheels.

    All three exist to be removed. `fade()` is part of the contract precisely
    so that no language module can implement transliteration without also
    implementing a way to wean the learner off it.
    """

    language: str
    #: What this system is called to a learner: "Revised Romanization",
    #: "Romaji (Hepburn)", "Pinyin".
    scheme_name: str
    #: Pinyin is genuinely needed at advanced levels for dictionary lookup and
    #: typing, so Mandarin sets this False. Korean romanisation is not, so it
    #: sets True and the app fades it to nothing.
    fully_removable: bool

    def transliterate(self, text: str, **options: Any) -> str:
        ...

    def fade(self, text: str, level: float, **options: Any) -> str:
        """Partial transliteration. level 1.0 = all, 0.0 = none."""
        ...


# ==========================================================================
# Grammar
# ==========================================================================

@runtime_checkable
class GrammarEngine(Protocol):
    """Deliberately thin.

    This protocol does NOT define conjugation, particles, tone sandhi or
    measure words, because no two of the three languages agree on which of
    those exist. It defines only what the shared lesson engine actually needs:
    look a point up, and find out which forms of a word are worth drilling.

    Language-specific richness lives on the concrete engine and is reached
    through `LanguageSpec.grammar`, typed as the concrete class in that
    language's own module. Korean code may call `.conjugate()`; shared code
    may not.
    """

    language: str

    def capabilities(self) -> frozenset[str]:
        """Which optional features this language supports.

        Recognised values: "conjugation", "particles", "honorifics",
        "speech_levels", "tone_sandhi", "measure_words", "aspect_particles",
        "pitch_accent", "counters", "keigo".

        The UI reads this to decide which panels to render. A language that
        does not declare "conjugation" gets no conjugation tab — rather than a
        tab that shows the dictionary form unchanged and pretends that is an
        answer.
        """
        ...

    def analyse(self, text: str) -> dict:
        """Best-effort breakdown of a phrase for the tutor and the UI.

        Return shape is language-defined. Korean returns stems, particles and
        endings; Mandarin returns word segmentation and function words.
        """
        ...

    def drill_forms(self, entry: dict) -> list[dict]:
        """Given a vocabulary entry, which forms are worth practising?

        Korean returns the conjugation table. Mandarin, which has no
        conjugation, returns tone-pair drills and measure-word pairings
        instead. Both are honest answers to "what should I practise about
        this word", which is the question the SRS actually asks.

        Unlike `analyse` and `conjugation_table`, whose shapes are entirely
        language-defined, this one is fixed, because the SRS and the practice
        screens consume it for every language:

            {"form_id": str, "form": str, "label": str, "category": str}

        `form` is deliberately not named after any language. An earlier version
        returned "korean", "japanese" and "chinese" from the three modules,
        which meant every shared consumer had to know all three names — the
        exact leak this architecture exists to prevent.
        """
        ...


# ==========================================================================
# Level ladders
# ==========================================================================

@runtime_checkable
class LevelLadder(Protocol):
    """How progress is banded, per language.

    CEFR is a European framework. Korean learners increasingly use it (and
    TOPIK), Japanese learners think in JLPT N5–N1, Mandarin learners in
    HSK 1–6. The vocabulary thresholds behind each band differ by a factor of
    three, so a single shared enum would be wrong for at least two of the
    three languages.
    """

    #: Ordered, easiest first.
    levels: tuple[str, ...]
    #: What the scheme is called: "CEFR", "JLPT", "HSK".
    scheme: str

    def estimate(
        self,
        script_mastery: float,
        vocab_known: int,
        grammar_known: int,
        accuracy: float,
    ) -> str:
        """Estimate the learner's band. Implementations should err low."""
        ...

    def describe(self, level: str) -> dict:
        """Human-readable milestone description for one band."""
        ...


# ==========================================================================
# Helpers
# ==========================================================================

KNOWN_CAPABILITIES = frozenset({
    "conjugation",
    "particles",
    "honorifics",
    "speech_levels",
    "keigo",
    "tone_sandhi",
    "measure_words",
    "counters",
    "aspect_particles",
    "pitch_accent",
    "stroke_order",
    "character_components",
    "syllable_blocks",
    "mora_timing",
})


def check_capabilities(caps: Iterable[str]) -> None:
    """Fail loudly on a typo'd capability rather than silently hiding a tab."""
    unknown = set(caps) - KNOWN_CAPABILITIES
    if unknown:
        raise ValueError(
            f"unknown capabilities {sorted(unknown)}; "
            f"add them to KNOWN_CAPABILITIES if they are real"
        )
