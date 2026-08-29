"""
Mandarin writing systems: pinyin and hanzi.

Pinyin is registered as a writing system in its own right rather than as a
romanisation. That is not a technicality — pinyin is taught first in Chinese
primary schools, it is how the language is typed, and it is how dictionaries
are ordered. A learner who cannot read pinyin cannot look anything up.

Hanzi is an open inventory, like kanji. It is taught by frequency band, and
`units()` returns only what has actually been authored — never a claim to
cover "all characters", which would give the learner a progress bar that can
never fill.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ...config import CONTENT_DIR
from . import pinyin as P


class PinyinWritingSystem:
    id = "pinyin"
    name = "Pinyin"
    native_name = "拼音"
    has_stroke_order = False
    is_closed_inventory = True
    language = "zh"

    def units(self) -> list[dict]:
        """Initials, finals and tones — the three things to master."""
        inv = P.inventory()
        out: list[dict] = []
        for i, item in enumerate(inv["initials"]):
            out.append({
                "id": f"zh-pinyin-initial-{item['unit']}",
                "unit": item["unit"], "kind": "initial",
                "name": item["unit"], "romanization": item["unit"],
                "group": item["group"], "note": item["note"],
                "teaching_stage": 1,
            })
        for item in inv["finals"]:
            out.append({
                "id": f"zh-pinyin-final-{item['unit']}",
                "unit": item["unit"], "kind": "final",
                "name": item["unit"], "romanization": item["unit"],
                "group": item["group"], "note": item["note"],
                "teaching_stage": 2,
            })
        for t in inv["tones"]:
            out.append({
                "id": f"zh-pinyin-tone-{t['tone']}",
                "unit": str(t["tone"]), "kind": "tone",
                "name": t["name"], "romanization": t["shape"],
                "group": "tone", "note": t["description"],
                "contour": t["contour"], "chinese": t["chinese"],
                "teaching_stage": 0,
            })
        out.sort(key=lambda u: (u["teaching_stage"], u["kind"], u["unit"]))
        return out

    def unit_count(self) -> int:
        return len(self.units())

    def decompose(self, text: str) -> list[dict]:
        """Mandarin decomposes into initial + final + tone.

        A third shape again, different from Korean's three-slot block and
        Japanese's mora. Each language's atom is what that language's
        learners actually manipulate.
        """
        return [s.to_dict() for s in P.parse_phrase(text)]

    def compose(self, parts: list[str]) -> str:
        """['zh', 'ong', '1'] -> 'zhōng'."""
        if len(parts) not in (2, 3):
            raise ValueError("a pinyin syllable takes initial + final, and optionally a tone")
        initial, final = parts[0], parts[1]
        tone = int(parts[2]) if len(parts) == 3 and str(parts[2]).isdigit() else 5
        syllable = P.parse(initial + final)
        if not syllable.valid:
            raise ValueError(f"{initial}{final} is not a possible Mandarin syllable")
        return P.add_tone_mark(syllable.plain, tone)

    def is_valid(self, text: str) -> bool:
        return all(s.valid for s in P.parse_phrase(text)) if text.strip() else False

    def contains_script(self, text: str) -> bool:
        return any(s.valid for s in P.parse_phrase(text))

    def syllable_table(self, initial: str) -> list[dict]:
        return P.syllable_table(initial)


@lru_cache(maxsize=1)
def _hanzi_data() -> list[dict]:
    path = Path(CONTENT_DIR) / "zh" / "writing" / "hanzi.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("characters", [])


def is_hanzi(ch: str) -> bool:
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF)


class HanziWritingSystem:
    id = "hanzi"
    name = "Chinese characters"
    native_name = "汉字"
    has_stroke_order = True
    is_closed_inventory = False
    language = "zh"

    def units(self) -> list[dict]:
        out = []
        for c in _hanzi_data():
            out.append({
                "id": f"zh-hanzi-{c['character']}",
                "unit": c["character"], "kind": "hanzi",
                "name": c.get("meaning", ""),
                "romanization": c.get("pinyin", ""),
                "teaching_stage": c.get("hsk", 99),
                "strokes": c.get("strokes"),
                "radical": c.get("radical", ""),
                "components": c.get("components", []),
                "traditional": c.get("traditional", ""),
                "examples": c.get("examples", []),
            })
        out.sort(key=lambda u: (u["teaching_stage"], u["unit"]))
        return out

    def unit_count(self) -> int:
        return len(_hanzi_data())

    def decompose(self, text: str) -> list[dict]:
        """Characters, annotated with their components where known.

        Chinese characters decompose into reusable components, which is what
        makes them learnable in bulk rather than one at a time: 妈 is 女
        (woman) plus 马 (horse, giving the sound ma).
        """
        index = {c["character"]: c for c in _hanzi_data()}
        out = []
        for ch in text:
            if is_hanzi(ch):
                c = index.get(ch, {})
                out.append({
                    "char": ch, "is_hanzi": True,
                    "pinyin": c.get("pinyin", ""), "meaning": c.get("meaning", ""),
                    "components": c.get("components", []),
                    "radical": c.get("radical", ""), "strokes": c.get("strokes"),
                    "known": bool(c),
                })
            else:
                out.append({"char": ch, "is_hanzi": False})
        return out

    def is_valid(self, text: str) -> bool:
        return all(is_hanzi(c) or c.isspace() for c in text)

    def contains_script(self, text: str) -> bool:
        return any(is_hanzi(c) for c in text)


PINYIN = PinyinWritingSystem()
HANZI = HanziWritingSystem()

#: Pinyin is the gate: nothing else in Mandarin can be learned without it.
ENGINE = PINYIN

BY_ID = {"pinyin": PINYIN, "hanzi": HANZI}


def get(writing_system: str):
    return BY_ID.get(writing_system, PINYIN)
