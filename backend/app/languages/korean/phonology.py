"""
Korean phonology engine: written form -> actual pronunciation, with reasons.

This is the engine behind the 받침 module. Given 한국어 it does not merely
answer 한구거 — it returns the ordered list of rules that fired, each with a
child-level explanation and the linguistic one, so the UI can show:

    한국어  ->  한구거
    Why?  The ㄱ underneath 국 had nowhere to sit, and 어 starts with a
          silent ㅇ, so ㄱ slid over and took its seat.  (연음, liaison)

Rules implemented follow 표준 발음법 (Standard Korean Pronunciation Rules).
Rules that are automatic — decided purely by the letters — are applied
unconditionally. Rules that need to know *what kind of word* this is
(a verb stem, a Sino-Korean compound, a compound-noun boundary) are gated
behind explicit hints, because guessing them silently would produce
confidently wrong Korean. Content entries can also carry a hand-checked
`pronunciation` field that overrides the engine entirely.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional

from .hangul import (
    COMPOUND_FINALS,
    Syllable,
    compose,
    decompose,
    is_hangul_syllable,
)

# --------------------------------------------------------------------------
# Rule catalogue — every entry carries both explanation registers
# --------------------------------------------------------------------------

RULES: dict[str, dict[str, str]] = {
    "liaison": {
        "ko": "연음",
        "en": "Linking",
        "simple": (
            "The little consonant sitting underneath had nowhere to go, and the "
            "next block starts with the silent ㅇ — an empty chair. So the "
            "consonant slides over and sits in it."
        ),
        "technical": (
            "A coda consonant is resyllabified as the onset of a following "
            "vowel-initial syllable. The underlying consonant surfaces intact, "
            "so neutralisation does not apply: 꽃이 → [꼬치], not [꼬디]."
        ),
    },
    "cluster_simplification": {
        "ko": "자음군 단순화",
        "en": "Cluster simplification",
        "simple": (
            "Two consonants were sitting underneath, but Korean only ever says "
            "one of them. The other one goes quiet."
        ),
        "technical": (
            "A complex coda reduces to a single segment when not resyllabified. "
            "Which member survives is lexically determined."
        ),
    },
    "neutralisation": {
        "ko": "음절의 끝소리 규칙",
        "en": "Final-consonant neutralisation",
        "simple": (
            "At the end of a block, Korean only ever makes seven sounds: "
            "ㄱ ㄴ ㄷ ㄹ ㅁ ㅂ ㅇ. Any other letter down there changes into "
            "the closest one and is not released."
        ),
        "technical": (
            "Coda consonants neutralise to one of seven unreleased archiphonemes. "
            "ㄲ/ㅋ → [ㄱ]; ㅅ/ㅆ/ㅈ/ㅊ/ㅌ/ㅎ → [ㄷ]; ㅍ → [ㅂ]."
        ),
    },
    "aspiration": {
        "ko": "격음화 (자음 축약)",
        "en": "Aspiration",
        "simple": (
            "ㅎ is a puff of air. When it bumps into ㄱ, ㄷ, ㅂ or ㅈ, the two "
            "melt together into the breathy version: ㅋ, ㅌ, ㅍ, ㅊ."
        ),
        "technical": (
            "ㅎ coalesces with an adjacent lax obstruent to yield the "
            "corresponding aspirate. Applies in both orders (ㅎ + C and C + ㅎ)."
        ),
    },
    "h_deletion": {
        "ko": "ㅎ 탈락",
        "en": "ㅎ deletion",
        "simple": "ㅎ is shy. In front of a vowel it disappears completely.",
        "technical": (
            "Intervocalic /h/ deletes; in ㄶ and ㅀ the /h/ deletes and the "
            "remaining sonorant resyllabifies. 좋아 → [조아], 많아 → [마나]."
        ),
    },
    "nasalisation": {
        "ko": "비음화",
        "en": "Nasalisation",
        "simple": (
            "The next block starts with a nose sound (ㄴ or ㅁ). It is hard to "
            "stop the air and then send it through your nose, so the consonant "
            "underneath turns into a nose sound too."
        ),
        "technical": (
            "Obstruent codas assimilate in nasality before a nasal onset: "
            "ㄱ → [ㅇ], ㄷ → [ㄴ], ㅂ → [ㅁ]."
        ),
    },
    "lateral_nasalisation": {
        "ko": "ㄹ의 비음화",
        "en": "ㄹ → ㄴ after a nasal or stop",
        "simple": "After ㅁ, ㅇ, ㄱ or ㅂ, a following ㄹ turns into ㄴ.",
        "technical": (
            "/l/ becomes [n] following a non-lateral consonant. Where the "
            "preceding coda is an obstruent this feeds nasalisation: "
            "국립 → 국닙 → [궁닙]."
        ),
    },
    "lateralisation": {
        "ko": "유음화",
        "en": "Lateralisation",
        "simple": "ㄴ and ㄹ next to each other are hard to say, so both become ㄹ.",
        "technical": (
            "/n/ and /l/ in contact assimilate to [ll] in either order: "
            "신라 → [실라], 설날 → [설랄]."
        ),
    },
    "tensification": {
        "ko": "경음화 (된소리되기)",
        "en": "Tensification",
        "simple": (
            "Right after ㄱ, ㄷ or ㅂ, your throat is already tight — so the "
            "next consonant comes out as the strong version: ㄲ ㄸ ㅃ ㅆ ㅉ."
        ),
        "technical": (
            "A lax obstruent onset becomes tense following an obstruent coda. "
            "This is fully automatic; the post-sonorant cases are not."
        ),
    },
    "tensification_morphological": {
        "ko": "경음화 (어간 뒤)",
        "en": "Tensification after a verb stem",
        "simple": (
            "After a verb or adjective stem ending in ㄴ or ㅁ, the ending's "
            "consonant is said strongly."
        ),
        "technical": (
            "Post-sonorant tensification applies to endings attached to a "
            "verbal stem in ㄴ/ㅁ (신다 → [신따]) but not across a noun "
            "boundary, so it requires morphological information."
        ),
    },
    "tensification_sino": {
        "ko": "한자어 ㄹ 뒤 경음화",
        "en": "Tensification after ㄹ in Sino-Korean",
        "simple": "In words that came from Chinese characters, ㄷ, ㅅ and ㅈ go strong after ㄹ.",
        "technical": (
            "In Sino-Korean compounds, /l/-final morphemes trigger tensification "
            "of a following ㄷ/ㅅ/ㅈ: 발달 → [발딸]. Native words do not."
        ),
    },
    "palatalisation": {
        "ko": "구개음화",
        "en": "Palatalisation",
        "simple": (
            "ㄷ and ㅌ made with the tongue tip get pulled toward the roof of "
            "the mouth by the 이 sound, and come out as ㅈ and ㅊ."
        ),
        "technical": (
            "Coronal stops palatalise before a suffixal /i/ or /hi/: "
            "굳이 → [구지], 같이 → [가치], 닫히다 → [다치다]."
        ),
    },
    "n_insertion": {
        "ko": "ㄴ 첨가",
        "en": "ㄴ insertion",
        "simple": (
            "When two words are glued together and the second starts with "
            "이/야/여/요/유, a ㄴ pops up between them."
        ),
        "technical": (
            "At a compound boundary before /i/ or a /j/-glide, [n] is inserted. "
            "Requires knowing the boundary, so it is hint-driven."
        ),
    },
    "ui_reduction": {
        "ko": "ㅢ의 발음",
        "en": "ㅢ simplification",
        "simple": "After a consonant, ㅢ is simply said as ㅣ.",
        "technical": (
            "/ɰi/ reduces to [i] when preceded by an onset consonant "
            "(희망 → [히망]); as a genitive particle 의 is commonly [에]."
        ),
    },
}

# --------------------------------------------------------------------------
# Segment tables
# --------------------------------------------------------------------------

#: 음절의 끝소리 규칙 — every written final maps to one of seven sounds.
NEUTRALISE: dict[str, str] = {
    "ㄱ": "ㄱ", "ㄲ": "ㄱ", "ㅋ": "ㄱ",
    "ㄴ": "ㄴ",
    "ㄷ": "ㄷ", "ㅅ": "ㄷ", "ㅆ": "ㄷ", "ㅈ": "ㄷ", "ㅊ": "ㄷ", "ㅌ": "ㄷ", "ㅎ": "ㄷ",
    "ㄹ": "ㄹ",
    "ㅁ": "ㅁ",
    "ㅂ": "ㅂ", "ㅍ": "ㅂ",
    "ㅇ": "ㅇ",
}

#: Which half of a complex coda survives when it is not resyllabified.
CLUSTER_SURVIVOR: dict[str, str] = {
    "ㄳ": "ㄱ", "ㄵ": "ㄴ", "ㄶ": "ㄴ", "ㄺ": "ㄱ", "ㄻ": "ㅁ",
    "ㄼ": "ㄹ", "ㄽ": "ㄹ", "ㄾ": "ㄹ", "ㄿ": "ㅂ", "ㅀ": "ㄹ", "ㅄ": "ㅂ",
}

#: Complex codas whose *reduced* form still tenses a following ㄱㄷㅅㅈ, per
#: 표준 발음법 §24–25. The surviving segment is a sonorant, so the plain
#: obstruent rule would miss these: 앉다 → [안따], 젊다 → [점따],
#: 넓다 → [널따], 핥다 → [할따], 읽고 → [일꼬].
#: These clusters occur almost exclusively in verb/adjective stems, so the
#: rule is automatic in practice and needs no morphological hint.
CLUSTER_TENSING = frozenset({"ㄼ", "ㄽ", "ㄾ", "ㅀ", "ㄺ", "ㄵ", "ㄻ"})

#: Syllables where ㄼ exceptionally keeps ㅂ instead of ㄹ.
BALP_EXCEPTIONS = frozenset({"밟"})

#: 표준 발음법 §11 붙임 restricts "ㄺ → [ㄹ] before ㄱ" to *verb and adjective
#: stems*: 읽고 → [일꼬] but 닭고기 → [닥꼬기]. The class of ㄺ-final stems is
#: closed, so listing it is exact rather than a heuristic.
RIEUL_GIYEOK_STEMS = frozenset({
    "읽", "맑", "밝", "붉", "늙", "묽", "얽", "굵", "긁", "갉", "낡", "옭", "곪",
})

TENSE_OF: dict[str, str] = {"ㄱ": "ㄲ", "ㄷ": "ㄸ", "ㅂ": "ㅃ", "ㅅ": "ㅆ", "ㅈ": "ㅉ"}
ASPIRATE_OF: dict[str, str] = {"ㄱ": "ㅋ", "ㄷ": "ㅌ", "ㅂ": "ㅍ", "ㅈ": "ㅊ"}

OBSTRUENT_CODAS = frozenset({"ㄱ", "ㄷ", "ㅂ"})
NASAL_ONSETS = frozenset({"ㄴ", "ㅁ"})
H_CODAS = frozenset({"ㅎ", "ㄶ", "ㅀ"})

#: Codas that behave as an obstruent for the purposes of C + ㅎ aspiration,
#: mapped to the sound that actually fuses with the ㅎ.
CODA_FOR_ASPIRATION: dict[str, tuple[str, str]] = {
    # coda -> (what stays behind, what fuses with ㅎ)
    "ㄱ": ("", "ㄱ"), "ㄲ": ("", "ㄱ"), "ㅋ": ("", "ㄱ"), "ㄺ": ("ㄹ", "ㄱ"), "ㄳ": ("", "ㄱ"),
    "ㄷ": ("", "ㄷ"), "ㅅ": ("", "ㄷ"), "ㅆ": ("", "ㄷ"), "ㅌ": ("", "ㄷ"),
    "ㅂ": ("", "ㅂ"), "ㅍ": ("", "ㅂ"), "ㄼ": ("ㄹ", "ㅂ"), "ㄿ": ("ㄹ", "ㅂ"), "ㅄ": ("", "ㅂ"),
    "ㅈ": ("", "ㅈ"), "ㅊ": ("", "ㅈ"), "ㄵ": ("ㄴ", "ㅈ"),
}

VOWEL_ONSET = "ㅇ"


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------

@dataclass
class SoundChange:
    """One rule firing, with everything the UI needs to explain it."""

    rule: str
    rule_ko: str
    rule_en: str
    index: int          # syllable position where the change is anchored
    before: str         # the two-syllable window before the rule fired
    after: str          # the same window after
    simple: str
    technical: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Pronunciation:
    written: str
    spoken: str
    changes: list[SoundChange] = field(default_factory=list)
    overridden: bool = False

    @property
    def changed(self) -> bool:
        return self.written != self.spoken

    def to_dict(self) -> dict:
        return {
            "written": self.written,
            "spoken": self.spoken,
            "changed": self.changed,
            "overridden": self.overridden,
            "changes": [c.to_dict() for c in self.changes],
        }


@dataclass
class Hints:
    """Information the letters alone cannot supply.

    verb_stem_ends_at  indices after which a verbal ending begins; enables
                       post-sonorant tensification (신다 → [신따]).
    sino_korean        the word is a Sino-Korean compound; enables ㄹ-tensification.
    compound_after     indices after which a new lexical word begins. Makes
                       the coda neutralise before it links, which is what
                       separates 첫인상 → [처딘상] from 꽃이 → [꼬치].
    n_insertion_after  indices where ㄴ is epenthesised (솜+이불 → [솜니불]).
                       Kept separate from `compound_after` because it is
                       lexically conditioned: 색연필 → [생년필] takes it,
                       첫인상 → [처딘상] does not, though both are compounds.
    genitive_ui        indices of 의 used as the genitive particle → [에].
    casual             model relaxed everyday speech rather than the
                       prescriptive standard: weakens ㅎ after a sonorant,
                       so 전화 → [저놔] and 결혼 → [겨론]. Off by default —
                       [전화] is what the standard prescribes, but [저놔]
                       is what learners actually hear.
    """

    verb_stem_ends_at: frozenset[int] = frozenset()
    sino_korean: bool = False
    compound_after: frozenset[int] = frozenset()
    n_insertion_after: frozenset[int] = frozenset()
    genitive_ui: frozenset[int] = frozenset()
    casual: bool = False

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "Hints":
        d = d or {}
        return cls(
            verb_stem_ends_at=frozenset(d.get("verb_stem_ends_at", ()) or ()),
            sino_korean=bool(d.get("sino_korean", False)),
            compound_after=frozenset(d.get("compound_after", ()) or ()),
            n_insertion_after=frozenset(d.get("n_insertion_after", ()) or ()),
            genitive_ui=frozenset(d.get("genitive_ui", ()) or ()),
            casual=bool(d.get("casual", False)),
        )


# --------------------------------------------------------------------------
# Internal working representation
# --------------------------------------------------------------------------

class _Cell:
    """A mutable syllable slot, or a literal passthrough character."""

    __slots__ = ("initial", "medial", "final", "literal", "cluster_origin", "boundary")

    def __init__(self, syl: Optional[Syllable], literal: str = ""):
        if syl is not None:
            self.initial, self.medial, self.final = syl.initial, syl.medial, syl.final
            self.literal = ""
        else:
            self.initial = self.medial = self.final = ""
            self.literal = literal
        self.cluster_origin: str = ""   # remembers a reduced complex coda
        self.boundary = False           # True if a word/space boundary follows

    @property
    def is_syllable(self) -> bool:
        return self.literal == ""

    def render(self) -> str:
        if not self.is_syllable:
            return self.literal
        return compose(self.initial, self.medial, self.final)


def _render(cells: list[_Cell]) -> str:
    return "".join(c.render() for c in cells)


def _window(cells: list[_Cell], i: int) -> str:
    lo, hi = max(0, i), min(len(cells), i + 2)
    return "".join(c.render() for c in cells[lo:hi])


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def pronounce(
    text: str,
    hints: Optional[Hints | dict] = None,
    override: Optional[str] = None,
) -> Pronunciation:
    """Return the spoken form of `text` plus an ordered trace of the rules.

    >>> pronounce("한국어").spoken
    '한구거'
    >>> pronounce("좋아요").spoken
    '조아요'
    >>> pronounce("학교").spoken
    '학꾜'
    """
    if override:
        return Pronunciation(written=text, spoken=override, changes=[], overridden=True)

    h = hints if isinstance(hints, Hints) else Hints.from_dict(hints)

    cells: list[_Cell] = []
    for ch in text:
        syl = decompose(ch)
        cells.append(_Cell(syl) if syl else _Cell(None, ch))

    changes: list[SoundChange] = []

    def note(rule: str, i: int, before: str, cells_now: list[_Cell]) -> None:
        after = _window(cells_now, i)
        if before == after:
            return
        meta = RULES[rule]
        changes.append(
            SoundChange(
                rule=rule,
                rule_ko=meta["ko"],
                rule_en=meta["en"],
                index=i,
                before=before,
                after=after,
                simple=meta["simple"],
                technical=meta["technical"],
            )
        )

    n = len(cells)

    # ---- Pass 0: ㅢ reduction (block-internal, order-independent) --------
    for i, c in enumerate(cells):
        if not c.is_syllable or c.medial != "ㅢ":
            continue
        before = _window(cells, i)
        if i in h.genitive_ui and c.initial == VOWEL_ONSET:
            c.medial = "ㅔ"
            note("ui_reduction", i, before, cells)
        elif c.initial != VOWEL_ONSET:
            c.medial = "ㅣ"
            note("ui_reduction", i, before, cells)

    # ---- Pass 1: ㄴ insertion at declared boundaries --------------------
    if h.n_insertion_after:
        for i in sorted(h.n_insertion_after, reverse=True):
            if i + 1 >= n or not cells[i].is_syllable or not cells[i + 1].is_syllable:
                continue
            nxt = cells[i + 1]
            if nxt.initial != VOWEL_ONSET:
                continue
            if nxt.medial not in ("ㅣ", "ㅑ", "ㅕ", "ㅛ", "ㅠ", "ㅒ", "ㅖ"):
                continue
            if not cells[i].final:
                continue
            before = _window(cells, i)
            nxt.initial = "ㄴ"
            note("n_insertion", i, before, cells)
        n = len(cells)

    # ---- Pass 2: boundary rules, left to right --------------------------
    for i in range(n - 1):
        cur, nxt = cells[i], cells[i + 1]
        if not cur.is_syllable or not nxt.is_syllable:
            continue
        if not cur.final:
            continue

        # -- 2a. ㅎ + obstruent  ->  aspirate ---------------------------
        if cur.final in H_CODAS and nxt.initial in ("ㄱ", "ㄷ", "ㅈ", "ㅅ"):
            before = _window(cells, i)
            cur.final = {"ㅎ": "", "ㄶ": "ㄴ", "ㅀ": "ㄹ"}[cur.final]
            nxt.initial = "ㅆ" if nxt.initial == "ㅅ" else ASPIRATE_OF[nxt.initial]
            note("aspiration", i, before, cells)
            continue

        # -- 2b. 구개음화 --------------------------------------------------
        # Checked before the generic C + ㅎ rule, because 닫히다 goes to
        # [다치다] and not [다티다]: the fused ㅌ immediately palatalises
        # before 이, and Korean speakers hear this as one change.
        if cur.final in ("ㄷ", "ㅌ", "ㄾ") and nxt.medial == "ㅣ":
            if nxt.initial == VOWEL_ONSET:
                before = _window(cells, i)
                nxt.initial = "ㅈ" if cur.final == "ㄷ" else "ㅊ"
                cur.final = "ㄹ" if cur.final == "ㄾ" else ""
                note("palatalisation", i, before, cells)
                continue
            if nxt.initial == "ㅎ" and cur.final in ("ㄷ", "ㅌ"):
                before = _window(cells, i)
                nxt.initial = "ㅊ"
                cur.final = ""
                note("palatalisation", i, before, cells)
                continue

        # -- 2c. obstruent + ㅎ  ->  aspirate ---------------------------
        if nxt.initial == "ㅎ" and cur.final in CODA_FOR_ASPIRATION:
            keep, fuse = CODA_FOR_ASPIRATION[cur.final]
            before = _window(cells, i)
            cur.final = keep
            nxt.initial = ASPIRATE_OF[fuse]
            note("aspiration", i, before, cells)
            continue

        # -- 2c-bis. casual ㅎ weakening after a sonorant -----------------
        # 전화 → [저놔], 결혼 → [겨론]. Prescriptively the ㅎ is kept, but
        # this is what learners actually hear, so it is opt-in.
        if h.casual and nxt.initial == "ㅎ" and cur.final in ("ㄴ", "ㄹ", "ㅁ", "ㅇ"):
            before = _window(cells, i)
            nxt.initial = cur.final if cur.final != "ㅇ" else VOWEL_ONSET
            if cur.final != "ㅇ":
                cur.final = ""
            note("h_deletion", i, before, cells)
            continue

        # -- 2d. ㅎ deletion before a vowel -------------------------------
        if cur.final in H_CODAS and nxt.initial == VOWEL_ONSET:
            before = _window(cells, i)
            remainder = {"ㅎ": "", "ㄶ": "ㄴ", "ㅀ": "ㄹ"}[cur.final]
            cur.final = remainder
            note("h_deletion", i, before, cells)
            if remainder:
                before = _window(cells, i)
                nxt.initial = remainder
                cur.final = ""
                note("liaison", i, before, cells)
            continue

        # -- 2e. 연음 -------------------------------------------------------
        if nxt.initial == VOWEL_ONSET and cur.final != "ㅇ":
            before = _window(cells, i)
            # Across a *lexical* boundary the coda neutralises first and the
            # neutralised sound is what links: 첫인상 → [처딘상], 맛없다 →
            # [마덥따] — unlike 첫이- inside one word, which would give [처시-].
            # Within a word (a particle or ending) the underlying consonant
            # survives intact: 꽃이 → [꼬치].
            if i in h.compound_after and cur.final not in COMPOUND_FINALS:
                neutral = NEUTRALISE.get(cur.final, cur.final)
                if neutral != cur.final:
                    cur.final = neutral
                    note("neutralisation", i, before, cells)
                    before = _window(cells, i)
            if cur.final in COMPOUND_FINALS:
                first, second = COMPOUND_FINALS[cur.final]
                cur.final = first
                # ㄳ/ㅄ/ㄽ surface with a tense ㅅ: 값이 → [갑씨], 몫을 → [목쓸]
                nxt.initial = "ㅆ" if second == "ㅅ" else second
            else:
                nxt.initial = cur.final
                cur.final = ""
            note("liaison", i, before, cells)
            continue

    # ---- Pass 3: cluster simplification + neutralisation ---------------
    for i, c in enumerate(cells):
        if not c.is_syllable or not c.final:
            continue
        if c.final in CLUSTER_SURVIVOR:
            before = _window(cells, i)
            survivor = CLUSTER_SURVIVOR[c.final]
            origin = c.final
            # 읽고 → [일꼬]: a ㄺ-final *verb stem* keeps ㄹ before ㄱ.
            # A noun does not: 닭고기 → [닥꼬기].
            if origin == "ㄺ" and i + 1 < len(cells) and cells[i + 1].is_syllable \
                    and cells[i + 1].initial == "ㄱ" \
                    and (c.render() in RIEUL_GIYEOK_STEMS or i in h.verb_stem_ends_at):
                survivor = "ㄹ"
            # 밟다 → [밥따] is the standard exception to ㄼ → ㄹ.
            elif origin == "ㄼ" and c.render() in BALP_EXCEPTIONS:
                survivor = "ㅂ"
            c.final = survivor
            c.cluster_origin = origin
            note("cluster_simplification", i, before, cells)

        neutral = NEUTRALISE.get(c.final, c.final)
        if neutral != c.final:
            before = _window(cells, i)
            c.final = neutral
            note("neutralisation", i, before, cells)

    # ---- Pass 4: tensification ------------------------------------------
    for i in range(len(cells) - 1):
        cur, nxt = cells[i], cells[i + 1]
        if not cur.is_syllable or not nxt.is_syllable or not cur.final:
            continue
        if nxt.initial not in TENSE_OF:
            continue

        if cur.final in OBSTRUENT_CODAS:
            before = _window(cells, i)
            nxt.initial = TENSE_OF[nxt.initial]
            note("tensification", i, before, cells)
            continue

        # 넓다 → [널따], 앉다 → [안따]: a reduced cluster still tenses even
        # though the segment left behind is a sonorant.
        if cur.cluster_origin in CLUSTER_TENSING:
            before = _window(cells, i)
            nxt.initial = TENSE_OF[nxt.initial]
            note("tensification", i, before, cells)
            continue

        # Hint-gated: after a verbal stem in ㄴ/ㅁ (신다 → [신따]).
        if cur.final in ("ㄴ", "ㅁ") and i in h.verb_stem_ends_at \
                and nxt.initial in ("ㄱ", "ㄷ", "ㅅ", "ㅈ"):
            before = _window(cells, i)
            nxt.initial = TENSE_OF[nxt.initial]
            note("tensification_morphological", i, before, cells)
            continue

        # Hint-gated: Sino-Korean ㄹ + ㄷ/ㅅ/ㅈ (발달 → [발딸]).
        if cur.final == "ㄹ" and h.sino_korean and nxt.initial in ("ㄷ", "ㅅ", "ㅈ"):
            before = _window(cells, i)
            nxt.initial = TENSE_OF[nxt.initial]
            note("tensification_sino", i, before, cells)
            continue

    # ---- Pass 5: nasalisation and lateralisation -------------------------
    for i in range(len(cells) - 1):
        cur, nxt = cells[i], cells[i + 1]
        if not cur.is_syllable or not nxt.is_syllable or not cur.final:
            continue

        # ㄹ becomes ㄴ after anything that is not ㄹ (feeds nasalisation).
        if nxt.initial == "ㄹ" and cur.final in ("ㅁ", "ㅇ", "ㄱ", "ㅂ"):
            before = _window(cells, i)
            nxt.initial = "ㄴ"
            note("lateral_nasalisation", i, before, cells)

        # 유음화 in both directions.
        if cur.final == "ㄴ" and nxt.initial == "ㄹ":
            before = _window(cells, i)
            cur.final = "ㄹ"
            note("lateralisation", i, before, cells)
            continue
        if cur.final == "ㄹ" and nxt.initial == "ㄴ":
            before = _window(cells, i)
            nxt.initial = "ㄹ"
            note("lateralisation", i, before, cells)
            continue

        # 비음화 proper.
        if nxt.initial in NASAL_ONSETS and cur.final in OBSTRUENT_CODAS:
            before = _window(cells, i)
            cur.final = {"ㄱ": "ㅇ", "ㄷ": "ㄴ", "ㅂ": "ㅁ"}[cur.final]
            note("nasalisation", i, before, cells)

    return Pronunciation(written=text, spoken=_render(cells), changes=changes)


def pronounce_phrase(
    text: str,
    hints: Optional[Hints | dict] = None,
    override: Optional[str] = None,
) -> Pronunciation:
    """Pronounce a phrase, treating each space-separated word independently.

    Korean sound changes apply within a 말토막 (phonological word). Applying
    them straight across a space produces wrong results for careful speech,
    so words are processed separately and rejoined.
    """
    if override:
        return Pronunciation(written=text, spoken=override, overridden=True)

    words = text.split(" ")
    spoken_parts: list[str] = []
    all_changes: list[SoundChange] = []
    offset = 0
    for w in words:
        if not w:
            spoken_parts.append(w)
            offset += 1
            continue
        res = pronounce(w, hints)
        spoken_parts.append(res.spoken)
        for c in res.changes:
            c.index += offset
            all_changes.append(c)
        offset += len(w) + 1
    return Pronunciation(written=text, spoken=" ".join(spoken_parts), changes=all_changes)


def explain(text: str, hints: Optional[Hints | dict] = None) -> dict:
    """A teaching-ready explanation payload: 한국어 → 한구거 and why."""
    res = pronounce_phrase(text, hints)
    steps = []
    for c in res.changes:
        steps.append(
            {
                "rule_id": c.rule,
                "rule": f"{c.rule_ko} ({c.rule_en})",
                "shows": f"{c.before} → {c.after}",
                "child_explanation": c.simple,
                "linguistic_explanation": c.technical,
            }
        )
    return {
        "written": res.written,
        "spoken": res.spoken,
        "changed": res.changed,
        "summary": f"{res.written} → {res.spoken}" if res.changed
        else f"{res.written} is pronounced exactly as it is written.",
        "steps": steps,
    }


def batchim_sound(final: str) -> str:
    """Which of the seven final sounds a written batchim actually makes."""
    if final in CLUSTER_SURVIVOR:
        final = CLUSTER_SURVIVOR[final]
    return NEUTRALISE.get(final, final)


def minimal_pairs(a: str, b: str) -> bool:
    """True when two words differ in exactly one jamo — used to build
    listening-discrimination drills for ㄱ/ㅋ/ㄲ and friends."""
    from .hangul import to_jamo

    ja, jb = to_jamo(a), to_jamo(b)
    if len(ja) != len(jb):
        return False
    return sum(1 for x, y in zip(ja, jb) if x != y) == 1
