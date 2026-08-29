"""
Japanese writing systems: hiragana, katakana, kanji.

Three separate engines rather than one, because they are learned separately
and mastery of one says nothing about the others. The shared core asks the
registry for a writing system by id and gets whichever of these applies.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ...config import CONTENT_DIR
from . import kana as K
from . import romaji as R


class _KanaWritingSystem:
    """Shared behaviour for the two syllabaries. They differ only in script."""

    has_stroke_order = True
    is_closed_inventory = True
    language = "ja"
    script: str = "hiragana"

    def units(self) -> list[dict]:
        out = []
        for u in K.inventory():
            char = u.hiragana if self.script == "hiragana" else u.katakana
            out.append({
                "id": f"ja-{self.script}-{char}",
                "unit": char,
                "kind": u.group,
                "name": u.romaji,
                "romanization": u.romaji,
                "group": u.group,
                "teaching_stage": u.teaching_stage,
                "row": u.row,
                "vowel": u.vowel,
                "pair": u.katakana if self.script == "hiragana" else u.hiragana,
                "derives_from": (u.from_kana if self.script == "hiragana"
                                 else K.to_katakana(u.from_kana)) if u.from_kana else "",
                "note": u.note,
                "mora": 1,
            })
        return out

    def unit_count(self) -> int:
        return len(K.inventory())

    def decompose(self, text: str) -> list[dict]:
        """Japanese decomposes into MORA, not characters.

        This is the shape the shared core gets, and it is deliberately not the
        same shape Korean returns. Korean's atom is a syllable block with three
        slots; Japanese's is a beat.
        """
        return [m.to_dict() for m in K.split_mora(text)]

    def is_valid(self, text: str) -> bool:
        check = K.is_hiragana if self.script == "hiragana" else K.is_katakana
        return all(check(c) or c.isspace() or not c.isalnum() for c in text)

    def contains_script(self, text: str) -> bool:
        check = K.is_hiragana if self.script == "hiragana" else K.is_katakana
        return any(check(c) for c in text)

    # -- Japanese-specific, reached by Japanese code only ------------------

    def mora_diagram(self, text: str) -> dict:
        return K.mora_diagram(text)

    def count_mora(self, text: str) -> int:
        return K.count_mora(text)

    def chart(self, group: str = "basic") -> list[list[Optional[str]]]:
        return K.chart(self.script, group)

    def convert(self, text: str) -> str:
        return (K.to_katakana(text) if self.script == "katakana"
                else K.to_hiragana(text))

    def from_romaji(self, romaji: str) -> str:
        return R.to_kana(romaji, katakana=self.script == "katakana")


class HiraganaWritingSystem(_KanaWritingSystem):
    id = "hiragana"
    name = "Hiragana"
    native_name = "ひらがな"
    script = "hiragana"


class KatakanaWritingSystem(_KanaWritingSystem):
    id = "katakana"
    name = "Katakana"
    native_name = "カタカナ"
    script = "katakana"


@lru_cache(maxsize=1)
def _kanji_data() -> list[dict]:
    path = Path(CONTENT_DIR) / "ja" / "writing" / "kanji.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("kanji", [])


class KanjiWritingSystem:
    """Kanji is an open inventory, so it is taught by frequency band.

    `units()` returns whatever band has been authored, never "all kanji" —
    there is no such list, and pretending otherwise would produce a progress
    bar that can never fill.
    """

    id = "kanji"
    name = "Kanji"
    native_name = "漢字"
    has_stroke_order = True
    is_closed_inventory = False
    language = "ja"

    def units(self) -> list[dict]:
        out = []
        for k in _kanji_data():
            out.append({
                "id": f"ja-kanji-{k['character']}",
                "unit": k["character"],
                "kind": "kanji",
                "name": k.get("meaning", ""),
                "romanization": "",
                "teaching_stage": k.get("grade", 99),
                "readings_on": k.get("on", []),
                "readings_kun": k.get("kun", []),
                "strokes": k.get("strokes"),
                "radical": k.get("radical", ""),
                "jlpt": k.get("jlpt", ""),
                "examples": k.get("examples", []),
            })
        out.sort(key=lambda u: (u["teaching_stage"], u["unit"]))
        return out

    def unit_count(self) -> int:
        return len(_kanji_data())

    def decompose(self, text: str) -> list[dict]:
        """Split text into kanji and non-kanji runs, annotating the kanji."""
        index = {k["character"]: k for k in _kanji_data()}
        out = []
        for ch in text:
            if K.is_kanji(ch):
                k = index.get(ch, {})
                out.append({"char": ch, "is_kanji": True,
                            "meaning": k.get("meaning", ""),
                            "on": k.get("on", []), "kun": k.get("kun", []),
                            "strokes": k.get("strokes"),
                            "known": bool(k)})
            else:
                out.append({"char": ch, "is_kanji": False,
                            "script": ("hiragana" if K.is_hiragana(ch)
                                       else "katakana" if K.is_katakana(ch) else "other")})
        return out

    def is_valid(self, text: str) -> bool:
        return all(K.is_kanji(c) or c.isspace() for c in text)

    def contains_script(self, text: str) -> bool:
        return any(K.is_kanji(c) for c in text)


HIRAGANA = HiraganaWritingSystem()
KATAKANA = KatakanaWritingSystem()
KANJI = KanjiWritingSystem()

#: The registry loads one ENGINE per language. Hiragana is the gate — nothing
#: else in Japanese is learnable before it — so it is the default.
ENGINE = HIRAGANA

BY_ID = {"hiragana": HIRAGANA, "katakana": KATAKANA, "kanji": KANJI}


def get(writing_system: str):
    return BY_ID.get(writing_system, HIRAGANA)
