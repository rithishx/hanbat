"""
Revised Romanization of Korean (국어의 로마자 표기법, 2000).

The official system is *transcription*-based, not transliteration-based: it
romanises what is said, not what is written. So 한국어 is `hangugeo`, not
`hangug-eo`, and 신라 is `silla`, not `sinra`. This module therefore runs the
text through the phonology engine first unless asked not to.

Romanization exists here only as a scaffold. The settings layer fades it out
as the learner's Hangul accuracy rises, and `fade_level` lets a caller ask for
a partially-romanised string so the transition is gradual rather than abrupt.
"""

from __future__ import annotations

import random
from typing import Optional

from .hangul import COMPOUND_FINALS, decompose, is_hangul_syllable
from .phonology import Hints, pronounce_phrase

INITIAL_ROMAN: dict[str, str] = {
    "ㄱ": "g", "ㄲ": "kk", "ㄴ": "n", "ㄷ": "d", "ㄸ": "tt", "ㄹ": "r",
    "ㅁ": "m", "ㅂ": "b", "ㅃ": "pp", "ㅅ": "s", "ㅆ": "ss", "ㅇ": "",
    "ㅈ": "j", "ㅉ": "jj", "ㅊ": "ch", "ㅋ": "k", "ㅌ": "t", "ㅍ": "p", "ㅎ": "h",
}

MEDIAL_ROMAN: dict[str, str] = {
    "ㅏ": "a", "ㅐ": "ae", "ㅑ": "ya", "ㅒ": "yae", "ㅓ": "eo", "ㅔ": "e",
    "ㅕ": "yeo", "ㅖ": "ye", "ㅗ": "o", "ㅘ": "wa", "ㅙ": "wae", "ㅚ": "oe",
    "ㅛ": "yo", "ㅜ": "u", "ㅝ": "wo", "ㅞ": "we", "ㅟ": "wi", "ㅠ": "yu",
    "ㅡ": "eu", "ㅢ": "ui", "ㅣ": "i",
}

FINAL_ROMAN: dict[str, str] = {
    "": "", "ㄱ": "k", "ㄲ": "k", "ㄳ": "k", "ㄴ": "n", "ㄵ": "n", "ㄶ": "n",
    "ㄷ": "t", "ㄹ": "l", "ㄺ": "k", "ㄻ": "m", "ㄼ": "l", "ㄽ": "l", "ㄾ": "l",
    "ㄿ": "p", "ㅀ": "l", "ㅁ": "m", "ㅂ": "p", "ㅄ": "p", "ㅅ": "t", "ㅆ": "t",
    "ㅇ": "ng", "ㅈ": "t", "ㅊ": "t", "ㅋ": "k", "ㅌ": "t", "ㅍ": "p", "ㅎ": "t",
}

#: An ambiguous romanisation is one a learner cannot map back to Hangul
#: without guessing. Flagging them lets the UI stop offering romanisation for
#: exactly the contrasts it cannot represent.
AMBIGUOUS_PAIRS = [
    ("ㅐ", "ㅔ", "ae vs e — these are near-identical in modern Seoul speech"),
    ("ㅚ", "ㅙ", "oe vs wae — merged for most speakers"),
    ("ㅓ", "ㅗ", "eo vs o — the single hardest vowel contrast for English speakers"),
    ("ㄱ", "ㅋ", "g/k — RR writes the same letter differently by position"),
]


def romanize_syllable(ch: str, prev_final: str = "") -> str:
    syl = decompose(ch)
    if syl is None:
        return ch
    out = INITIAL_ROMAN[syl.initial] + MEDIAL_ROMAN[syl.medial]
    out += FINAL_ROMAN.get(syl.final, "")
    return out


def romanize(
    text: str,
    phonetic: bool = True,
    hints: Optional[Hints | dict] = None,
    hyphenate: bool = False,
    capitalize: bool = False,
) -> str:
    """han'gug'eo -> 'hangugeo'.

    phonetic=True  (default) romanises the *pronounced* form, which is what
                   the official standard specifies: 신라 -> 'silla'.
    phonetic=False romanises letter by letter: 신라 -> 'sinra'. Useful when
                   showing a learner how the spelling maps to letters.
    hyphenate=True inserts '-' between syllables, which disambiguates
                   sequences like 'eo' (ㅓ) from 'e'+'o'.
    """
    source = pronounce_phrase(text, hints).spoken if phonetic else text

    parts: list[str] = []
    for ch in source:
        if is_hangul_syllable(ch):
            parts.append(romanize_syllable(ch))
        else:
            parts.append(ch)

    if hyphenate:
        out = ""
        for i, p in enumerate(parts):
            prev_is_syllable = i > 0 and is_hangul_syllable(source[i - 1])
            if prev_is_syllable and is_hangul_syllable(source[i]):
                out += "-"
            out += p
    else:
        out = "".join(parts)

    return out[:1].upper() + out[1:] if capitalize and out else out


def fade(text: str, level: float, seed: Optional[int] = None, **kw) -> str:
    """Partial romanisation for weaning learners off the crutch.

    level 1.0 romanises everything, 0.0 romanises nothing, and values in
    between leave the syllables the learner is most likely to know in Hangul
    and romanise the rest. The choice is deterministic per (text, seed) so a
    learner does not see a word flicker between forms on re-render.
    """
    level = max(0.0, min(1.0, level))
    if level >= 1.0:
        return romanize(text, **kw)
    if level <= 0.0:
        return text

    rng = random.Random(seed if seed is not None else hash(text) & 0xFFFF)
    out: list[str] = []
    for ch in text:
        if is_hangul_syllable(ch) and rng.random() < level:
            out.append(romanize(ch, **kw))
        else:
            out.append(ch)
    return "".join(out)


def ambiguity_warnings(text: str) -> list[str]:
    """Contrasts in `text` that romanisation cannot faithfully represent."""
    from .hangul import to_jamo

    jamo = set(to_jamo(text))
    out: list[str] = []
    for a, b, why in AMBIGUOUS_PAIRS:
        if a in jamo or b in jamo:
            out.append(why)
    return out


def with_romanization(text: str, show: bool = True, level: float = 1.0) -> dict:
    """The payload the UI renders under a Korean string."""
    return {
        "korean": text,
        "romanization": fade(text, level) if show else None,
        "romanization_full": romanize(text),
        "romanization_literal": romanize(text, phonetic=False),
        "pronounced": pronounce_phrase(text).spoken,
    }
