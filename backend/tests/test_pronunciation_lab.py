"""
The pronunciation lab.

Three languages, three genuinely different accounts of why spelling and sound
come apart — Korean's assimilation rules, Japanese's timing, Mandarin's tone
changes — rendered through one shape. The tests here check the two properties
that make the lab trustworthy: every rule explains itself twice, plainly first
and technically second; and every worked example is *computed by the engine*
rather than authored, so the reference material cannot drift away from the code
that produces it.
"""

from __future__ import annotations

import pytest

from app.languages import registry as R

LANGUAGES = ("ko", "ja", "zh")


@pytest.fixture(params=LANGUAGES)
def engine(request):
    return R.get(request.param).pronunciation


# ==========================================================================
# The shared shape
# ==========================================================================

def test_every_language_publishes_a_rule_index(engine):
    rules = engine.rules()
    assert rules, f"{engine.language} publishes no rules"


def test_every_rule_has_both_registers_and_they_differ(engine):
    """Plain words first, terminology second. A rule with only the technical
    account is the grammar reference the learner already failed to understand.
    """
    for rule in engine.rules():
        assert rule["simple"], f"{rule['id']} has no plain explanation"
        assert rule["technical"], f"{rule['id']} has no technical explanation"
        assert rule["simple"] != rule["technical"]
        assert len(rule["simple"]) > 40


def test_every_rule_is_named_in_the_language_as_well_as_english(engine):
    for rule in engine.rules():
        assert rule["name"], f"{rule['id']} has no English name"
        assert rule["native_name"], f"{rule['id']} has no native name"


def test_the_plain_explanation_avoids_the_terminology(engine):
    """The whole teaching philosophy in one assertion: the simple version is
    for someone who does not yet know the word for what is happening."""
    jargon = ("resyllabif", "phoneme", "allophone", "monomoraic",
              "isochronous", "coda consonant", "obstruent")
    for rule in engine.rules():
        lowered = rule["simple"].lower()
        for term in jargon:
            assert term not in lowered, (
                f"{rule['id']}'s plain explanation uses {term!r}")


def test_every_rule_carries_a_worked_example(engine):
    for rule in engine.rules():
        assert rule["examples"], f"{rule['id']} has no example"
        for ex in rule["examples"]:
            assert ex["written"] and ex["spoken"]
            assert ex["note"], "an example without a reason teaches nothing"


# ==========================================================================
# The examples are computed, not typed
# ==========================================================================

def test_korean_examples_actually_trigger_the_rule_they_illustrate():
    """This is the guarantee the lab is built on. Every example is run through
    the phonology engine when the index is built, so a rule change cannot leave
    a worked example quietly contradicting it."""
    for rule in R.get("ko").pronunciation.rules():
        for ex in rule["examples"]:
            assert ex["verified"], (
                f"{rule['id']}: {ex['written']} no longer triggers its own rule")


def test_korean_examples_match_the_engine_exactly():
    from app.languages.korean import phonology as P

    for rule in R.get("ko").pronunciation.rules():
        for ex in rule["examples"]:
            recomputed = P.pronounce_phrase(ex["written"], ex.get("hints") or None)
            assert ex["spoken"] == recomputed.spoken


def test_japanese_beat_counts_come_from_the_mora_engine():
    from app.languages.japanese import kana as K

    for rule in R.get("ja").pronunciation.rules():
        for ex in rule["examples"]:
            assert ex["beats"] == K.count_mora(ex["written"])


def test_mandarin_examples_come_from_the_sandhi_engine():
    from app.languages.mandarin import tones as T

    for rule in R.get("zh").pronunciation.rules():
        for ex in rule["examples"]:
            assert ex["spoken"] == T.apply_sandhi(ex["written"]).spoken


# ==========================================================================
# What each language actually teaches — and it is not the same thing
# ==========================================================================

def test_korean_teaches_sound_changes():
    ids = {r["id"] for r in R.get("ko").pronunciation.rules()}
    assert {"liaison", "nasalisation", "tensification", "palatalisation"} <= ids


def test_japanese_teaches_timing_rather_than_sound_change():
    """Kana is near-phonemic. What Japanese has instead is beats, and the lab
    says so rather than inventing sound changes to fill the same shape."""
    ids = {r["id"] for r in R.get("ja").pronunciation.rules()}
    assert {"sokuon_is_a_silent_beat", "long_vowel_is_two_beats"} <= ids
    assert not ({"liaison", "nasalisation"} & ids)


def test_mandarin_teaches_tone_change():
    ids = {r["id"] for r in R.get("zh").pronunciation.rules()}
    assert {"third_tone_sandhi", "bu_sandhi", "yi_sandhi"} <= ids


def test_no_two_languages_share_a_rule_id():
    seen: dict[str, str] = {}
    for code in LANGUAGES:
        for rule in R.get(code).pronunciation.rules():
            assert rule["id"] not in seen, (
                f"{code} and {seen.get(rule['id'])} both define {rule['id']}")
            seen[rule["id"]] = code


# ==========================================================================
# The example that shows where a rule stops
# ==========================================================================

def test_mandarin_shows_where_a_rule_does_not_apply():
    """The half of a rule learners are never taught. 不 rises before a fourth
    tone and stays put everywhere else, and seeing both is what makes the rule
    usable rather than memorised."""
    bu = next(r for r in R.get("zh").pronunciation.rules() if r["id"] == "bu_sandhi")
    assert any(ex["verified"] for ex in bu["examples"])
    assert any(ex.get("shows_the_limit") for ex in bu["examples"])


def test_korean_rules_that_need_a_hint_say_which():
    """Four Korean rules are morphologically or lexically conditioned — 첫인상
    is [천닌상] and 첫아들 is [처다들], and the spelling cannot tell you which.
    Their examples carry the hint that makes them fire, rather than silently
    failing to demonstrate the rule."""
    rules = {r["id"]: r for r in R.get("ko").pronunciation.rules()}
    for rule_id in ("n_insertion", "tensification_sino",
                    "tensification_morphological", "ui_reduction"):
        examples = rules[rule_id]["examples"]
        assert any(ex.get("hints") for ex in examples), (
            f"{rule_id} needs a hint but no example supplies one")


# ==========================================================================
# Through the API
# ==========================================================================

def test_the_lab_endpoint_serves_all_three(api_client):
    for code in LANGUAGES:
        lab = api_client.get(f"/api/pronunciation/lab?lang={code}").json()
        assert lab["rules"]
        assert lab["difficulties"]
        assert lab["note"]


def test_a_rule_can_be_drilled_from_its_own_examples(api_client):
    d = api_client.get("/api/pronunciation/drill?lang=ko&rule=liaison").json()
    assert d["rule"]["id"] == "liaison"
    assert d["items"]
    first = d["items"][0]
    assert first["explained"]["steps"][0]["rule_id"] == "liaison"
    assert first["explained"]["steps"][0]["child_explanation"]


def test_an_unknown_rule_is_a_404_not_an_empty_drill(api_client):
    r = api_client.get("/api/pronunciation/drill?lang=ko&rule=nonsense")
    assert r.status_code == 404
