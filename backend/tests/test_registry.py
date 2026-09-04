"""
The language registry, and the promise that shared code stays language-neutral.

The last test in this file is the important one: it greps the shared modules
for language-specific strings. It exists because the failure mode this refactor
guards against is gradual — nobody hard-codes "Korean" into the SRS engine on
purpose, they just add "one small special case" and then another.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.languages import registry as R
from app.languages.protocols import (
    GrammarEngine,
    KNOWN_CAPABILITIES,
    PronunciationEngine,
    TransliterationEngine,
    WritingSystemEngine,
    check_capabilities,
)

BACKEND = Path(__file__).resolve().parent.parent


# ==========================================================================
# Registration
# ==========================================================================

def test_three_languages_are_registered():
    assert set(R.codes()) == {"ko", "ja", "zh"}


def test_lookup_by_code():
    assert R.get("ko").name == "Korean"
    assert R.get("ja").native_name == "日本語"
    assert R.get("zh").flag == "🇨🇳"


def test_unknown_language_names_the_known_ones():
    with pytest.raises(R.UnknownLanguage) as e:
        R.get("fr")
    assert "'ko'" in str(e.value)


def test_try_get_is_forgiving():
    assert R.try_get("fr") is None
    assert R.try_get("ko") is not None


def test_cannot_register_the_same_code_twice():
    with pytest.raises(ValueError, match="already registered"):
        R.register(R.LanguageSpec(code="ko", name="Duplicate",
                                  native_name="x", flag="x"))


def test_capabilities_are_validated_on_construction():
    with pytest.raises(ValueError, match="unknown capabilities"):
        R.LanguageSpec(code="xx", name="X", native_name="X", flag="X",
                       capabilities=frozenset({"telepathy"}))


def test_check_capabilities_accepts_known_ones():
    check_capabilities(KNOWN_CAPABILITIES)


# ==========================================================================
# Writing systems
# ==========================================================================

def test_each_language_declares_its_scripts():
    assert [w.id for w in R.get("ko").writing_systems] == ["hangul"]
    assert [w.id for w in R.get("ja").writing_systems] == ["hiragana", "katakana", "kanji"]
    assert [w.id for w in R.get("zh").writing_systems] == ["pinyin", "hanzi"]


def test_open_inventories_are_marked_as_such():
    """Kanji and hanzi cannot be enumerated; kana and jamo can."""
    ja = R.get("ja")
    assert ja.writing_system("hiragana").is_closed_inventory is True
    assert ja.writing_system("kanji").is_closed_inventory is False
    assert ja.writing_system("kanji").unit_count is None
    assert R.get("zh").writing_system("hanzi").is_closed_inventory is False
    assert R.get("ko").writing_system("hangul").is_closed_inventory is True


def test_scripts_have_a_teaching_order():
    ja = R.get("ja")
    order = {w.id: w.teaching_order for w in ja.writing_systems}
    assert order["hiragana"] < order["katakana"] < order["kanji"]


# ==========================================================================
# Capabilities differ, and that is the point
# ==========================================================================

def test_mandarin_does_not_claim_conjugation():
    """Mandarin has no conjugation. Declaring it would produce a UI tab that
    shows the dictionary form unchanged and calls that an answer."""
    assert R.get("zh").supports("conjugation") is False
    assert R.get("ko").supports("conjugation") is True
    assert R.get("ja").supports("conjugation") is True


def test_only_mandarin_claims_tone_sandhi():
    assert R.get("zh").supports("tone_sandhi") is True
    assert R.get("ko").supports("tone_sandhi") is False
    assert R.get("ja").supports("tone_sandhi") is False


def test_only_korean_claims_syllable_blocks():
    assert R.get("ko").supports("syllable_blocks") is True
    assert R.get("ja").supports("syllable_blocks") is False


def test_only_japanese_claims_keigo():
    assert R.get("ja").supports("keigo") is True
    assert R.get("ko").supports("keigo") is False
    assert R.get("ko").supports("honorifics") is True   # Korean has its own system


# ==========================================================================
# Korean's engines satisfy the protocols
# ==========================================================================

def test_korean_engines_load():
    ko = R.get("ko")
    assert ko.writing is not None
    assert ko.pronunciation is not None
    assert ko.transliteration is not None
    assert ko.grammar is not None
    assert ko.levels is not None


@pytest.mark.parametrize("attr,proto", [
    ("writing", WritingSystemEngine),
    ("pronunciation", PronunciationEngine),
    ("transliteration", TransliterationEngine),
    ("grammar", GrammarEngine),
])
def test_korean_satisfies_protocols_structurally(attr, proto):
    assert isinstance(getattr(R.get("ko"), attr), proto)


def test_korean_writing_system_enumerates_all_jamo():
    units = R.get("ko").writing.units()
    letters = {u["unit"] for u in units}
    for c in "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㄲㄸㅃㅆㅉ":
        assert c in letters, f"consonant {c} missing"
    for v in "ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣㅐㅔㅘㅝㅚㅟㅢ":
        assert v in letters, f"vowel {v} missing"


def test_korean_writing_system_composes_and_decomposes():
    ws = R.get("ko").writing
    assert ws.compose(["ㅎ", "ㅏ", "ㄴ"]) == "한"
    parts = ws.decompose("한국")
    assert [p["char"] for p in parts] == ["한", "국"]
    assert parts[0]["formula"] == "ㅎ + ㅏ + ㄴ = 한"


def test_korean_pronunciation_still_explains():
    out = R.get("ko").pronunciation.explain("한국어")
    assert out["spoken"] == "한구거"
    assert out["steps"][0]["rule_id"] == "liaison"


def test_korean_grammar_drills_verbs_and_nouns_differently():
    g = R.get("ko").grammar
    verb = g.drill_forms({"term": "먹다", "pos": "verb"})
    assert any(f["form"] == "먹어요" for f in verb)
    noun = g.drill_forms({"term": "책", "pos": "noun"})
    assert any(f["form"] == "책은" for f in noun)
    assert any(f["form"] == "책을" for f in noun)

    # The key is `form` in every language — see GrammarEngine.drill_forms.
    # An earlier version returned "korean", "japanese" and "chinese", which
    # meant shared code had to know all three names.
    for code, word in (("ko", "책"), ("ja", "本"), ("zh", "书")):
        forms = R.get(code).grammar.drill_forms({"term": word, "pos": "noun"})
        assert forms, f"{code} produced no drill forms for a noun"
        for f in forms:
            assert set(f) >= {"form_id", "form", "label"}


def _unwritten_language() -> R.LanguageSpec:
    """A language registered before any of its engines exist.

    Every language passes through this state — Japanese and Mandarin both did
    — so the behaviour is tested against a spec built here rather than against
    whichever real language happens to be least finished today. Pointing these
    tests at a real language means they quietly stop testing anything the
    moment that language is completed.
    """
    return R.LanguageSpec(
        code="xx", name="Unwrittenish", native_name="—", flag="🏳️",
        writing_module="app.languages.unwrittenish.writing",
        confusions_module="app.languages.unwrittenish.confusions",
        levels_module="app.languages.unwrittenish.levels",
        status="planned", status_note="Nothing built yet.",
    )


def test_unwritten_language_modules_fail_loudly_not_silently():
    """Asking for an engine that has not been written must raise, not return a
    stub that quietly does nothing."""
    with pytest.raises(ModuleNotFoundError):
        _ = _unwritten_language().writing


def test_unwritten_confusions_degrade_to_empty():
    """Confusions are optional, so a missing module returns {} rather than
    raising — the adaptive engine falls back to generic weakness tracking.
    This is the one engine allowed to degrade instead of failing."""
    assert _unwritten_language().confusions == {}
    assert len(R.get("ko").confusions) == 10
    assert len(R.get("ja").confusions) == 8
    assert len(R.get("zh").confusions) == 8


def test_each_language_has_its_own_confusions():
    """Korean's 은/는 and Japanese's は/が are different problems with
    different explanations, and neither language sees the other's."""
    ko = set(R.get("ko").confusions)
    ja = set(R.get("ja").confusions)
    zh = set(R.get("zh").confusions)
    assert ko and ja and zh
    assert not (ko & ja), "confusion ids must not be shared between languages"
    assert not (ko & zh) and not (ja & zh)


# ==========================================================================
# Status honesty
# ==========================================================================

def test_status_reflects_reality():
    """A learner must never open a language and find an empty curriculum
    without warning. Every language says where it actually stands."""
    assert R.get("ko").status == "in_progress"
    assert R.get("ko").is_usable is True

    assert R.get("ja").status == "foundation"
    assert R.get("ja").is_usable is True

    assert R.get("zh").status == "foundation"
    assert R.get("zh").is_usable is True

    # A language declared usable must actually have its engines importable.
    # This is the assertion that catches a status promoted ahead of the work.
    for spec in R.all_languages():
        if spec.is_usable:
            assert spec.writing and spec.pronunciation and spec.grammar
            assert spec.levels.levels

    for spec in R.all_languages():
        assert spec.status_note, f"{spec.code} must say what is and is not there"


def test_serialisation_is_json_safe():
    import json
    d = R.get("ko").to_dict(include_engines=True)
    json.loads(json.dumps(d))
    assert d["code"] == "ko"
    assert d["level_scheme"].startswith("CEFR")
    assert d["transliteration"]["scheme"] == "Revised Romanization"


# ==========================================================================
# The guard rail
# ==========================================================================

#: registry.py is deliberately absent from this list — naming the languages is
#: its entire job, and it is the one file that is allowed to.
SHARED_MODULES = [
    "app/engines/srs.py",
    "app/engines/adaptive.py",
    "app/engines/confusion.py",
    "app/engines/diagnosis.py",
    "app/engines/session.py",
    "app/engines/remediation.py",
    "app/db.py",
    "app/migrations.py",
    "app/languages/protocols.py",
]

#: Strings that must not appear in shared code as *logic*. Comments and
#: docstrings may use them as examples — that is how the code explains itself
#: — so only executable lines are checked.
FORBIDDEN = re.compile(r'"(Korean|Japanese|Mandarin|Hangul|hangul_mastery)"')


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """Executable lines only: no comments, no docstring bodies."""
    out = []
    in_doc = False
    delim = ""
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if in_doc:
            if delim in line:
                in_doc = False
            continue
        if line.startswith(('"""', "'''")):
            delim = line[:3]
            if not (len(line) > 3 and line.endswith(delim)):
                in_doc = True
            continue
        if line.startswith("#") or not line:
            continue
        out.append((n, raw))
    return out


@pytest.mark.parametrize("rel", SHARED_MODULES)
def test_shared_code_does_not_hard_code_a_language(rel):
    path = BACKEND / rel
    offenders = [
        (n, line.strip())
        for n, line in _code_lines(path)
        if FORBIDDEN.search(line)
    ]
    assert not offenders, (
        f"{rel} hard-codes a language in executable code: {offenders}. "
        f"Shared modules must go through the registry."
    )


def test_no_korean_text_in_shared_engine_logic():
    """Korean characters in shared code mean content has leaked back in."""
    hangul = re.compile(r"[가-힣]")
    for rel in ("app/engines/srs.py", "app/engines/confusion.py"):
        for n, line in _code_lines(BACKEND / rel):
            assert not hangul.search(line), (
                f"{rel}:{n} contains Korean text in executable code: {line.strip()}"
            )
