"""
Two ways the app acts on what it knows, rather than only reporting it.

**Review modes.** The scheduler says which cards are due; it has nothing to say
about how they are asked, so every review used to be the same recognition
question — and recognition is the one skill a learner already has by the time a
card comes back. The mode is now chosen from the learner's weak skills.

**Practice my mistakes.** A list of errors with no button on it is a
scoreboard. These are the learner's own items, re-asked in the direction that
proves they have been fixed rather than the one they were originally met in.

The rule both share, and most of these tests defend: harder is not always
better. A card met four minutes ago is not made into a production test, and
careless slips are not drilled at all.
"""

from __future__ import annotations

import random

import pytest

from app.engines import adaptive as A


WEIGHTS = {"listening": 0.9, "vocabulary": 0.6, "pronunciation": 0.3}


# ==========================================================================
# Choosing how to ask
# ==========================================================================

@pytest.mark.parametrize("state", ["new", "learning"])
def test_a_card_still_being_learned_is_never_made_harder(state):
    """You cannot recall what you met four minutes ago.

    A card failed for that reason would be read by the scheduler as
    forgetting, and the interval would collapse for no real reason.
    """
    for seed in range(30):
        got = A.review_mode(state=state, item_type="vocab", weights=WEIGHTS,
                            rng=random.Random(seed))
        assert got["mode"] == "recognise"


def test_a_card_with_one_sensible_face_is_left_alone():
    """Rotating a script unit or grammar point would be variety for its own sake."""
    for item_type in ("script_unit", "grammar", "sentence"):
        got = A.review_mode(state="review", item_type=item_type, weights=WEIGHTS,
                            rng=random.Random(1))
        assert got["mode"] == "recognise"


def test_with_no_evidence_nothing_changes():
    for seed in range(20):
        got = A.review_mode(state="review", item_type="vocab", weights={},
                            rng=random.Random(seed))
        assert got["mode"] == "recognise"


def test_weak_skills_change_how_due_cards_are_asked():
    modes = {A.review_mode(state="review", item_type="vocab", weights=WEIGHTS,
                           rng=random.Random(s))["mode"] for s in range(200)}
    assert {"recall", "listen", "speak"} <= modes


def test_most_reviews_are_still_ordinary_reviews():
    """Forty production tests in a row is not rigour, it is a queue nobody finishes."""
    seen = [A.review_mode(state="review", item_type="vocab", weights=WEIGHTS,
                          rng=random.Random(s))["mode"] for s in range(400)]
    ordinary = seen.count("recognise") / len(seen)
    assert 0.45 < ordinary < 0.8


def test_the_weakest_skill_is_favoured_but_does_not_monopolise():
    harder = [m for m in
              (A.review_mode(state="review", item_type="vocab", weights=WEIGHTS,
                             rng=random.Random(s))["mode"] for s in range(500))
              if m != "recognise"]
    assert harder.count("listen") > harder.count("speak")
    assert harder.count("speak") > 0


def test_a_changed_format_always_explains_itself():
    for seed in range(200):
        got = A.review_mode(state="review", item_type="vocab", weights=WEIGHTS,
                            rng=random.Random(seed))
        if got["mode"] != "recognise":
            assert got["why"], got
            assert got["skill"] in WEIGHTS


def test_the_queue_reports_the_modes_it_chose(api_client):
    r = api_client.get("/api/review/queue?lang=ko&seed=1")
    assert r.status_code == 200
    data = r.json()
    assert "modes" in data
    for item in data["items"]:
        assert item["ask"]["mode"] in ("recognise", "recall", "listen", "speak")


# ==========================================================================
# Practice my mistakes
# ==========================================================================

def _make_mistake(client, **kw) -> None:
    body = {"correct": False, "skill": "vocabulary", "item_type": "vocab",
            "item_id": "ko-v-0001", "expected": "사람", "given": "사림",
            "response_ms": 9000}
    body.update(kw)
    assert client.post("/api/answer?lang=ko", json=body).status_code == 200


def test_practising_mistakes_uses_the_learners_own_items(api_client):
    _make_mistake(api_client, expected="학교", given="학원", item_id="ko-v-0002")
    r = api_client.post("/api/mistakes/practice?lang=ko", json={"count": 20})
    data = r.json()
    assert data["count"] > 0
    answers = {e["answer"] for e in data["exercises"]}
    assert "학교" in answers
    assert all(e["data"]["from_mistake"] for e in data["exercises"])


def test_a_vocabulary_gap_comes_back_as_recall_not_recognition(api_client):
    _make_mistake(api_client, expected="사람", given="사림", item_id="ko-v-0003")
    data = api_client.post("/api/mistakes/practice?lang=ko",
                           json={"reason": "vocabulary", "count": 20}).json()
    assert data["count"] > 0
    assert {e["kind"] for e in data["exercises"]} == {"vocab_recall"}


def test_a_listening_mistake_comes_back_as_dictation(api_client):
    _make_mistake(api_client, skill="listening", expected="시간", given="시강",
                  item_id="ko-v-0004")
    data = api_client.post("/api/mistakes/practice?lang=ko",
                           json={"reason": "listening", "count": 20}).json()
    assert data["count"] > 0
    for e in data["exercises"]:
        assert e["kind"] == "listen_type"
        assert e["audio"]


def test_careless_slips_are_excluded_on_purpose(api_client):
    """Thirty words you already know is exactly the busywork to avoid."""
    # Right first, then one character out and answered far faster than this
    # learner's own median: the diagnosis engine calls that a slip, not a gap.
    body = {"correct": True, "skill": "vocabulary", "item_type": "vocab",
            "item_id": "ko-v-0009", "expected": "감사합니다", "given": "감사합니다",
            "response_ms": 9000}
    api_client.post("/api/answer?lang=ko", json=body)
    body.update({"correct": False, "given": "감사합니가", "response_ms": 600})
    assert api_client.post("/api/answer?lang=ko", json=body) \
        .json()["diagnosis"]["reason"] == "careless"

    default = api_client.post("/api/mistakes/practice?lang=ko",
                              json={"count": 50}).json()
    assert default["excluded_careless"] is True
    assert "감사합니다" not in {e["answer"] for e in default["exercises"]}

    asked = api_client.post("/api/mistakes/practice?lang=ko",
                            json={"reason": "careless", "count": 50}).json()
    assert asked["excluded_careless"] is False


def test_an_empty_practice_says_so_rather_than_returning_a_blank_screen(api_client):
    data = api_client.post("/api/mistakes/practice?lang=ja",
                           json={"count": 5}).json()
    assert data["count"] == 0
    assert "Nothing to practise" in data["note"]


def test_practice_can_be_narrowed_to_one_specific_point(api_client):
    for _ in range(2):
        api_client.post("/api/answer?lang=ko", json={
            "correct": False, "skill": "pronunciation", "expected": "꽃이",
            "given": "", "response_ms": 8000})
    data = api_client.post("/api/mistakes/practice?lang=ko",
                           json={"focus": "pron:liaison", "count": 20}).json()
    assert data["count"] > 0
    assert {e["data"]["focus"] for e in data["exercises"]} == {"pron:liaison"}


def test_every_mistake_group_says_what_to_do_about_it(api_client):
    data = api_client.get("/api/mistakes?lang=ko").json()
    assert data["next_steps"]
    for reason, step in data["next_steps"].items():
        assert step["advice"], reason
        # Careless is the one reason whose correct next step is "nothing".
        assert step["practisable"] is (reason != "careless")


def test_the_careless_advice_is_to_slow_down_not_to_practise_more(api_client):
    data = api_client.get("/api/mistakes?lang=ko").json()
    advice = data["next_steps"].get("careless", {}).get("advice", "")
    if advice:
        assert "slow down" in advice
        assert "not scheduled" in advice


def test_the_mistakes_screen_knows_the_specific_points_too(api_client):
    data = api_client.get("/api/mistakes?lang=ko").json()
    assert "weak_points" in data
    assert data["weak_point_summary"]
