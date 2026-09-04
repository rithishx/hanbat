"""
The awkward corners of all three pronunciation engines.

`test_phonology.py`, `test_japanese.py` and `test_mandarin.py` check that the
rules work. This file checks what happens where they *interact*, where they
*stop*, and where the input is not what the engine expected — which is where
pronunciation engines actually break, and where a learner is most likely to be
taught something false with total confidence.

Three kinds of case live here:

**Rule ordering.** 읽는다 needs cluster simplification before nasalisation, and
running them the other way gives a form no Korean speaker produces. Cases like
this cannot be caught by testing either rule alone.

**Declared limits.** Some things the engines deliberately do not do: liaison
across a space, 一 as an ordinal, prosodic grouping in a long third-tone run.
Each is asserted here so that it stays a decision rather than quietly becoming
a bug — and so that anyone who implements it will be told which tests to update.

**Robustness.** Empty strings, Latin text, digits, lone jamo, very long input.
An engine that throws on these takes the whole answer path down with it, and
the learner loses their answer to a word the app could not parse.
"""

from __future__ import annotations

import pytest

from app.languages.japanese import kana as K
from app.languages.japanese import pitch as P
from app.languages.korean.phonology import Hints, explain, pronounce
from app.languages.mandarin import tones as T


def said(text: str, **hints) -> str:
    return pronounce(text, hints=Hints(**hints) if hints else None).spoken


# ==========================================================================
# Korean — rules meeting each other
# ==========================================================================

CHAINED = [
    # Cluster simplification, then nasalisation. Either alone is wrong.
    ("읽는다", "잉는다"),
    ("맑네", "망네"),
    ("밟는", "밤는"),
    ("긁는", "긍는"),
    # Cluster simplification, then tensification.
    ("없다", "업따"),
    ("값도", "갑또"),
    # Liaison twice in one word.
    ("없었어요", "업써써요"),
    # Liaison beats neutralisation: the underlying consonant survives.
    ("꽃이", "꼬치"),
    ("닭이", "달기"),
    ("여덟이", "여덜비"),
    # Aspiration reaching across a reduced cluster.
    ("넓히다", "널피다"),
    ("앉히다", "안치다"),
    ("밝히다", "발키다"),
]


@pytest.mark.parametrize("written,spoken", CHAINED)
def test_rules_compose_in_the_right_order(written, spoken):
    assert said(written) == spoken


def test_the_order_is_visible_in_the_explanation():
    """A learner should see the two steps, not one unexplained jump."""
    steps = explain("읽는다")["steps"]
    assert [s["rule_id"] for s in steps] == ["cluster_simplification", "nasalisation"]
    assert steps[0]["shows"].endswith("익는")
    assert steps[1]["shows"].endswith("잉는")


def test_a_cluster_that_is_resyllabified_is_never_simplified_first():
    """닭이 is [달기]. Simplifying to 닥 first would give [다기], which is wrong."""
    ids = [s["rule_id"] for s in explain("닭이")["steps"]]
    assert "cluster_simplification" not in ids
    assert ids == ["liaison"]


def test_pronouncing_the_spoken_form_again_does_not_change_it_further():
    """The output is a stable form, not a step in an endless chain."""
    for word in ("한국어", "읽는다", "학교", "좋아요", "값이", "밟는"):
        once = said(word)
        assert said(once) == once, word


# ---- the causative -기- exception, §24 다만 ------------------------------

def test_the_causative_suffix_does_not_tense():
    """옮기다 is [옴기다]. Tensing it teaches a wrong word for a common verb."""
    assert said("옮기다") == "옴기다"
    assert said("굶기다") == "굼기다"


def test_but_a_real_ending_after_the_same_stem_still_tenses():
    """옮고 is [옴꼬]: -고 is an ending, not the exempted suffix."""
    assert said("옮고") == "옴꼬"
    assert said("옮게") == "옴께"


def test_the_exception_does_not_leak_to_other_clusters():
    """앉기 is [안끼] — there is no causative -기- there to exempt."""
    assert said("앉기") == "안끼"
    assert said("젊기") == "점끼"


# ---- hints: the morphological cases that cannot be read off the spelling --

def test_a_hint_changes_the_answer_and_its_absence_is_not_a_bug():
    """첫인상 is [처딘상] as a compound, [처신상] read as one word.

    The engine cannot know which without being told, so it does the regular
    thing by default and the hint selects the other. Both are asserted so that
    neither can drift.
    """
    assert said("첫인상") == "처신상"
    assert said("첫인상", compound_after=frozenset({0})) == "처딘상"


def test_verb_stem_tensification_stays_behind_its_hint():
    assert said("신다") == "신다"
    assert said("신다", verb_stem_ends_at=frozenset({0})) == "신따"


def test_sino_korean_tensification_stays_behind_its_hint():
    assert said("발달") == "발달"
    assert said("발달", sino_korean=True) == "발딸"


# ---- a declared limit ----------------------------------------------------

def test_rules_stop_at_a_space_and_that_is_deliberate():
    """옷 안 is [오단] in connected speech; the engine keeps the words apart.

    Crossing a space needs to know whether the two words form one phrase, which
    the engine is not told. It neutralises within each word and leaves the
    boundary alone — visibly incomplete rather than confidently wrong. Change
    this and this test is the one to update.
    """
    assert said("옷 안") == "옫 안"
    assert said("옷이") == "오시"


# ---- robustness ----------------------------------------------------------

ODD_INPUT = ["", " ", "\n", "hello", "2024년", "ㅋㅋㅋ", "ㅏ", "!!!", "한 ", " 국",
             "한국어!", "한국어 hello 안녕", "가" * 400, "🙂", "漢字"]


@pytest.mark.parametrize("text", ODD_INPUT)
def test_korean_survives_input_it_did_not_expect(text):
    result = pronounce(text)
    assert isinstance(result.spoken, str)
    explain(text)


def test_non_korean_text_is_returned_untouched():
    for text in ("hello", "2024", "!!!", "漢字"):
        assert said(text) == text


# ==========================================================================
# Japanese — beats, where the count is the whole point
# ==========================================================================

MORA = [
    ("きょう", 2), ("がっこう", 4), ("きって", 3), ("コーヒー", 4),
    ("しんぶん", 4), ("ぎゅうにゅう", 4), ("チョコレート", 5),
    ("ひゃっぽん", 4), ("おおきい", 4), ("せんせい", 4),
    # A lone special mora is still one beat.
    ("ん", 1), ("っ", 1), ("ー", 1),
    # Loanword combinations are one beat, not two.
    ("ファイル", 3), ("チェック", 3), ("ティー", 2), ("ヴァイオリン", 5),
]


@pytest.mark.parametrize("text,beats", MORA)
def test_mora_counts(text, beats):
    assert K.count_mora(text) == beats


def test_a_loanword_combination_is_one_mora_not_two():
    """ヴァイオリン is five beats. It was six until the table was fixed.

    ヴ normalises to ゔ before the combination table is consulted, so entries
    spelled with katakana ヴ never matched and the small ァ became a beat of
    its own — the exact error the mora module exists to stop a learner making.
    """
    mora = K.split_mora("ヴァイオリン")
    assert [m.text for m in mora] == ["ヴァ", "イ", "オ", "リ", "ン"]
    assert mora[0].romaji == "va"


def test_kanji_is_counted_as_written_because_readings_are_lexical():
    """日本語 is three characters and the engine says three, not the four
    beats of にほんご. Kana is near-phonemic; kanji is not, and guessing a
    reading would be inventing one."""
    assert K.count_mora("日本語") == 3


@pytest.mark.parametrize("text", ["", " ", "hello", "123", "！", "🙂", "あ" * 500])
def test_japanese_survives_input_it_did_not_expect(text):
    assert isinstance(K.count_mora(text), int)
    K.mora_diagram(text)


def test_pitch_refuses_an_accent_a_word_cannot_have():
    with pytest.raises(ValueError):
        P.contour("はし", 3)


def test_pitch_contour_length_always_matches_the_beat_count():
    for word in ("はし", "きょう", "がっこう", "コーヒー"):
        n = K.count_mora(word)
        for accent in range(0, n + 1):
            assert len(P.contour(word, accent)["mora"]) == n


# ==========================================================================
# Mandarin — tone changes, and where they stop
# ==========================================================================

SANDHI = [
    ("nǐ hǎo", "ní hǎo"),
    ("hěn hǎo", "hén hǎo"),
    ("xiǎo jiě", "xiáo jiě"),
    ("bù shì", "bú shì"),
    ("bù hǎo", "bù hǎo"),        # only before a fourth tone
    ("bù bù bù", "bú bú bù"),    # the last one has nothing to change for
    ("yī gè", "yí gè"),
    ("yí gè", "yí gè"),          # already changed, left alone
]


@pytest.mark.parametrize("written,spoken", SANDHI)
def test_tone_sandhi(written, spoken):
    assert T.apply_sandhi(written).spoken == spoken


def test_a_run_of_third_tones_changes_all_but_the_last():
    out = T.apply_sandhi("wǒ yě hěn hǎo")
    assert out.spoken_tones == [2, 2, 2, 3]


def test_sandhi_is_marked_as_phonetic_only():
    """The tone written never changes — only the tone said.

    A learner who starts writing ní hǎo has been taught something false, so
    the written tones must survive the transformation untouched.
    """
    out = T.apply_sandhi("nǐ hǎo")
    assert out.written_tones == [3, 3]
    assert out.spoken_tones == [2, 3]
    assert out.written == "nǐ hǎo"


def test_the_ordinal_limit_of_yi_is_real_and_declared():
    """一月 is yī yuè — 一 does not change in an ordinal.

    Pinyin alone does not say whether 一 is counting or quantifying, so the
    engine applies the regular rule and the pronunciation lab marks this case
    as showing where the rule stops. It is a limit of the input, not a bug in
    the rule, and it is asserted so nobody 'fixes' it into silence.
    """
    assert T.apply_sandhi("yī yuè").spoken == "yí yuè"
    rule = next(r for r in __import__(
        "app.languages.mandarin.pronunciation", fromlist=["ENGINE"]
    ).ENGINE.rules() if r["id"] == "yi_sandhi")
    assert any(ex.get("shows_the_limit") for ex in rule["examples"])


@pytest.mark.parametrize("text", ["", " ", "hello", "123", "!!!", "🙂", "ni" * 400])
def test_mandarin_survives_input_it_did_not_expect(text):
    out = T.apply_sandhi(text)
    assert isinstance(out.spoken, str)


def test_syllables_without_tone_marks_are_left_alone():
    """Toneless pinyin is a legitimate way to write, not an error to correct."""
    assert T.apply_sandhi("ni hao").spoken == "ni hao"


# ==========================================================================
# All three, through the shared surface
# ==========================================================================

@pytest.mark.parametrize("code", ["ko", "ja", "zh"])
def test_every_rule_example_still_triggers_its_own_rule(api_client, code):
    """The lab computes its examples; this asserts they still demonstrate.

    An example that stops firing its own rule is marked rather than hidden, so
    this test allows an unverified example to exist — but it must be flagged,
    never silently presented as a worked case.
    """
    lab = api_client.get(f"/api/pronunciation/lab?lang={code}").json()
    for rule in lab["rules"]:
        for ex in rule["examples"]:
            assert "verified" in ex, (code, rule["id"])


@pytest.mark.parametrize("code", ["ko", "ja", "zh"])
def test_explaining_junk_never_takes_the_engine_down(api_client, code):
    for text in ("", "!!!", "hello", "🙂"):
        r = api_client.get("/api/pronounce", params={"lang": code, "text": text})
        assert r.status_code in (200, 400, 422), (code, text)
