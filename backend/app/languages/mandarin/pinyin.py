"""
Pinyin: parsing, tone marks, and syllable structure.

Pinyin is treated here as a writing system in its own right, not as a
romanisation to be discarded. That is the honest position: pinyin is how
Chinese is typed, how dictionaries are ordered, and how children are taught to
read. Unlike Korean romanisation — which exists only as a scaffold — pinyin
stays useful at every level, which is why the transliteration engine reports
`fully_removable = False`.

A Mandarin syllable has a rigid three-part shape:

    initial + final + tone        zhōng  =  zh + ong + tone 1

There are 21 initials and around 37 finals, and only about 400 of the possible
combinations actually occur. That small, closed inventory is what makes
Mandarin pronunciation learnable as a system rather than word by word.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Optional

# --------------------------------------------------------------------------
# Tone marks
# --------------------------------------------------------------------------

#: vowel -> (tone1, tone2, tone3, tone4). Tone 5 is the bare vowel.
TONE_MARKS: dict[str, tuple[str, str, str, str]] = {
    "a": ("ā", "á", "ǎ", "à"),
    "e": ("ē", "é", "ě", "è"),
    "i": ("ī", "í", "ǐ", "ì"),
    "o": ("ō", "ó", "ǒ", "ò"),
    "u": ("ū", "ú", "ǔ", "ù"),
    "ü": ("ǖ", "ǘ", "ǚ", "ǜ"),
}

MARKED_TO_PLAIN: dict[str, tuple[str, int]] = {}
for _v, _marks in TONE_MARKS.items():
    for _i, _m in enumerate(_marks, start=1):
        MARKED_TO_PLAIN[_m] = (_v, _i)

TONE_NAMES = {
    1: {"name": "First tone", "chinese": "第一声", "contour": "high level",
        "shape": "˥", "description": "Start high and stay there. Like holding a note."},
    2: {"name": "Second tone", "chinese": "第二声", "contour": "rising",
        "shape": "˧˥", "description": "Rise from the middle to the top — like the "
                                      "English question 'huh?'"},
    3: {"name": "Third tone", "chinese": "第三声", "contour": "low dipping",
        "shape": "˨˩˦", "description": "Drop low and stay low. The textbook rise at "
                                       "the end only happens when the syllable stands alone."},
    4: {"name": "Fourth tone", "chinese": "第四声", "contour": "falling",
        "shape": "˥˩", "description": "Fall sharply from the top — like a firm English 'No!'"},
    5: {"name": "Neutral tone", "chinese": "轻声", "contour": "unstressed",
        "shape": "·", "description": "Short, light, and takes its pitch from the "
                                     "syllable before it."},
}

# --------------------------------------------------------------------------
# Syllable structure
# --------------------------------------------------------------------------

#: Longest first, so zh/ch/sh are matched before z/c/s.
INITIALS: tuple[str, ...] = (
    "zh", "ch", "sh",
    "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h",
    "j", "q", "x", "r", "z", "c", "s",
)

INITIAL_GROUPS: dict[str, tuple[str, ...]] = {
    "labial": ("b", "p", "m", "f"),
    "alveolar": ("d", "t", "n", "l"),
    "velar": ("g", "k", "h"),
    "palatal": ("j", "q", "x"),
    "retroflex": ("zh", "ch", "sh", "r"),
    "dental_sibilant": ("z", "c", "s"),
}

FINALS: tuple[str, ...] = (
    "iang", "iong", "uang", "ueng", "üan",
    "ang", "eng", "ing", "ong", "iao", "ian", "uai", "uan", "üe", "ün",
    "ai", "ei", "ao", "ou", "an", "en", "er", "ia", "ie", "iu", "in",
    "ua", "uo", "ui", "un", "ün",
    "a", "o", "e", "i", "u", "ü",
)

FINAL_GROUPS: dict[str, tuple[str, ...]] = {
    "simple": ("a", "o", "e", "i", "u", "ü"),
    "compound": ("ai", "ei", "ao", "ou"),
    "nasal": ("an", "en", "ang", "eng", "ong", "in", "ing", "un", "ün"),
    "retroflex": ("er",),
    "i_group": ("ia", "ie", "iao", "iu", "ian", "in", "iang", "ing", "iong"),
    "u_group": ("ua", "uo", "uai", "ui", "uan", "un", "uang", "ueng"),
    "u_umlaut_group": ("üe", "üan", "ün"),
}

#: Syllables written with y/w have no real initial — the y/w is a spelling
#: device for a final that would otherwise start with i/u/ü.
Y_W_REWRITE: dict[str, str] = {
    "yi": "i", "ya": "ia", "ye": "ie", "yao": "iao", "you": "iu",
    "yan": "ian", "yin": "in", "yang": "iang", "ying": "ing", "yong": "iong",
    "wu": "u", "wa": "ua", "wo": "uo", "wai": "uai", "wei": "ui",
    "wan": "uan", "wen": "un", "wang": "uang", "weng": "ueng",
    "yu": "ü", "yue": "üe", "yuan": "üan", "yun": "ün",
}

#: After j, q, x and y the umlaut is not written — ju is really jü.
DROPS_UMLAUT = ("j", "q", "x", "y")


@dataclass(frozen=True)
class Syllable:
    """One Mandarin syllable, fully decomposed."""

    raw: str
    initial: str
    final: str
    tone: int              # 1-4, or 5 for neutral
    valid: bool = True
    note: str = ""
    #: 儿化 — a retroflex -r suffixed to the syllable, as in 哪儿 nǎr. Stored
    #: as a flag rather than as part of the final, because it is a suffix
    #: attached to the word, not one of the ~35 finals.
    erhua: bool = False

    @property
    def plain(self) -> str:
        """Toneless pinyin: zhōng -> zhong."""
        return (self.initial + _write_final(self.initial, self.final)
                + ("r" if self.erhua else ""))

    @property
    def numbered(self) -> str:
        """zhong1 — how pinyin is typed and stored."""
        return f"{self.plain}{self.tone}"

    @property
    def marked(self) -> str:
        """zhōng — how pinyin is read."""
        return add_tone_mark(self.plain, self.tone)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(plain=self.plain, numbered=self.numbered, marked=self.marked,
                 tone_name=TONE_NAMES[self.tone]["name"],
                 initial_group=initial_group(self.initial),
                 final_group=final_group(self.final))
        return d


def initial_group(initial: str) -> str:
    for group, members in INITIAL_GROUPS.items():
        if initial in members:
            return group
    return "none" if not initial else "other"


def final_group(final: str) -> str:
    for group, members in FINAL_GROUPS.items():
        if final in members:
            return group
    return "other"


# --------------------------------------------------------------------------
# Tone marks on and off
# --------------------------------------------------------------------------

def strip_tone(text: str) -> tuple[str, int]:
    """'zhōng' -> ('zhong', 1).  'zhong1' -> ('zhong', 1).  'zhong' -> ('zhong', 5)."""
    m = re.fullmatch(r"([a-zA-ZüÜ]+)([1-5])", text.strip())
    if m:
        return m.group(1).lower(), int(m.group(2))

    tone = 5
    out = []
    for ch in text.strip():
        if ch in MARKED_TO_PLAIN:
            plain, t = MARKED_TO_PLAIN[ch]
            out.append(plain)
            tone = t
        else:
            out.append(ch)
    return "".join(out).lower(), tone


def add_tone_mark(plain: str, tone: int) -> str:
    """Put the mark on the right vowel.

    The rule, in order: a and e always take it; in `ou` the o takes it;
    otherwise it goes on the last vowel. That last clause is what makes
    `iu` -> `iù` and `ui` -> `uì`, which learners get wrong constantly.
    """
    if tone == 5 or not (1 <= tone <= 4):
        return plain
    s = plain.replace("v", "ü")

    for vowel in ("a", "e"):
        idx = s.find(vowel)
        if idx >= 0:
            return s[:idx] + TONE_MARKS[vowel][tone - 1] + s[idx + 1:]

    idx = s.find("ou")
    if idx >= 0:
        return s[:idx] + TONE_MARKS["o"][tone - 1] + s[idx + 1:]

    for i in range(len(s) - 1, -1, -1):
        if s[i] in TONE_MARKS:
            return s[:i] + TONE_MARKS[s[i]][tone - 1] + s[i + 1:]
    return s


def to_numbered(text: str) -> str:
    """Convert marked pinyin to the numbered form used for typing and storage."""
    return " ".join(s.numbered if s.valid else s.raw for s in parse_phrase(text))


def to_marked(text: str) -> str:
    """Convert numbered pinyin to the marked form used for reading."""
    return " ".join(s.marked if s.valid else s.raw for s in parse_phrase(text))


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def parse(text: str) -> Syllable:
    """Break one pinyin syllable into initial, final and tone."""
    raw = text.strip()
    plain, tone = strip_tone(raw)
    plain = plain.replace("v", "ü")

    if not plain:
        return Syllable(raw, "", "", 5, False, "empty")

    # y- and w- syllables have no initial; the letter stands in for a glide.
    if plain in Y_W_REWRITE:
        return Syllable(raw, "", Y_W_REWRITE[plain], tone)

    initial = ""
    for cand in INITIALS:
        if plain.startswith(cand):
            initial = cand
            break

    rest = plain[len(initial):]
    # ju/qu/xu/yu are really jü/qü/xü/yü — the umlaut is simply not written.
    if initial in DROPS_UMLAUT and rest.startswith("u"):
        rest = "ü" + rest[1:]

    # zhi/chi/shi/ri/zi/ci/si have a syllabic final written 'i' that is not
    # the vowel of 'ni' — a real phonetic difference the spelling hides. This
    # is checked *before* the general lookup, because 'i' is also an ordinary
    # final and would otherwise match first and swallow the explanation.
    if rest == "i" and initial in ("zh", "ch", "sh", "r", "z", "c", "s"):
        return Syllable(raw, initial, "i", tone, True,
                        "The 'i' here is not the ee sound of 'ni' — it is a buzz "
                        "held in the position of the initial.")

    if rest in FINALS:
        return Syllable(raw, initial, rest, tone)

    for cand in sorted(FINALS, key=len, reverse=True):
        if rest == cand:
            return Syllable(raw, initial, cand, tone)

    # 儿化: a trailing -r on an otherwise valid syllable. 哪儿 is nǎr, not a
    # syllable with a final "ar". `er` itself is a real final, so it is
    # excluded here rather than being read as "e" plus erhua.
    if rest.endswith("r") and rest != "er" and rest[:-1] in FINALS:
        return Syllable(raw, initial, rest[:-1], tone, True,
                        "儿化 — an -r suffixed to the syllable, common in "
                        "northern speech.", erhua=True)

    return Syllable(raw, initial, rest, tone, False,
                    f"{rest!r} is not a pinyin final")


_SYLLABLE_SPLIT = re.compile(r"[a-zA-ZüÜāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+[1-5]?")


def segment(text: str) -> list[str]:
    """Split pinyin into syllables, spaces or no spaces.

    Pinyin is normally written with the syllables of a word joined up —
    Zhōngguó, péngyou, xièxie — so anything that walks a phrase syllable by
    syllable (tone sandhi above all) has to be able to find the boundaries.

    The rule is longest-match-first, which is exactly the convention pinyin
    orthography assumes: `xian` is one syllable, and the writer who means
    xi + an is required to write the apostrophe in `xi'an`. Because the
    apostrophe is a real boundary marker, it is left to split the text before
    this function ever sees it.
    """
    out: list[str] = []
    for run in _SYLLABLE_SPLIT.findall(text):
        out.extend(_split_run(run))
    return out


def _split_run(run: str) -> list[str]:
    if parse(run).valid:
        return [run]
    n = len(run)
    memo: dict[int, Optional[list[str]]] = {}

    def solve(i: int) -> Optional[list[str]]:
        if i == n:
            return []
        if i in memo:
            return memo[i]
        memo[i] = None
        for j in range(n, i, -1):            # longest piece first
            if not parse(run[i:j]).valid:
                continue
            rest = solve(j)
            if rest is not None:
                memo[i] = [run[i:j]] + rest
                return memo[i]
        return memo[i]

    # An unsplittable run is returned whole, so `parse` can report *why* it is
    # not pinyin rather than this function silently dropping it.
    return solve(0) or [run]


def parse_phrase(text: str) -> list[Syllable]:
    """Parse pinyin written with or without spaces between syllables."""
    return [parse(tok) for tok in segment(text)]


def is_valid_syllable(text: str) -> bool:
    return parse(text).valid


def tone_of(text: str) -> int:
    return parse(text).tone


def tones_of(text: str) -> list[int]:
    return [s.tone for s in parse_phrase(text)]


# --------------------------------------------------------------------------
# Teaching data
# --------------------------------------------------------------------------

INITIAL_NOTES: dict[str, str] = {
    "b": "Unaspirated. Closer to English 'p' in 'spin' than to 'b' in 'bin'.",
    "p": "Aspirated. A strong puff of air, like English 'p' in 'pin'.",
    "d": "Unaspirated, like the 't' in 'stop'.",
    "t": "Aspirated, like 't' in 'top'.",
    "g": "Unaspirated, like the 'k' in 'skin'.",
    "k": "Aspirated, like 'k' in 'kin'.",
    "j": "Tongue flat and forward, near 'jee'. Always followed by i or ü.",
    "q": "Same position as j, with a strong puff. Not English 'q'.",
    "x": "Same position as j and q, a soft hiss. Not English 'x'.",
    "zh": "Tongue curled back. Like 'j' in 'jar' with the tongue tip raised.",
    "ch": "Retroflex, aspirated. zh with a puff of air.",
    "sh": "Retroflex 'sh', tongue curled back.",
    "r": "Retroflex, between English 'r' and the 's' in 'measure'. Not a rolled r.",
    "z": "Like the 'ds' in 'reads'. Unaspirated.",
    "c": "Like the 'ts' in 'cats', with a strong puff.",
    "s": "Like English 's'. Tongue flat.",
    "f": "Like English 'f'.",
    "m": "Like English 'm'.",
    "n": "Like English 'n'.",
    "l": "Like English 'l'.",
    "h": "Further back than English 'h' — a little friction, like Scottish 'loch'.",
}

FINAL_NOTES: dict[str, str] = {
    "i": "After zh/ch/sh/r/z/c/s this is a buzz, not 'ee'.",
    "e": "Not English 'e'. A back unrounded vowel, closer to the 'u' in 'duh'.",
    "ü": "Say 'ee', then round your lips without moving your tongue.",
    "ian": "Sounds like 'yen', not 'ee-ahn'.",
    "iu": "Really 'iou' — there is a hidden o in the middle.",
    "ui": "Really 'uei' — there is a hidden e in the middle.",
    "un": "Really 'uen'.",
    "er": "The tongue curls up. This final takes no initial.",
    "ong": "Closer to 'oong' than to English 'ong'.",
}

#: The contrasts English speakers reliably fail on.
HARD_CONTRASTS: list[dict] = [
    {"pair": ["j", "zh"], "why": "Both sound like English 'j'. j is flat and forward; "
                                 "zh is curled back."},
    {"pair": ["q", "ch"], "why": "Both sound like English 'ch'. Same tongue difference."},
    {"pair": ["x", "sh"], "why": "Both sound like English 'sh'. Same tongue difference."},
    {"pair": ["b", "p"], "why": "Aspiration, not voicing. Hold a hand to your mouth: "
                                "p moves it, b does not."},
    {"pair": ["u", "ü"], "why": "nu and nü are different words. ü is 'ee' with rounded lips."},
    {"pair": ["e", "o"], "why": "Mandarin 'e' is unrounded and further back than English 'e'."},
    {"pair": ["an", "ang"], "why": "Where the nasal ends: tongue tip forward for -n, "
                                   "back of the tongue for -ng."},
]


def inventory() -> dict:
    """Everything a learner has to master, as data for the writing module."""
    return {
        "initials": [
            {"unit": i, "group": initial_group(i), "note": INITIAL_NOTES.get(i, "")}
            for i in sorted(INITIALS, key=lambda x: (len(x), x))
        ],
        "finals": [
            {"unit": f, "group": final_group(f), "note": FINAL_NOTES.get(f, "")}
            for f in sorted(set(FINALS), key=lambda x: (len(x), x))
        ],
        "tones": [{"tone": t, **info} for t, info in TONE_NAMES.items()],
        "hard_contrasts": HARD_CONTRASTS,
    }


def syllable_table(initial: str) -> list[dict]:
    """Every final that combines with one initial, in all four tones.

    Only about 400 of the possible combinations exist. Showing which ones are
    real is more useful than showing the full grid.
    """
    out = []
    for f in FINALS:
        s = parse(initial + _write_final(initial, f))
        if s.valid:
            out.append({
                "final": f,
                "syllable": s.plain,
                "tones": [add_tone_mark(s.plain, t) for t in range(1, 5)],
            })
    return out


def _write_final(initial: str, final: str) -> str:
    """Spell a final the way pinyin actually writes it after this initial."""
    if not initial:
        for spelled, actual in Y_W_REWRITE.items():
            if actual == final:
                return spelled
        return final
    if initial in DROPS_UMLAUT and final.startswith("ü"):
        return "u" + final[1:]
    return final
