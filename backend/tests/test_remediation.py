"""
From "pronunciation is weak" to "you keep dropping 연음".

Two properties are load-bearing here and most of this file defends them.

**Attribution must be derived, never guessed.** Every focus point comes from a
language's own engine, and the rule blamed for a wrong answer is the one the
phonology says fired. Where the evidence does not isolate one, the module has
to say so rather than pick.

**The threshold must hold.** A single slip is not a pattern, and building an
eight-minute course around one would waste the learner's time and teach them
that the app's judgement is noise.
"""

from __future__ import annotations

import pytest

from app import store
from app.engines import remediation as R


@pytest.fixture(scope="module")
def ko_points(api_client):
    """The real Korean catalogue, from the real content files."""
    return R.catalogue("ko", store.grammar("ko"))


# ==========================================================================
# The catalogue
# ==========================================================================

def test_catalogue_is_assembled_from_the_language_itself(ko_points):
    kinds = {p.kind for p in ko_points.values()}
    assert kinds == {R.PRONUNCIATION, R.GRAMMAR, R.CONFUSION}
    assert len(ko_points) > 30


def test_every_point_can_teach_itself(ko_points):
    """A point with no explanation is a label, and a label fixes nothing."""
    for p in ko_points.values():
        assert p.simple, p.id
        assert p.title, p.id


def test_pronunciation_points_carry_the_engines_own_examples(ko_points):
    liaison = ko_points["pron:liaison"]
    assert liaison.native_title == "연음"
    assert "한국어" in liaison.examples


def test_ids_are_namespaced_so_kinds_cannot_collide(ko_points):
    for fid, p in ko_points.items():
        assert fid == f"{p.kind}:{p.source_id}"


def test_each_language_has_its_own_catalogue_and_they_do_not_mix(api_client):
    ko = R.catalogue("ko", store.grammar("ko"))
    ja = R.catalogue("ja", store.grammar("ja"))
    zh = R.catalogue("zh", store.grammar("zh"))
    assert ko and ja and zh
    assert not (set(ko) & set(ja))
    assert not (set(ja) & set(zh))
    assert not (set(ko) & set(zh))


def test_an_unknown_language_gets_an_empty_catalogue_not_an_error():
    assert R.catalogue("xx") == {}


def test_a_language_with_no_grammar_rows_still_has_sound_points():
    points = R.catalogue("ko", grammar_rows=[])
    assert any(p.kind == R.PRONUNCIATION for p in points.values())
    assert not any(p.kind == R.GRAMMAR for p in points.values())


# ==========================================================================
# Attribution — the derived part
# ==========================================================================

def test_the_headline_case(ko_points):
    """한국어 is a liaison word, and the engine is what says so."""
    got = R.attribute("ko", skill="pronunciation", expected="한국어",
                      points=ko_points)
    assert got.focus == "pron:liaison"
    assert got.attributed and got.certain


def test_a_grammar_item_needs_no_inference(ko_points):
    got = R.attribute("ko", skill="grammar", item_type="grammar",
                      item_id="ko-g-001", expected="이에요", given="예요",
                      points=ko_points)
    assert got.focus == "grammar:ko-g-001"


def test_a_matched_confusion_wins(ko_points):
    """The confusion engine already decided this was a specific pair."""
    cid = next(p.source_id for p in ko_points.values() if p.kind == R.CONFUSION)
    got = R.attribute("ko", skill="grammar", item_type="grammar",
                      item_id="ko-g-001", confusion_id=cid, points=ko_points)
    assert got.focus == f"confusion:{cid}"


def test_a_written_vocabulary_slip_is_not_attributed_to_a_sound_rule(ko_points):
    got = R.attribute("ko", skill="vocabulary", expected="사람", given="사림",
                      points=ko_points)
    assert not got.attributed


def test_an_unknown_grammar_id_does_not_invent_a_point(ko_points):
    got = R.attribute("ko", skill="grammar", item_type="grammar",
                      item_id="ko-g-999", points=ko_points)
    assert not got.attributed


# ---- the chain, which is where this gets interesting ---------------------

CHAIN = "읽는다"          # cluster simplification, then nasalisation


def test_a_chained_answer_is_blamed_at_the_point_it_stopped(ko_points):
    """익는다 applied the first rule and not the second."""
    got = R.attribute("ko", skill="pronunciation", expected=CHAIN,
                      given="익는다", points=ko_points)
    assert got.focus == "pron:nasalisation"


def test_a_fully_correct_pronunciation_is_never_blamed_on_a_rule(ko_points):
    """The regression that made this logic worth writing twice.

    잉는다 is right. Checking each rule's output independently marked the first
    rule as failed, because its intermediate form is consumed by the second —
    which would have taught the learner to fix something they had just done
    correctly.
    """
    got = R.attribute("ko", skill="pronunciation", expected=CHAIN,
                      given="잉는다", points=ko_points)
    assert not got.attributed
    assert "applied correctly" in got.why


def test_a_wrong_ending_after_correct_sound_changes_is_not_a_rule_failure(ko_points):
    got = R.attribute("ko", skill="pronunciation", expected=CHAIN,
                      given="잉는대", points=ko_points)
    assert not got.attributed


def test_ambiguity_is_declared_rather_than_resolved(ko_points):
    """Two rules, and nothing in the answer says which one broke."""
    got = R.attribute("ko", skill="pronunciation", expected=CHAIN,
                      given="", points=ko_points)
    assert not got.attributed
    assert got.certain is False
    assert "does not say which one" in got.why


def test_a_written_answer_does_not_fake_spoken_evidence(ko_points):
    """Dictation asks for the written form, so no spoken fragment appears.

    Reading that absence as failure would blame the first rule on every
    correct dictation answer.
    """
    got = R.attribute("ko", skill="listening", expected=CHAIN,
                      given=CHAIN, points=ko_points)
    assert not got.attributed


def test_a_single_rule_word_is_still_attributed_from_a_written_answer(ko_points):
    got = R.attribute("ko", skill="listening", expected="한국어",
                      given="한국어", points=ko_points)
    assert got.focus == "pron:liaison"


def test_attribution_survives_a_string_the_engine_cannot_handle(ko_points):
    for junk in ("", "   ", "!!!", "x" * 300):
        R.attribute("ko", skill="pronunciation", expected=junk, points=ko_points)


# ==========================================================================
# Weakness and the threshold
# ==========================================================================

def test_one_failure_is_not_a_pattern(ko_points):
    weak = R.weak_points(ko_points, {"pron:liaison": 1})
    assert weak[0].failures == 1
    assert not weak[0].warrants_remediation


def test_the_threshold_is_where_it_says_it_is(ko_points):
    below = R.weak_points(ko_points, {"pron:liaison": R.REMEDIATION_THRESHOLD - 1})
    at = R.weak_points(ko_points, {"pron:liaison": R.REMEDIATION_THRESHOLD})
    assert not below[0].warrants_remediation
    assert at[0].warrants_remediation


def test_weak_points_are_ranked_by_failures(ko_points):
    weak = R.weak_points(ko_points, {
        "pron:liaison": 2, "pron:nasalisation": 7, "grammar:ko-g-001": 4})
    assert [w.point.id for w in weak] == [
        "pron:nasalisation", "grammar:ko-g-001", "pron:liaison"]


def test_a_point_the_catalogue_no_longer_has_is_dropped(ko_points):
    """A renamed rule should vanish from the learner's list, not appear raw."""
    weak = R.weak_points(ko_points, {"pron:renamed_away": 9, "pron:liaison": 2})
    assert [w.point.id for w in weak] == ["pron:liaison"]


def test_the_summary_says_what_is_missing_below_the_threshold(ko_points):
    weak = R.weak_points(ko_points, {"pron:liaison": 1})
    note = R.summarise(weak)
    assert str(R.REMEDIATION_THRESHOLD - 1) in note


def test_the_summary_of_nothing_does_not_manufacture_a_worry():
    assert "not failed often enough" in R.summarise([]) or \
           "Nothing has failed" in R.summarise([])


# ==========================================================================
# The plan
# ==========================================================================

def test_a_sound_plan_teaches_then_hears_then_says_then_produces(ko_points):
    plan = R.plan(ko_points["pron:liaison"], has_sentences=True)
    assert [s.id for s in plan.steps] == ["understand", "hear", "say", "produce"]
    assert plan.steps[0].teach["simple"]
    assert plan.minutes > 0


def test_a_plan_drills_the_points_own_examples_and_nothing_else(ko_points):
    plan = R.plan(ko_points["pron:liaison"], has_sentences=True)
    examples = set(ko_points["pron:liaison"].examples)
    for step in plan.steps:
        pool = (step.spec or {}).get("pool") or (step.spec or {}).get("targets")
        if pool:
            assert set(pool) <= examples


def test_a_language_with_no_sentence_bank_loses_the_production_step(ko_points):
    plan = R.plan(ko_points["pron:liaison"], has_sentences=False)
    assert "produce" not in [s.id for s in plan.steps]
    assert any(s["id"] == "produce" for s in plan.skipped)
    assert "faked" in plan.skipped[0]["why"]


def test_a_rule_with_one_example_gets_dictation_not_an_impossible_choice(ko_points):
    """"Which did you hear" needs a second word to hear it against."""
    thin = next(p for p in ko_points.values()
                if p.kind == R.PRONUNCIATION and len(p.examples) == 1)
    hear = next(s for s in R.plan(thin).steps if s.id == "hear")
    assert hear.spec["type"] == "listen_type"
    assert "without inventing one" in hear.why


def test_a_rule_with_no_examples_drills_nothing_and_says_why(ko_points):
    empty = R.FocusPoint(id="pron:x", kind=R.PRONUNCIATION, skill="pronunciation",
                         title="x", simple="x", examples=())
    plan = R.plan(empty)
    assert [s.id for s in plan.steps] == ["understand"]
    assert "inventing words" in plan.skipped[0]["why"]


def test_a_grammar_plan_recognises_before_it_produces(ko_points):
    plan = R.plan(ko_points["grammar:ko-g-001"], has_sentences=True)
    ids = [s.id for s in plan.steps]
    assert ids == ["understand", "spot", "fix", "produce"]
    assert ids.index("spot") < ids.index("fix")


def test_a_grammar_plan_targets_only_its_own_point(ko_points):
    plan = R.plan(ko_points["grammar:ko-g-002"], has_sentences=True)
    for step in plan.steps[1:]:
        assert step.spec["grammar_id"] == "ko-g-002"


def test_every_real_point_produces_a_usable_plan(ko_points):
    for p in ko_points.values():
        plan = R.plan(p, has_sentences=True)
        assert plan.steps, p.id
        assert plan.steps[0].id == "understand"
        assert plan.minutes >= 2


@pytest.mark.parametrize("code", ["ko", "ja", "zh"])
def test_all_three_languages_can_be_remediated(api_client, code):
    points = R.catalogue(code, store.grammar(code))
    assert points, code
    for p in list(points.values())[:6]:
        assert R.plan(p, has_sentences=(code == "ko")).steps


# ==========================================================================
# The API
# ==========================================================================

def _wrong(client, n: int, **kw) -> None:
    body = {"correct": False, "skill": "pronunciation", "expected": "한국어",
            "given": "", "response_ms": 6000}
    body.update(kw)
    for _ in range(n):
        r = client.post("/api/answer?lang=ko", json=body)
        assert r.status_code == 200


def test_answering_wrong_records_which_rule_it_was(api_client):
    r = api_client.post("/api/answer?lang=ko", json={
        "correct": False, "skill": "pronunciation", "expected": "한국어",
        "given": "", "response_ms": 6000})
    assert r.json()["focus"]["id"] == "pron:liaison"


def test_repeated_failures_cross_the_threshold_and_earn_a_plan(api_client):
    _wrong(api_client, R.REMEDIATION_THRESHOLD + 1, expected="꽃이")
    data = api_client.get("/api/remediation?lang=ko").json()
    assert "pron:liaison" in data["ready"]
    assert data["threshold"] == R.REMEDIATION_THRESHOLD

    plan = api_client.get("/api/remediation/pron:liaison?lang=ko").json()
    assert plan["warrants_remediation"] is True
    assert [s["id"] for s in plan["steps"]][:2] == ["understand", "hear"]
    assert plan["your_mistakes"]


def test_a_plan_is_available_for_a_point_you_have_not_failed(api_client):
    """Wanting to drill a rule is not conditional on failing it first."""
    r = api_client.get("/api/remediation/pron:nasalisation?lang=ko")
    assert r.status_code == 200
    assert r.json()["warrants_remediation"] is False


def test_an_unknown_point_is_a_404_not_an_empty_plan(api_client):
    assert api_client.get("/api/remediation/pron:nope?lang=ko").status_code == 404


def test_finishing_a_plan_clears_what_it_was_built_from(api_client):
    _wrong(api_client, R.REMEDIATION_THRESHOLD + 1, expected="옷이")
    before = api_client.get("/api/remediation?lang=ko").json()
    assert "pron:liaison" in before["ready"]

    done = api_client.post("/api/remediation/pron:liaison/done?lang=ko").json()
    assert done["cleared"] > 0

    after = api_client.get("/api/remediation?lang=ko").json()
    assert "pron:liaison" not in after["ready"]


def test_the_session_plans_a_remediation_block_when_one_is_earned(api_client):
    _wrong(api_client, R.REMEDIATION_THRESHOLD + 1, expected="맏이")
    plan = api_client.get("/api/session/plan?lang=ko&minutes=25&seed=3").json()
    blocks = [b for b in plan["blocks"] if b["kind"] == "remediation"]
    assert blocks, [b["kind"] for b in plan["blocks"]]
    assert blocks[0]["payload"]["point_id"]
    assert "pattern rather than bad luck" in blocks[0]["why"]


def test_remediation_is_scoped_to_one_language(api_client):
    """A Korean rule problem must not appear in a Japanese session."""
    ja = api_client.get("/api/remediation?lang=ja").json()
    assert ja["ready"] == []
    assert all(not w["id"].startswith("pron:liaison") for w in ja["weak_points"])


def test_a_confusion_uses_its_own_drill_rather_than_a_copy(ko_points):
    """A confusion has no grammar id, so the grammar-error drills cannot run.

    Asking for them produced "no worked errors are written for this" on a point
    the app demonstrably knows about — an honest message about the wrong thing,
    which is worse than no message.
    """
    point = next(p for p in ko_points.values()
                 if p.kind == R.CONFUSION and p.skill == "grammar")
    plan = R.plan(point, has_sentences=True)
    assert [s.id for s in plan.steps] == ["understand", "tell_apart", "produce"]
    drill = plan.steps[1].spec
    assert drill["type"] == "confusion_drill"
    assert drill["confusion_id"] == point.source_id


def test_every_drill_spec_a_plan_produces_can_actually_be_built(api_client, ko_points):
    """The end-to-end guard: no plan may reference a drill that returns nothing.

    Each spec is run through the real practice endpoint. A step that comes back
    empty, or comes back as the "unsupported" marker, would show the learner a
    dead end in the middle of a fix they were told would help.
    """
    for point in ko_points.values():
        for step in R.plan(point, has_sentences=True).steps:
            if not step.spec:
                continue
            r = api_client.post("/api/practice?lang=ko",
                                json={"spec": step.spec, "seed": 7})
            assert r.status_code == 200, (point.id, step.id)
            built = r.json()["exercises"]
            assert built, (point.id, step.id, step.spec)
            assert built[0]["kind"] != "unsupported", (point.id, step.id, step.spec)
