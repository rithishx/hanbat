"""
Exercise generation.

Lessons store *specs*, not questions:

    {"type": "jamo_recognition", "pool": ["ㅏ", "ㅣ", "ㅗ"], "count": 8}

expanded here into concrete items at request time. That indirection buys three
things. A drill draws fresh items every session, so the learner cannot memorise
that question four is always ㅗ. The content files stay small — nineteen
lessons produce eighty-eight specs rather than eight hundred hand-written
questions. And a generator improvement reaches every lesson at once.

Generators are registered per language. `jamo_recognition` belongs to Korean;
`tone_pair` will belong to Mandarin; `listen_type` is shared because "type what
you hear" means the same thing everywhere. A spec whose type nobody has
registered returns an explicit `unsupported` marker rather than an empty list,
so a half-built language module surfaces as a visible gap instead of a lesson
that silently renders nothing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional

from ..languages import registry

#: A generator takes (spec, context) and returns a list of Exercise.
Generator = Callable[[dict, "GenContext"], list["Exercise"]]

_GENERATORS: dict[tuple[str, str], Generator] = {}   # (language|"*", kind) -> fn
_SKILLS: dict[tuple[str, str], str] = {}             # (language|"*", kind) -> skill


@dataclass
class Exercise:
    """One concrete question, ready to render."""

    kind: str
    prompt: str
    answer: Any
    #: Multiple-choice options, empty for free-entry questions.
    options: list[str] = field(default_factory=list)
    #: What to show the learner after they answer — never just "wrong".
    explain: str = ""
    #: Audio to play, if any: text the TTS layer should speak.
    audio: str = ""
    #: Extra payload the UI needs (jamo parts, syllable layout, ...).
    data: dict = field(default_factory=dict)
    skill: str = "grammar"
    difficulty: float = 0.5
    item_type: str = ""
    item_id: str = ""
    hints: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GenContext:
    """Everything a generator may need beyond its own spec."""

    language: str
    rng: random.Random
    #: Rows from the content cache, if the generator needs real vocabulary.
    vocab: list[dict] = field(default_factory=list)
    script_units: list[dict] = field(default_factory=list)
    level: str = ""
    hints: bool = True

    @property
    def spec(self):
        return registry.get(self.language)


def register(kind: str, language: str = "*",
             skill: str = "grammar") -> Callable[[Generator], Generator]:
    """Register a generator. `language="*"` means it works for any language.

    `skill` is declared here so the four-skill tracker can classify an exercise
    without running it. It lives with the generator rather than in a table in
    the loader, because a shared table would have to list every language's
    exercise kinds — `jamo_recognition`, `mora_count`, `tone_sandhi_predict` —
    which is exactly the kind of creeping language knowledge in shared code
    this architecture is built to avoid.
    """
    def deco(fn: Generator) -> Generator:
        _GENERATORS[(language, kind)] = fn
        _SKILLS[(language, kind)] = skill
        return fn
    return deco


def _lookup(language: str, kind: str) -> Optional[Generator]:
    return _GENERATORS.get((language, kind)) or _GENERATORS.get(("*", kind))


def skill_for(language: str, kind: str, default: str = "grammar") -> str:
    """Which of the four skills a generator kind exercises."""
    return (_SKILLS.get((language, kind))
            or _SKILLS.get(("*", kind))
            or default)


def supported_kinds(language: str) -> list[str]:
    return sorted({k for (lang, k) in _GENERATORS if lang in (language, "*")})


def generate(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Expand one generator spec into concrete exercises."""
    kind = spec.get("type", "")
    fn = _lookup(ctx.language, kind)
    if fn is None:
        return [Exercise(
            kind="unsupported", prompt=f"Exercise type {kind!r} is not implemented "
            f"for {ctx.language} yet.", answer=None,
            explain="This is a gap in the language module, not a bug in the lesson. "
                    "It is surfaced rather than hidden so it can be fixed.",
            data={"requested_kind": kind, "language": ctx.language},
        )]
    try:
        return fn(spec, ctx)
    except Exception as e:                   # a broken generator must not kill a lesson
        return [Exercise(
            kind="error", prompt=f"Could not build {kind!r} exercises.", answer=None,
            explain=f"{type(e).__name__}: {e}",
            data={"requested_kind": kind},
        )]


def _sample(pool: list, n: int, rng: random.Random) -> list:
    """Sample without replacement, repeating the pool if it is too small."""
    if not pool:
        return []
    out: list = []
    while len(out) < n:
        chunk = list(pool)
        rng.shuffle(chunk)
        out.extend(chunk[: n - len(out)])
    return out[:n]


def _distractors(correct: str, pool: list[str], n: int, rng: random.Random) -> list[str]:
    others = [p for p in pool if p != correct]
    rng.shuffle(others)
    opts = others[:n] + [correct]
    rng.shuffle(opts)
    return opts


# ==========================================================================
# Language-agnostic generators
# ==========================================================================

@register("listen_type", skill="listening")
def gen_listen_type(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Dictation. Works for any language that can produce audio for a string."""
    pool = spec.get("pool") or [v["term"] for v in ctx.vocab]
    items = _sample(pool, spec.get("count", 6), ctx.rng)
    return [Exercise(
        kind="listen_type", skill="listening",
        prompt="Type what you hear.", answer=item, audio=item,
        hints=spec.get("hints", ctx.hints),
        explain=f"The answer was {item}.",
        item_type="sentence", item_id=item,
    ) for item in items]


@register("listen_choose", skill="listening")
def gen_listen_choose(spec: dict, ctx: GenContext) -> list[Exercise]:
    pool = spec.get("pool") or [v["term"] for v in ctx.vocab]
    if len(pool) < 2:
        return []
    items = _sample(pool, spec.get("count", 6), ctx.rng)
    return [Exercise(
        kind="listen_choose", skill="listening",
        prompt="Which one did you hear?", answer=item, audio=item,
        options=_distractors(item, pool, 3, ctx.rng),
        item_type="sentence", item_id=item,
    ) for item in items]


@register("vocab_recall", skill="vocabulary")
def gen_vocab_recall(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Meaning -> term. The direction that actually builds production."""
    rows = [v for v in ctx.vocab if v.get("term") and v.get("meaning")]
    if len(rows) < 4:
        return []
    picked = _sample(rows, spec.get("count", 8), ctx.rng)
    terms = [r["term"] for r in rows]
    return [Exercise(
        kind="vocab_recall", skill="vocabulary",
        prompt=f"How do you say “{r['meaning']}”?",
        answer=r["term"], audio=r["term"],
        options=_distractors(r["term"], terms, 3, ctx.rng)
                 if spec.get("multiple_choice", True) else [],
        explain=(r.get("example_native") or "") + (
            f"  —  {r.get('example_en')}" if r.get("example_en") else ""),
        item_type="vocab", item_id=r["id"],
    ) for r in picked]


@register("vocab_recognise", skill="vocabulary")
def gen_vocab_recognise(spec: dict, ctx: GenContext) -> list[Exercise]:
    rows = [v for v in ctx.vocab if v.get("term") and v.get("meaning")]
    if len(rows) < 4:
        return []
    picked = _sample(rows, spec.get("count", 8), ctx.rng)
    meanings = [r["meaning"] for r in rows]
    return [Exercise(
        kind="vocab_recognise", skill="vocabulary",
        prompt=r["term"], answer=r["meaning"], audio=r["term"],
        options=_distractors(r["meaning"], meanings, 3, ctx.rng),
        item_type="vocab", item_id=r["id"],
    ) for r in picked]


@register("concept_to_korean", skill="writing")
@register("concept_to_target", skill="writing")
def gen_concept(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Situation -> produce the language. Not translation.

    The prompt describes a situation rather than an English sentence, because
    "Translate: I want to eat" trains you to build Korean out of English,
    while "You are hungry — tell your friend" trains you to build it out of
    the situation. Only the second one survives contact with a real
    conversation.
    """
    prompts = spec.get("prompts") or []
    return [Exercise(
        kind="produce", skill="writing",
        prompt=p.get("situation", ""), answer=p.get("target", ""),
        explain=p.get("note", ""), audio=p.get("target", ""),
        hints=False,
        data={"accepts_variants": True},
    ) for p in prompts]


@register("multiple_choice")
def gen_multiple_choice(spec: dict, ctx: GenContext) -> list[Exercise]:
    return [Exercise(
        kind="multiple_choice", skill=spec.get("skill", "grammar"),
        prompt=q.get("q", ""), answer=q.get("a"),
        options=q.get("options", []), explain=q.get("why", ""),
    ) for q in spec.get("questions", [])]


@register("pronounce", skill="speaking")
def gen_pronounce(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Record and compare.

    Scoring depends on a speech engine being configured. When none is, the
    exercise still works as listen-and-repeat and says so, rather than
    inventing a score.
    """
    targets = spec.get("targets") or spec.get("pool") or []
    return [Exercise(
        kind="pronounce", skill="speaking",
        prompt=f"Say: {t}", answer=t, audio=t,
        explain=spec.get("note", ""),
        data={"scoring": "requires_stt_engine"},
        item_type="pronunciation", item_id=t,
    ) for t in targets]


@register("read_aloud", skill="speaking")
def gen_read_aloud(spec: dict, ctx: GenContext) -> list[Exercise]:
    return [Exercise(
        kind="read_aloud", skill="speaking",
        prompt=f"Read this aloud: {item}", answer=item, audio=item,
        explain=spec.get("note", ""),
        data={"scoring": "requires_stt_engine"},
    ) for item in (spec.get("items") or [])]


@register("confusion_drill")
def gen_confusion_drill(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Drill one confusion pair, using that language's own examples.

    Shared, because the *mechanism* is shared even though not one of the pairs
    is: the engine looks up `CONFUSIONS` through the registry, so Korean gets
    은/는 versus 이/가, Japanese gets は versus が, and Mandarin gets 不 versus
    没 — from the same six lines of code.
    """
    confusions = registry.get(ctx.language).confusions
    c = confusions.get(spec.get("confusion_id", ""))
    if c is None:
        return []
    examples = c.examples or []
    if not examples:
        return []
    picks = _sample(examples, spec.get("count", min(6, len(examples))), ctx.rng)
    return [Exercise(
        kind="confusion_drill", skill="grammar",
        prompt=ex.get("english") or c.drill_prompt,
        answer=ex.get("target", ""),
        audio=ex.get("target", ""),
        explain=ex.get("why") or c.one_line,
        hints=spec.get("hints", True),
        data={"confusion_id": c.id, "one_line": c.one_line, "title": c.title},
        item_type="confusion", item_id=c.id,
    ) for ex in picks]


@register("word_read", skill="reading")
def gen_word_read(spec: dict, ctx: GenContext) -> list[Exercise]:
    out = []
    for item in spec.get("items", []):
        term = (item.get("target") or item.get("term")
                or item.get("korean", ""))   # "korean" is the legacy spelling
        if not term:
            continue
        out.append(Exercise(
            kind="word_read", skill="reading",
            prompt=term, answer=item.get("meaning", ""), audio=term,
            explain=item.get("note") or item.get("breakdown", ""),
            data={"pronounced": item.get("pronounced", "")},
            item_type="vocab", item_id=term,
        ))
    return out


# Import the language packs so their generators self-register. Kept at the
# bottom so the shared generators above are defined first.
def load_language_generators(language: str) -> int:
    """Import a language's exercise module, if it has one. Returns how many
    generators it contributed."""
    import importlib
    before = len(_GENERATORS)
    try:
        importlib.import_module(f"app.languages.{_PACKAGE[language]}.exercises")
    except (KeyError, ModuleNotFoundError):
        return 0
    return len(_GENERATORS) - before


_PACKAGE = {"ko": "korean", "ja": "japanese", "zh": "mandarin"}
