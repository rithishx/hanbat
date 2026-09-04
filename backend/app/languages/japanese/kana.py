"""
Japanese kana: hiragana, katakana, and the units that actually matter.

The organising idea here is the **mora**, not the character. Japanese timing is
mora-based — every mora takes roughly the same length — and almost everything
that confuses learners comes from mora that are not one character:

    きょう   is 2 mora (きょ + う), not 3 characters' worth
    がっこう is 4 mora (が + っ + こ + う); the っ is a full beat of silence
    ん       is its own mora, never a coda attached to the previous one

Getting this right is the Japanese equivalent of getting 받침 right in Korean.
A learner who counts characters will say きょう in three beats and sound wrong
in a way they cannot hear or fix.

The gojūon is defined once as data and everything else is derived from it, so
hiragana, katakana and romaji can never drift out of step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

# Hiragana U+3041–U+3096, Katakana U+30A1–U+30FA. The two scripts are laid out
# identically, exactly 0x60 apart, which is why conversion is arithmetic rather
# than a lookup table.
KANA_OFFSET = 0x60
HIRAGANA_START, HIRAGANA_END = 0x3041, 0x3096
KATAKANA_START, KATAKANA_END = 0x30A1, 0x30FA

#: The long-vowel mark. Katakana only, and a full mora of its own.
CHOONPU = "ー"

# --------------------------------------------------------------------------
# The gojūon, as data
# --------------------------------------------------------------------------

#: (hiragana, romaji, row, column). Katakana is derived.
#: Rows are the consonant series; columns are the vowels a/i/u/e/o.
GOJUON: tuple[tuple[str, str, str, str], ...] = (
    ("あ", "a", "", "a"),   ("い", "i", "", "i"),   ("う", "u", "", "u"),
    ("え", "e", "", "e"),   ("お", "o", "", "o"),

    ("か", "ka", "k", "a"), ("き", "ki", "k", "i"), ("く", "ku", "k", "u"),
    ("け", "ke", "k", "e"), ("こ", "ko", "k", "o"),

    ("さ", "sa", "s", "a"), ("し", "shi", "s", "i"), ("す", "su", "s", "u"),
    ("せ", "se", "s", "e"), ("そ", "so", "s", "o"),

    ("た", "ta", "t", "a"), ("ち", "chi", "t", "i"), ("つ", "tsu", "t", "u"),
    ("て", "te", "t", "e"), ("と", "to", "t", "o"),

    ("な", "na", "n", "a"), ("に", "ni", "n", "i"), ("ぬ", "nu", "n", "u"),
    ("ね", "ne", "n", "e"), ("の", "no", "n", "o"),

    ("は", "ha", "h", "a"), ("ひ", "hi", "h", "i"), ("ふ", "fu", "h", "u"),
    ("へ", "he", "h", "e"), ("ほ", "ho", "h", "o"),

    ("ま", "ma", "m", "a"), ("み", "mi", "m", "i"), ("む", "mu", "m", "u"),
    ("め", "me", "m", "e"), ("も", "mo", "m", "o"),

    ("や", "ya", "y", "a"), ("ゆ", "yu", "y", "u"), ("よ", "yo", "y", "o"),

    ("ら", "ra", "r", "a"), ("り", "ri", "r", "i"), ("る", "ru", "r", "u"),
    ("れ", "re", "r", "e"), ("ろ", "ro", "r", "o"),

    ("わ", "wa", "w", "a"), ("を", "o", "w", "o"),

    ("ん", "n", "n", ""),
)

#: 濁点 — two ticks that voice the consonant.
DAKUTEN: tuple[tuple[str, str, str, str], ...] = (
    ("が", "ga", "g", "a"), ("ぎ", "gi", "g", "i"), ("ぐ", "gu", "g", "u"),
    ("げ", "ge", "g", "e"), ("ご", "go", "g", "o"),

    ("ざ", "za", "z", "a"), ("じ", "ji", "z", "i"), ("ず", "zu", "z", "u"),
    ("ぜ", "ze", "z", "e"), ("ぞ", "zo", "z", "o"),

    ("だ", "da", "d", "a"), ("ぢ", "ji", "d", "i"), ("づ", "zu", "d", "u"),
    ("で", "de", "d", "e"), ("ど", "do", "d", "o"),

    ("ば", "ba", "b", "a"), ("び", "bi", "b", "i"), ("ぶ", "bu", "b", "u"),
    ("べ", "be", "b", "e"), ("ぼ", "bo", "b", "o"),
)

#: 半濁点 — a small circle. Only the h-row takes it.
HANDAKUTEN: tuple[tuple[str, str, str, str], ...] = (
    ("ぱ", "pa", "p", "a"), ("ぴ", "pi", "p", "i"), ("ぷ", "pu", "p", "u"),
    ("ぺ", "pe", "p", "e"), ("ぽ", "po", "p", "o"),
)

#: Which plain kana each voiced one comes from — the teaching relationship.
VOICING_SOURCE: dict[str, str] = {
    "が": "か", "ぎ": "き", "ぐ": "く", "げ": "け", "ご": "こ",
    "ざ": "さ", "じ": "し", "ず": "す", "ぜ": "せ", "ぞ": "そ",
    "だ": "た", "ぢ": "ち", "づ": "つ", "で": "て", "ど": "と",
    "ば": "は", "び": "ひ", "ぶ": "ふ", "べ": "へ", "ぼ": "ほ",
    "ぱ": "は", "ぴ": "ひ", "ぷ": "ふ", "ぺ": "へ", "ぽ": "ほ",
}

SMALL_Y = {"ゃ": "や", "ゅ": "ゆ", "ょ": "よ"}
SMALL_VOWELS = {"ぁ": "あ", "ぃ": "い", "ぅ": "う", "ぇ": "え", "ぉ": "お"}
SOKUON = "っ"          # the small tsu: a full beat of held silence
SOKUON_KATAKANA = "ッ"

#: 拗音 — a consonant kana in the i-column plus a small ya/yu/yo. One mora.
YOON_BASES = ("き", "し", "ち", "に", "ひ", "み", "り",
              "ぎ", "じ", "ぢ", "び", "ぴ")

#: Hepburn spellings for the yōon that are not simply base + y.
YOON_ROMAJI: dict[str, str] = {
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
    "ぢゃ": "ja", "ぢゅ": "ju", "ぢょ": "jo",
}

#: Extra combinations used almost only in loanwords: ファ, ティ, ウィ, ヴ...
FOREIGN_COMBOS: dict[str, str] = {
    "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo",
    "てぃ": "ti", "でぃ": "di", "とぅ": "tu", "どぅ": "du",
    "うぃ": "wi", "うぇ": "we", "うぉ": "wo",
    "しぇ": "she", "ちぇ": "che", "じぇ": "je",
    "つぁ": "tsa", "つぃ": "tsi", "つぇ": "tse", "つぉ": "tso",
    # ヴ normalises to ゔ before this table is consulted, so the keys have to be
    # written in hiragana like every other entry. Spelling them with katakana ヴ
    # meant ヴァイオリン counted as six beats instead of five, because the pair
    # never matched and the small ァ became a mora of its own.
    "ゔぁ": "va", "ゔぃ": "vi", "ゔぇ": "ve", "ゔぉ": "vo",
}

#: ヴ on its own is a mora like any other, and its reading is not derivable
#: from the gojūon table because it is not in it.
STANDALONE_ROMAJI = {"ゔ": "vu"}

# --------------------------------------------------------------------------
# Derived lookups
# --------------------------------------------------------------------------

ALL_BASIC = GOJUON + DAKUTEN + HANDAKUTEN

HIRAGANA_TO_ROMAJI: dict[str, str] = {k: r for k, r, _, _ in ALL_BASIC}
ROW_OF: dict[str, str] = {k: row for k, _, row, _ in ALL_BASIC}
VOWEL_OF: dict[str, str] = {k: v for k, _, _, v in ALL_BASIC}

#: Every mora unit that can stand alone, hiragana form.
BASIC_HIRAGANA: tuple[str, ...] = tuple(k for k, *_ in ALL_BASIC)

VOWEL_ROWS = ("a", "i", "u", "e", "o")
CONSONANT_ROWS = ("", "k", "s", "t", "n", "h", "m", "y", "r", "w",
                  "g", "z", "d", "b", "p")


def to_katakana(text: str) -> str:
    """ひらがな -> ヒラガナ. Non-hiragana passes through untouched."""
    return "".join(
        chr(ord(c) + KANA_OFFSET) if HIRAGANA_START <= ord(c) <= HIRAGANA_END else c
        for c in text
    )


def to_hiragana(text: str) -> str:
    """カタカナ -> かたかな."""
    return "".join(
        chr(ord(c) - KANA_OFFSET) if KATAKANA_START <= ord(c) <= KATAKANA_END else c
        for c in text
    )


def is_hiragana(ch: str) -> bool:
    return len(ch) == 1 and HIRAGANA_START <= ord(ch) <= HIRAGANA_END


def is_katakana(ch: str) -> bool:
    return len(ch) == 1 and (KATAKANA_START <= ord(ch) <= KATAKANA_END or ch == CHOONPU)


def is_kana(ch: str) -> bool:
    return is_hiragana(ch) or is_katakana(ch)


def is_kanji(ch: str) -> bool:
    """CJK Unified Ideographs, plus the common extension blocks."""
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF) or (0xF900 <= o <= 0xFAFF)


def contains_japanese(text: str) -> bool:
    return any(is_kana(c) or is_kanji(c) for c in text)


BASIC_KATAKANA: tuple[str, ...] = tuple(to_katakana(k) for k in BASIC_HIRAGANA)


# --------------------------------------------------------------------------
# Mora
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Mora:
    """One beat of Japanese.

    `text` may be one or two characters — きょ is a single mora written with
    two. `kind` is what makes the timing teachable: a learner who knows that
    っ is a *silent beat* rather than a doubled letter will get the rhythm of
    がっこう right the first time.
    """

    text: str
    kind: str          # normal | yoon | sokuon | moraic_n | long_vowel | small_vowel
    romaji: str = ""
    script: str = ""   # hiragana | katakana | other

    @property
    def is_silent(self) -> bool:
        return self.kind == "sokuon"

    def to_dict(self) -> dict:
        return {"text": self.text, "kind": self.kind, "romaji": self.romaji,
                "script": self.script, "is_silent": self.is_silent}


def _script_of(ch: str) -> str:
    if is_hiragana(ch):
        return "hiragana"
    if is_katakana(ch):
        return "katakana"
    return "other"


def split_mora(text: str) -> list[Mora]:
    """Break Japanese text into mora — the beats a speaker actually times.

    きょう   -> [きょ, う]        2 beats
    がっこう -> [が, っ, こ, う]   4 beats
    コーヒー -> [コ, ー, ヒ, ー]   4 beats
    """
    out: list[Mora] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        hira_ch, hira_next = to_hiragana(ch), to_hiragana(nxt)
        script = _script_of(ch)

        # 拗音: consonant + small ya/yu/yo is ONE mora
        if hira_next in SMALL_Y and hira_ch in YOON_BASES:
            pair = ch + nxt
            out.append(Mora(pair, "yoon", _yoon_romaji(hira_ch + hira_next), script))
            i += 2
            continue

        # Loanword combos: フ + ァ, テ + ィ — also one mora
        if hira_next in SMALL_VOWELS:
            key = hira_ch + hira_next
            if key in FOREIGN_COMBOS:
                out.append(Mora(ch + nxt, "small_vowel", FOREIGN_COMBOS[key], script))
                i += 2
                continue

        if ch in (SOKUON, SOKUON_KATAKANA):
            out.append(Mora(ch, "sokuon", "", script))
        elif ch == CHOONPU:
            out.append(Mora(ch, "long_vowel", "", script))
        elif hira_ch == "ん":
            out.append(Mora(ch, "moraic_n", "n", script))
        else:
            out.append(Mora(ch, "normal",
                            HIRAGANA_TO_ROMAJI.get(hira_ch)
                            or STANDALONE_ROMAJI.get(hira_ch, ch), script))
        i += 1
    return out


def _yoon_romaji(pair: str) -> str:
    if pair in YOON_ROMAJI:
        return YOON_ROMAJI[pair]
    base = pair[0]
    small = pair[1]
    consonant = ROW_OF.get(base, "")
    vowel = {"ゃ": "a", "ゅ": "u", "ょ": "o"}[small]
    return f"{consonant}y{vowel}"


def count_mora(text: str) -> int:
    """How many beats. The number Japanese rhythm is built on."""
    return len(split_mora(text))


def mora_diagram(text: str) -> dict:
    """A teaching-ready breakdown, for the timing exercises."""
    mora = split_mora(text)
    return {
        "text": text,
        "count": len(mora),
        "mora": [m.to_dict() for m in mora],
        "beats": " · ".join(m.text if not m.is_silent else "（ ）" for m in mora),
        "note": _timing_note(mora),
    }


def _timing_note(mora: list[Mora]) -> str:
    kinds = {m.kind for m in mora}
    notes = []
    if "sokuon" in kinds:
        notes.append("The small っ is a full beat of silence — stop, hold, then continue.")
    if "moraic_n" in kinds:
        notes.append("ん is its own beat, not a letter tacked onto the one before it.")
    if "long_vowel" in kinds:
        notes.append("ー holds the vowel for a second beat.")
    if "yoon" in kinds:
        notes.append("A small ゃゅょ merges with the kana before it: two characters, one beat.")
    return " ".join(notes)


# --------------------------------------------------------------------------
# Teaching inventory
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class KanaUnit:
    hiragana: str
    katakana: str
    romaji: str
    row: str
    vowel: str
    group: str          # basic | dakuten | handakuten | yoon
    teaching_stage: int
    from_kana: str = ""     # the plain kana a voiced one derives from
    note: str = ""


def _stage(row: str, group: str) -> int:
    """Teaching order: vowels, then the rows in gojūon order, then voicing,
    then the combinations. This is the order every Japanese textbook uses and
    the order the kana chart is printed in, so it matches what a learner will
    see everywhere else."""
    if group == "basic":
        return {"": 1, "k": 2, "s": 3, "t": 4, "n": 5,
                "h": 6, "m": 7, "y": 8, "r": 9, "w": 10}.get(row, 10)
    if group == "dakuten":
        return 11
    if group == "handakuten":
        return 12
    return 13


NOTES: dict[str, str] = {
    "し": "shi, not si. The whole s-row keeps its shape except this one.",
    "ち": "chi, not ti.",
    "つ": "tsu. Start with your tongue where it is for 't' and release into an 's'.",
    "ふ": "fu, but softer than an English f — blow gently between your lips, no teeth.",
    "を": "Pronounced exactly like お. It survives only as the object particle.",
    "ん": "Its own full beat. Its sound shifts to match what follows: n, m, or ng.",
    "は": "Pronounced wa when it is the topic particle, ha everywhere else.",
    "へ": "Pronounced e when it is the direction particle, he everywhere else.",
    "じ": "ji. じ and ぢ sound identical; じ is used for almost everything.",
    "ず": "zu. Same story as じ — ず over づ except in a few compounds.",
    "ぢ": "Identical to じ in modern Japanese. Rare — appears in 鼻血 and little else.",
    "づ": "Identical to ず. Rare — 続く and a handful of compounds.",
}


def inventory(include_yoon: bool = True) -> list[KanaUnit]:
    """Every teachable kana unit, in teaching order."""
    out: list[KanaUnit] = []
    for group, table in (("basic", GOJUON), ("dakuten", DAKUTEN),
                         ("handakuten", HANDAKUTEN)):
        for hira, romaji, row, vowel in table:
            out.append(KanaUnit(
                hiragana=hira, katakana=to_katakana(hira), romaji=romaji,
                row=row, vowel=vowel, group=group,
                teaching_stage=_stage(row, group),
                from_kana=VOICING_SOURCE.get(hira, ""),
                note=NOTES.get(hira, ""),
            ))
    if include_yoon:
        for base in YOON_BASES:
            for small in ("ゃ", "ゅ", "ょ"):
                pair = base + small
                out.append(KanaUnit(
                    hiragana=pair, katakana=to_katakana(pair),
                    romaji=_yoon_romaji(pair),
                    row=ROW_OF.get(base, ""), vowel={"ゃ": "a", "ゅ": "u", "ょ": "o"}[small],
                    group="yoon", teaching_stage=13,
                    note="One beat, written with two characters.",
                ))
    out.sort(key=lambda u: (u.teaching_stage, VOWEL_ROWS.index(u.vowel)
                            if u.vowel in VOWEL_ROWS else 9))
    return out


def chart(script: str = "hiragana", group: str = "basic") -> list[list[Optional[str]]]:
    """The five-column gojūon grid, as printed in every textbook."""
    table = {"basic": GOJUON, "dakuten": DAKUTEN, "handakuten": HANDAKUTEN}[group]
    rows: dict[str, dict[str, str]] = {}
    for hira, _, row, vowel in table:
        rows.setdefault(row, {})[vowel] = hira if script == "hiragana" else to_katakana(hira)
    order = [r for r in CONSONANT_ROWS if r in rows]
    return [[rows[r].get(v) for v in VOWEL_ROWS] for r in order]


def minimal_pairs_by_mora() -> list[dict]:
    """Word pairs that differ only in mora count.

    This is the drill that makes Japanese length audible. English speakers
    routinely miss these, and they are real words with unrelated meanings.
    """
    return [
        {"pair": ["おばさん", "おばあさん"], "meanings": ["aunt", "grandmother"],
         "differs": "vowel length", "mora": [4, 5]},
        {"pair": ["おじさん", "おじいさん"], "meanings": ["uncle", "grandfather"],
         "differs": "vowel length", "mora": [4, 5]},
        {"pair": ["きて", "きって"], "meanings": ["come / wear", "stamp"],
         "differs": "the small っ", "mora": [2, 3]},
        {"pair": ["おと", "おっと"], "meanings": ["sound", "husband"],
         "differs": "the small っ", "mora": [2, 3]},
        {"pair": ["ビル", "ビール"], "meanings": ["building", "beer"],
         "differs": "vowel length", "mora": [2, 3]},
        {"pair": ["ここ", "こうこう"], "meanings": ["here", "high school"],
         "differs": "vowel length", "mora": [2, 4]},
        {"pair": ["かこ", "かっこ"], "meanings": ["the past", "brackets"],
         "differs": "the small っ", "mora": [2, 3]},
        {"pair": ["しゅじん", "しゅうじん"], "meanings": ["husband", "prisoner"],
         "differs": "vowel length", "mora": [3, 4]},
    ]
