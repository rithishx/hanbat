"""
Why an answer was wrong.

The load-bearing test in this file is the careless one. Everything else in the
adaptive engine keys off "this learner is weak at X", and a learner who mistypes
a word they know must not have that word pushed back at them — that is the
system mistaking haste for ignorance, and it wastes exactly the study time the
whole application exists to spend well.
"""

from __future__ import annotations

import pytest

from app.engines import diagnosis as D


def history(seen=0, correct=0, last=False, median=0) -> D.ItemHistory:
    return D.ItemHistory(seen=seen, correct=correct,
                         last_was_correct=last, median_response_ms=median)


# ==========================================================================
# The six knowledge reasons
# ==========================================================================

@pytest.mark.parametrize("skill,reason", [
    ("vocabulary", "vocabulary"),
    ("grammar", "grammar"),
    ("pronunciation", "pronunciation"),
    ("listening", "listening"),
    ("reading", "reading"),
    ("writing", "writing"),
])
def test_the_exercise_says_what_was_being_tested(skill, reason):
    d = D.diagnose(skill=skill, expected="가", given="나")
    assert d.reason == reason
    assert d.because


def test_speaking_is_reported_as_pronunciation():
    """A learner does not experience a mispronunciation as a separate
    "speaking" problem, and the fix is the same either way."""
    assert D.diagnose(skill="speaking", expected="한국", given="항국").reason == "pronunciation"


def test_an_unknown_skill_does_not_crash():
    assert D.diagnose(skill="telepathy", expected="a", given="b").reason in D.REASONS


def test_every_reason_has_advice_a_learner_can_act_on():
    for reason in D.REASONS:
        info = D.REASON_INFO[reason]
        assert info["name"] and info["simple"] and info["advice"]


# ==========================================================================
# Careless — the reason that must not become a weakness
# ==========================================================================

def test_a_typo_on_something_already_known_is_careless():
    d = D.diagnose(
        skill="vocabulary", expected="먹어요", given="먹어여",
        history=history(seen=6, correct=5, last=True, median=4000),
        response_ms=3800,
    )
    assert d.reason == "careless"
    assert d.counts_as_weakness is False
    assert "right before" in d.because


def test_a_typo_on_something_never_answered_correctly_is_a_real_gap():
    """The near-miss signal is only trustworthy with prior success behind it.

    Without that, "one character out" is just as likely to be a half-learned
    word, and calling it carelessness would let a real gap hide.
    """
    d = D.diagnose(
        skill="vocabulary", expected="먹어요", given="먹어여",
        history=history(seen=3, correct=0),
    )
    assert d.reason == "vocabulary"


def test_answering_far_too_fast_on_a_known_item_is_careless():
    d = D.diagnose(
        skill="grammar", expected="먹었습니다", given="먹습니다다",
        history=history(seen=10, correct=9, last=True, median=6000),
        response_ms=900,
    )
    assert d.reason == "careless"
    assert d.evidence["your_median_ms"] == 6000


def test_one_character_apart_is_not_a_near_miss_on_a_one_character_answer():
    """은 versus 는 differ by one character and are the most consequential
    particle distinction in Korean. Excusing that as a typo would hide the
    exact confusion the whole adaptive engine exists to catch."""
    d = D.diagnose(
        skill="grammar", expected="은", given="는",
        history=history(seen=10, correct=9, last=True, median=6000),
        response_ms=5800,
    )
    assert d.reason == "grammar"


def test_a_long_answer_one_character_out_is_still_a_near_miss():
    d = D.diagnose(
        skill="writing", expected="안녕하세요", given="안녕하세오",
        history=history(seen=4, correct=3, last=True, median=5000),
        response_ms=4800,
    )
    assert d.reason == "careless"


def test_a_wrong_multiple_choice_pick_is_never_careless():
    """Choosing the wrong option is a decision, not a slip of the fingers.

    Excusing it as carelessness would hide exactly the confusions the adaptive
    engine exists to find.
    """
    d = D.diagnose(
        skill="vocabulary", expected="개", given="게",
        history=history(seen=8, correct=7, last=True, median=4000),
        response_ms=3900,
        had_options=True,
    )
    assert d.reason == "vocabulary"


def test_a_blank_answer_is_a_gap_however_fast_it_arrived():
    d = D.diagnose(
        skill="writing", expected="먹어요", given="   ",
        history=history(seen=9, correct=8, last=True, median=8000),
        response_ms=300,
    )
    assert d.reason == "writing"
    assert d.evidence["blank"] is True


def test_a_wildly_different_answer_is_not_a_slip():
    d = D.diagnose(
        skill="vocabulary", expected="안녕하세요", given="감사합니다",
        history=history(seen=5, correct=4, last=True, median=4000),
        response_ms=3500,
    )
    assert d.reason == "vocabulary"


def test_a_first_encounter_can_never_be_careless():
    d = D.diagnose(skill="vocabulary", expected="책", given="채",
                   history=history(), response_ms=100)
    assert d.reason == "vocabulary"


# ==========================================================================
# Confusions know better than the skill label
# ==========================================================================

def test_a_sound_confusion_is_diagnosed_as_pronunciation():
    """Mandarin's j/zh pair arrives through a listening exercise but is a
    pronunciation problem. The language module's own tags say which."""
    d = D.diagnose(skill="listening", expected="jī", given="zhī",
                   confusion_tags=("pronunciation", "HSK1"))
    assert d.reason == "pronunciation"


def test_a_structural_confusion_is_diagnosed_as_grammar():
    d = D.diagnose(skill="vocabulary", expected="은", given="이",
                   confusion_tags=("particles", "A1"))
    assert d.reason == "grammar"


def test_the_tags_come_from_the_language_not_from_here():
    """Every registered confusion tags itself; nothing here names a language."""
    from app.languages import registry

    for code in ("ko", "ja", "zh"):
        tagged = [c for c in registry.get(code).confusions.values() if c.tags]
        assert tagged, f"{code} confusions carry no tags"


# ==========================================================================
# Edit distance
# ==========================================================================

@pytest.mark.parametrize("a,b,n", [
    ("", "", 0),
    ("abc", "abc", 0),
    ("abc", "abd", 1),
    ("abc", "ab", 1),
    ("abc", "", 3),
    ("먹어요", "먹어여", 1),
    ("먹어요", "먹었어요", 1),
    ("kitten", "sitting", 3),
])
def test_edit_distance(a, b, n):
    assert D.edit_distance(a, b) == n


def test_edit_distance_is_symmetric():
    assert D.edit_distance("한국어", "한국") == D.edit_distance("한국", "한국어")


# ==========================================================================
# Summarising a learner's pattern
# ==========================================================================

def test_a_dominant_reason_is_named():
    s = D.summarise(["grammar"] * 7 + ["vocabulary", "listening"])
    assert s["dominant"] == "grammar"
    assert "one thing to fix" in s["note"]


def test_careless_slips_are_counted_apart_from_real_gaps():
    """A learner with thirty slips and two gaps has a different problem from
    one with thirty gaps, and the advice has to differ too."""
    s = D.summarise(["careless"] * 30 + ["vocabulary", "grammar"])
    assert s["careless_total"] == 30
    assert s["real_total"] == 2
    assert "Slowing down" in s["note"]
    assert s["dominant"] in ("vocabulary", "grammar")


def test_no_mistakes_summarises_to_nothing_rather_than_crashing():
    s = D.summarise([])
    assert s["dominant"] is None
    assert s["real_total"] == 0
    assert s["note"] == ""
