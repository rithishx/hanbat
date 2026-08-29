"""
Mandarin engines.

Tone sandhi gets the most coverage, because it is Mandarin's equivalent of
Korean's 받침 rules and Japanese's mora timing: the thing a learner gets wrong
invisibly for months. 你好 is written with two third tones and said with a
rising tone and a third — and a learner who says it as written is understood,
but never sounds like they speak the language.

The second thing tested hard here is what Mandarin does *not* have. There is no
conjugation, no honorific system and no particles of the Korean or Japanese
kind, and the module has to say so rather than quietly returning a word
unchanged and calling it a conjugation.
"""

from __future__ import annotations

import pytest

from app.languages.mandarin import grammar as G
from app.languages.mandarin import pinyin as P
from app.languages.mandarin import tones as T
from app.languages.mandarin.confusions import CONFUSIONS
from app.languages.mandarin.grammar import ENGINE as GRAMMAR
from app.languages.mandarin.levels import ENGINE as LEVELS
from app.languages.mandarin.pronunciation import ENGINE as PRON
from app.languages.mandarin.transliteration import ENGINE as TRANSLIT
from app.languages.mandarin.writing import HANZI, PINYIN


# ==========================================================================
# The syllable inventory
# ==========================================================================

def test_initials_and_finals_are_complete():
    assert len(P.INITIALS) == 21
    for expected in ("b", "p", "zh", "ch", "sh", "r", "j", "q", "x", "z", "c", "s"):
        assert expected in P.INITIALS
    for expected in ("a", "ai", "ang", "iong", "ü", "üe", "er"):
        assert expected in P.FINALS


def test_initials_are_matched_longest_first():
    """zh must win over z, or every retroflex syllable parses wrong."""
    assert P.parse("zhōng").initial == "zh"
    assert P.parse("zōng").initial == "z"
    assert P.parse("chī").initial == "ch"
    assert P.parse("cì").initial == "c"


@pytest.mark.parametrize("text,initial,final,tone", [
    ("mā", "m", "a", 1),
    ("hǎo", "h", "ao", 3),
    ("zhōng", "zh", "ong", 1),
    ("guó", "g", "uo", 2),
    ("xué", "x", "üe", 2),          # the umlaut is not written after x
    ("qù", "q", "ü", 4),
    ("ma", "m", "a", 5),            # no mark means neutral, not "unknown"
    ("yī", "", "i", 1),             # y stands in for the glide
    ("wǔ", "", "u", 3),
])
def test_parse(text, initial, final, tone):
    s = P.parse(text)
    assert s.valid, s.note
    assert (s.initial, s.final, s.tone) == (initial, final, tone)


def test_the_hidden_i_is_flagged_not_silently_wrong():
    """The i of shi is not the i of ni, and the spelling hides it."""
    s = P.parse("shī")
    assert s.valid
    assert "not the ee sound" in s.note
    assert not P.parse("nǐ").note


def test_umlaut_survives_where_it_is_contrastive():
    """nu and nü are different words, so n and l keep the dots."""
    assert P.parse("nǔ").final == "u"
    assert P.parse("nǚ").final == "ü"
    assert P.parse("nǚ").plain == "nü"
    assert P.parse("lǜ").final == "ü"


def test_tone_marks_land_on_the_right_vowel():
    assert P.add_tone_mark("hao", 3) == "hǎo"       # a wins
    assert P.add_tone_mark("gou", 3) == "gǒu"       # ou -> the o
    assert P.add_tone_mark("jiu", 3) == "jiǔ"       # otherwise the last vowel
    assert P.add_tone_mark("gui", 4) == "guì"
    assert P.add_tone_mark("xue", 2) == "xué"       # e wins over u
    assert P.add_tone_mark("ma", 5) == "ma"         # neutral gets no mark


def test_round_trip_through_the_numbered_form():
    for word in ("mā", "hǎo", "zhōng", "guó", "xué", "nǚ", "jiǔ", "guì"):
        s = P.parse(word)
        assert P.parse(s.numbered).marked == word


def test_invalid_syllables_say_why():
    s = P.parse("xoq")
    assert not s.valid
    assert "not a pinyin final" in s.note


# ==========================================================================
# Segmentation — pinyin is written without spaces
# ==========================================================================

@pytest.mark.parametrize("text,expected", [
    ("Zhōngguó", ["Zhōng", "guó"]),
    ("péngyou", ["péng", "you"]),
    ("xièxie", ["xiè", "xie"]),
    ("wèishénme", ["wèi", "shén", "me"]),
    ("huǒchēzhàn", ["huǒ", "chē", "zhàn"]),
    ("nǐ hǎo", ["nǐ", "hǎo"]),
])
def test_segment(text, expected):
    assert P.segment(text) == expected


def test_the_apostrophe_is_a_real_boundary():
    """nǚ'ér is two syllables. Without the apostrophe it would read as nǚr."""
    assert P.segment("nǚ'ér") == ["nǚ", "ér"]
    assert len(P.segment("nǚér")) == 1        # and that one is 儿化


def test_erhua_is_a_suffix_not_a_final():
    s = P.parse("nǎr")
    assert s.valid and s.erhua
    assert s.final == "a"
    assert s.plain == "nar"
    assert not P.parse("ér").erhua            # er is a real final


def test_an_unsplittable_run_is_returned_whole_so_parse_can_explain():
    assert P.segment("xoqz") == ["xoqz"]
    assert not P.parse("xoqz").valid


# ==========================================================================
# Tone sandhi — the reason this module exists
# ==========================================================================

def test_third_tone_sandhi():
    assert T.apply_sandhi("nǐ hǎo").spoken == "ní hǎo"
    assert T.apply_sandhi("hěn hǎo").spoken == "hén hǎo"


def test_third_tone_sandhi_runs_left_to_right():
    """我很好 is 2-2-3, not 3-2-3.

    The rule applies against the *underlying* tones, left to right. Running it
    right to left — or against tones already changed by an earlier step — gives
    3-2-3, which is wrong and is the mistake this test was written to catch.
    """
    res = T.apply_sandhi("wǒ hěn hǎo")
    assert res.spoken_tones == [2, 2, 3]
    assert res.spoken == "wó hén hǎo"


def test_bu_sandhi():
    assert T.apply_sandhi("bù shì").spoken == "bú shì"
    assert T.apply_sandhi("bù hǎo").spoken == "bù hǎo"     # unchanged before 3


def test_yi_sandhi():
    assert T.apply_sandhi("yī gè").spoken == "yí gè"       # before a 4th tone
    assert T.apply_sandhi("yī qǐ").spoken == "yì qǐ"       # before the others
    # As an ordinal or a bare number it does not change at all.
    assert T.apply_sandhi("yī", hints={"yi_is_ordinal": True}).spoken == "yī"


def test_nothing_changes_when_nothing_should():
    res = T.apply_sandhi("jīn tiān")
    assert not res.changed
    assert res.spoken == res.written
    assert res.changes == []


def test_neutral_tone_is_never_applied_automatically():
    """中国 is Zhōngguó, not Zhōngguo.

    An earlier version auto-neutralised every syllable on a "commonly neutral"
    list and mispronounced the name of the country. The list is documentation
    now: an unmarked syllable already parses as neutral, so the content file
    decides and the engine does not guess.
    """
    assert T.apply_sandhi("Zhōngguó").spoken_tones == [1, 2]
    assert T.apply_sandhi("péngyou").spoken_tones == [2, 5]
    assert "guo" in T.COMMONLY_NEUTRAL
    assert not hasattr(T, "ALWAYS_NEUTRAL")


def test_explain_gives_a_simple_reason_and_a_technical_one():
    out = T.explain("nǐ hǎo")
    assert out["changed"]
    step = out["steps"][0]
    assert step["child_explanation"] and step["linguistic_explanation"]
    assert step["child_explanation"] != step["linguistic_explanation"]
    # The patient-teacher version must not reach for terminology.
    assert "sandhi" not in step["child_explanation"].lower()


def test_all_twenty_tone_pairs_are_drillable():
    drills = T.tone_pair_drills()
    assert len(drills) == 20
    assert {d["pair"] for d in drills} == {
        f"{a}-{b}" for a in range(1, 5) for b in range(1, 6)}
    assert all(d.get("difficulty") for d in drills)
    third_third = next(d for d in drills if d["pair"] == "3-3")
    assert "2-3" in third_third["note"]


def test_minimal_pairs_are_real_words_that_differ_only_in_tone():
    for group in T.minimal_pairs():
        plains = {P.parse(m["pinyin"]).plain for m in group["set"]}
        assert len(plains) == 1, f"{group['syllable']} members differ by more than tone"
        assert len({P.parse(m["pinyin"]).tone for m in group["set"]}) == len(group["set"])


# ==========================================================================
# What Mandarin does not have
# ==========================================================================

def test_mandarin_declares_no_conjugation():
    """The architectural claim, asserted.

    A shared grammar base class would have forced a `conjugate()` here that
    returned the word unchanged. There isn't one, and the capability is not
    declared, so no conjugation view is ever offered for Mandarin.
    """
    assert "conjugation" not in GRAMMAR.capabilities()
    assert not hasattr(GRAMMAR, "conjugate")


def test_capabilities_are_mandarins_own():
    caps = GRAMMAR.capabilities()
    assert {"tone_sandhi", "measure_words", "aspect_particles"} <= caps
    # Korean's and Japanese's grammar features are absent, not stubbed.
    assert not ({"honorifics", "speech_levels", "keigo", "counters"} & caps)


def test_drill_forms_differ_by_part_of_speech():
    noun = {f["form_id"]: f for f in GRAMMAR.drill_forms(
        {"term": "书", "pos": "noun", "counter": "本"})}
    verb = {f["form_id"]: f for f in GRAMMAR.drill_forms({"term": "吃", "pos": "verb"})}
    assert "measure" in noun and "measure" not in verb
    assert "aspect_了" in verb and "aspect_了" not in noun
    assert noun["measure"]["form"] == "一本书"
    assert verb["negative"]["form"] == "不吃"
    assert verb["negative_past"]["form"] == "没吃"


def test_a_noun_with_no_recorded_measure_word_falls_back_to_the_safe_one():
    """个 is what a speaker reaches for when they are unsure, so it is what the
    app shows — rather than guessing a specific one and teaching it wrong."""
    forms = {f["form_id"]: f for f in GRAMMAR.drill_forms(
        {"term": "东西", "pos": "noun"})}
    assert forms["measure"]["form"] == "一个东西"


# ==========================================================================
# Grammar reference data
# ==========================================================================

def test_measure_words_carry_a_default_and_a_reason():
    words = {m["word"]: m for m in G.MEASURE_WORDS}
    assert "个" in words
    assert "when you do not know" in words["个"]["note"].lower()
    for m in G.MEASURE_WORDS:
        assert m["examples"], f"{m['word']} needs examples"
        assert m["for"]


def test_aspect_particles_warn_against_the_tense_reading():
    le = next(a for a in G.ASPECT if a["particle"] == "了")
    assert "not" in le["simple"].lower() and "past tense" in le["simple"].lower()
    assert le["warning"]


def test_word_order_puts_time_before_the_verb():
    assert G.WORD_ORDER["full"].index("Time") < G.WORD_ORDER["full"].index("Verb")
    assert G.WORD_ORDER["examples"]


# ==========================================================================
# Levels
# ==========================================================================

def test_hsk_runs_upward_unlike_jlpt():
    assert LEVELS.scheme == "HSK"
    assert LEVELS.levels[1] == "HSK1"
    assert LEVELS.levels[-1] == "HSK6"
    assert LEVELS.next_level("HSK1") == "HSK2"
    assert LEVELS.next_level("HSK6") is None


def test_a_beginner_who_cannot_read_pinyin_stays_at_the_bottom():
    assert LEVELS.estimate(0.2, 400, 40, 90) == "pre-HSK1"


def test_tutor_notes_tell_the_model_what_mandarin_does_not_do():
    from app.languages.mandarin.levels import TUTOR_NOTES

    assert "no conjugation" in TUTOR_NOTES.lower()
    assert "measure word" in TUTOR_NOTES.lower()
    assert "了" in TUTOR_NOTES


# ==========================================================================
# Writing systems
# ==========================================================================

def test_pinyin_is_a_closed_inventory_and_hanzi_is_not():
    assert PINYIN.is_closed_inventory is True
    assert HANZI.is_closed_inventory is False
    units = PINYIN.units()
    kinds = {u["kind"] for u in units}
    assert kinds == {"initial", "final", "tone"}
    assert len(units) > 50


def test_hanzi_reports_an_empty_inventory_rather_than_inventing_one():
    """No character content is authored yet, and the engine says so."""
    assert HANZI.units() == []


# ==========================================================================
# Transliteration — the one language where romanisation does not go away
# ==========================================================================

def test_pinyin_is_not_a_crutch_to_be_removed():
    assert TRANSLIT.fully_removable is False
    assert TRANSLIT.remove_by_level is None


def test_pinyin_cannot_be_derived_from_characters():
    """The honest blank.

    行 is xíng in 不行 and háng in 银行. Without a dictionary there is no
    answer, so the engine returns "" and says why — rather than echoing the
    characters back into a field the UI will label "pinyin".
    """
    assert TRANSLIT.transliterate("银行") == ""
    assert TRANSLIT.can_transliterate("银行") is False
    assert TRANSLIT.can_transliterate("yín háng") is True
    warnings = TRANSLIT.ambiguity_warnings("银行")
    assert any("dictionary" in w for w in warnings)


def test_transliteration_converts_between_pinyin_spellings():
    assert TRANSLIT.transliterate("ni3 hao3") == "nǐ hǎo"
    assert TRANSLIT.transliterate("nǐ hǎo", style="numbered") == "ni3 hao3"


def test_warnings_flag_the_traps():
    warnings = TRANSLIT.ambiguity_warnings("nǐ hǎo")
    assert any("third tone" in w.lower() for w in warnings)
    assert any("i" in w for w in TRANSLIT.ambiguity_warnings("shī"))


# ==========================================================================
# Pronunciation difficulties
# ==========================================================================

def test_tones_are_ranked_as_the_hardest_thing():
    points = PRON.difficulty_points()
    high = [d for d in points if d["severity"] == "high"]
    assert any(d["id"] == "tones" for d in high)
    assert any(d["id"] == "retroflex_vs_palatal" for d in high)
    for d in points:
        assert d["why_hard"] and d["fix"], f"{d['id']} must say why and how"


def test_pronounce_returns_the_spoken_form_and_explain_shows_the_working():
    out = PRON.pronounce("nǐ hǎo")
    assert out["spoken"] == "ní hǎo"
    assert out["changed"] is True
    assert PRON.explain("nǐ hǎo")["steps"]


# ==========================================================================
# Confusions
# ==========================================================================

def test_confusions_are_mandarins_own_problems():
    assert set(CONFUSIONS) >= {"le_is_not_past", "bu_vs_mei", "tone_2_vs_3",
                               "j_vs_zh", "measure_words"}
    for c in CONFUSIONS.values():
        assert c.simple and c.rule and c.one_line
        assert c.simple != c.rule, f"{c.id}: the two explanations must differ"
        assert c.examples, f"{c.id} needs examples"
        for ex in c.examples:
            assert ex.get("target"), f"{c.id}: an example has no target text"


def test_the_le_confusion_says_the_thing_that_costs_learners_years():
    c = CONFUSIONS["le_is_not_past"]
    assert "completion" in c.one_line.lower()
    assert "past tense" in c.title.lower()
    assert "明天" in c.simple, "the future example is the one that makes it land"
