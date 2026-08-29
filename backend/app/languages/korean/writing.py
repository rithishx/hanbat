"""
Hangul as a WritingSystemEngine.

A thin adapter over `hangul.py`. The engine module stays free of protocol
concerns so it can be used directly by Korean-specific code (which knows about
initials, medials and finals), while this adapter answers the narrower
questions the shared core asks of any writing system.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ...config import CONTENT_DIR
from . import hangul as H


@lru_cache(maxsize=1)
def _jamo_data() -> dict:
    """Load the authored jamo content once."""
    base = Path(CONTENT_DIR) / "ko" / "hangul"
    out: dict = {"consonants": [], "vowels": []}
    for name, key in (("consonants.json", "consonants"), ("vowels.json", "vowels")):
        path = base / name
        if path.exists():
            out[key] = json.loads(path.read_text(encoding="utf-8")).get(key, [])
    return out


class HangulWritingSystem:
    id = "hangul"
    name = "Hangul"
    native_name = "한글"
    has_stroke_order = True
    is_closed_inventory = True
    language = "ko"

    # -- inventory ---------------------------------------------------------

    def units(self) -> list[dict]:
        """Every jamo in teaching order, with its authored explanation.

        Teaching order is not alphabetical order. It groups letters by how
        hard they are for a beginner: the letters that already exist in
        English come first, the three-way tense contrast comes last.
        """
        data = _jamo_data()
        units: list[dict] = []
        for c in data["consonants"]:
            units.append({
                "id": f"ko-jamo-{c['letter']}",
                "unit": c["letter"],
                "kind": "consonant",
                "name": c.get("name", ""),
                "romanization": c.get("name_rr", ""),
                "group": c.get("group", ""),
                "teaching_stage": c.get("teaching_stage", 99),
                "sound": c.get("sound", {}),
                "shape": c.get("shape", {}),
                "examples": c.get("examples", []),
                "contrast_with": c.get("contrast_with", []),
                "can_be_final": c.get("can_be_batchim", False),
            })
        for v in data["vowels"]:
            units.append({
                "id": f"ko-jamo-{v['letter']}",
                "unit": v["letter"],
                "kind": "vowel",
                "name": v.get("name", ""),
                "romanization": v.get("rr", ""),
                "group": v.get("group", ""),
                "teaching_stage": v.get("teaching_stage", 99),
                "sound": {"initial": v.get("rr", ""), "ipa": v.get("ipa", ""),
                          "english_hint": v.get("english_hint", ""),
                          "common_error": v.get("common_error", "")},
                "shape": {"origin": v.get("construction", ""),
                          "built_from": v.get("built_from", [])},
                "examples": v.get("examples", []),
                "contrast_with": v.get("contrast_with", []),
                "priority_drill": v.get("priority_drill", False),
            })
        units.sort(key=lambda u: (u["teaching_stage"], u["kind"] != "vowel"))
        return units

    def unit_count(self) -> int:
        return len(H.INITIALS) + len(H.MEDIALS) + len(H.FINALS) - 1

    # -- structure ---------------------------------------------------------

    def decompose(self, text: str) -> list[dict]:
        """Break text into syllable blocks and their jamo.

        Korean's answer to "what are the written parts of this" is
        three-dimensional — an initial, a medial and an optional final laid
        out in a square — which is why the shared core treats the return
        shape as language-defined rather than forcing a flat list.
        """
        out: list[dict] = []
        for ch in text:
            if H.is_hangul_syllable(ch):
                out.append(H.describe_syllable(ch))
            else:
                out.append({"char": ch, "is_hangul": False})
        return out

    def compose(self, parts: list[str]) -> str:
        """['ㅎ','ㅏ','ㄴ'] -> '한'."""
        if len(parts) == 2:
            return H.compose(parts[0], parts[1])
        if len(parts) == 3:
            return H.compose(parts[0], parts[1], parts[2])
        raise ValueError("a Hangul block takes 2 or 3 jamo (initial, vowel, optional final)")

    def is_valid(self, text: str) -> bool:
        return all(
            H.is_hangul_syllable(c) or H.is_jamo(c) or c.isspace() or not c.isalnum()
            for c in text
        )

    def contains_script(self, text: str) -> bool:
        return H.contains_hangul(text)

    # -- practice support --------------------------------------------------

    def grid(self, initials: Optional[list[str]] = None,
             medials: Optional[list[str]] = None) -> list[list[str]]:
        """The 가나다 practice table."""
        return H.syllable_grid(
            initials or list(H.BASIC_CONSONANTS),
            medials or list(H.BASIC_VOWELS),
        )

    def stroke_order(self, unit: str) -> list[str]:
        for group in _jamo_data().values():
            for entry in group:
                if entry.get("letter") == unit:
                    return entry.get("shape", {}).get("stroke_order", [])
        return []


ENGINE = HangulWritingSystem()
