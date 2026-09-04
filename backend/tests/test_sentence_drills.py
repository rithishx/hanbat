"""
Sentence-based drills, and the three exercise families that were missing.

The application could test recognition, recall, listening, writing and
pronunciation. It could not test *translation*, *sentence completion* or
*grammar transformation* — which between them are most of what a language class
actually does. These are shared generators because the task is shared; only the
sentences differ, and those come from each language's own content.

`grammar_transform` is the interesting one. It reaches into each language's own
grammar engine, so Korean gets conjugations, Japanese gets particles and
politeness registers, and Mandarin — which has no conjugation at all — gets
aspect particles. One drill, three genuinely different grammars, and no shared
code that knows which is which.
"""

from __future__ import annotations

import random

import pytest

from app import db, store
from app.content import loader
from app.engines import exercises as X


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    """A real database with the real content files behind it."""
    path = tmp_path_factory.mktemp("sentences") / "t.sqlite3"
    conn = db.connect(path)
    db.init_db(conn, path)
    report = loader.load_all(conn)
    assert report.ok, report.errors
    return conn


def context(conn, language: str, seed: int = 1) -> X.GenContext:
    X.load_language_generators(language)
    return X.GenContext(
        language=language,
        rng=random.Random(seed),
        vocab=store.vocab(language, limit=300, conn=conn),
        sentences=store.sentences(language, conn=conn),
        grammar=store.grammar(language, conn=conn),
    )


# ==========================================================================
# The sentence bank itself
# ==========================================================================

def test_korean_sentences_load(loaded):
    rows = store.sentences("ko", conn=loaded)
    assert len(rows) >= 12


def test_pronunciation_is_derived_not_authored(loaded):
    """The same rule as vocabulary: a fix to the phonology engine must reach
    every sentence, not leave hand-written strings quietly wrong."""
    rows = {r["target"]: r for r in store.sentences("ko", conn=loaded)}
    s = rows["밥을 먹어요."]
    assert s["pronunciation"] == "바블 머거요."      # liaison, twice
    assert s["pronunciation"] != s["target"]


def test_a_sentence_knows_which_words_and_grammar_it_uses(loaded):
    """This is what makes targeted practice possible: after getting 은/는
    wrong, the drill can be built from sentences that actually use it."""
    rows = store.sentences("ko", conn=loaded)
    assert any(r["vocab_ids"] for r in rows)
    assert any(r["grammar_ids"] for r in rows)

    with_particle = store.sentences("ko", grammar_id="ko-g-002", conn=loaded)
    assert with_particle
    assert all("ko-g-002" in r["grammar_ids"] for r in with_particle)


def test_sentences_are_searchable(loaded):
    hits = loader.rebuild_search_index(loaded, "ko")
    assert hits > 0
    found = loaded.execute(
        "SELECT term FROM search_index WHERE kind='sentence' AND language='ko' LIMIT 1"
    ).fetchone()
    assert found is not None


# ==========================================================================
# Translation, both directions
# ==========================================================================

def test_translation_into_english_tests_comprehension(loaded):
    ex = X.generate({"type": "translate_to_english", "count": 3},
                    context(loaded, "ko"))
    assert len(ex) == 3
    for e in ex:
        assert e.skill == "reading"
        assert e.prompt and e.answer
        assert e.item_type == "sentence"


def test_translation_into_the_target_tests_production(loaded):
    ex = X.generate({"type": "translate_to_target", "count": 3},
                    context(loaded, "ko"))
    assert all(e.skill == "writing" for e in ex)
    # The prompt is English and the answer is Korean — the hard direction.
    assert all(e.prompt.isascii() for e in ex)
    assert all(not str(e.answer).isascii() for e in ex)


def test_production_marking_is_lenient_about_spacing(loaded):
    """Japanese and Mandarin are written without spaces, and a learner who adds
    one has not made a mistake worth failing."""
    ex = X.generate({"type": "translate_to_target", "count": 1},
                    context(loaded, "ko"))
    assert ex[0].data["accepts_variants"] is True


# ==========================================================================
# Sentence completion
# ==========================================================================

def test_a_blank_is_actually_blanked_out(loaded):
    ex = X.generate({"type": "sentence_complete", "count": 4},
                    context(loaded, "ko"))
    assert ex
    for e in ex:
        assert "____" in e.prompt
        assert str(e.answer) not in e.prompt
        assert str(e.answer) in e.options


def test_completion_says_why_not_just_which(loaded):
    """A blank marked right or wrong with no reason teaches nothing."""
    ex = X.generate({"type": "sentence_complete", "count": 4},
                    context(loaded, "ko"))
    assert all(len(e.explain) > 20 for e in ex)


def test_blanks_are_authored_rather_than_chosen_at_random(loaded):
    """A randomly deleted word usually has several defensible answers, and
    marking one of them wrong teaches a learner to distrust the app."""
    rows = store.sentences("ko", conn=loaded)
    authored = [b for r in rows for b in r["blanks"]]
    assert authored
    for b in authored:
        assert b.get("why"), "every blank must justify its answer"
        assert b["answer"] in b.get("options", [])


# ==========================================================================
# Grammar transformation
# ==========================================================================

def test_transformation_uses_the_language_s_own_grammar_engine(loaded):
    """The architectural payoff, in one test: the same drill produces
    conjugations for Korean and aspect particles for Mandarin, and neither
    language knows the other exists."""
    ko = X.generate({"type": "grammar_transform", "count": 6}, context(loaded, "ko"))
    zh = X.generate({"type": "grammar_transform", "count": 6}, context(loaded, "zh", 5))

    assert ko and zh
    assert all(e.skill == "grammar" for e in ko + zh)
    # Mandarin has no conjugation, so nothing here can be one.
    assert all("conjugat" not in e.prompt.lower() for e in zh)


def test_every_language_can_run_the_transformation_drill(loaded):
    for code in ("ko", "ja", "zh"):
        ex = X.generate({"type": "grammar_transform", "count": 4},
                        context(loaded, code, seed=7))
        assert ex, f"{code} produced no transformations"
        for e in ex:
            assert e.answer and e.prompt
            assert e.answer != e.data.get("from")


def test_authored_sentence_transforms_are_preferred_where_they_exist(loaded):
    """"Make this sentence past" teaches more than "make this word past"."""
    ex = X.generate({"type": "grammar_transform", "count": 8},
                    context(loaded, "ko", seed=3))
    assert any(e.item_type == "sentence" for e in ex)


# ==========================================================================
# Honesty about missing content
# ==========================================================================

@pytest.mark.parametrize("kind", [
    "translate_to_english", "translate_to_target",
    "sentence_complete", "sentence_order",
])
def test_a_language_without_sentences_says_so_rather_than_returning_nothing(
        loaded, kind):
    """An empty list is indistinguishable from a bug. Japanese and Mandarin
    have no sentence bank yet, and the drill says exactly that."""
    ex = X.generate({"type": kind, "count": 3}, context(loaded, "ja"))
    assert len(ex) == 1
    assert ex[0].kind == "unsupported"
    assert ex[0].data["missing"] == "sentences"
    assert "gap in the curriculum" in ex[0].explain


def test_the_session_does_not_plan_drills_a_language_cannot_build(loaded):
    from app.engines import adaptive as A
    from app.engines import session as S

    model = A.LearnerModel()
    model.skills["writing"] = A.SkillScore(
        skill="writing", name="Writing", native_name="", score=10,
        attempts=50, confidence=1.0)

    plan = S.build(language="ja", model=model, due_now=0, minutes=30,
                   new_vocab=5, has_sentences=False, seed=2)
    planned = {s["type"] for b in plan.blocks for s in b.payload.get("specs", [])}
    assert not (planned & S.SENTENCE_KINDS)

    korean = S.build(language="ko", model=model, due_now=0, minutes=30,
                     new_vocab=5, has_sentences=True, seed=2)
    assert korean.blocks     # Korean has a bank, so nothing is excluded


# ==========================================================================
# Drills built from the curriculum's own error catalogue
#
# Every grammar point carries wrong/right pairs describing what learners of
# that language actually write. They were authored, displayed, and never
# drilled. These two generators read them as exercises, which makes them the
# only drills in the app whose distractors are real errors rather than
# plausible-looking ones.
# ==========================================================================

def test_spot_the_error_offers_the_real_wrong_version(loaded):
    ctx = context(loaded, "ko")
    ex = X.generate({"type": "spot_the_error", "count": 5}, ctx)
    assert len(ex) == 5
    for e in ex:
        assert e.answer in e.options
        assert e.data["wrong"] in e.options
        assert e.answer != e.data["wrong"]
        assert e.explain, "a right/wrong pair without a reason teaches nothing"


def test_fixing_a_sentence_is_production_not_recognition(loaded):
    ctx = context(loaded, "ko")
    ex = X.generate({"type": "fix_the_sentence", "count": 4}, ctx)
    assert ex and all(not e.options for e in ex)
    assert all(e.skill == "writing" for e in ex)
    for e in ex:
        assert e.data["wrong"] in e.prompt
        assert e.answer not in e.prompt


def test_error_drills_can_be_narrowed_to_one_grammar_point(loaded):
    ctx = context(loaded, "ko")
    ex = X.generate({"type": "spot_the_error", "grammar_id": "ko-g-001",
                     "count": 4}, ctx)
    assert ex and all(e.item_id == "ko-g-001" for e in ex)


def test_a_point_with_no_authored_errors_says_so_rather_than_going_quiet(loaded):
    """An empty list is indistinguishable from "this drill does not exist"."""
    ctx = context(loaded, "ko")
    ex = X.generate({"type": "fix_the_sentence", "grammar_id": "ko-g-404"}, ctx)
    assert len(ex) == 1
    assert ex[0].kind == "unsupported"
    assert ex[0].data["missing"] == "error_pairs"
    assert "ko-g-404" in ex[0].prompt


@pytest.mark.parametrize("language", ["ko", "ja", "zh"])
def test_all_three_languages_have_error_pairs_to_drill(loaded, language):
    ctx = context(loaded, language)
    ex = X.generate({"type": "spot_the_error", "count": 3}, ctx)
    assert ex and ex[0].kind == "spot_the_error", language


def test_error_drills_never_offer_the_same_string_twice(loaded):
    for language in ("ko", "ja", "zh"):
        ctx = context(loaded, language)
        for e in X.generate({"type": "spot_the_error", "count": 8}, ctx):
            assert len(set(e.options)) == len(e.options), (language, e.options)
