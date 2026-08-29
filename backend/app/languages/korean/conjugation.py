"""
Korean verb and adjective conjugation engine.

Everything is built from three "bases", because every Korean ending attaches
to exactly one of them:

    vowel base   for endings in 아/어    먹 -> 먹어,  가 -> 가,  쓰 -> 써
    으 base      for endings in -(으)-   먹 -> 먹으,  가 -> 가,  듣 -> 들으
    plain base   for endings attached    먹 -> 먹,    살 -> 사 (before ㄴㅂㅅ)
                 directly

Get those three right and the ~40 forms below fall out mechanically. Getting
them right is the whole job, because that is where every irregular lives.

Irregularity in Korean is *lexical*, not predictable from spelling: 걷다 "walk"
is ㄷ-irregular but 걷다 "roll up" is regular, and both are spelled the same.
So the engine consults an explicit lexicon first, falls back to per-class
defaults that are right far more often than not, and always lets a caller (or
a content file) declare the class outright. It never silently guesses on the
genuinely ambiguous entries — `classify()` reports its confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Literal, Optional

from .hangul import (
    Syllable,
    compose,
    decompose,
    ends_with_batchim,
    final_of,
)

PartOfSpeech = Literal["verb", "adjective", "copula", "unknown"]
Irregular = Literal["", "ㄷ", "ㅂ", "ㅅ", "ㅎ", "르", "러", "으", "ㄹ", "우", "여", "거라", "너라"]


# ==========================================================================
# Irregularity lexicon
# ==========================================================================

#: ㄷ -> ㄹ before a vowel.  듣다 -> 들어요
IRREGULAR_D = frozenset({
    "듣다", "걷다", "묻다", "싣다", "깨닫다", "붇다", "일컫다", "눋다", "겯다",
    "긷다", "내닫다", "치닫다", "알아듣다", "못알아듣다", "여쭙다",
})
REGULAR_D = frozenset({
    "받다", "닫다", "믿다", "얻다", "쏟다", "뜯다", "묻다", "돋다", "굳다",
    "곧다", "뻗다", "얻다", "걷다",
})
#: Spelled identically, different classes. Content must disambiguate.
AMBIGUOUS_D = {
    "걷다": ("walk = ㄷ-irregular (걸어요); roll up / collect = regular (걷어요)"),
    "묻다": ("ask = ㄷ-irregular (물어요); bury / get stained = regular (묻어요)"),
}

#: ㅂ -> 우 before a vowel.  춥다 -> 추워요
IRREGULAR_B = frozenset({
    "춥다", "덥다", "쉽다", "어렵다", "무겁다", "가볍다", "아름답다", "귀엽다",
    "맵다", "싱겁다", "차갑다", "뜨겁다", "즐겁다", "고맙다",
    "반갑다", "무섭다", "부럽다", "그립다", "외롭다", "괴롭다", "더럽다",
    "시끄럽다", "부드럽다", "새롭다", "아깝다", "가깝다", "두껍다", "얇다",
    "눕다", "줍다", "굽다", "돕다", "곱다", "깁다", "밉다", "사납다", "서럽다", "정답다", "이롭다", "해롭다", "간지럽다", "너그럽다",
})
REGULAR_B = frozenset({
    "입다", "잡다", "좁다", "씹다", "뽑다", "접다", "업다", "집다", "굽다",
    "씹다", "밟다", })
AMBIGUOUS_B = {
    "굽다": "bend = ㅂ-irregular (구워요 for grill); 굽다 'be bent' is regular",
}
#: 돕다 and 곱다 give 도와요 / 고와요 rather than 도워요 / 고워요.
B_IRREGULAR_O = frozenset({"돕다", "곱다"})

#: ㅅ drops before a vowel, but the 으 stays.  짓다 -> 지어요, 지으면
IRREGULAR_S = frozenset({
    "짓다", "낫다", "붓다", "잇다", "긋다", "젓다", "잣다", "쓴X",
})
REGULAR_S = frozenset({
    "웃다", "씻다", "벗다", "빗다", "솟다", "빼앗다", "빗다", })

#: ㅎ drops; the 아/어 ending fuses to 애/얘.  빨갛다 -> 빨개요
IRREGULAR_H = frozenset({
    "빨갛다", "파랗다", "노랗다", "하얗다", "까맣다", "그렇다", "이렇다",
    "저렇다", "어떻다", "동그랗다", "커다랗다", "누렇다", "허옇다", "뽀얗다",
    "발갛다", "말갛다", "새까맣다", "새하얗다", "시퍼렇다",
})
REGULAR_H = frozenset({"좋다", "넣다", "놓다", "낳다", "쌓다", "찧다", "빻다", "닿다"})

#: 르 -> ㄹㄹ before a vowel.  모르다 -> 몰라요
IRREGULAR_REU = frozenset({
    "모르다", "부르다", "다르다", "빠르다", "고르다", "기르다", "누르다",
    "흐르다", "이르다", "자르다", "오르다", "지르다", "서두르다", "가르다",
    "마르다", "게으르다", "바르다", "무르다", "두르다", "타이르다", "저지르다",
})
#: 러-irregular: the ending itself gains a ㄹ.  이르다 -> 이르러요
IRREGULAR_REO = frozenset({"이르다", "푸르다", "누르다", "노르다"})
#: 르-final but plain 으-regular.  따르다 -> 따라요
REGULAR_REU = frozenset({"따르다", "들르다", "치르다", "다다르다", "우러르다"})
AMBIGUOUS_REU = {
    "이르다": "arrive = 러-irregular (이르러요); say/be early = 르-irregular (일러요)",
    "누르다": "press = 르-irregular (눌러요); be yellow = 러-irregular (누르러요)",
}

#: 우-irregular — exactly one verb.  푸다 -> 퍼요
IRREGULAR_U = frozenset({"푸다"})
#: 여-irregular — 하다 and everything built on it.
IRREGULAR_YEO_SUFFIX = "하다"

#: Suppletive honorific stems. These are separate words, not conjugations.
HONORIFIC_SUPPLETION: dict[str, tuple[str, str]] = {
    "먹다": ("드시다", "잡수시다"),
    "마시다": ("드시다", "드시다"),
    "자다": ("주무시다", "주무시다"),
    "있다": ("계시다", "계시다"),
    "없다": ("안 계시다", "안 계시다"),
    "말하다": ("말씀하시다", "말씀하시다"),
    "죽다": ("돌아가시다", "돌아가시다"),
    "주다": ("주시다", "주시다"),
    "데리고 가다": ("모시고 가다", "모시고 가다"),
    "배고프다": ("시장하시다", "시장하시다"),
}

#: Verbs where 안-negation is ungrammatical or unnatural; use the listed word.
NEGATION_SUPPLETION: dict[str, str] = {
    "알다": "모르다",
    "있다": "없다",
    "맛있다": "맛없다",
    "재미있다": "재미없다",
}

#: Common adjectives, so the engine can pick -는 vs -(으)ㄴ correctly when the
#: caller does not say which part of speech a word is.
KNOWN_ADJECTIVES = frozenset({
    "좋다", "나쁘다", "크다", "작다", "많다", "적다", "높다", "낮다", "길다",
    "짧다", "빠르다", "느리다", "덥다", "춥다", "따뜻하다", "시원하다", "쉽다",
    "어렵다", "무겁다", "가볍다", "예쁘다", "귀엽다", "멋있다",     "맛없다", "재미있다", "재미없다", "바쁘다", "아프다", "슬프다", "기쁘다",
    "행복하다", "피곤하다", "배고프다", "배부르다", "비싸다", "싸다", "새롭다",
    "젊다", "늙다", "밝다", "어둡다", "조용하다", "시끄럽다", "깨끗하다",
    "더럽다", "친절하다", "똑똑하다", "이상하다", "중요하다", "필요하다",
    "같다", "다르다", "빨갛다", "파랗다", "노랗다", "하얗다", "까맣다",
    "맵다", "짜다", "달다", "쓰다", "시다", "싱겁다", "뜨겁다", "차갑다",
    "무섭다", "부끄럽다", "심심하다", "복잡하다", "간단하다", "위험하다",
    "안전하다", "건강하다", "유명하다", "고맙다", "감사하다",
    "미안하다", "죄송하다", "반갑다", "즐겁다", "심각하다", "넓다", "좁다",
    "멀다", "가깝다", "어둡다", "두껍다", "얇다", "굵다", "가늘다", "얕다",
    "깊다", "두렵다", "흐리다", "맑다", "부드럽다", "신선하다", "귀찮다",
    "답답하다", "억울하다", "서운하다", "창피하다", "다양하다", "특별하다",
    "평범하다", "정확하다", "확실하다", "분명하다", "가능하다", "불가능하다",
    "편하다", "불편하다", "싫다", "괜찮다", "착하다", "부지런하다", "게으르다",
    "외롭다", "괴롭다", "그립다", "부럽다", "아깝다", "지루하다", "신나다",
    "화나다", "놀랍다", "훌륭하다", "대단하다", "충분하다", "부족하다",
    "많다", "이르다", "늦다", "가난하다", "부자다", "튼튼하다", "약하다",
    "강하다", "단단하다", "무겁다", "시원하다", "따뜻하다", "덥다", "선선하다",
})

#: Words the classifier will guess "verb" for even though they may not be one.
#: Vocabulary entries declare `pos` explicitly, so this only matters for
#: free-text lookups — but the guess is reported rather than hidden.
ADJECTIVE_SUFFIXES = ("스럽다", "롭다", "답다", "쁘다", "차다")


# ==========================================================================
# Classification
# ==========================================================================

@dataclass
class Classification:
    dictionary_form: str
    stem: str
    pos: PartOfSpeech
    irregular: Irregular
    confident: bool
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def stem_of(dictionary_form: str) -> str:
    """먹다 -> 먹.  Raises if the word does not end in 다."""
    df = dictionary_form.strip()
    if not df.endswith("다"):
        raise ValueError(f"{df!r} is not a dictionary form — Korean verbs end in 다")
    return df[:-1]


def classify(
    dictionary_form: str,
    pos: Optional[PartOfSpeech] = None,
    irregular: Optional[Irregular] = None,
) -> Classification:
    """Work out part of speech and irregular class, declaring uncertainty."""
    df = dictionary_form.strip()
    stem = stem_of(df)
    note = ""
    confident = True

    # -- part of speech -------------------------------------------------
    if pos is None:
        if df in KNOWN_ADJECTIVES:
            pos = "adjective"
        elif df.endswith(ADJECTIVE_SUFFIXES):
            pos = "adjective"
        elif df in ("이다", "아니다"):
            pos = "copula"
        else:
            pos = "verb"

    # -- irregular class ------------------------------------------------
    if irregular is not None:
        return Classification(df, stem, pos, irregular, True, "declared by content")

    last = decompose(stem[-1]) if stem else None
    irr: Irregular = ""

    if df.endswith(IRREGULAR_YEO_SUFFIX):
        irr = "여"
    elif df in IRREGULAR_U:
        irr = "우"
    elif stem.endswith("르"):
        if df in REGULAR_REU:
            irr = "으"
        elif df in IRREGULAR_REO:
            irr = "러"
            if df in AMBIGUOUS_REU:
                confident = False
                note = AMBIGUOUS_REU[df]
        elif df in IRREGULAR_REU:
            irr = "르"
            if df in AMBIGUOUS_REU:
                confident = False
                note = AMBIGUOUS_REU[df]
        else:
            irr = "르"          # 르-irregular is by far the larger class
            confident = False
            note = "assumed 르-irregular; 따르다/들르다/치르다 are the 으-regular exceptions"
    elif last is not None and last.final == "ㄹ":
        irr = "ㄹ"              # ㄹ-deletion is exceptionless
    elif last is not None and last.medial == "ㅡ" and not last.final:
        irr = "으"              # 쓰다, 크다, 바쁘다 — also exceptionless
    elif last is not None and last.final == "ㄷ":
        if df in AMBIGUOUS_D:
            irr = "ㄷ"
            confident = False
            note = AMBIGUOUS_D[df]
        elif df in IRREGULAR_D:
            irr = "ㄷ"
        elif df in REGULAR_D:
            irr = ""
        else:
            irr = ""
            confident = False
            note = "ㄷ-final verbs split roughly evenly; assumed regular"
    elif last is not None and last.final == "ㅂ":
        if df in AMBIGUOUS_B:
            irr = "ㅂ"
            confident = False
            note = AMBIGUOUS_B[df]
        elif df in IRREGULAR_B:
            irr = "ㅂ"
        elif df in REGULAR_B:
            irr = ""
        elif pos == "adjective":
            irr = "ㅂ"          # nearly every ㅂ-final adjective is irregular
            note = "assumed ㅂ-irregular (typical for adjectives)"
        else:
            irr = ""
            confident = False
            note = "ㅂ-final verbs are usually regular; assumed regular"
    elif last is not None and last.final == "ㅅ":
        if df in IRREGULAR_S:
            irr = "ㅅ"
        elif df in REGULAR_S:
            irr = ""
        else:
            irr = ""
            confident = False
            note = "ㅅ-final verbs are usually regular; assumed regular"
    elif last is not None and last.final == "ㅎ":
        if df in REGULAR_H:
            irr = ""
        elif df in IRREGULAR_H:
            irr = "ㅎ"
        elif pos == "adjective":
            irr = "ㅎ"
            note = "assumed ㅎ-irregular (좋다 is the one regular ㅎ adjective)"
        else:
            irr = ""

    return Classification(df, stem, pos, irr, confident, note)


# ==========================================================================
# The three bases
# ==========================================================================

def _harmony(stem: str, irr: Irregular) -> str:
    """Choose 아 or 어 by 모음조화 (vowel harmony)."""
    idx = len(stem) - 1
    # 으/르 stems look through the ㅡ to the syllable before it:
    # 바쁘다 -> 바 has ㅏ -> 바빠요;  예쁘다 -> 예 -> 예뻐요.
    if irr in ("으", "르", "러") and idx > 0:
        idx -= 1
    syl = decompose(stem[idx])
    if syl is None:
        return "어"
    return "아" if syl.medial in ("ㅏ", "ㅗ") else "어"


#: Vowel + 아/어 contractions that are obligatory in speech.
_CONTRACT: dict[tuple[str, str], str] = {
    ("ㅏ", "아"): "ㅏ", ("ㅓ", "어"): "ㅓ", ("ㅕ", "어"): "ㅕ",
    ("ㅐ", "어"): "ㅐ", ("ㅔ", "어"): "ㅔ", ("ㅒ", "어"): "ㅒ", ("ㅖ", "어"): "ㅖ",
    ("ㅗ", "아"): "ㅘ", ("ㅜ", "어"): "ㅝ", ("ㅣ", "어"): "ㅕ", ("ㅚ", "어"): "ㅙ",
}


def vowel_base(stem: str, irr: Irregular = "", pos: PartOfSpeech = "verb") -> str:
    """The stem joined to its 아/어 ending. 먹 -> 먹어, 가 -> 가, 쓰 -> 써."""
    if not stem:
        return stem
    v = _harmony(stem, irr)
    head, tail = stem[:-1], stem[-1]
    syl = decompose(tail)
    if syl is None:
        return stem + v

    # ---- irregular stems ------------------------------------------------
    if irr == "여":                                  # 하다 -> 해
        return stem[:-1] + "해"

    if irr == "으":                                  # 쓰 -> 써, 바쁘 -> 바빠
        dropped = syl.replace(medial="ㅏ" if v == "아" else "ㅓ")
        return head + dropped.char

    if irr == "르":                                  # 모르 -> 몰라, 부르 -> 불러
        if not head:
            return head + compose("ㄹ", "ㅏ" if v == "아" else "ㅓ")
        prev = decompose(head[-1])
        prev = prev.replace(final="ㄹ")
        return head[:-1] + prev.char + compose("ㄹ", "ㅏ" if v == "아" else "ㅓ")

    if irr == "러":                                  # 이르 -> 이르러, 푸르 -> 푸르러
        return stem + compose("ㄹ", "ㅓ")

    if irr == "우":                                  # 푸 -> 퍼
        return head + compose(syl.initial, "ㅓ")

    if irr == "ㅎ":                                  # 빨갛 -> 빨개, 하얗 -> 하얘
        fused = "ㅒ" if syl.medial == "ㅑ" else "ㅐ"
        return head + compose(syl.initial, fused)

    if irr == "ㅂ":                                  # 춥 -> 추워, 돕 -> 도와
        base = head + syl.replace(final="").char
        if stem + "다" in B_IRREGULAR_O or (len(stem) == 1 and syl.medial == "ㅗ"):
            return base + compose("ㅇ", "ㅘ")
        return base + compose("ㅇ", "ㅝ")

    if irr == "ㄷ":                                  # 듣 -> 들어
        return head + syl.replace(final="ㄹ").char + compose("ㅇ", "ㅏ" if v == "아" else "ㅓ")

    if irr == "ㅅ":                                  # 짓 -> 지어, 낫 -> 나아
        return head + syl.replace(final="").char + compose("ㅇ", "ㅏ" if v == "아" else "ㅓ")

    # ---- regular --------------------------------------------------------
    if syl.final:                                    # 먹 -> 먹어
        return stem + v
    merged = _CONTRACT.get((syl.medial, v))
    if merged:                                       # 보 + 아 -> 봐
        return head + syl.replace(medial=merged).char
    return stem + v                                  # 쉬 + 어 -> 쉬어


def eu_base(stem: str, irr: Irregular = "") -> tuple[str, bool]:
    """Prepare the stem for an -(으)- ending.

    Returns (base, needs_eu). `needs_eu` says whether the ending's 으 should
    actually be written: 먹 -> ('먹', True) giving 먹으면, 가 -> ('가', False)
    giving 가면, 살 -> ('사', False) giving 사세요.
    """
    if not stem:
        return stem, False
    head, tail = stem[:-1], stem[-1]
    syl = decompose(tail)
    if syl is None:
        return stem, False

    if irr == "ㄷ":                       # 듣 -> 들으면
        return head + syl.replace(final="ㄹ").char, True
    if irr == "ㅂ":                       # 춥 -> 추우면 (ㅂ becomes 우, 으 absorbed)
        return head + syl.replace(final="").char + "우", False
    if irr == "ㅅ":                       # 짓 -> 지으면 (ㅅ goes, 으 stays)
        return head + syl.replace(final="").char, True
    if irr == "ㅎ":                       # 빨갛 -> 빨가면 (ㅎ and 으 both go)
        return head + syl.replace(final="").char, False
    if irr == "ㄹ" or syl.final == "ㄹ":  # 살 -> handled by the caller
        return stem, False

    return stem, bool(syl.final)


def plain_base(stem: str, ending: str, irr: Irregular = "") -> str:
    """Prepare the stem for an ending that attaches directly.

    Only ㄹ-stems change: ㄹ drops before an ending starting with ㄴ, ㅂ, ㅅ
    or ㄹ — the schoolroom mnemonic is "ㄹ 탈락: ㄴㅂㅅ 오".
        살 + 습니다 -> 삽니다      살 + 세요 -> 사세요
        살 + 는     -> 사는        살 + 고   -> 살고
    """
    if not stem or not ending:
        return stem
    syl = decompose(stem[-1])
    if syl is None or syl.final != "ㄹ":
        return stem
    first = decompose(ending[0])
    trigger = first.initial if first else ending[0]
    if trigger in ("ㄴ", "ㅂ", "ㅅ", "ㄹ") or ending[0] in ("ㄴ", "ㅂ", "ㅅ", "ㄹ"):
        return stem[:-1] + syl.replace(final="").char
    return stem


def _attach_batchim(text: str, jamo: str) -> str:
    """Add a final consonant to the last syllable: 가 + ㅆ -> 갔, 먹어 + ㅆ -> 먹었."""
    syl = decompose(text[-1])
    if syl is None or syl.final:
        return text + jamo
    return text[:-1] + syl.replace(final=jamo).char


def past_base(stem: str, irr: Irregular = "", pos: PartOfSpeech = "verb") -> str:
    """The 았/었 stem: 먹 -> 먹었, 가 -> 갔, 하 -> 했."""
    return _attach_batchim(vowel_base(stem, irr, pos), "ㅆ")


def eu_ending(stem: str, irr: Irregular, ending: str) -> str:
    """Attach an -(으)X ending, writing the 으 only when it is needed."""
    base, needs = eu_base(stem, irr)
    if irr == "ㄹ":
        base = plain_base(base, ending, irr)
        needs = False
    return base + (("으" + ending) if needs else ending)


def eu_batchim(stem: str, irr: Irregular, jamo: str, rest: str = "") -> str:
    """Attach an -(으)ㄴ / -(으)ㄹ style ending whose core is a bare consonant.

    먹 -> 먹은,  가 -> 간,  살 -> 산,  듣 -> 들은,  촥 -> 추운,  살 + ㄹ -> 살
    """
    base, needs = eu_base(stem, irr)
    # Only a genuine ㄹ-stem deletes its ㄹ. The ㄹ that the ㄷ-irregular
    # *creates* (듣 -> 들) is not one, and it still takes the 으: 들은, not 든.
    if irr == "ㄹ":
        if jamo == "ㄹ":
            return base + rest                      # 살 + (으)ㄹ -> 살
        head = decompose(base[-1]).replace(final="").char
        return _attach_batchim(base[:-1] + head, jamo) + rest
    if needs:
        return base + _attach_batchim("으", jamo) + rest
    return _attach_batchim(base, jamo) + rest


# ==========================================================================
# Form catalogue
# ==========================================================================

@dataclass
class Form:
    id: str
    korean: str
    label_en: str
    label_ko: str
    category: str
    speech_level: str
    note: str = ""

    def to_dict(self) -> dict:
        """Serialised with language-neutral aliases alongside the named fields.

        The conjugation table's shape is language-defined — Korean groups by
        speech level, Japanese by politeness register — but a table still has
        to render. `form` and `label_native` are the two keys every language
        provides, so the UI can show a row without knowing whose table it is.
        """
        d = asdict(self)
        d["form"] = self.korean
        d["label_native"] = self.label_ko
        return d


SPEECH_LEVELS = {
    "haeyo": {"ko": "해요체", "en": "Polite informal", "when": "The default for almost every situation a learner will be in."},
    "hapsyo": {"ko": "하십시오체", "en": "Formal polite", "when": "Announcements, news, service staff, presentations, the military."},
    "hae": {"ko": "해체 (반말)", "en": "Casual", "when": "Close friends your own age or younger, and family. Using it wrongly is rude."},
    "handa": {"ko": "한다체", "en": "Plain / written", "when": "Books, newspapers, diaries, academic writing. Not usually spoken."},
    "none": {"ko": "—", "en": "Not level-marked", "when": "Connectives and modifiers take their level from the final verb."},
}


def conjugate(
    dictionary_form: str,
    pos: Optional[PartOfSpeech] = None,
    irregular: Optional[Irregular] = None,
) -> dict[str, Form]:
    """Build the full conjugation table for one word."""
    c = classify(dictionary_form, pos, irregular)
    stem, irr, p = c.stem, c.irregular, c.pos

    V = vowel_base(stem, irr, p)
    P = past_base(stem, irr, p)
    forms: dict[str, Form] = {}

    def add(fid: str, korean: str, en: str, ko: str, cat: str, lvl: str, note: str = "") -> None:
        forms[fid] = Form(fid, korean, en, ko, cat, lvl, note)

    # ---- present --------------------------------------------------------
    add("present_polite", V + "요", "Present, polite", "현재 (해요체)", "tense", "haeyo",
        "The workhorse form. Learn this one first.")
    add("present_formal", _formal(stem, irr), "Present, formal",
        "현재 (하십시오체)", "tense", "hapsyo")
    add("present_casual", V, "Present, casual", "현재 (반말)", "tense", "hae",
        "Identical to the polite form minus 요.")
    add("present_plain",
        _plain_declarative(stem, irr, p), "Present, plain", "현재 (한다체)", "tense", "handa")

    # ---- past -----------------------------------------------------------
    add("past_polite", P + "어요", "Past, polite", "과거 (해요체)", "tense", "haeyo")
    add("past_formal", P + "습니다", "Past, formal", "과거 (하십시오체)", "tense", "hapsyo")
    add("past_casual", P + "어", "Past, casual", "과거 (반말)", "tense", "hae")
    add("past_plain", P + "다", "Past, plain", "과거 (한다체)", "tense", "handa")

    # ---- future / intention ---------------------------------------------
    add("future_polite", eu_batchim(stem, irr, "ㄹ", " 거예요"), "Future, polite",
        "미래 (-(으)ㄹ 거예요)", "tense", "haeyo", "Plan or expectation.")
    add("future_formal", eu_batchim(stem, irr, "ㄹ", " 겁니다"), "Future, formal",
        "미래 (-(으)ㄹ 겁니다)", "tense", "hapsyo")
    add("future_gett", plain_base(stem, "겠", irr) + "겠어요", "Will / I expect",
        "-겠어요", "tense", "haeyo",
        "Stronger intention, or a guess about someone else. 맛있겠어요 = 'that looks tasty'.")

    # ---- honorific ------------------------------------------------------
    sup = HONORIFIC_SUPPLETION.get(dictionary_form)
    hon_note = f"Careful — Korean uses the separate word {sup[0]} here, not a conjugation." if sup else ""
    add("honorific_present", eu_ending(stem, irr, "세요"), "Honorific present",
        "-(으)세요", "honorific", "haeyo", hon_note)
    add("honorific_past", eu_ending(stem, irr, "셨어요"), "Honorific past",
        "-(으)셨어요", "honorific", "haeyo", hon_note)
    add("honorific_formal", eu_ending(stem, irr, "십니다"), "Honorific formal",
        "-(으)십니다", "honorific", "hapsyo", hon_note)

    # ---- negation -------------------------------------------------------
    neg_word = NEGATION_SUPPLETION.get(dictionary_form)
    short_neg = _short_negative(dictionary_form, V)
    add("negative_short", neg_word + "요" if neg_word else short_neg + "요",
        "Negative (short)", "안 + 동사", "negation", "haeyo",
        f"안 does not work with {dictionary_form}; Korean uses {neg_word}." if neg_word else
        "Split 하다-verbs: 공부하다 becomes 공부 안 해요.")
    add("negative_long", plain_base(stem, "지", irr) + "지 않아요", "Negative (long)",
        "-지 않아요", "negation", "haeyo", "Slightly more formal or emphatic than 안.")
    add("negative_ability", "못 " + V + "요" if not dictionary_form.endswith("하다")
        else dictionary_form[:-2] + " 못 해요", "Cannot (inability)", "못 + 동사",
        "negation", "haeyo", "About ability or circumstance, not choice.")
    add("negative_ability_long", plain_base(stem, "지", irr) + "지 못해요",
        "Cannot (long)", "-지 못해요", "negation", "haeyo")

    # ---- imperative / propositive ---------------------------------------
    if p == "verb":
        add("imperative_polite", eu_ending(stem, irr, "세요"), "Please do",
            "-(으)세요", "mood", "haeyo")
        add("imperative_formal", eu_ending(stem, irr, "십시오"), "Please do (formal)",
            "-(으)십시오", "mood", "hapsyo", "Signs, announcements, service staff.")
        add("imperative_casual", V + "라" if final_of(V) else V, "Do it (casual)",
            "-아/어라", "mood", "hae", "Blunt. Only downward, to friends or children.")
        add("imperative_negative", plain_base(stem, "지", irr) + "지 마세요", "Please don't",
            "-지 마세요", "mood", "haeyo")
        add("propositive_polite", eu_batchim(stem, irr, "ㄹ", "까요?"), "Shall we?",
            "-(으)ㄹ까요?", "mood", "haeyo")
        add("propositive_formal", _lets_formal(stem, irr), "Let's (formal)",
            "-(으)ㅂ시다", "mood", "hapsyo",
            "Sounds bossy to someone senior — use -(으)ㄹ까요? instead.")
        add("propositive_casual", plain_base(stem, "자", irr) + "자", "Let's (casual)",
            "-자", "mood", "hae")

    # ---- modifiers (relative clauses) -----------------------------------
    if p == "verb":
        add("modifier_present", plain_base(stem, "는", irr) + "는", "Modifier, present",
            "-는", "modifier", "none", "먹는 사람 = the person who is eating.")
        add("modifier_past", eu_batchim(stem, irr, "ㄴ"), "Modifier, past",
            "-(으)ㄴ", "modifier", "none", "먹은 사람 = the person who ate.")
    else:
        add("modifier_present", eu_batchim(stem, irr, "ㄴ"), "Modifier, present",
            "-(으)ㄴ", "modifier", "none", "Adjectives take -(으)ㄴ where verbs take -는.")
    add("modifier_future", eu_batchim(stem, irr, "ㄹ"), "Modifier, future",
        "-(으)ㄹ", "modifier", "none", "먹을 사람 = the person who will eat.")
    add("modifier_retrospective", plain_base(stem, "던", irr) + "던", "Modifier, recalled",
        "-던", "modifier", "none", "Something habitual or unfinished in the past.")

    # ---- connectives ----------------------------------------------------
    add("connect_and", plain_base(stem, "고", irr) + "고", "and (then)", "-고",
        "connective", "none")
    add("connect_so", V + "서", "so / and then", "-아/어서", "connective", "none",
        "Cause, or one action leading into the next. Cannot take a past-tense marker.")
    add("connect_because", eu_ending(stem, irr, "니까"), "because", "-(으)니까",
        "connective", "none", "Speaker's reasoning. The only one of the two usable before a command.")
    add("connect_but", plain_base(stem, "지", irr) + "지만", "but", "-지만",
        "connective", "none")
    add("connect_background",
        (plain_base(stem, "는", irr) + "는데") if p == "verb" else eu_batchim(stem, irr, "ㄴ", "데"),
        "and / but (setting the scene)", "-는데 / -(으)ㄴ데", "connective", "none",
        "The single most useful intermediate ending. Sets up context for what follows.")
    add("connect_if", eu_ending(stem, irr, "면"), "if / when", "-(으)면",
        "connective", "none")
    add("connect_while", eu_ending(stem, irr, "면서"), "while", "-(으)면서",
        "connective", "none")
    if p == "verb":
        add("connect_intend", eu_ending(stem, irr, "려고"), "intending to", "-(으)려고",
            "connective", "none")
        add("connect_purpose", eu_ending(stem, irr, "러"), "in order to (go/come)",
            "-(으)러", "connective", "none", "Only with verbs of motion: 먹으러 가요.")

    # ---- auxiliaries ----------------------------------------------------
    if p == "verb":
        add("aux_want", plain_base(stem, "고", irr) + "고 싶어요", "want to",
            "-고 싶어요", "auxiliary", "haeyo",
            "Only for your own wishes. For someone else's, use -고 싶어해요.")
        add("aux_progressive", plain_base(stem, "고", irr) + "고 있어요", "is doing",
            "-고 있어요", "auxiliary", "haeyo")
        add("aux_try", V + " 보세요", "try doing", "-아/어 보세요", "auxiliary", "haeyo")
        add("aux_favour", V + " 주세요", "please do (for me)", "-아/어 주세요",
            "auxiliary", "haeyo")
    add("aux_must", V + "야 해요", "must / have to", "-아/어야 해요", "auxiliary", "haeyo")
    add("aux_can", eu_batchim(stem, irr, "ㄹ", " 수 있어요"), "can / is able to",
        "-(으)ㄹ 수 있어요", "auxiliary", "haeyo")
    add("aux_cannot", eu_batchim(stem, irr, "ㄹ", " 수 없어요"), "cannot",
        "-(으)ㄹ 수 없어요", "auxiliary", "haeyo")

    return forms


def _formal(stem: str, irr: Irregular) -> str:
    """-ㅂ니다 / -습니다, with ㄹ-deletion. 가 -> 갑니다, 먹 -> 먹습니다, 살 -> 삽니다."""
    base = plain_base(stem, "습니다", irr)
    if ends_with_batchim(base):
        return base + "습니다"
    return _attach_batchim(base, "ㅂ") + "니다"


def _lets_formal(stem: str, irr: Irregular) -> str:
    """-(으)ㅂ시다. 가 -> 갑시다, 먹 -> 먹읍시다, 살 -> 삽시다."""
    base, needs = eu_base(stem, irr)
    if irr == "ㄹ":
        base = base[:-1] + decompose(base[-1]).replace(final="").char
        return _attach_batchim(base, "ㅂ") + "시다"
    if needs:
        return base + "읍시다"
    return _attach_batchim(base, "ㅂ") + "시다"


def _plain_declarative(stem: str, irr: Irregular, pos: PartOfSpeech) -> str:
    """한다체: verbs take -ㄴ다/는다, adjectives take plain -다."""
    if pos != "verb":
        return stem + "다"
    base = plain_base(stem, "ㄴ다", irr)
    if ends_with_batchim(base):
        return base + "는다"
    return _attach_batchim(base, "ㄴ") + "다"


def _short_negative(dictionary_form: str, vowel_form: str) -> str:
    """안 goes before the verb — except 하다-verbs, which split around it."""
    if dictionary_form.endswith("하다") and len(dictionary_form) > 2:
        return dictionary_form[:-2] + " 안 해"
    return "안 " + vowel_form


# ==========================================================================
# Presentation helpers
# ==========================================================================

def conjugation_table(
    dictionary_form: str,
    pos: Optional[PartOfSpeech] = None,
    irregular: Optional[Irregular] = None,
) -> dict:
    """A grouped, UI-ready table plus an explanation of the irregular class."""
    c = classify(dictionary_form, pos, irregular)
    forms = conjugate(dictionary_form, pos, irregular)

    grouped: dict[str, list[dict]] = {}
    for f in forms.values():
        grouped.setdefault(f.category, []).append(f.to_dict())

    return {
        "dictionary_form": dictionary_form,
        "stem": c.stem,
        "part_of_speech": c.pos,
        "irregular": c.irregular or "regular",
        "irregular_explained": IRREGULAR_EXPLANATIONS.get(c.irregular, IRREGULAR_EXPLANATIONS[""]),
        "confident": c.confident,
        "note": c.note,
        "bases": {
            "vowel": vowel_base(c.stem, c.irregular, c.pos),
            "eu": "".join(eu_base(c.stem, c.irregular)[0]),
            "eu_needs_written": eu_base(c.stem, c.irregular)[1],
            "plain": c.stem,
        },
        "categories": grouped,
        "speech_levels": SPEECH_LEVELS,
    }


IRREGULAR_EXPLANATIONS: dict[str, dict[str, str]] = {
    "": {
        "name": "Regular",
        "simple": "This one behaves. The stem never changes — just add the ending.",
        "technical": "No stem alternation; endings attach to the invariant stem.",
        "example": "먹다 → 먹어요 / 먹으면 / 먹습니다",
    },
    "ㄷ": {
        "name": "ㄷ irregular",
        "simple": "When a vowel comes next, the ㄷ underneath turns into ㄹ. Before a consonant it stays as ㄷ.",
        "technical": "Stem-final /t/ → /l/ before a vowel-initial or 으-initial ending.",
        "example": "듣다 → 들어요 / 들으면, but 듣고 / 듣습니다",
    },
    "ㅂ": {
        "name": "ㅂ irregular",
        "simple": "The ㅂ underneath melts into a 우 sound when a vowel follows.",
        "technical": "Stem-final /p/ → /w/, surfacing as 우 and fusing with the ending vowel.",
        "example": "춥다 → 추워요 / 추우면, but 춥고 / 춥습니다",
    },
    "ㅅ": {
        "name": "ㅅ irregular",
        "simple": "The ㅅ underneath disappears before a vowel — but unlike ㅂ, nothing takes its place, so the two vowels sit side by side.",
        "technical": "Stem-final /s/ deletes before a vowel; no contraction follows, and the 으 of -(으)- is still written.",
        "example": "짓다 → 지어요 / 지으면, but 짓고 / 짓습니다",
    },
    "ㅎ": {
        "name": "ㅎ irregular",
        "simple": "Almost every colour word does this. The ㅎ vanishes and the ending turns into 애.",
        "technical": "Stem-final /h/ deletes; the 아/어 ending fuses with the stem vowel to 애 (얘 after ㅑ). 좋다 is the sole regular ㅎ adjective.",
        "example": "빨갛다 → 빨개요 / 빨간, but 빨갛고 / 빨갛습니다",
    },
    "르": {
        "name": "르 irregular",
        "simple": "The 르 splits in two: a ㄹ jumps back underneath the syllable before it, and a new ㄹ starts the ending.",
        "technical": "The /ɯ/ of 르 deletes and /l/ geminates across the syllable boundary before an 아/어 ending.",
        "example": "모르다 → 몰라요, 부르다 → 불러요, but 모르고 / 모르면",
    },
    "러": {
        "name": "러 irregular",
        "simple": "Only four words do this. The stem stays whole and the ending gains an extra ㄹ.",
        "technical": "The 어 ending surfaces as 러 after 이르다(arrive), 푸르다, 누르다(be yellow), 노르다.",
        "example": "푸르다 → 푸르러요",
    },
    "으": {
        "name": "으 irregular",
        "simple": "The ㅡ is a weak vowel. When 아/어 comes along it gives up its seat entirely.",
        "technical": "Stem-final /ɯ/ deletes before an 아/어 ending; harmony is then decided by the preceding syllable.",
        "example": "쓰다 → 써요, 바쁘다 → 바빠요, 예쁘다 → 예뻐요",
    },
    "ㄹ": {
        "name": "ㄹ deletion",
        "simple": "The ㄹ underneath falls off before ㄴ, ㅂ and ㅅ. Everywhere else it stays.",
        "technical": "Stem-final /l/ deletes before endings beginning ㄴ, ㅂ, ㅅ or ㄹ. Exceptionless, so arguably regular.",
        "example": "살다 → 살아요 / 삽니다 / 사세요 / 사는",
    },
    "우": {
        "name": "우 irregular",
        "simple": "One single verb in the whole language does this: 푸다, to scoop.",
        "technical": "Stem-final /u/ deletes before 어. The only member is 푸다 → 퍼요.",
        "example": "푸다 → 퍼요",
    },
    "여": {
        "name": "여 irregular (하다)",
        "simple": "하다 is its own thing: 하 + 여 squashes into 해. Every -하다 word follows it.",
        "technical": "하- selects the allomorph 여, contracting to 해. Applies to the entire 하다 class.",
        "example": "하다 → 해요, 공부하다 → 공부해요",
    },
}
