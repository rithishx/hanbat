"""Hangul composition/decomposition must round-trip all 11,172 syllables."""

import pytest

from app.languages.korean import hangul as H


def test_all_syllables_round_trip():
    """Every modern Hangul block decomposes and recomposes to itself."""
    for code in range(H.SBASE, H.SBASE + H.SCOUNT):
        ch = chr(code)
        syl = H.decompose(ch)
        assert syl is not None
        assert syl.char == ch


def test_compose_basic():
    assert H.compose("ㅎ", "ㅏ", "ㄴ") == "한"
    assert H.compose("ㄱ", "ㅏ") == "가"
    assert H.compose("ㅇ", "ㅏ", "ㄴ") == "안"
    assert H.compose("ㅁ", "ㅜ", "ㄹ") == "물"
    assert H.compose("ㅂ", "ㅏ", "ㄺ") == "밝"


def test_decompose_basic():
    assert H.decompose("한") == H.Syllable("ㅎ", "ㅏ", "ㄴ")
    assert H.decompose("가") == H.Syllable("ㄱ", "ㅏ", "")
    assert H.decompose("값") == H.Syllable("ㄱ", "ㅏ", "ㅄ")
    assert H.decompose("A") is None


def test_compose_rejects_invalid():
    with pytest.raises(ValueError):
        H.compose("ㅏ", "ㅏ")            # vowel in the initial slot
    with pytest.raises(ValueError):
        H.compose("ㄱ", "ㄴ")            # consonant in the vowel slot
    with pytest.raises(ValueError):
        H.compose("ㄱ", "ㅏ", "ㄸ")      # ㄸ can never be a batchim


def test_jamo_round_trip():
    for word in ["한국어", "안녕하세요", "값", "닭", "읽었습니다", "괜찮아요"]:
        assert H.from_jamo(H.to_jamo(word)) == word


def test_to_jamo_splits_compounds_on_request():
    assert H.to_jamo("한") == ["ㅎ", "ㅏ", "ㄴ"]
    assert H.to_jamo("값", split_compounds=True) == ["ㄱ", "ㅏ", "ㅂ", "ㅅ"]
    assert H.to_jamo("화", split_compounds=True) == ["ㅎ", "ㅗ", "ㅏ"]


def test_batchim_detection():
    assert H.ends_with_batchim("책") is True
    assert H.ends_with_batchim("사과") is False
    assert H.ends_with_batchim("값") is True
    assert H.final_of("책") == "ㄱ"
    assert H.final_of("사과") == ""


def test_particle_selection():
    """The single most-used fact in Korean grammar."""
    assert H.attach_particle("책", H.OBJECT) == "책을"
    assert H.attach_particle("사과", H.OBJECT) == "사과를"
    assert H.attach_particle("선생님", H.TOPIC) == "선생님은"
    assert H.attach_particle("친구", H.TOPIC) == "친구는"
    assert H.attach_particle("물", H.SUBJECT) == "물이"
    assert H.attach_particle("커피", H.SUBJECT) == "커피가"
    assert H.attach_particle("학생", H.COPULA) == "학생이에요"
    assert H.attach_particle("의사", H.COPULA) == "의사예요"


def test_layout_classification():
    assert H.decompose("하").layout == "side_by_side"
    assert H.decompose("호").layout == "stacked"
    assert H.decompose("화").layout == "wrapped"
    assert H.decompose("한").layout == "side_by_side_with_batchim"
    assert H.decompose("혼").layout == "stacked_with_batchim"


def test_describe_syllable():
    d = H.describe_syllable("한")
    assert d["formula"] == "ㅎ + ㅏ + ㄴ = 한"
    assert d["initial_name"] == "히읗"
    assert d["final_name"] == "니은"
    assert d["has_batchim"] is True

    d = H.describe_syllable("아")
    assert d["initial_silent"] is True


def test_jamo_inventory_sizes():
    assert len(H.INITIALS) == 19
    assert len(H.MEDIALS) == 21
    assert len(H.FINALS) == 28
    assert len(H.BASIC_CONSONANTS) == 14
    assert len(H.TENSE_CONSONANTS) == 5
    assert len(H.BASIC_VOWELS) == 10
    assert len(H.SEVEN_FINAL_SOUNDS) == 7


def test_syllable_grid():
    grid = H.syllable_grid(["ㄱ", "ㄴ"], ["ㅏ", "ㅑ"])
    assert grid == [["가", "갸"], ["나", "냐"]]
