"""
Pronunciation rules, checked against 표준 발음법 and standard dictionary forms.

Every expected value here is the prescriptive standard pronunciation. Where
everyday speech differs (전화 → [저놔]) that is tested separately under the
`casual` flag, because a learning app must not teach the casual form as if it
were the standard one.
"""

import pytest

from app.languages.korean.phonology import (
    Hints,
    batchim_sound,
    explain,
    minimal_pairs,
    pronounce,
    pronounce_phrase,
)

# --------------------------------------------------------------------------
# 연음 — linking
# --------------------------------------------------------------------------

LIAISON = [
    ("한국어", "한구거"), ("옷이", "오시"), ("꽃이", "꼬치"), ("밭에", "바테"),
    ("낮에", "나제"), ("앞에", "아페"), ("밖에", "바께"), ("있어요", "이써요"),
    ("맛있어요", "마시써요"), ("책을", "채글"), ("음악을", "으마글"),
    ("앉아", "안자"), ("읽어", "일거"), ("젊어", "절머"), ("넓어", "널버"),
    ("핥아", "할타"), ("값이", "갑씨"), ("없어", "업써"), ("몫을", "목쓸"),
]

# --------------------------------------------------------------------------
# 음절의 끝소리 규칙 — the seven final sounds
# --------------------------------------------------------------------------

NEUTRALISATION = [
    ("꽃", "꼳"), ("밖", "박"), ("앞", "압"), ("부엌", "부억"), ("옷", "옫"),
    ("낮", "낟"), ("밭", "받"), ("히읗", "히읃"), ("빛", "빋"), ("숲", "숩"),
]

CLUSTERS = [
    ("닭", "닥"), ("삶", "삼"), ("여덟", "여덜"), ("넋", "넉"), ("값", "갑"),
    ("앉", "안"), ("핥", "할"), ("읊", "읍"), ("몫", "목"),
]

# --------------------------------------------------------------------------
# 비음화 / 유음화
# --------------------------------------------------------------------------

NASALISATION = [
    ("국물", "궁물"), ("한국말", "한궁말"), ("먹는", "멍는"), ("있는", "인는"),
    ("합니다", "함니다"), ("감사합니다", "감사함니다"), ("악몽", "앙몽"),
    ("식물", "싱물"), ("작년", "장년"), ("닫는", "단는"), ("입는", "임는"),
    ("종로", "종노"), ("담력", "담녁"), ("국립", "궁닙"), ("협력", "혐녁"),
    ("법률", "범뉼"), ("놓는", "논는"), ("않는", "안는"),
]

LATERALISATION = [
    ("신라", "실라"), ("설날", "설랄"), ("연락", "열락"), ("관리", "괄리"),
    ("칼날", "칼랄"), ("뚫는", "뚤른"), ("난로", "날로"),
]

# --------------------------------------------------------------------------
# 경음화 / 격음화 / 구개음화 / ㅎ 탈락
# --------------------------------------------------------------------------

TENSIFICATION = [
    ("학교", "학꾜"), ("먹다", "먹따"), ("국밥", "국빱"), ("입다", "입따"),
    ("읽다", "익따"), ("읽고", "일꼬"), ("맑고", "말꼬"), ("밝다", "박따"),
    ("넓다", "널따"), ("밟다", "밥따"), ("핥다", "할따"), ("훑다", "훌따"),
    ("앉다", "안따"), ("젊다", "점따"), ("삶다", "삼따"), ("얹다", "언따"),
    ("읽습니다", "익씀니다"), ("닭장", "닥짱"), ("옷과", "옫꽈"),
]

ASPIRATION = [
    ("축하", "추카"), ("맏형", "마텽"), ("좁히다", "조피다"), ("입학", "이팍"),
    ("좋고", "조코"), ("많다", "만타"), ("싫지", "실치"), ("놓다", "노타"),
    ("급히", "그피"), ("법학", "버팍"),
]

H_DELETION = [
    ("좋아요", "조아요"), ("많아", "마나"), ("싫어", "시러"), ("놓아", "노아"),
    ("낳은", "나은"), ("괜찮아요", "괜차나요"),
]

PALATALISATION = [
    ("굳이", "구지"), ("같이", "가치"), ("해돋이", "해도지"), ("닫히다", "다치다"),
    ("굳히다", "구치다"), ("붙이다", "부치다"),
]

UI_VOWEL = [("희망", "히망"), ("무늬", "무니"), ("띄어쓰기", "띠어쓰기")]

UNCHANGED = [
    ("사랑", "사랑"), ("공부", "공부"), ("갈비", "갈비"), ("강남", "강남"),
    ("일곱", "일곱"), ("여섯", "여섣"), ("커피", "커피"), ("바나나", "바나나"),
]


@pytest.mark.parametrize("written,spoken", LIAISON)
def test_liaison(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", NEUTRALISATION + CLUSTERS)
def test_final_neutralisation(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", NASALISATION)
def test_nasalisation(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", LATERALISATION)
def test_lateralisation(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", TENSIFICATION)
def test_tensification(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", ASPIRATION)
def test_aspiration(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", H_DELETION)
def test_h_deletion(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", PALATALISATION)
def test_palatalisation(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", UI_VOWEL)
def test_ui_reduction(written, spoken):
    assert pronounce(written).spoken == spoken


@pytest.mark.parametrize("written,spoken", UNCHANGED)
def test_words_that_do_not_change(written, spoken):
    assert pronounce(written).spoken == spoken


# --------------------------------------------------------------------------
# Lexically-conditioned rules must NOT fire without their hint
# --------------------------------------------------------------------------

def test_noun_keeps_giyeok_where_verb_stem_would_not():
    """읽고 → [일꼬] but 닭고기 → [닥꼬기]. Same letters, different class."""
    assert pronounce("읽고").spoken == "일꼬"
    assert pronounce("닭고기").spoken == "닥꼬기"


def test_compound_boundary_changes_liaison():
    """Within a word the coda survives; across a compound it neutralises first."""
    assert pronounce("첫인상").spoken == "처신상"          # no hint: treated as one word
    assert pronounce("첫인상", Hints(compound_after={0})).spoken == "처딘상"
    assert pronounce("맛없다", Hints(compound_after={0})).spoken == "마덥따"


def test_n_insertion_requires_a_hint():
    assert pronounce("솜이불").spoken == "소미불"
    assert pronounce("솜이불", Hints(n_insertion_after={0})).spoken == "솜니불"
    assert pronounce("색연필", Hints(n_insertion_after={0})).spoken == "생년필"
    assert pronounce("한여름", Hints(n_insertion_after={0})).spoken == "한녀름"


def test_standard_keeps_h_but_casual_drops_it():
    assert pronounce("결혼").spoken == "결혼"
    assert pronounce("전화").spoken == "전화"
    assert pronounce("결혼", Hints(casual=True)).spoken == "겨론"
    assert pronounce("전화", Hints(casual=True)).spoken == "저놔"


def test_sino_korean_tensification_is_hint_gated():
    assert pronounce("발달").spoken == "발달"
    assert pronounce("발달", Hints(sino_korean=True)).spoken == "발딸"


def test_explicit_override_wins():
    p = pronounce("무엇을", override="뭐를")
    assert p.spoken == "뭐를"
    assert p.overridden is True


# --------------------------------------------------------------------------
# Phrases, explanations, helpers
# --------------------------------------------------------------------------

def test_rules_do_not_leak_across_spaces():
    """Each phonological word is processed on its own."""
    assert pronounce_phrase("밥 먹어요").spoken == "밥 머거요"
    assert pronounce_phrase("한국 사람").spoken == "한국 사람"


def test_explain_returns_ordered_reasons():
    out = explain("한국어")
    assert out["spoken"] == "한구거"
    assert out["changed"] is True
    assert len(out["steps"]) >= 1
    step = out["steps"][0]
    assert step["rule_id"] == "liaison"
    assert "연음" in step["rule"]
    assert step["child_explanation"]
    assert step["linguistic_explanation"]
    assert "→" in step["shows"]


def test_explain_says_so_when_nothing_changes():
    out = explain("사랑")
    assert out["changed"] is False
    assert "exactly as it is written" in out["summary"]


def test_batchim_sound_collapses_to_seven():
    assert batchim_sound("ㅋ") == "ㄱ"
    assert batchim_sound("ㅅ") == "ㄷ"
    assert batchim_sound("ㅍ") == "ㅂ"
    assert batchim_sound("ㄺ") == "ㄱ"
    assert batchim_sound("ㅄ") == "ㅂ"
    assert set(batchim_sound(f) for f in "ㄱㄲㅋㄴㄷㅅㅆㅈㅊㅌㅎㄹㅁㅂㅍㅇ") == set("ㄱㄴㄷㄹㅁㅂㅇ")


def test_minimal_pairs():
    assert minimal_pairs("불", "풀") is True
    assert minimal_pairs("달", "탈") is True
    assert minimal_pairs("살", "쌀") is True
    assert minimal_pairs("불", "바다") is False
    assert minimal_pairs("불", "불") is False
