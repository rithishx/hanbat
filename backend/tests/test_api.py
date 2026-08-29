"""
End-to-end API tests.

These run against a real app with a real database and the real content files.
They cover the flow a learner actually takes — onboard, open a lesson, answer
questions, build a review queue — and assert the two properties that matter
most: that Korean works, and that nothing leaks between languages.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """A fresh app with its own database, torn down afterwards."""
    tmp = tempfile.mkdtemp(prefix="hanbat-test-")
    os.environ["HANBAT_DATA_DIR"] = tmp
    os.environ["HANBAT_DB"] = str(Path(tmp) / "test.sqlite3")

    # config reads the environment at import time, so reload the chain.
    import importlib
    from app import config, db
    importlib.reload(config)
    importlib.reload(db)
    from app import store
    importlib.reload(store)
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def planned_language():
    """Temporarily register a language that has been declared but not built.

    Korean, Japanese and Mandarin are all usable now, so there is no real
    language left to test the "not ready yet" path against — and inventing a
    permanent placeholder in the registry just to keep a test green would be
    exactly the fake functionality this project forbids. Instead the spec is
    registered for the duration of one test and removed again.
    """
    from app.languages import registry

    spec = registry.LanguageSpec(
        code="xx", name="Planned Language", native_name="—", flag="🏳️",
        content_dir="xx", status="planned",
        status_note="Declared but not built yet.",
    )
    registry._REGISTRY[spec.code] = spec
    try:
        yield spec.code
    finally:
        registry._REGISTRY.pop(spec.code, None)


# ==========================================================================
# The app is alive and honest about itself
# ==========================================================================

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["offline"] is True
    assert body["content_errors"] == []


def test_korean_content_actually_loaded(client):
    counts = client.get("/api/health").json()["languages"]["ko"]
    assert counts["lessons"] >= 19
    assert counts["vocab"] >= 250
    assert counts["grammar"] >= 20


def test_runtime_declares_what_needs_the_network(client):
    body = client.get("/api/runtime").json()
    assert body["offline_capable"] is True
    ids = {f["id"] for f in body["network_features"]}
    assert "ai_tutor_remote" in ids
    assert all(f["enabled_by_default"] is False for f in body["network_features"])


# ==========================================================================
# Languages
# ==========================================================================

def test_three_languages_listed(client):
    body = client.get("/api/languages").json()
    assert {L["code"] for L in body["languages"]} == {"ko", "ja", "zh"}
    assert body["active"] == "ko"


def test_every_language_declares_how_complete_it_is(client):
    by_code = {L["code"]: L for L in client.get("/api/languages").json()["languages"]}
    assert by_code["ko"]["status"] == "in_progress"
    assert by_code["ja"]["status"] == "foundation"
    assert by_code["zh"]["status"] == "foundation"
    for L in by_code.values():
        assert L["status_note"], f"{L['code']} must say what is missing"


def test_unknown_language_is_a_404_naming_the_known_ones(client):
    r = client.get("/api/lessons?lang=fr")
    assert r.status_code == 404
    assert r.json()["known"] == ["ja", "ko", "zh"]


def test_requesting_an_unready_language_is_a_409_not_an_empty_list(client, planned_language):
    """An empty list reads as a bug. A 409 with a reason reads as a roadmap.

    All three real languages are usable now, so this is checked against a
    temporarily registered planned one — the state every language starts in.
    """
    r = client.get(f"/api/lessons?lang={planned_language}")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "language_not_ready"
    assert detail["message"]


def test_switching_language_persists(client):
    assert client.post("/api/languages/active", json={"language": "ja"}).status_code == 200
    assert client.get("/api/me").json()["active_language"] == "ja"
    client.post("/api/languages/active", json={"language": "ko"})
    assert client.get("/api/me").json()["active_language"] == "ko"


def test_mandarin_conjugation_is_refused_on_principle(client):
    """Mandarin has no conjugation, so there is no conjugation view for it."""
    r = client.get("/api/conjugate?word=x&lang=zh")
    assert r.status_code == 409


# ==========================================================================
# Content
# ==========================================================================

def test_lessons_are_ordered_and_gated(client):
    body = client.get("/api/lessons").json()
    lessons = body["lessons"]
    assert lessons[0]["id"] == "ko-hangul-000"
    assert lessons[0]["locked"] is False
    later = next(L for L in lessons if L["id"] == "ko-batchim-003")
    assert later["locked"] is True
    assert later["blocked_by"]


def test_lesson_carries_its_steps(client):
    L = client.get("/api/lessons/ko-hangul-001").json()
    steps = L["steps"]
    assert [s["step"] for s in steps][:2] == ["warmup", "learn"]
    assert any(s["step"] == "summary" for s in steps)


def test_vocab_entry_computes_pronunciation_and_drills(client):
    v = client.get("/api/vocab/ko-v-0302").json()      # 먹다
    assert v["term"] == "먹다"
    assert v["pronunciation"] == "먹따"
    assert v["pronunciation_explained"]["spoken"] == "먹따"
    forms = {f["form"] for f in v["drill_forms"]}
    assert "먹어요" in forms


def test_grammar_point_resolves_its_cross_references(client):
    g = client.get("/api/grammar/ko-g-002").json()      # 은/는
    assert g["name_native"] == "은/는"
    assert g["mistakes"]
    assert any(p["id"] == "ko-g-003" for p in g["contrast_points"])


def test_writing_system_compose_and_decompose(client):
    r = client.get("/api/writing/compose?parts=ㅎ,ㅏ,ㄴ").json()
    assert r["result"] == "한"
    d = client.get("/api/writing/decompose?text=한국").json()
    assert [p["char"] for p in d["parts"]] == ["한", "국"]


def test_compose_rejects_impossible_blocks(client):
    assert client.get("/api/writing/compose?parts=ㅏ,ㅏ").status_code == 400


def test_pronunciation_explains_itself(client):
    r = client.get("/api/pronounce?text=한국어").json()
    assert r["spoken"] == "한구거"
    assert r["steps"][0]["rule_id"] == "liaison"
    assert r["steps"][0]["child_explanation"]
    assert r["steps"][0]["linguistic_explanation"]


def test_casual_pronunciation_is_opt_in(client):
    assert client.get("/api/pronounce?text=전화").json()["spoken"] == "전화"
    assert client.get("/api/pronounce?text=전화&casual=true").json()["spoken"] == "저놔"


def test_conjugation_table(client):
    t = client.get("/api/conjugate?word=춥다").json()
    assert t["irregular"] == "ㅂ"
    assert t["bases"]["vowel"] == "추워"
    tense = {f["id"]: f["korean"] for f in t["categories"]["tense"]}
    assert tense["present_polite"] == "추워요"
    assert tense["past_polite"] == "추웠어요"


def test_transliteration_reports_that_it_should_disappear(client):
    r = client.get("/api/transliterate?text=한국어").json()
    assert r["full"] == "hangugeo"
    assert r["fully_removable"] is True


def test_search_finds_across_kinds(client):
    r = client.get("/api/search?q=먹다").json()
    assert r["total"] >= 1
    assert "conjugation" in r          # a 다-form also returns its table


# ==========================================================================
# The study loop
# ==========================================================================

def test_exercises_generate_for_a_lesson(client):
    r = client.get("/api/lessons/ko-hangul-001/exercises?seed=1").json()
    assert r["count"] > 0
    kinds = {e["kind"] for e in r["exercises"]}
    assert "unsupported" not in kinds and "error" not in kinds
    for e in r["exercises"]:
        assert e["prompt"]
        assert e["answer"] is not None


def test_practice_on_demand(client):
    r = client.post("/api/practice", json={
        "spec": {"type": "conjugate", "form": "present_polite",
                 "include_irregulars": True, "count": 5}, "seed": 3}).json()
    assert r["count"] == 5
    for e in r["exercises"]:
        assert e["answer"].endswith("요")
        assert e["explain"]


def test_unimplemented_exercise_kind_surfaces_rather_than_vanishing(client):
    r = client.post("/api/practice",
                    json={"spec": {"type": "tone_pair", "count": 3}}).json()
    assert r["exercises"][0]["kind"] == "unsupported"


def test_answering_correctly_schedules_and_awards_xp(client):
    r = client.post("/api/answer", json={
        "correct": True, "skill": "vocabulary",
        "item_type": "vocab", "item_id": "ko-v-0081"}).json()
    assert r["correct"] is True
    assert r["xp"] == 2
    assert r["srs"]["state"] in ("learning", "review")
    assert r["srs"]["next_due_in"]


def test_a_wrong_answer_explains_instead_of_just_marking(client):
    r = client.post("/api/answer", json={
        "correct": False, "skill": "grammar", "item_type": "grammar",
        "item_id": "ko-g-002", "expected": "이", "given": "은"}).json()
    assert r["correct"] is False
    assert r["message"] == "Not quite."
    assert r["try_again"] is True
    assert r["confusion"]["id"] == "topic_vs_subject"
    assert r["confusion"]["simple"]


def test_repeated_confusion_reaches_the_mistakes_list(client):
    for _ in range(3):
        client.post("/api/answer", json={
            "correct": False, "skill": "grammar", "item_type": "grammar",
            "item_id": "ko-g-002", "expected": "이", "given": "은"})
    m = client.get("/api/mistakes").json()
    assert m["total"] >= 1
    top = m["mistakes"][0]
    assert top["times_seen"] >= 3
    assert top["confusion_id"] == "topic_vs_subject"


def test_mini_course_exists_for_a_registered_confusion(client):
    c = client.get("/api/mini-course/topic_vs_subject").json()
    assert c["language"] == "ko"
    assert c["id"] == "ko-mini-topic_vs_subject"
    steps = {s["step"] for s in c["steps"]}
    assert {"understand", "learn", "examples", "practice", "recall", "summary"} <= steps


def test_review_queue_after_answering(client):
    r = client.get("/api/review/queue").json()
    assert r["summary"]["total"] >= 1
    for item in r["items"]:
        assert set(item["preview"]) == {"again", "hard", "good", "easy"}


def test_grading_a_card_moves_it(client):
    client.post("/api/review/enqueue", json={
        "items": [{"item_type": "vocab", "item_id": "ko-v-0090"}]})
    r = client.post("/api/review/grade", json={
        "item_type": "vocab", "item_id": "ko-v-0090", "grade": "good"}).json()
    assert r["card"]["state"] in ("learning", "review")


def test_bad_grade_is_rejected(client):
    assert client.post("/api/review/grade", json={
        "item_type": "vocab", "item_id": "ko-v-0090",
        "grade": "amazing"}).status_code == 400


def test_completing_a_lesson_awards_xp_and_unlocks_the_next(client):
    before = client.get("/api/dashboard").json()["xp"]
    client.post("/api/lessons/ko-hangul-000/progress",
                json={"status": "completed", "score": 100})
    after = client.get("/api/dashboard").json()["xp"]
    assert after > before
    lessons = client.get("/api/lessons").json()
    nxt = next(L for L in lessons["lessons"] if L["id"] == "ko-hangul-001")
    assert nxt["locked"] is False


# ==========================================================================
# Dashboard
# ==========================================================================

def test_dashboard_answers_the_three_questions(client):
    d = client.get("/api/dashboard").json()
    assert d["next_lesson"] is not None                  # what should I learn next
    assert "srs" in d and "due_now" in d["srs"]          # what do I need to review
    assert isinstance(d["confusions"], list)             # why do I keep getting this wrong
    assert d["recommendations"]
    for rec in d["recommendations"]:
        assert rec["reason"], "every recommendation must say why"


def test_dashboard_greets_in_the_target_language(client):
    assert client.get("/api/dashboard").json()["greeting"]["native"] == "오늘의 한국어"


def test_progress_uses_the_korean_level_ladder(client):
    p = client.get("/api/progress").json()
    assert p["level_scheme"].startswith("CEFR")
    assert [l["level"] for l in p["ladder"]][:3] == ["pre-A1", "A1", "A2"]
    assert p["ladder"][1]["topik"] == "TOPIK I, level 1"


def test_skills_are_named_in_korean(client):
    skills = client.get("/api/dashboard").json()["skills"]
    assert skills["reading"]["native_name"] == "읽기"
    assert skills["listening"]["native_name"] == "듣기"


def test_all_languages_view_lists_every_language(client):
    body = client.get("/api/progress/all").json()
    assert {L["code"] for L in body["languages"]} == {"ko", "ja", "zh"}
    ko = next(L for L in body["languages"] if L["code"] == "ko")
    assert ko["started"] is True
    ja = next(L for L in body["languages"] if L["code"] == "ja")
    assert ja["started"] is False


# ==========================================================================
# Isolation, at the HTTP level
# ==========================================================================

def test_korean_progress_does_not_appear_under_another_language(client):
    """Korean has cards by now. Japanese is a real language with its own
    content and must still show zero, because nothing has been studied in it."""
    ko = client.get("/api/review/summary?lang=ko").json()
    assert ko["total"] >= 1

    ja = client.get("/api/review/summary?lang=ja").json()
    assert ja["total"] == 0
    assert ja["due_now"] == 0

    # Mandarin is a third real language and must also show zero, not Korean's
    # numbers and not Japanese's.
    zh = client.get("/api/review/summary?lang=zh").json()
    assert zh["total"] == 0

    body = client.get("/api/progress/all").json()
    japanese = next(L for L in body["languages"] if L["code"] == "ja")
    assert japanese.get("known", {}).get("all", 0) == 0


def test_switching_language_switches_the_whole_curriculum(client):
    """The property the refactor exists for: one call changes everything."""
    client.post("/api/languages/active", json={"language": "ja"})
    ja_lessons = client.get("/api/lessons").json()
    ja_grammar = client.get("/api/grammar").json()
    assert ja_lessons["lessons"][0]["id"].startswith("ja-")
    assert ja_grammar["points"][0]["id"].startswith("ja-")
    assert client.get("/api/dashboard").json()["greeting"]["native"] == "今日の日本語"
    assert client.get("/api/progress").json()["level_scheme"] == "JLPT"

    client.post("/api/languages/active", json={"language": "ko"})
    ko_lessons = client.get("/api/lessons").json()
    assert ko_lessons["lessons"][0]["id"].startswith("ko-")
    assert client.get("/api/dashboard").json()["greeting"]["native"] == "오늘의 한국어"
    assert client.get("/api/progress").json()["level_scheme"].startswith("CEFR")


def test_japanese_mora_engine_is_reachable_through_the_api(client):
    r = client.get("/api/pronounce?text=がっこう&lang=ja").json()
    assert r["mora_count"] == 4
    assert "4 mora" in r["summary"]


def test_japanese_conjugation_classes(client):
    assert client.get("/api/conjugate?word=食べる&lang=ja").json()["verb_class"] == "ichidan"
    assert client.get("/api/conjugate?word=帰る&lang=ja").json()["verb_class"] == "godan"
    t = client.get("/api/conjugate?word=書く&lang=ja").json()
    forms = {f["id"]: f["japanese"]
             for group in t["categories"].values() for f in group}
    assert forms["masu"] == "書きます"
    assert forms["te"] == "書いて"
    assert forms["nai"] == "書かない"
    assert forms["potential"] == "書ける"
    # Japanese groups its forms differently from Korean, because the two
    # languages carve up their conjugations differently.
    assert "keigo" in t["categories"]
    assert t["stems"]["te"] == "書いて"


def test_streak_is_shared_across_languages_by_design(client):
    me = client.get("/api/me").json()
    assert me["streak"]["current"] >= 1


# ==========================================================================
# AI and speech degrade honestly
# ==========================================================================

def test_ai_is_off_and_says_why(client):
    s = client.get("/api/ai/status").json()
    assert s["enabled"] is False
    assert s["available"] is False
    assert "without it" in s["note"]
    for p in s["providers"]:
        assert p["hint"], "each provider must explain how to enable it"


def test_asking_the_tutor_while_disabled_returns_a_reason_not_a_fake_reply(client):
    r = client.post("/api/ai/ask", json={"message": "저는 학교를 가요."}).json()
    assert r["available"] is False
    assert r["text"] == ""
    assert r["reason"]


def test_pronunciation_scoring_is_not_claimed_without_an_engine(client):
    caps = client.get("/api/speech/capabilities").json()
    assert caps["scoring"]["available"] is False
    assert "No score is invented" in caps["scoring"]["note"]


def test_speech_difficulties_are_language_specific(client):
    d = client.get("/api/speech/difficulties").json()["difficulties"]
    ids = {x["id"] for x in d}
    assert "three_way_obstruents" in ids
    assert "eo_vs_o" in ids
    high = [x for x in d if x["severity"] == "high"]
    assert all(x["fix"] for x in high)


# ==========================================================================
# Settings and data ownership
# ==========================================================================

def test_settings_round_trip(client):
    r = client.patch("/api/settings",
                     json={"settings": {"daily_goal_minutes": 25}}).json()
    assert r["settings"]["daily_goal_minutes"] == 25
    assert client.get("/api/dashboard").json()["today"]["goal_minutes"] == 25


def test_unknown_setting_is_rejected(client):
    assert client.patch("/api/settings",
                        json={"settings": {"nonsense": 1}}).status_code == 400


def test_export_contains_the_learners_progress(client):
    body = client.get("/api/data/export").json()
    assert body["format"] == "hanbat-progress"
    assert body["counts"]["srs_card"] >= 1
    assert body["counts"]["attempt"] >= 1


def test_export_can_be_scoped_to_one_language(client):
    body = client.get("/api/data/export?language=ko").json()
    assert all(r["language"] == "ko" for r in body["tables"]["srs_card"])


def test_export_import_round_trip(client):
    exported = client.get("/api/data/export").json()
    r = client.post("/api/data/import",
                    json={"payload": exported, "mode": "merge"}).json()
    assert r["imported"] is True
    assert "Content was not imported" in r["note"]


def test_import_rejects_a_foreign_file(client):
    assert client.post("/api/data/import",
                       json={"payload": {"format": "something-else"}}).status_code == 400


def test_vocab_csv_export(client):
    r = client.get("/api/data/export/vocab.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "term,meaning" in r.text.replace("﻿", "")


def test_anki_export_is_tab_separated(client):
    r = client.get("/api/data/export/anki.txt")
    assert r.status_code == 200
    assert r.text.startswith("#separator:tab")


# ==========================================================================
# Onboarding
# ==========================================================================

def test_onboarding_questions_are_data_not_hard_coded_ui(client):
    q = client.get("/api/onboarding/questions").json()
    ids = [x["id"] for x in q["questions"]]
    assert ids == ["language", "experience", "goal", "minutes"]
    lang_opts = q["questions"][0]["options"]
    assert {o["value"] for o in lang_opts} == {"ko", "ja", "zh"}
    assert next(o for o in lang_opts if o["value"] == "ko")["enabled"] is True
    assert next(o for o in lang_opts if o["value"] == "ja")["enabled"] is True
    assert next(o for o in lang_opts if o["value"] == "zh")["enabled"] is True


def test_onboarding_a_complete_beginner_skips_placement(client):
    r = client.post("/api/onboarding", json={
        "language": "ko", "experience": "none", "goal": "travel", "minutes": 15}).json()
    assert r["starting_level"] == "pre-A1"
    assert r["needs_placement"] is False


def test_onboarding_an_experienced_learner_gets_a_placement_test(client):
    r = client.post("/api/onboarding", json={
        "language": "ko", "experience": "intermediate", "goal": "work"}).json()
    assert r["needs_placement"] is True
    test = client.get("/api/placement?seed=5").json()
    assert test["sections"]
    assert all(s["exercises"] for s in test["sections"])


def test_placement_gates_on_reading_the_script(client):
    """Strong vocabulary with weak script reading still starts at the beginning."""
    r = client.post("/api/placement", json={
        "scores": {"script": 0.3, "vocabulary": 0.9, "grammar": 0.8}}).json()
    assert r["level"] == "pre-A1"
    assert "writing system" in r["reason"]


def test_placement_uses_the_weakest_section_not_the_average(client):
    r = client.post("/api/placement", json={
        "scores": {"script": 1.0, "reading": 0.95, "vocabulary": 0.9,
                   "grammar": 0.2, "listening": 0.9}}).json()
    assert "weakest" in r["reason"]
    assert r["level"] in ("A1", "A2")


def test_onboarding_refuses_a_language_that_is_not_ready(client, planned_language):
    assert client.post("/api/onboarding", json={
        "language": planned_language, "experience": "none"}).status_code == 409
    # ...but accepts every language that is
    for code in ("ko", "ja", "zh"):
        assert client.post("/api/onboarding", json={
            "language": code, "experience": "none"}).status_code == 200
    client.post("/api/languages/active", json={"language": "ko"})
