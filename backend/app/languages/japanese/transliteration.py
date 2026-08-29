"""Romaji as a TransliterationEngine."""

from __future__ import annotations

from typing import Any

from . import romaji as R


class JapaneseTransliteration:
    language = "ja"
    scheme_name = "Romaji (Hepburn)"
    #: Romaji genuinely disappears once kana is learned — Japanese is not
    #: written in it. The one lasting use is typing, and that is the wapuro
    #: style, which the app teaches as an input skill rather than as reading.
    fully_removable = True
    remove_by_level = "N5"

    def transliterate(self, text: str, **options: Any) -> str:
        return R.romanize(text, style=options.get("style", "hepburn"),
                          capitalize=options.get("capitalize", False))

    def fade(self, text: str, level: float, **options: Any) -> str:
        return R.fade(text, level, seed=options.get("seed"))

    def to_script(self, romaji: str, katakana: bool = False) -> str:
        """Romaji in, kana out — the IME behaviour, for typing practice."""
        return R.to_kana(romaji, katakana=katakana)

    def styles(self) -> list[dict]:
        return [
            {"id": "hepburn", "name": "Hepburn", "example": "Tōkyō",
             "used_for": "Dictionaries, signage, most published romanisation."},
            {"id": "simple", "name": "Hepburn without macrons", "example": "Tokyo",
             "used_for": "Passports and English-language text. Hides vowel length."},
            {"id": "wapuro", "name": "Keyboard input", "example": "toukyou",
             "used_for": "What you actually type. Encodes every mora faithfully."},
        ]

    def ambiguity_warnings(self, text: str) -> list[str]:
        return R.ambiguity_warnings(text)


ENGINE = JapaneseTransliteration()
