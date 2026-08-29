"""Pinyin as a TransliterationEngine — with an important caveat."""

from __future__ import annotations

import re
from typing import Any

from . import pinyin as P
from . import tones as T

#: Han characters. Detected rather than converted, deliberately — see below.
_HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


class MandarinTransliteration:
    language = "zh"
    scheme_name = "Pinyin"
    #: This is the one that differs from Korean and Japanese. Romanisation is
    #: a crutch in those languages and the app fades it to nothing. Pinyin is
    #: not: it is how Chinese is typed, how dictionaries are ordered, and how
    #: pronunciation is recorded. It fades from *reading practice* so learners
    #: stop leaning on it there, but it never disappears from the app.
    fully_removable = False
    remove_by_level = None

    def transliterate(self, text: str, **options: Any) -> str:
        """Convert between pinyin spellings — not from characters to pinyin.

        Hanzi cannot be converted here, and pretending otherwise would be the
        most damaging kind of fake functionality in this application. 行 is
        xíng in 不行 and háng in 银行; 长 is cháng in 长城 and zhǎng in 长大.
        Reading a character correctly requires knowing the word, which means a
        dictionary, which this module does not have.

        So a string containing characters returns "" — an honest blank the UI
        can show as "no pinyin recorded" — rather than the characters echoed
        back where pinyin was expected. Vocabulary files author the pinyin
        alongside the word, and that authored value is what gets stored.
        """
        if _HAN.search(text):
            return ""
        style = options.get("style", "marked")
        if style == "numbered":
            return P.to_numbered(text)
        return P.to_marked(text)

    def can_transliterate(self, text: str) -> bool:
        """False when the text contains characters, which need a dictionary."""
        return not _HAN.search(text)

    def fade(self, text: str, level: float, **options: Any) -> str:
        """Fade pinyin from *hanzi* reading practice.

        Fading here means hiding the pinyin above the characters, not
        romanising less of the pinyin itself.
        """
        import random

        level = max(0.0, min(1.0, level))
        if level <= 0.0:
            return ""
        if level >= 1.0:
            return self.transliterate(text, **options)
        rng = random.Random(options.get("seed") or (hash(text) & 0xFFFF))
        syllables = P.parse_phrase(text)
        return " ".join(s.marked if rng.random() < level else "…" for s in syllables)

    def styles(self) -> list[dict]:
        return [
            {"id": "marked", "name": "Tone marks", "example": "nǐ hǎo",
             "used_for": "Reading, teaching materials, dictionaries."},
            {"id": "numbered", "name": "Tone numbers", "example": "ni3 hao3",
             "used_for": "Typing, databases, and anywhere marks are awkward."},
        ]

    def to_script(self, text: str) -> str:
        return P.to_marked(text)

    def ambiguity_warnings(self, text: str) -> list[str]:
        out = []
        if _HAN.search(text):
            out.append("Pinyin cannot be derived from characters without a "
                       "dictionary: 行 is xíng in 不行 and háng in 银行. The "
                       "pinyin shown for a word comes from that word's entry, "
                       "not from converting its characters.")
        syllables = P.parse_phrase(text)
        if any(s.tone == 5 for s in syllables):
            out.append("A syllable here has no tone mark. In pinyin that means "
                       "neutral tone — it does not mean 'tone unknown'.")
        if any(s.tone == 3 for s in syllables):
            out.append("Third tones are written as they are stored, not as they "
                       "are said. nǐ hǎo is written with two third tones and "
                       "spoken as ní hǎo.")
        if any(s.final == "i" and s.initial in ("zh", "ch", "sh", "r", "z", "c", "s")
               for s in syllables):
            out.append("The 'i' after zh/ch/sh/r/z/c/s is not the ee of 'ni'. "
                       "Pinyin reuses the letter for a different sound.")
        return out


ENGINE = MandarinTransliteration()
