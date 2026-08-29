"""
Conjugation, with the irregular classes tested exhaustively.

Irregular verbs are where a Korean learning app either earns trust or loses
it: a learner who is taught 춥어요 will say 춥어요 for years. Every expected
value below is the standard form.
"""

import pytest

from app.languages.korean.conjugation import (
    IRREGULAR_EXPLANATIONS,
    classify,
    conjugate,
    conjugation_table,
    eu_base,
    past_base,
    stem_of,
    vowel_base,
)


def form(word, fid, **kw):
    return conjugate(word, **kw)[fid].korean


# ==========================================================================
# Regular stems and the 아/어 contractions
# ==========================================================================

REGULAR_PRESENT = [
    ("먹다", "먹어요"), ("읽다", "읽어요"), ("입다", "입어요"), ("잡다", "잡아요"),
    ("웃다", "웃어요"), ("씻다", "씻어요"), ("받다", "받아요"), ("닫다", "닫아요"),
    ("믿다", "믿어요"), ("좋다", "좋아요"), ("넣다", "넣어요"), ("놓다", "놓아요"),
    ("앉다", "앉아요"), ("있다", "있어요"), ("없다", "없어요"), ("작다", "작아요"),
]

CONTRACTIONS = [
    ("가다", "가요"),          # ㅏ + 아 -> ㅏ
    ("서다", "서요"),          # ㅓ + 어 -> ㅓ
    ("켜다", "켜요"),          # ㅕ + 어 -> ㅕ
    ("보다", "봐요"),          # ㅗ + 아 -> ㅘ
    ("오다", "와요"),
    ("주다", "줘요"),          # ㅜ + 어 -> ㅝ
    ("배우다", "배워요"),
    ("마시다", "마셔요"),      # ㅣ + 어 -> ㅕ
    ("가르치다", "가르쳐요"),
    ("기다리다", "기다려요"),
    ("되다", "돼요"),          # ㅚ + 어 -> ㅙ
    ("보내다", "보내요"),      # ㅐ + 어 -> ㅐ
    ("세다", "세요"),          # ㅔ + 어 -> ㅔ
    ("쉬다", "쉬어요"),        # ㅟ + 어 does NOT contract
    ("하다", "해요"),          # 여-irregular
    ("공부하다", "공부해요"),
    ("좋아하다", "좋아해요"),
]


@pytest.mark.parametrize("word,expected", REGULAR_PRESENT + CONTRACTIONS)
def test_present_polite(word, expected):
    assert form(word, "present_polite") == expected


# ==========================================================================
# 으 irregular — the ㅡ gives up its seat
# ==========================================================================

EU = [
    ("쓰다", "써요"), ("크다", "커요"), ("끄다", "꺼요"), ("뜨다", "떠요"),
    ("바쁘다", "바빠요"), ("예쁘다", "예뻐요"), ("아프다", "아파요"),
    ("고프다", "고파요"), ("배고프다", "배고파요"), ("슬프다", "슬퍼요"),
    ("기쁘다", "기뻐요"), ("나쁘다", "나빠요"), ("모으다", "모아요"),
]


@pytest.mark.parametrize("word,expected", EU)
def test_eu_irregular(word, expected):
    assert form(word, "present_polite") == expected
    assert classify(word).irregular == "으"


def test_eu_harmony_looks_past_the_eu():
    """바쁘다 → 바빠요 (바 has ㅏ) but 예쁘다 → 예뻐요 (예 does not)."""
    assert vowel_base("바쁘", "으") == "바빠"
    assert vowel_base("예쁘", "으") == "예뻐"
    assert vowel_base("쓰", "으") == "써"        # no preceding syllable -> 어


# ==========================================================================
# ㄷ irregular
# ==========================================================================

D_IRREGULAR = [
    ("듣다", "들어요"), ("걷다", "걸어요"), ("깨닫다", "깨달아요"),
    ("싣다", "실어요"), ("묻다", "물어요"),
]
D_REGULAR = [("받다", "받아요"), ("닫다", "닫아요"), ("믿다", "믿어요"), ("얻다", "얻어요")]


@pytest.mark.parametrize("word,expected", D_IRREGULAR)
def test_d_irregular(word, expected):
    assert form(word, "present_polite") == expected


@pytest.mark.parametrize("word,expected", D_REGULAR)
def test_d_regular(word, expected):
    assert form(word, "present_polite") == expected


def test_d_irregular_across_ending_types():
    """ㄷ → ㄹ before a vowel or 으, but stays ㄷ before a consonant."""
    assert form("듣다", "present_polite") == "들어요"
    assert form("듣다", "connect_if") == "들으면"
    assert form("듣다", "imperative_polite") == "들으세요"
    assert form("듣다", "modifier_past") == "들은"
    assert form("듣다", "future_polite") == "들을 거예요"
    assert form("듣다", "present_formal") == "듣습니다"     # unchanged
    assert form("듣다", "connect_and") == "듣고"            # unchanged
    assert form("듣다", "connect_but") == "듣지만"          # unchanged


def test_created_rieul_is_not_a_rieul_stem():
    """듣 becomes 들, but 들은 keeps the 으 — unlike a true ㄹ-stem (산)."""
    assert form("듣다", "modifier_past") == "들은"
    assert form("살다", "modifier_past") == "산"


def test_ambiguous_d_verbs_are_flagged():
    for word in ("걷다", "묻다"):
        c = classify(word)
        assert c.confident is False
        assert "irregular" in c.note
    # and the caller can settle it
    assert form("묻다", "present_polite", irregular="") == "묻어요"
    assert form("묻다", "present_polite", irregular="ㄷ") == "물어요"


# ==========================================================================
# ㅂ irregular
# ==========================================================================

B_IRREGULAR = [
    ("춥다", "추워요"), ("덥다", "더워요"), ("쉽다", "쉬워요"), ("어렵다", "어려워요"),
    ("무겁다", "무거워요"), ("가볍다", "가벼워요"), ("아름답다", "아름다워요"),
    ("귀엽다", "귀여워요"), ("맵다", "매워요"), ("고맙다", "고마워요"),
    ("반갑다", "반가워요"), ("가깝다", "가까워요"), ("눕다", "누워요"),
    ("줍다", "주워요"),
]
B_TO_WA = [("돕다", "도와요"), ("곱다", "고와요")]
B_REGULAR = [("입다", "입어요"), ("잡다", "잡아요"), ("좁다", "좁아요"), ("뽑다", "뽑아요")]


@pytest.mark.parametrize("word,expected", B_IRREGULAR + B_TO_WA)
def test_b_irregular(word, expected):
    assert form(word, "present_polite") == expected


@pytest.mark.parametrize("word,expected", B_REGULAR)
def test_b_regular(word, expected):
    assert form(word, "present_polite") == expected


def test_b_irregular_absorbs_the_eu():
    """춥 + (으)면 → 추우면, not 추우으면."""
    assert form("춥다", "connect_if") == "추우면"
    assert form("춥다", "connect_because") == "추우니까"
    assert form("춥다", "modifier_present") == "추운"
    assert form("춥다", "future_polite") == "추울 거예요"
    assert form("춥다", "present_formal") == "춥습니다"
    assert eu_base("춥", "ㅂ") == ("추우", False)


# ==========================================================================
# ㅅ irregular — ㅅ goes, but the 으 stays
# ==========================================================================

S_IRREGULAR = [
    ("짓다", "지어요"), ("낫다", "나아요"), ("붓다", "부어요"), ("잇다", "이어요"),
    ("긋다", "그어요"), ("젓다", "저어요"),
]
S_REGULAR = [("웃다", "웃어요"), ("씻다", "씻어요"), ("벗다", "벗어요"), ("솟다", "솟아요")]


@pytest.mark.parametrize("word,expected", S_IRREGULAR)
def test_s_irregular(word, expected):
    assert form(word, "present_polite") == expected


@pytest.mark.parametrize("word,expected", S_REGULAR)
def test_s_regular(word, expected):
    assert form(word, "present_polite") == expected


def test_s_irregular_keeps_the_eu_unlike_b():
    """The contrast that trips learners up: 지으면 but 추우면."""
    assert form("짓다", "connect_if") == "지으면"
    assert form("짓다", "modifier_past") == "지은"
    assert form("춥다", "connect_if") == "추우면"


# ==========================================================================
# ㅎ irregular — nearly every colour word
# ==========================================================================

H_IRREGULAR = [
    ("빨갛다", "빨개요"), ("파랗다", "파래요"), ("노랗다", "노래요"),
    ("까맣다", "까매요"), ("하얗다", "하얘요"), ("그렇다", "그래요"),
    ("이렇다", "이래요"), ("저렇다", "저래요"), ("어떻다", "어때요"),
]


@pytest.mark.parametrize("word,expected", H_IRREGULAR)
def test_h_irregular(word, expected):
    assert form(word, "present_polite") == expected


def test_h_irregular_modifiers_and_conditionals():
    assert form("빨갛다", "modifier_present") == "빨간"
    assert form("빨갛다", "connect_if") == "빨가면"
    assert form("빨갛다", "present_formal") == "빨갛습니다"
    assert form("하얗다", "modifier_present") == "하얀"


def test_joh_da_is_the_regular_exception():
    assert form("좋다", "present_polite") == "좋아요"
    assert form("좋다", "modifier_present") == "좋은"
    assert classify("좋다").irregular == ""


def test_h_final_verbs_stay_regular():
    for w, e in [("넣다", "넣어요"), ("놓다", "놓아요"), ("낳다", "낳아요"), ("쌓다", "쌓아요")]:
        assert form(w, "present_polite") == e


# ==========================================================================
# 르 and 러
# ==========================================================================

REU = [
    ("모르다", "몰라요"), ("부르다", "불러요"), ("다르다", "달라요"),
    ("빠르다", "빨라요"), ("흐르다", "흘러요"), ("고르다", "골라요"),
    ("자르다", "잘라요"), ("오르다", "올라요"), ("서두르다", "서둘러요"),
    ("게으르다", "게을러요"),
]
REO = [("푸르다", "푸르러요"), ("노르다", "노르러요")]
REU_REGULAR = [("따르다", "따라요"), ("들르다", "들러요"), ("치르다", "치러요")]


@pytest.mark.parametrize("word,expected", REU)
def test_reu_irregular(word, expected):
    assert form(word, "present_polite") == expected


@pytest.mark.parametrize("word,expected", REO)
def test_reo_irregular(word, expected):
    assert form(word, "present_polite") == expected


@pytest.mark.parametrize("word,expected", REU_REGULAR)
def test_reu_regular_exceptions(word, expected):
    assert form(word, "present_polite") == expected


def test_reu_only_affects_vowel_endings():
    assert form("모르다", "connect_if") == "모르면"
    assert form("모르다", "present_formal") == "모릅니다"
    assert form("모르다", "connect_and") == "모르고"


# ==========================================================================
# ㄹ deletion
# ==========================================================================

def test_rieul_deletion_before_n_b_s():
    assert form("살다", "present_polite") == "살아요"      # vowel: ㄹ stays
    assert form("살다", "present_formal") == "삽니다"      # ㅂ: ㄹ goes
    assert form("살다", "honorific_present") == "사세요"   # ㅅ: ㄹ goes
    assert form("살다", "modifier_present") == "사는"      # ㄴ: ㄹ goes
    assert form("살다", "connect_because") == "사니까"     # ㄴ: ㄹ goes
    assert form("살다", "connect_if") == "살면"            # 으-ending: ㄹ stays, no 으
    assert form("살다", "connect_and") == "살고"           # ㄱ: ㄹ stays
    assert form("살다", "modifier_future") == "살"         # (으)ㄹ merges
    assert form("살다", "modifier_past") == "산"


@pytest.mark.parametrize("word,fid,expected", [
    ("만들다", "present_formal", "만듭니다"),
    ("만들다", "modifier_past", "만든"),
    ("만들다", "modifier_present", "만드는"),
    ("알다", "present_formal", "압니다"),
    ("알다", "modifier_present", "아는"),
    ("놀다", "propositive_formal", "놉시다"),
    ("길다", "modifier_present", "긴"),
    ("멀다", "modifier_present", "먼"),
    ("팔다", "honorific_present", "파세요"),
    ("열다", "present_formal", "엽니다"),
])
def test_rieul_stems(word, fid, expected):
    assert form(word, fid) == expected


def test_u_irregular_is_a_single_verb():
    assert form("푸다", "present_polite") == "퍼요"
    assert classify("푸다").irregular == "우"


# ==========================================================================
# Tense
# ==========================================================================

PAST = [
    ("먹다", "먹었어요"), ("가다", "갔어요"), ("오다", "왔어요"), ("보다", "봤어요"),
    ("하다", "했어요"), ("공부하다", "공부했어요"), ("마시다", "마셨어요"),
    ("주다", "줬어요"), ("되다", "됐어요"), ("쓰다", "썼어요"), ("바쁘다", "바빴어요"),
    ("춥다", "추웠어요"), ("듣다", "들었어요"), ("모르다", "몰랐어요"),
    ("짓다", "지었어요"), ("빨갛다", "빨갰어요"), ("살다", "살았어요"),
    ("있다", "있었어요"), ("좋다", "좋았어요"),
]


@pytest.mark.parametrize("word,expected", PAST)
def test_past_polite(word, expected):
    assert form(word, "past_polite") == expected


FORMAL = [
    ("먹다", "먹습니다"), ("가다", "갑니다"), ("하다", "합니다"), ("있다", "있습니다"),
    ("살다", "삽니다"), ("만들다", "만듭니다"), ("춥다", "춥습니다"),
    ("좋다", "좋습니다"), ("모르다", "모릅니다"),
]


@pytest.mark.parametrize("word,expected", FORMAL)
def test_present_formal(word, expected):
    assert form(word, "present_formal") == expected


FUTURE = [
    ("먹다", "먹을 거예요"), ("가다", "갈 거예요"), ("하다", "할 거예요"),
    ("듣다", "들을 거예요"), ("살다", "살 거예요"), ("춥다", "추울 거예요"),
    ("짓다", "지을 거예요"), ("만들다", "만들 거예요"),
]


@pytest.mark.parametrize("word,expected", FUTURE)
def test_future(word, expected):
    assert form(word, "future_polite") == expected


# ==========================================================================
# Modifiers, mood, negation, connectives
# ==========================================================================

def test_verbs_and_adjectives_take_different_present_modifiers():
    assert form("먹다", "modifier_present") == "먹는"       # verb
    assert form("좋다", "modifier_present") == "좋은"       # adjective
    assert form("크다", "modifier_present") == "큰"
    assert form("작다", "modifier_present") == "작은"
    assert form("먹다", "modifier_past") == "먹은"
    assert form("먹다", "modifier_future") == "먹을"


def test_neundae_picks_the_right_shape():
    assert form("먹다", "connect_background") == "먹는데"
    assert form("춥다", "connect_background") == "추운데"
    assert form("좋다", "connect_background") == "좋은데"


def test_negation():
    assert form("먹다", "negative_short") == "안 먹어요"
    assert form("가다", "negative_short") == "안 가요"
    assert form("먹다", "negative_long") == "먹지 않아요"
    assert form("공부하다", "negative_short") == "공부 안 해요"
    assert form("먹다", "negative_ability") == "못 먹어요"
    assert form("공부하다", "negative_ability") == "공부 못 해요"


def test_negation_suppletion_is_reported():
    f = conjugate("알다")["negative_short"]
    assert f.korean == "모르요" or "모르" in f.korean
    assert "모르다" in f.note


def test_propositive_and_imperative():
    assert form("먹다", "propositive_polite") == "먹을까요?"
    assert form("가다", "propositive_polite") == "갈까요?"
    assert form("먹다", "propositive_formal") == "먹읍시다"
    assert form("가다", "propositive_formal") == "갑시다"
    assert form("먹다", "propositive_casual") == "먹자"
    assert form("먹다", "imperative_polite") == "먹으세요"
    assert form("가다", "imperative_polite") == "가세요"
    assert form("먹다", "imperative_formal") == "먹으십시오"
    assert form("먹다", "imperative_negative") == "먹지 마세요"


def test_plain_style():
    assert form("먹다", "present_plain") == "먹는다"
    assert form("가다", "present_plain") == "간다"
    assert form("살다", "present_plain") == "산다"
    assert form("좋다", "present_plain") == "좋다"        # adjectives take bare 다
    assert form("먹다", "past_plain") == "먹었다"


def test_auxiliaries():
    assert form("먹다", "aux_want") == "먹고 싶어요"
    assert form("먹다", "aux_progressive") == "먹고 있어요"
    assert form("먹다", "aux_can") == "먹을 수 있어요"
    assert form("먹다", "aux_cannot") == "먹을 수 없어요"
    assert form("듣다", "aux_can") == "들을 수 있어요"
    assert form("먹다", "aux_favour") == "먹어 주세요"
    assert form("가다", "aux_try") == "가 보세요"


def test_connectives():
    assert form("먹다", "connect_and") == "먹고"
    assert form("먹다", "connect_so") == "먹어서"
    assert form("듣다", "connect_so") == "들어서"
    assert form("먹다", "connect_because") == "먹으니까"
    assert form("먹다", "connect_but") == "먹지만"
    assert form("먹다", "connect_if") == "먹으면"
    assert form("먹다", "connect_purpose") == "먹으러"
    assert form("먹다", "connect_intend") == "먹으려고"


def test_adjectives_have_no_imperative():
    """You cannot order someone to be tall."""
    assert "imperative_polite" not in conjugate("크다")
    assert "propositive_casual" not in conjugate("좋다")
    assert "imperative_polite" in conjugate("먹다")


# ==========================================================================
# Table assembly
# ==========================================================================

def test_stem_of_rejects_non_dictionary_forms():
    assert stem_of("먹다") == "먹"
    with pytest.raises(ValueError):
        stem_of("먹어요")


def test_conjugation_table_shape():
    t = conjugation_table("춥다")
    assert t["stem"] == "춥"
    assert t["part_of_speech"] == "adjective"
    assert t["irregular"] == "ㅂ"
    assert t["irregular_explained"]["name"] == "ㅂ irregular"
    assert t["bases"]["vowel"] == "추워"
    assert "tense" in t["categories"]
    assert any(f["id"] == "present_polite" for f in t["categories"]["tense"])


def test_every_irregular_class_has_an_explanation():
    for cls in ("", "ㄷ", "ㅂ", "ㅅ", "ㅎ", "르", "러", "으", "ㄹ", "우", "여"):
        e = IRREGULAR_EXPLANATIONS[cls]
        assert e["simple"] and e["technical"] and e["example"]


def test_past_base_helper():
    assert past_base("먹", "") == "먹었"
    assert past_base("가", "") == "갔"
    assert past_base("하", "여") == "했"


def test_no_form_is_empty():
    """A blank conjugation would silently teach nothing. Guard against it."""
    for word in ["먹다", "가다", "하다", "춥다", "듣다", "살다", "모르다",
                 "짓다", "빨갛다", "쓰다", "좋다", "있다"]:
        for fid, f in conjugate(word).items():
            assert f.korean.strip(), f"{word}/{fid} produced an empty form"
