"""
Hangul engine: composition, decomposition, and jamo metadata.

Korean syllable blocks occupy Unicode U+AC00..U+D7A3 and are algorithmically
composed:

    code = 0xAC00 + (L_index * 21 + V_index) * 28 + T_index

where L is the initial consonant (초성, 19 options), V the medial vowel
(중성, 21 options) and T the final consonant (종성, 28 options including
"none"). Everything in this module is derived from that formula rather than
from lookup tables of pre-built syllables, so any of the 11,172 modern
syllable blocks round-trips correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterator, Optional

# --------------------------------------------------------------------------
# Unicode constants
# --------------------------------------------------------------------------

SBASE = 0xAC00
LBASE = 0x1100
VBASE = 0x1161
TBASE = 0x11A7
LCOUNT = 19
VCOUNT = 21
TCOUNT = 28
NCOUNT = VCOUNT * TCOUNT          # 588
SCOUNT = LCOUNT * NCOUNT          # 11172

# Compatibility-jamo (U+31xx) forms — the ones users actually type and read.
INITIALS: tuple[str, ...] = (
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
)

MEDIALS: tuple[str, ...] = (
    "ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ",
    "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ",
)

FINALS: tuple[str, ...] = (
    "", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ",
    "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
)

INITIAL_INDEX = {c: i for i, c in enumerate(INITIALS)}
MEDIAL_INDEX = {c: i for i, c in enumerate(MEDIALS)}
FINAL_INDEX = {c: i for i, c in enumerate(FINALS)}

# Compound finals split into their two component jamo. Used by the liaison
# rule (the first half stays put, the second half moves to the next syllable)
# and by cluster simplification.
COMPOUND_FINALS: dict[str, tuple[str, str]] = {
    "ㄳ": ("ㄱ", "ㅅ"),
    "ㄵ": ("ㄴ", "ㅈ"),
    "ㄶ": ("ㄴ", "ㅎ"),
    "ㄺ": ("ㄹ", "ㄱ"),
    "ㄻ": ("ㄹ", "ㅁ"),
    "ㄼ": ("ㄹ", "ㅂ"),
    "ㄽ": ("ㄹ", "ㅅ"),
    "ㄾ": ("ㄹ", "ㅌ"),
    "ㄿ": ("ㄹ", "ㅍ"),
    "ㅀ": ("ㄹ", "ㅎ"),
    "ㅄ": ("ㅂ", "ㅅ"),
}

# Compound vowels split into the simple vowels they are drawn from. This is
# what makes "ㅘ is just ㅗ + ㅏ, and it sounds like it looks" teachable.
COMPOUND_MEDIALS: dict[str, tuple[str, ...]] = {
    "ㅐ": ("ㅏ", "ㅣ"),
    "ㅒ": ("ㅑ", "ㅣ"),
    "ㅔ": ("ㅓ", "ㅣ"),
    "ㅖ": ("ㅕ", "ㅣ"),
    "ㅘ": ("ㅗ", "ㅏ"),
    "ㅙ": ("ㅗ", "ㅏ", "ㅣ"),
    "ㅚ": ("ㅗ", "ㅣ"),
    "ㅝ": ("ㅜ", "ㅓ"),
    "ㅞ": ("ㅜ", "ㅓ", "ㅣ"),
    "ㅟ": ("ㅜ", "ㅣ"),
    "ㅢ": ("ㅡ", "ㅣ"),
}

# --------------------------------------------------------------------------
# Jamo metadata used across the teaching content
# --------------------------------------------------------------------------

#: Letter names as Korean children learn them (기역, 니은, ...).
CONSONANT_NAMES: dict[str, str] = {
    "ㄱ": "기역", "ㄴ": "니은", "ㄷ": "디귿", "ㄹ": "리을", "ㅁ": "미음",
    "ㅂ": "비읍", "ㅅ": "시옷", "ㅇ": "이응", "ㅈ": "지읒", "ㅊ": "치읓",
    "ㅋ": "키읔", "ㅌ": "티읕", "ㅍ": "피읖", "ㅎ": "히읗",
    "ㄲ": "쌍기역", "ㄸ": "쌍디귿", "ㅃ": "쌍비읍", "ㅆ": "쌍시옷", "ㅉ": "쌍지읒",
}

#: Articulation class. "plain" / "aspirated" / "tense" is the three-way
#: contrast that English speakers find hardest, so it is first-class data.
CONSONANT_CLASS: dict[str, str] = {
    "ㄱ": "plain", "ㄷ": "plain", "ㅂ": "plain", "ㅈ": "plain", "ㅅ": "plain",
    "ㅋ": "aspirated", "ㅌ": "aspirated", "ㅍ": "aspirated", "ㅊ": "aspirated",
    "ㄲ": "tense", "ㄸ": "tense", "ㅃ": "tense", "ㅉ": "tense", "ㅆ": "tense",
    "ㄴ": "nasal", "ㅁ": "nasal", "ㅇ": "nasal",
    "ㄹ": "liquid", "ㅎ": "fricative",
}

#: Which plain/aspirated/tense letters belong to the same series.
CONSONANT_SERIES: dict[str, tuple[str, ...]] = {
    "velar": ("ㄱ", "ㅋ", "ㄲ"),
    "alveolar": ("ㄷ", "ㅌ", "ㄸ"),
    "bilabial": ("ㅂ", "ㅍ", "ㅃ"),
    "affricate": ("ㅈ", "ㅊ", "ㅉ"),
    "sibilant": ("ㅅ", "ㅆ"),
}

#: Vowels written on a vertical stem sit to the RIGHT of the initial
#: consonant; vowels on a horizontal stem sit BELOW it. This drives the
#: syllable-block layout diagram in the UI.
VERTICAL_MEDIALS = frozenset("ㅏㅐㅑㅒㅓㅔㅕㅖㅣ")
HORIZONTAL_MEDIALS = frozenset("ㅗㅛㅜㅠㅡ")
MIXED_MEDIALS = frozenset("ㅘㅙㅚㅝㅞㅟㅢ")

BASIC_CONSONANTS = ("ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ",
                    "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ")
TENSE_CONSONANTS = ("ㄲ", "ㄸ", "ㅃ", "ㅆ", "ㅉ")
BASIC_VOWELS = ("ㅏ", "ㅑ", "ㅓ", "ㅕ", "ㅗ", "ㅛ", "ㅜ", "ㅠ", "ㅡ", "ㅣ")
COMPLEX_VOWELS = ("ㅐ", "ㅔ", "ㅚ", "ㅟ", "ㅢ", "ㅘ", "ㅙ", "ㅝ", "ㅞ", "ㅒ", "ㅖ")

#: The only finals that are *pronounced* in modern Korean. Every other
#: written final collapses into one of these seven (음절의 끝소리 규칙).
SEVEN_FINAL_SOUNDS = ("ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅇ")


# --------------------------------------------------------------------------
# Core types
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Syllable:
    """A decomposed Hangul syllable block."""

    initial: str
    medial: str
    final: str = ""

    @property
    def char(self) -> str:
        return compose(self.initial, self.medial, self.final)

    @property
    def has_batchim(self) -> bool:
        return self.final != ""

    @property
    def is_compound_batchim(self) -> bool:
        return self.final in COMPOUND_FINALS

    @property
    def layout(self) -> str:
        """How the block is arranged on the page — used to draw the diagram."""
        if self.medial in HORIZONTAL_MEDIALS:
            base = "stacked"       # ㅗ under ㅎ  ->  호
        elif self.medial in VERTICAL_MEDIALS:
            base = "side_by_side"  # ㅏ beside ㅎ ->  하
        else:
            base = "wrapped"       # ㅘ wraps around ->  화
        return f"{base}_with_batchim" if self.final else base

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(
            char=self.char,
            has_batchim=self.has_batchim,
            layout=self.layout,
            parts=self.parts(),
        )
        return d

    def parts(self) -> list[str]:
        """Flat jamo list, splitting compound finals: 한 -> [ㅎ, ㅏ, ㄴ]."""
        out = [self.initial, self.medial]
        if self.final:
            out.append(self.final)
        return out

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.char

    def replace(self, **kw) -> "Syllable":
        return Syllable(
            initial=kw.get("initial", self.initial),
            medial=kw.get("medial", self.medial),
            final=kw.get("final", self.final),
        )


# --------------------------------------------------------------------------
# Composition / decomposition
# --------------------------------------------------------------------------

def is_hangul_syllable(ch: str) -> bool:
    return len(ch) == 1 and SBASE <= ord(ch) < SBASE + SCOUNT


def is_jamo(ch: str) -> bool:
    """True for a standalone compatibility jamo like ㄱ or ㅏ."""
    return len(ch) == 1 and 0x3131 <= ord(ch) <= 0x3163


def contains_hangul(text: str) -> bool:
    return any(is_hangul_syllable(c) or is_jamo(c) for c in text)


def compose(initial: str, medial: str, final: str = "") -> str:
    """ㅎ + ㅏ + ㄴ -> 한. Raises ValueError on an impossible combination."""
    try:
        li = INITIAL_INDEX[initial]
    except KeyError:
        raise ValueError(f"{initial!r} is not a valid initial consonant (초성)") from None
    try:
        vi = MEDIAL_INDEX[medial]
    except KeyError:
        raise ValueError(f"{medial!r} is not a valid vowel (중성)") from None
    try:
        ti = FINAL_INDEX[final or ""]
    except KeyError:
        raise ValueError(f"{final!r} is not a valid final consonant (종성)") from None
    return chr(SBASE + (li * VCOUNT + vi) * TCOUNT + ti)


def decompose(ch: str) -> Optional[Syllable]:
    """한 -> Syllable(ㅎ, ㅏ, ㄴ). Returns None for non-syllable characters."""
    if not is_hangul_syllable(ch):
        return None
    index = ord(ch) - SBASE
    li, rem = divmod(index, NCOUNT)
    vi, ti = divmod(rem, TCOUNT)
    return Syllable(INITIALS[li], MEDIALS[vi], FINALS[ti])


def decompose_text(text: str) -> list[Syllable | str]:
    """Decompose a string, passing non-Hangul characters through untouched."""
    out: list[Syllable | str] = []
    for ch in text:
        syl = decompose(ch)
        out.append(syl if syl is not None else ch)
    return out


def to_jamo(text: str, split_compounds: bool = False) -> list[str]:
    """Flatten text to a jamo sequence. 한국 -> [ㅎ,ㅏ,ㄴ,ㄱ,ㅜ,ㄱ]."""
    out: list[str] = []
    for item in decompose_text(text):
        if isinstance(item, str):
            out.append(item)
            continue
        out.append(item.initial)
        if split_compounds and item.medial in COMPOUND_MEDIALS:
            out.extend(COMPOUND_MEDIALS[item.medial])
        else:
            out.append(item.medial)
        if item.final:
            if split_compounds and item.final in COMPOUND_FINALS:
                out.extend(COMPOUND_FINALS[item.final])
            else:
                out.append(item.final)
    return out


def from_jamo(jamo: list[str]) -> str:
    """Greedy re-assembly of a jamo list into syllable blocks."""
    out: list[str] = []
    i = 0
    n = len(jamo)
    while i < n:
        c = jamo[i]
        if c not in INITIAL_INDEX or i + 1 >= n or jamo[i + 1] not in MEDIAL_INDEX:
            out.append(c)
            i += 1
            continue
        initial, medial = c, jamo[i + 1]
        i += 2
        final = ""
        # Take a following consonant as batchim only if it is not itself the
        # initial of the next syllable.
        if i < n and jamo[i] in FINAL_INDEX and jamo[i] != "":
            takes_next_vowel = i + 1 < n and jamo[i + 1] in MEDIAL_INDEX
            if not takes_next_vowel:
                final = jamo[i]
                i += 1
        out.append(compose(initial, medial, final))
    return "".join(out)


def syllables(text: str) -> Iterator[Syllable]:
    """Yield only the Hangul syllables of a string."""
    for item in decompose_text(text):
        if isinstance(item, Syllable):
            yield item


# --------------------------------------------------------------------------
# Facts the learning modules ask for
# --------------------------------------------------------------------------

def ends_with_batchim(word: str) -> bool:
    """Does the last syllable of `word` carry a final consonant?

    This is the single most-used fact in Korean grammar: it decides
    은/는, 이/가, 을/를, 과/와, (으)로, -아요/-어요 alternations.
    """
    for ch in reversed(word):
        syl = decompose(ch)
        if syl is not None:
            return syl.has_batchim
    return False


def final_of(word: str) -> str:
    """The written batchim of the last syllable, or '' if there is none."""
    for ch in reversed(word):
        syl = decompose(ch)
        if syl is not None:
            return syl.final
    return ""


def pick_particle(word: str, with_batchim: str, without_batchim: str) -> str:
    """Choose the right allomorph. pick_particle('책', '은', '는') -> '은'."""
    return with_batchim if ends_with_batchim(word) else without_batchim


TOPIC = ("은", "는")
SUBJECT = ("이", "가")
OBJECT = ("을", "를")
AND_NOUN = ("과", "와")
COPULA = ("이에요", "예요")


def attach_particle(word: str, pair: tuple[str, str]) -> str:
    """attach_particle('책', OBJECT) -> '책을'"""
    return word + pick_particle(word, *pair)


def describe_syllable(ch: str) -> dict:
    """Everything the UI needs to explain one syllable block to a learner."""
    syl = decompose(ch)
    if syl is None:
        return {"char": ch, "is_hangul": False}
    info = syl.to_dict()
    info["is_hangul"] = True
    info["initial_name"] = CONSONANT_NAMES.get(syl.initial, syl.initial)
    info["initial_silent"] = syl.initial == "ㅇ"
    info["medial_parts"] = list(COMPOUND_MEDIALS.get(syl.medial, ()))
    info["final_parts"] = list(COMPOUND_FINALS.get(syl.final, ())) if syl.final else []
    info["final_name"] = CONSONANT_NAMES.get(syl.final, syl.final) if syl.final else None
    info["formula"] = " + ".join(syl.parts()) + " = " + syl.char
    return info


def possible_syllables(initial: str, medial: str) -> list[str]:
    """Every valid block from one initial+medial across all 28 finals."""
    return [compose(initial, medial, f) for f in FINALS]


def syllable_grid(initials: list[str], medials: list[str]) -> list[list[str]]:
    """The classic 가나다 practice table."""
    return [[compose(i, m) for m in medials] for i in initials]
