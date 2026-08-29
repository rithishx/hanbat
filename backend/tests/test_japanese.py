"""
Japanese engines.

Mora counting gets the most coverage, because it is Japanese's equivalent of
Korean's 받침 rules: the thing a learner gets wrong invisibly for months and
that makes them hard to understand. きって and きて are different words.
"""

from __future__ import annotations

import pytest

from app.languages.japanese import kana as K
from app.languages.japanese import romaji as R
from app.languages.japanese import verbs as V
from app.languages.japanese.grammar import ENGINE as GRAMMAR
from app.languages.japanese.levels import ENGINE as LEVELS
from app.languages.japanese.pronunciation import ENGINE as PRON
from app.languages.japanese.writing import HIRAGANA, KANJI, KATAKANA


# ==========================================================================
# Kana inventory
# ==========================================================================

def test_gojuon_is_complete():
    assert len(K.GOJUON) == 46          # 一 the classic count
    assert len(K.DAKUTEN) == 20
    assert len(K.HANDAKUTEN) == 5


def test_hiragana_katakana_conversion_round_trips():
    for word in ["とうきょう", "こんにちは", "がっこう", "しゃしん", "ざっし"]:
        assert K.to_hiragana(K.to_katakana(word)) == word


def test_script_detection():
    assert K.is_hiragana("あ") and not K.is_hiragana("ア")
    assert K.is_katakana("ア") and not K.is_katakana("あ")
    assert K.is_kanji("学") and not K.is_kanji("あ")
    assert K.is_katakana("ー")           # the long-vowel mark is katakana


def test_voicing_relationships_are_recorded():
    assert K.VOICING_SOURCE["が"] == "か"
    assert K.VOICING_SOURCE["ぱ"] == "は"
    assert K.VOICING_SOURCE["ざ"] == "さ"


def test_inventory_is_in_teaching_order():
    units = K.inventory()
    stages = [u.teaching_stage for u in units]
    assert stages == sorted(stages)
    assert units[0].hiragana == "あ"


def test_chart_is_the_textbook_grid():
    grid = K.chart()
    assert grid[0] == ["あ", "い", "う", "え", "お"]
    assert grid[1] == ["か", "き", "く", "け", "こ"]
    assert grid[7] == ["や", None, "ゆ", None, "よ"]


# ==========================================================================
# Mora — the important one
# ==========================================================================

MORA = [
    ("あ", 1), ("ん", 1),
    ("にほん", 3), ("せんせい", 4), ("ともだち", 4),
    ("きょう", 2),        # yoon is one mora
    ("しゃしん", 3), ("りょこう", 3), ("べんきょう", 4),
    ("がっこう", 4),      # sokuon is its own mora
    ("きって", 3), ("ざっし", 3), ("ちょっと", 3), ("いっぱい", 4),
    ("コーヒー", 4),      # each ー is a mora
    ("ビール", 3), ("スーパー", 4),
    ("おばあさん", 5), ("おじいさん", 5),
    ("ふぁいる", 3),      # loanword combos are one mora
    ("とうきょう", 4),
]


@pytest.mark.parametrize("word,count", MORA)
def test_mora_count(word, count):
    assert K.count_mora(word) == count


def test_mora_kinds_are_labelled():
    mora = K.split_mora("がっこう")
    assert [m.kind for m in mora] == ["normal", "sokuon", "normal", "normal"]
    assert mora[1].is_silent is True


def test_yoon_is_one_mora_of_two_characters():
    mora = K.split_mora("きょう")
    assert len(mora) == 2
    assert mora[0].text == "きょ"
    assert mora[0].kind == "yoon"
    assert mora[0].romaji == "kyo"


def test_minimal_pairs_differ_by_exactly_one_mora():
    for p in K.minimal_pairs_by_mora():
        a, b = p["pair"]
        assert K.count_mora(a) == p["mora"][0]
        assert K.count_mora(b) == p["mora"][1]
        assert p["mora"][1] > p["mora"][0]


def test_mora_diagram_explains_the_timing():
    d = K.mora_diagram("がっこう")
    assert d["count"] == 4
    assert "（ ）" in d["beats"]            # the silent beat is shown
    assert "silence" in d["note"]


# ==========================================================================
# Romaji
# ==========================================================================

HEPBURN = [
    ("とうきょう", "tōkyō"), ("おおさか", "ōsaka"),
    ("きって", "kitte"), ("がっこう", "gakkō"), ("ざっし", "zasshi"),
    ("まっちゃ", "matcha"),
    ("しんぶん", "shinbun"), ("たんい", "tan'i"),
    ("しゃしん", "shashin"), ("ちょっと", "chotto"), ("じゅう", "jū"),
    ("コーヒー", "kōhī"), ("せんせい", "sensei"), ("にほん", "nihon"),
    ("つくえ", "tsukue"), ("ふじさん", "fujisan"),
]


@pytest.mark.parametrize("kana,expected", HEPBURN)
def test_hepburn(kana, expected):
    assert R.romanize(kana) == expected


def test_the_three_styles_serve_different_purposes():
    assert R.romanize("とうきょう", "hepburn") == "tōkyō"
    assert R.romanize("とうきょう", "simple") == "tokyo"
    assert R.romanize("とうきょう", "wapuro") == "toukyou"


TYPING = [
    ("toukyou", "とうきょう"), ("kitte", "きって"), ("gakkou", "がっこう"),
    ("shashin", "しゃしん"), ("konnichiha", "こんにちは"), ("matcha", "まっちゃ"),
    ("zasshi", "ざっし"), ("nihongo", "にほんご"), ("sensei", "せんせい"),
    ("kippu", "きっぷ"), ("ryokou", "りょこう"), ("anzen", "あんぜん"),
]


@pytest.mark.parametrize("typed,kana", TYPING)
def test_typing_romaji_produces_kana(typed, kana):
    assert R.to_kana(typed) == kana


def test_wapuro_round_trips():
    for word in ["とうきょう", "がっこう", "しゃしん", "こんにちは", "ざっし", "まっちゃ"]:
        assert R.to_kana(R.romanize(word, "wapuro")) == word


def test_romaji_warns_about_what_it_hides():
    warnings = R.ambiguity_warnings("とうきょうは")
    assert any("beat" in w or "long vowel" in w for w in warnings)
    assert any("wa" in w for w in warnings)


# ==========================================================================
# Verbs
# ==========================================================================

GODAN_TE = [
    ("書く", "書いて"), ("泳ぐ", "泳いで"), ("話す", "話して"),
    ("待つ", "待って"), ("取る", "取って"), ("買う", "買って"),
    ("死ぬ", "死んで"), ("遊ぶ", "遊んで"), ("読む", "読んで"),
]


@pytest.mark.parametrize("word,te", GODAN_TE)
def test_godan_te_form_sound_changes(word, te):
    assert V.conjugate(word)["te"].japanese == te


def test_iku_is_the_one_te_form_exception():
    """行く is godan く but gives 行って, not 行いて. The only one."""
    assert V.conjugate("行く")["te"].japanese == "行って"
    assert V.conjugate("書く")["te"].japanese == "書いて"


def test_ichidan_verbs_just_drop_ru():
    for word, masu in [("食べる", "食べます"), ("見る", "見ます"),
                       ("起きる", "起きます"), ("教える", "教えます")]:
        assert V.conjugate(word)["masu"].japanese == masu


def test_verbs_that_look_ichidan_but_are_godan():
    """帰る, 走る, 切る. A closed list, and getting them wrong is very visible."""
    for word, masu in [("帰る", "帰ります"), ("走る", "走ります"), ("切る", "切ります")]:
        assert V.classify(word).verb_class == "godan"
        assert V.conjugate(word)["masu"].japanese == masu


def test_kanji_hidden_ichidan_verbs_are_listed_not_guessed():
    """見る is ichidan but its spelling shows only 見. No rule recovers that."""
    assert V.classify("見る").verb_class == "ichidan"
    assert V.classify("食べる").verb_class == "ichidan"


def test_a_kanji_ru_verb_outside_the_list_reports_low_confidence():
    c = V.classify("殴る")
    assert c.confident is False
    assert "hidden inside the kanji" in c.note


def test_u_verbs_take_wa_not_a_in_the_negative():
    assert V.conjugate("買う")["nai"].japanese == "買わない"
    assert V.conjugate("会う")["nai"].japanese == "会わない"


def test_the_two_irregular_verbs():
    assert V.conjugate("する")["masu"].japanese == "します"
    assert V.conjugate("する")["te"].japanese == "して"
    assert V.conjugate("する")["potential"].japanese == "できる"
    assert V.conjugate("来る")["masu"].japanese == "来ます"
    assert V.conjugate("来る")["nai"].japanese == "来ない"
    assert V.conjugate("来る")["imperative"].japanese == "来い"


def test_kuru_keeps_its_kanji_while_the_reading_changes():
    """来ます, 来ない and 来て are all written 来 and read ki-, ko-, ki-."""
    forms = V.conjugate("来る")
    for f in ("masu", "nai", "te"):
        assert forms[f].japanese.startswith("来")
    # written in kana instead, the readings show
    kana_forms = V.conjugate("くる")
    assert kana_forms["masu"].japanese == "きます"
    assert kana_forms["nai"].japanese == "こない"


def test_suru_compounds_conjugate_like_suru():
    assert V.conjugate("勉強する")["masu"].japanese == "勉強します"
    assert V.conjugate("勉強する")["te"].japanese == "勉強して"
    assert V.classify("勉強する").verb_class == "suru"


def test_aru_is_irregular_only_in_the_negative():
    assert V.conjugate("ある")["masu"].japanese == "あります"
    assert V.conjugate("ある")["nai"].japanese == "ない"


def test_derived_forms():
    f = V.conjugate("書く")
    assert f["potential"].japanese == "書ける"
    assert f["volitional"].japanese == "書こう"
    assert f["passive"].japanese == "書かれる"
    assert f["causative"].japanese == "書かせる"
    assert f["ba"].japanese == "書けば"
    assert f["tara"].japanese == "書いたら"
    assert f["tai"].japanese == "書きたい"
    assert f["te_kudasai"].japanese == "書いてください"


def test_keigo_uses_separate_words_where_they_exist():
    f = V.conjugate("食べる")
    assert f["sonkei"].japanese == "召し上がる"
    assert f["kenjou"].japanese == "いただく"
    assert "separate word" in f["sonkei"].note


def test_keigo_falls_back_to_the_regular_pattern():
    f = V.conjugate("書く")
    assert f["sonkei"].japanese == "お書きになる"
    assert f["kenjou"].japanese == "お書きする"


# ==========================================================================
# Adjectives
# ==========================================================================

def test_i_adjectives():
    f = V.conjugate("高い")
    assert f["negative"].japanese == "高くない"
    assert f["past"].japanese == "高かった"
    assert f["te"].japanese == "高くて"
    assert f["adverb"].japanese == "高く"


def test_ii_is_the_one_irregular_i_adjective():
    f = V.conjugate("いい")
    assert f["negative"].japanese == "よくない"
    assert f["past"].japanese == "よかった"
    assert f["dictionary"].japanese == "いい"


def test_na_adjectives():
    f = V.conjugate("静か")
    assert f["negative"].japanese == "静かじゃない"
    assert f["past"].japanese == "静かだった"
    assert f["modifier"].japanese == "静かな"
    assert f["adverb"].japanese == "静かに"


def test_adjectives_have_no_potential_or_imperative():
    assert "potential" not in V.conjugate("高い")
    assert "imperative" not in V.conjugate("静か")


def test_no_form_is_empty():
    for word in ["書く", "食べる", "する", "来る", "ある", "帰る",
                 "高い", "いい", "静か", "勉強する"]:
        for fid, f in V.conjugate(word).items():
            assert f.japanese.strip(), f"{word}/{fid} produced an empty form"


# ==========================================================================
# The adapters
# ==========================================================================

def test_writing_systems_are_separate():
    assert HIRAGANA.id == "hiragana" and KATAKANA.id == "katakana"
    assert len(HIRAGANA.units()) == len(KATAKANA.units())
    assert HIRAGANA.units()[0]["unit"] != KATAKANA.units()[0]["unit"]


def test_kanji_is_an_open_inventory():
    assert KANJI.is_closed_inventory is False
    assert HIRAGANA.is_closed_inventory is True


def test_japanese_decomposes_into_mora_not_characters():
    """The shape differs from Korean's on purpose."""
    parts = HIRAGANA.decompose("きょう")
    assert len(parts) == 2
    assert parts[0]["text"] == "きょ"


def test_pronunciation_explains_the_beats():
    out = PRON.explain("がっこう")
    assert out["mora_count"] == 4
    assert any(s["rule_id"] == "sokuon" for s in out["steps"])


def test_difficulty_points_lead_with_length():
    d = PRON.difficulty_points()
    assert d[0]["id"] == "vowel_length"
    assert d[0]["causes_misunderstanding"] is True
    assert all(p["fix"] for p in d)


def test_pitch_accent_is_declared_but_not_invented():
    pitch = next(p for p in PRON.difficulty_points() if p["id"] == "pitch_accent")
    assert pitch["severity"] == "low"
    assert "would teach confident errors" in pitch["note"]


def test_grammar_capabilities_differ_from_korean():
    caps = GRAMMAR.capabilities()
    assert "keigo" in caps
    assert "mora_timing" in caps
    assert "syllable_blocks" not in caps
    assert "speech_levels" not in caps      # Korean's system, not Japanese's


def test_grammar_analyse_is_honest_about_being_shallow():
    out = GRAMMAR.analyse("私は 学校に 行きます")
    assert out["depth"] == "surface"
    assert "morphological analyser" in out["note"]
    assert out["words"][0]["particle"] == "は"


def test_counters_are_provided_with_their_sound_changes():
    counters = {c["counter"]: c for c in GRAMMAR.counters()}
    assert "つ" in counters and "人" in counters and "本" in counters
    assert "ふたり" in counters["人"]["readings"]
    assert "いっぽん" in counters["本"]["readings"]


# ==========================================================================
# JLPT
# ==========================================================================

def test_jlpt_runs_from_n5_up_to_n1():
    assert LEVELS.levels == ("pre-N5", "N5", "N4", "N3", "N2", "N1")
    assert LEVELS.scheme == "JLPT"


def test_kana_gates_the_ladder():
    assert LEVELS.estimate(0.4, 5000, 200, 90) == "pre-N5"
    assert LEVELS.estimate(0.95, 10000, 250, 90) == "N1"


def test_every_level_describes_what_you_can_do():
    for level in LEVELS.levels:
        d = LEVELS.describe(level)
        assert d["can_do"]
        assert d["milestone"]
