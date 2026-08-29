"""
Tone sandhi: what the tones are written as, versus what they are said as.

This is Mandarin's counterpart to the Korean 받침 engine. In both languages the
written form and the spoken form come apart in rule-governed ways, and in both
the learner needs to see *why*, not just *what*. The rules themselves have
nothing in common — Korean's are about consonants meeting across syllable
boundaries; Mandarin's are about pitch contours colliding — which is exactly
why the two live in separate modules.

The rules implemented here are the ones that are genuinely automatic:

    third-tone sandhi   nǐ hǎo   is said  ní hǎo
    half-third          hǎo chī  the 3 does not rise; it just stays low
    不 bù               bù shì   is said  bú shì
    一 yī               yī tiān  is said  yì tiān
                        yī dìng  is said  yí dìng

Neutral-tone assignment is *lexical*, not automatic — 东西 means "thing" with a
neutral second syllable and "east-west" with a first tone — so the engine never
assigns it. A syllable written without a tone already parses as neutral, which
means the content file decides, exactly as it should: writing "guo" gives a
neutral tone and writing "guó" keeps tone 2, so 中国 stays zhōngguó.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from . import pinyin as P

# --------------------------------------------------------------------------
# Rule catalogue
# --------------------------------------------------------------------------

RULES: dict[str, dict[str, str]] = {
    "third_tone_sandhi": {
        "zh": "三声变调",
        "en": "Third-tone sandhi",
        "simple": (
            "Two low dipping tones in a row is hard to say — you would have to "
            "sink twice with no room in between. So the first one gives up and "
            "rises instead."
        ),
        "technical": (
            "A third tone becomes a second tone before another third tone. The "
            "change is phonetic only: the syllable is still written with tone 3."
        ),
    },
    "half_third": {
        "zh": "半三声",
        "en": "Half third tone",
        "simple": (
            "On its own, a third tone dips down and comes back up. In front of "
            "any other tone, it only does the first half — it drops low and "
            "stays there. The rise you learned is the exception, not the rule."
        ),
        "technical": (
            "Before tones 1, 2, 4 and the neutral tone, tone 3 surfaces as a "
            "low-falling allotone with no final rise."
        ),
    },
    "bu_sandhi": {
        "zh": "不的变调",
        "en": "不 tone change",
        "simple": (
            "不 is normally bù, falling. But two falling tones in a row collide, "
            "so before another falling tone it rises instead: bú."
        ),
        "technical": "不 shifts from tone 4 to tone 2 before a tone-4 syllable.",
    },
    "yi_sandhi": {
        "zh": "一的变调",
        "en": "一 tone change",
        "simple": (
            "一 changes to suit what follows. Before a falling tone it rises "
            "(yí); before anything else it falls (yì). On its own, counting, or "
            "at the end of a word, it stays flat: yī."
        ),
        "technical": (
            "一 is tone 1 in isolation, ordinals and final position; tone 2 "
            "before tone 4; tone 4 before tones 1, 2 and 3."
        ),
    },
    "neutral_tone": {
        "zh": "轻声",
        "en": "Neutral tone",
        "simple": (
            "Some syllables lose their tone entirely and become short and light, "
            "taking their pitch from whatever came before."
        ),
        "technical": (
            "Toneless syllables: grammatical particles, some suffixes, the second "
            "half of reduplicated kinship terms. Lexically determined, not "
            "predictable from the characters."
        ),
    },
}

#: Syllables that are *often* neutral — but only in one of their meanings.
#: guo is neutral as the aspect particle 过 and tone 2 in 中国; ma is neutral
#: as 吗 and tone 1 in 妈. So this list is documentation for the lesson
#: content, NOT something the engine applies on its own. An unmarked syllable
#: already parses as tone 5, so nothing needs guessing: writing "guo" gets a
#: neutral tone and writing "guó" keeps tone 2, which is exactly right.
COMMONLY_NEUTRAL: frozenset[str] = frozenset({
    "de", "le", "ne", "ma", "ba", "zhe", "guo", "me", "zi", "tou", "men",
})

#: Characters those neutral syllables correspond to, for the hanzi path.
NEUTRAL_CHARACTERS: frozenset[str] = frozenset("的了呢吗吧着过么子头们地得")


@dataclass
class ToneChange:
    rule: str
    rule_zh: str
    rule_en: str
    index: int
    syllable: str
    written_tone: int
    spoken_tone: int
    before: str
    after: str
    simple: str
    technical: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Pronunciation:
    written: str
    spoken: str
    written_tones: list[int] = field(default_factory=list)
    spoken_tones: list[int] = field(default_factory=list)
    changes: list[ToneChange] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.written_tones != self.spoken_tones

    def to_dict(self) -> dict:
        return {
            "written": self.written,
            "spoken": self.spoken,
            "written_tones": self.written_tones,
            "spoken_tones": self.spoken_tones,
            "changed": self.changed,
            "changes": [c.to_dict() for c in self.changes],
        }


@dataclass
class Hints:
    """What the tones alone cannot tell you.

    yi_is_ordinal   一 in 第一 or when counting keeps tone 1.
    neutral_at      indices the content declares neutral, beyond the safe list.
    word_breaks     indices where a new word starts; third-tone sandhi does not
                    reach across a major phrase boundary in careful speech.
    """

    yi_is_ordinal: bool = False
    neutral_at: frozenset[int] = frozenset()
    word_breaks: frozenset[int] = frozenset()

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "Hints":
        d = d or {}
        return cls(
            yi_is_ordinal=bool(d.get("yi_is_ordinal", False)),
            neutral_at=frozenset(d.get("neutral_at", ()) or ()),
            word_breaks=frozenset(d.get("word_breaks", ()) or ()),
        )


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------

def apply_sandhi(text: str, hints: Optional[Hints | dict] = None) -> Pronunciation:
    """Written pinyin in, spoken pinyin out, with the reasons.

    >>> apply_sandhi("nǐ hǎo").spoken
    'ní hǎo'
    >>> apply_sandhi("bù shì").spoken
    'bú shì'
    """
    h = hints if isinstance(hints, Hints) else Hints.from_dict(hints)
    syllables = P.parse_phrase(text)
    if not syllables:
        return Pronunciation(text, text, [], [])

    written = [s.tone for s in syllables]
    tones = list(written)
    plains = [s.plain for s in syllables]
    changes: list[ToneChange] = []

    def note(rule: str, i: int, old: int, new: int) -> None:
        meta = RULES[rule]
        changes.append(ToneChange(
            rule=rule, rule_zh=meta["zh"], rule_en=meta["en"], index=i,
            syllable=plains[i], written_tone=old, spoken_tone=new,
            before=P.add_tone_mark(plains[i], old),
            after=P.add_tone_mark(plains[i], new) if new != 5 else plains[i],
            simple=meta["simple"], technical=meta["technical"],
        ))

    # ---- 1. Declared neutral tones --------------------------------------
    # Only where the content says so. 中国 is zhōngguó, not zhōngguo, and an
    # engine that neutralised every "guo" would mispronounce the name of the
    # country. A syllable written without a tone is already tone 5.
    for i in sorted(h.neutral_at):
        if 0 <= i < len(tones) and tones[i] != 5:
            old = tones[i]
            tones[i] = 5
            note("neutral_tone", i, old, 5)

    # ---- 2. 不 and 一 -----------------------------------------------------
    # These run before third-tone sandhi because 一 can become tone 4, which
    # then feeds the half-third rule on a preceding 3.
    for i, plain in enumerate(plains):
        nxt = tones[i + 1] if i + 1 < len(tones) else None

        if plain == "bu" and nxt is not None:
            new = 2 if nxt == 4 else 4
            if tones[i] != new:
                old = tones[i]
                tones[i] = new
                note("bu_sandhi", i, old, new)

        elif plain == "yi" and nxt is not None and not h.yi_is_ordinal:
            if nxt == 4:
                new = 2
            elif nxt in (1, 2, 3):
                new = 4
            else:
                new = tones[i]
            if tones[i] != new:
                old = tones[i]
                tones[i] = new
                note("yi_sandhi", i, old, new)

    # ---- 3. Third-tone sandhi -------------------------------------------
    # Decided against the UNDERLYING tones, left to right. A run of three
    # third tones becomes 2-2-3: each one changes because the next is
    # underlyingly third, even though that next one has itself changed.
    # Reading the already-changed values instead would give 3-2-3, which is
    # wrong — 我很好 is wó hén hǎo, not wǒ hén hǎo.
    base = list(tones)
    for i in range(len(tones) - 1):
        if base[i] == 3 and base[i + 1] == 3 and (i + 1) not in h.word_breaks:
            tones[i] = 2
            note("third_tone_sandhi", i, 3, 2)

    # ---- 4. Half third ---------------------------------------------------
    # Not a tone change — the syllable is still tone 3 — but it is what the
    # learner actually has to produce, so it is reported as a step.
    for i, t in enumerate(tones):
        if t == 3 and i + 1 < len(tones) and tones[i + 1] in (1, 2, 4, 5):
            note("half_third", i, 3, 3)

    spoken = " ".join(
        P.add_tone_mark(p, t) if t != 5 else p for p, t in zip(plains, tones)
    )
    return Pronunciation(text, spoken, written, tones, changes)


def explain(text: str, hints: Optional[Hints | dict] = None) -> dict:
    """A teaching-ready payload: nǐ hǎo → ní hǎo and why."""
    res = apply_sandhi(text, hints)
    steps = [{
        "rule_id": c.rule,
        "rule": f"{c.rule_zh} ({c.rule_en})",
        "shows": (f"{c.before} → {c.after}" if c.rule != "half_third"
                  else f"{c.before} stays low — no rise"),
        "child_explanation": c.simple,
        "linguistic_explanation": c.technical,
    } for c in res.changes]

    return {
        "written": res.written,
        "spoken": res.spoken,
        "changed": res.changed,
        "written_tones": res.written_tones,
        "spoken_tones": res.spoken_tones,
        "summary": (f"{res.written} → {res.spoken}" if res.changed
                    else f"{res.written} is said with the tones as written."),
        "steps": steps,
    }


def tone_pair_drills() -> list[dict]:
    """All twenty tone pairs, which is how tones are actually practised.

    Learners who drill tones in isolation and then cannot say a two-syllable
    word are the norm. Tones interact, and the pair is the real unit.
    """
    out = []
    for first in range(1, 5):
        for second in range(1, 6):
            example = _PAIR_EXAMPLES.get((first, second))
            entry = {
                "pair": f"{first}-{second}",
                "first": P.TONE_NAMES[first]["contour"],
                "second": P.TONE_NAMES[second]["contour"],
                "difficulty": _PAIR_DIFFICULTY.get((first, second), "medium"),
            }
            if example:
                entry.update(example)
            if first == 3 and second == 3:
                entry["note"] = ("Said as 2-3. This pair never surfaces as "
                                 "written, which is why it needs its own drill.")
            out.append(entry)
    return out


_PAIR_EXAMPLES: dict[tuple[int, int], dict] = {
    (1, 1): {"pinyin": "jīntiān", "hanzi": "今天", "meaning": "today"},
    (1, 2): {"pinyin": "Zhōngguó", "hanzi": "中国", "meaning": "China"},
    (1, 3): {"pinyin": "shāngchǎng", "hanzi": "商场", "meaning": "shopping centre"},
    (1, 4): {"pinyin": "jīhuì", "hanzi": "机会", "meaning": "opportunity"},
    (1, 5): {"pinyin": "māma", "hanzi": "妈妈", "meaning": "mother"},
    (2, 1): {"pinyin": "míngtiān", "hanzi": "明天", "meaning": "tomorrow"},
    (2, 2): {"pinyin": "yóujú", "hanzi": "邮局", "meaning": "post office"},
    (2, 3): {"pinyin": "píjiǔ", "hanzi": "啤酒", "meaning": "beer"},
    (2, 4): {"pinyin": "wénhuà", "hanzi": "文化", "meaning": "culture"},
    (2, 5): {"pinyin": "péngyou", "hanzi": "朋友", "meaning": "friend"},
    (3, 1): {"pinyin": "Běijīng", "hanzi": "北京", "meaning": "Beijing"},
    (3, 2): {"pinyin": "měiguó", "hanzi": "美国", "meaning": "America"},
    (3, 3): {"pinyin": "nǐ hǎo", "hanzi": "你好", "meaning": "hello"},
    (3, 4): {"pinyin": "kǎoshì", "hanzi": "考试", "meaning": "exam"},
    (3, 5): {"pinyin": "jiějie", "hanzi": "姐姐", "meaning": "older sister"},
    (4, 1): {"pinyin": "diànshī", "hanzi": "电视", "meaning": "television"},
    (4, 2): {"pinyin": "wèntí", "hanzi": "问题", "meaning": "question, problem"},
    (4, 3): {"pinyin": "diànnǎo", "hanzi": "电脑", "meaning": "computer"},
    (4, 4): {"pinyin": "zàijiàn", "hanzi": "再见", "meaning": "goodbye"},
    (4, 5): {"pinyin": "xièxie", "hanzi": "谢谢", "meaning": "thank you"},
}

_PAIR_DIFFICULTY: dict[tuple[int, int], str] = {
    (2, 1): "hard", (2, 2): "hard", (3, 3): "hard", (3, 2): "hard",
    (4, 4): "hard", (1, 1): "easy", (4, 5): "easy", (1, 5): "easy",
}


def minimal_pairs() -> list[dict]:
    """Words that differ only in tone. The reason tones are not optional."""
    return [
        {"syllable": "ma", "set": [
            {"pinyin": "mā", "hanzi": "妈", "meaning": "mother"},
            {"pinyin": "má", "hanzi": "麻", "meaning": "hemp; numb"},
            {"pinyin": "mǎ", "hanzi": "马", "meaning": "horse"},
            {"pinyin": "mà", "hanzi": "骂", "meaning": "to scold"},
            {"pinyin": "ma", "hanzi": "吗", "meaning": "question particle"},
        ], "note": "The classic demonstration set."},
        {"syllable": "shui", "set": [
            {"pinyin": "shuǐ", "hanzi": "水", "meaning": "water"},
            {"pinyin": "shuì", "hanzi": "睡", "meaning": "to sleep"},
        ], "note": "Ordering water and asking to sleep are one tone apart."},
        {"syllable": "mai", "set": [
            {"pinyin": "mǎi", "hanzi": "买", "meaning": "to buy"},
            {"pinyin": "mài", "hanzi": "卖", "meaning": "to sell"},
        ], "note": "Opposite meanings, one tone apart. Context does not save you."},
        {"syllable": "wen", "set": [
            {"pinyin": "wèn", "hanzi": "问", "meaning": "to ask"},
            {"pinyin": "wěn", "hanzi": "吻", "meaning": "to kiss"},
        ], "note": "Worth getting right."},
        {"syllable": "tang", "set": [
            {"pinyin": "tāng", "hanzi": "汤", "meaning": "soup"},
            {"pinyin": "táng", "hanzi": "糖", "meaning": "sugar"},
            {"pinyin": "tǎng", "hanzi": "躺", "meaning": "to lie down"},
            {"pinyin": "tàng", "hanzi": "烫", "meaning": "scalding hot"},
        ], "note": "All four tones, all food-adjacent, all different."},
        {"syllable": "shu", "set": [
            {"pinyin": "shū", "hanzi": "书", "meaning": "book"},
            {"pinyin": "shǔ", "hanzi": "鼠", "meaning": "rat"},
            {"pinyin": "shù", "hanzi": "树", "meaning": "tree"},
        ], "note": ""},
    ]
