"""Revised Romanization as a TransliterationEngine."""

from __future__ import annotations

from typing import Any

from . import romanization as R


class KoreanTransliteration:
    language = "ko"
    scheme_name = "Revised Romanization"
    #: Korean romanisation exists only as a scaffold. Nothing in real Korean
    #: life is written in it except place names on road signs, so the app
    #: fades it to zero and never brings it back.
    fully_removable = True
    #: Where the fade should be complete. Once a learner can read Hangul,
    #: romanisation actively slows them down — it gives the eye something
    #: easier to land on.
    remove_by_level = "A1"

    def transliterate(self, text: str, **options: Any) -> str:
        return R.romanize(
            text,
            phonetic=options.get("phonetic", True),
            hints=options.get("hints"),
            hyphenate=options.get("hyphenate", False),
            capitalize=options.get("capitalize", False),
        )

    def fade(self, text: str, level: float, **options: Any) -> str:
        return R.fade(text, level, seed=options.get("seed"))

    def with_reading(self, text: str, show: bool = True, level: float = 1.0) -> dict:
        return R.with_romanization(text, show, level)

    def ambiguity_warnings(self, text: str) -> list[str]:
        """Contrasts romanisation cannot represent faithfully.

        Worth surfacing: a learner who trusts romanisation will merge ㅓ and
        ㅗ forever, because 'eo' and 'o' look related in a way the sounds are
        not.
        """
        return R.ambiguity_warnings(text)


ENGINE = KoreanTransliteration()
