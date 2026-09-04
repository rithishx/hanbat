"""
Japanese pitch accent: the contour is a rule, the kernel is a fact.

These tests hold that line. The shape of a contour is checked against the two
rules that generate it, and the *absence* of accent data for ordinary words is
asserted just as firmly as the presence of it for the documented pairs —
because a silently invented accent is the failure mode this module exists to
prevent.
"""

from __future__ import annotations

import pytest

from app.languages.japanese import kana as K
from app.languages.japanese import pitch as P
from app.languages.japanese.pronunciation import ENGINE


# ==========================================================================
# The rule
# ==========================================================================

@pytest.mark.parametrize("mora,accent,shape", [
    (2, 0, "LH"),
    (2, 1, "HL"),
    (2, 2, "LH"),
    (3, 0, "LHH"),
    (3, 1, "HLL"),
    (3, 2, "LHL"),
    (3, 3, "LHH"),
    (4, 2, "LHLL"),
    (1, 0, "L"),
    (1, 1, "H"),
])
def test_contour_shapes(mora, accent, shape):
    assert P.pattern(mora, accent)["shape"] == shape


def test_first_two_mora_always_differ():
    """The one rule with no exceptions: a word cannot start on a plateau."""
    for mora in range(2, 8):
        for accent in range(0, mora + 1):
            highs = P.pattern(mora, accent)["highs"]
            assert highs[0] != highs[1], f"{mora}-mora, accent {accent}"


def test_pitch_never_rises_after_it_falls():
    for mora in range(1, 8):
        for accent in range(0, mora + 1):
            highs = P.pattern(mora, accent)["highs"]
            fallen = False
            for i in range(1, len(highs)):
                if not highs[i] and highs[i - 1]:
                    fallen = True
                elif fallen:
                    assert not highs[i], f"rose again: {mora}/{accent}"


def test_heiban_and_odaka_differ_only_on_the_particle():
    """The whole reason 端 and 橋 are a teaching example."""
    flat = P.pattern(2, 0)
    tail = P.pattern(2, 2)
    assert flat["shape"] == tail["shape"]
    assert flat["particle"] == "high"
    assert tail["particle"] == "low"
    assert flat["with_particle"] != tail["with_particle"]


@pytest.mark.parametrize("accent,mora,kind", [
    (0, 3, "heiban"),
    (1, 3, "atamadaka"),
    (2, 3, "nakadaka"),
    (3, 3, "odaka"),
    (1, 1, "atamadaka"),
])
def test_kind_names(accent, mora, kind):
    assert P.kind_of(accent, mora) == kind
    assert kind in P.KINDS


def test_every_kind_has_both_explanations():
    for kind, info in P.KINDS.items():
        assert info["simple"] and info["technical"]
        assert info["simple"] != info["technical"]


def test_impossible_accent_is_refused():
    with pytest.raises(ValueError):
        P.pattern(2, 3)
    with pytest.raises(ValueError):
        P.pattern(2, -1)
    with pytest.raises(ValueError):
        P.pattern(0, 0)


# ==========================================================================
# The contour, attached to real mora
# ==========================================================================

def test_contour_uses_the_same_mora_split_as_the_timing_rules():
    """きょう is two beats in both places or the lab contradicts itself."""
    c = P.contour("きょう", 1)
    assert len(c["mora"]) == K.count_mora("きょう") == 2
    assert c["mora"][0]["text"] == "きょ"


def test_contour_marks_where_the_drop_is():
    c = P.contour("はし", 1)
    assert c["drop_after"] == 1
    assert [m["pitch"] for m in c["mora"]] == ["high", "low"]


def test_flat_words_report_no_drop():
    assert P.contour("はし", 0)["drop_after"] is None


def test_contour_carries_romaji_for_each_beat():
    c = P.contour("かみ", 2)
    assert [m["romaji"] for m in c["mora"]] == ["ka", "mi"]


# ==========================================================================
# The fact — and its boundary
# ==========================================================================

def test_documented_words_have_accents():
    assert P.accent_for("箸") == 1
    assert P.accent_for("橋") == 2
    assert P.accent_for("端") == 0


def test_undocumented_words_return_none_not_zero():
    """None means "not known". Zero is a real pattern and would be a guess."""
    for word in ("水", "学生", "こんにちは", "テレビ"):
        assert P.accent_for(word) is None


def test_documented_sets_are_genuinely_minimal_pairs():
    for entry in P.DOCUMENTED:
        accents = {s["accent"] for s in entry["senses"]}
        assert len(entry["senses"]) >= 2, entry["reading"]
        # At least one contrast per set, or it is not teaching anything.
        assert len(accents) >= 2, entry["reading"]


def test_documented_accents_are_possible_for_their_reading():
    for entry in P.DOCUMENTED:
        n = K.count_mora(entry["reading"])
        for sense in entry["senses"]:
            assert 0 <= sense["accent"] <= n, (entry["reading"], sense["word"])


def test_kami_set_admits_that_pitch_does_not_separate_everything():
    """紙 and 髪 share an accent. The set says so rather than hiding it."""
    entry = next(e for e in P.DOCUMENTED if e["reading"] == "かみ")
    accents = [s["accent"] for s in entry["senses"]]
    assert accents.count(2) == 2
    assert "context" in entry["note"]


def test_pairs_computes_contours_at_call_time():
    for entry in P.pairs():
        for sense in entry["senses"]:
            c = sense["contour"]
            assert c["accent"] == sense["accent"]
            assert len(c["mora"]) == entry["mora"]


def test_report_states_what_is_not_shipped():
    r = P.report()
    assert r["supported"] is True
    assert r["not_stored"]
    assert r["documented_words"] == sum(len(e["senses"]) for e in P.DOCUMENTED)


# ==========================================================================
# The engine, and the other two languages
# ==========================================================================

def test_pronounce_attaches_pitch_for_a_documented_word():
    out = ENGINE.pronounce("箸")
    assert out["pitch"]["accent"] == 1
    assert out["pitch"]["kind"] == "atamadaka"


def test_pronounce_omits_pitch_for_an_unknown_word():
    assert "pitch" not in ENGINE.pronounce("学生")


def test_pronounce_accepts_a_caller_supplied_accent():
    out = ENGINE.pronounce("がくせい", accent=0)
    assert out["pitch"]["kind"] == "heiban"
    assert out["pitch"]["shape"] == "LHHH"


def test_caller_supplied_accent_wins_over_the_documented_one():
    out = ENGINE.pronounce("箸", accent=0)
    assert out["pitch"]["accent"] == 0


def test_pitch_does_not_disturb_the_mora_output():
    plain = ENGINE.pronounce("がくせい")
    accented = ENGINE.pronounce("がくせい", accent=0)
    assert plain["mora"] == accented["mora"]
    assert plain["mora_count"] == accented["mora_count"]


def test_korean_and_mandarin_do_not_claim_pitch_accent():
    from app.languages.korean.pronunciation import ENGINE as KO
    from app.languages.mandarin.pronunciation import ENGINE as ZH
    assert not hasattr(KO, "pitch_accent")
    assert not hasattr(ZH, "pitch_accent")


def test_lab_endpoint_carries_pitch_only_for_japanese(api_client):
    ja = api_client.get("/api/pronunciation/lab", params={"lang": "ja"}).json()
    assert ja["pitch_accent"]["supported"] is True
    assert ja["pitch_accent"]["pairs"]

    for code in ("ko", "zh"):
        other = api_client.get("/api/pronunciation/lab", params={"lang": code}).json()
        assert "pitch_accent" not in other
