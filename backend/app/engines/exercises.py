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
    #: Real sentences, so vocabulary and grammar can be drilled in context
    #: rather than only as isolated pairs.
    sentences: list[dict] = field(default_factory=list)
    #: Grammar points, including the wrong-versus-right pairs each one carries.
    #: Those pairs are authored by whoever wrote the curriculum and describe the
    #: errors learners of that language actually make, which makes them better
    #: drill material than anything a generator could assemble.
    grammar: list[dict] = field(default_factory=list)
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


def kinds_by_skill(language: str) -> dict[str, list[str]]:
    """Every drill this language can run, grouped by what it exercises.

    Built from the registry rather than a table, so a new generator becomes
    available to the adaptive picker the moment it is written — which is the
    point of generators declaring their own skill.
    """
    out: dict[str, list[str]] = {}
    for (lang, kind), skill in _SKILLS.items():
        if lang in (language, "*"):
            out.setdefault(skill, []).append(kind)
    for kinds in out.values():
        kinds.sort()
    return out


def choose_kinds(
    language: str,
    weights: dict[str, float],
    count: int,
    rng: random.Random,
    exclude: frozenset[str] = frozenset(),
) -> list[str]:
    """Pick `count` drill kinds, biased towards the skills that need work.

    Biased, not restricted. A session made only of a learner's worst skill is
    demoralising and teaches badly — interleaving is what makes practice stick,
    and a learner who never sees anything they are good at stops coming back.
    So every available skill keeps a floor weight and can still appear.
    """
    available = kinds_by_skill(language)
    pool = [(skill, kinds) for skill, kinds in available.items()
            if kinds and skill in weights]
    if not pool:
        return []

    # The floor is what keeps this "biased towards" rather than "only".
    floors = [(skill, max(0.12, weights.get(skill, 0.0))) for skill, _ in pool]
    total = sum(w for _, w in floors)

    picked: list[str] = []
    for _ in range(count):
        roll = rng.random() * total
        chosen = floors[-1][0]
        running = 0.0
        for skill, w in floors:
            running += w
            if roll <= running:
                chosen = skill
                break
        candidates = [k for k in available[chosen] if k not in exclude]
        if not candidates:
            continue
        picked.append(rng.choice(candidates))
    return picked


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


# --------------------------------------------------------------------------
# Sentence-based drills
#
# Everything below works from real sentences rather than isolated word pairs.
# That is the point: a learner who can pair 먹다 with "to eat" and cannot say
# "I ate already" has learned a flashcard, not a language. These are shared
# across languages because the *task* is shared — only the sentences differ,
# and those come from each language's own content.
# --------------------------------------------------------------------------

@register("translate_to_english", skill="reading")
def gen_translate_to_english(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Read a sentence, say what it means.

    The easier direction, and the honest one to start with: comprehension
    arrives long before production, and testing only production early makes a
    learner feel they know nothing.
    """
    rows = _sentence_pool(spec, ctx)
    if not rows:
        return _no_sentences("translate_to_english", ctx)
    picks = _sample(rows, spec.get("count", 6), ctx.rng)
    return [Exercise(
        kind="translate_to_english", skill="reading",
        prompt=r["target"], answer=r["english"], audio=r["target"],
        explain=_sentence_note(r),
        data={"transliteration": r.get("transliteration", ""),
              "pronunciation": r.get("pronunciation", ""),
              "accepts_variants": True, "free_text": True},
        hints=spec.get("hints", True),
        item_type="sentence", item_id=r["id"],
    ) for r in picks]


@register("translate_to_target", skill="writing")
def gen_translate_to_target(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Given the meaning, build the sentence.

    Harder, and where the real learning is. Marked leniently on spacing,
    because Japanese and Mandarin are written without spaces and a learner who
    adds one has not made a mistake worth failing.
    """
    rows = _sentence_pool(spec, ctx)
    if not rows:
        return _no_sentences("translate_to_target", ctx)
    picks = _sample(rows, spec.get("count", 5), ctx.rng)
    return [Exercise(
        kind="translate_to_target", skill="writing",
        prompt=r["english"], answer=r["target"], audio=r["target"],
        explain=_sentence_note(r),
        data={"accepts_variants": True, "free_text": True,
              "chunks": r.get("chunks") or []},
        hints=spec.get("hints", False),
        item_type="sentence", item_id=r["id"],
    ) for r in picks]


@register("sentence_complete", skill="grammar")
def gen_sentence_complete(spec: dict, ctx: GenContext) -> list[Exercise]:
    """One piece removed from a real sentence, with the reason attached.

    The blanks are authored rather than chosen at random, because a randomly
    deleted word usually has several defensible answers and marking one of them
    wrong teaches a learner to distrust the app.
    """
    rows = [r for r in _sentence_pool(spec, ctx) if r.get("blanks")]
    if not rows:
        return _no_sentences("sentence_complete", ctx)
    picks = _sample(rows, spec.get("count", 6), ctx.rng)
    out = []
    for r in picks:
        blank = ctx.rng.choice(r["blanks"])
        answer = blank.get("answer", "")
        if not answer or answer not in r["target"]:
            continue
        options = list(blank.get("options") or [])
        if answer not in options:
            options.append(answer)
        ctx.rng.shuffle(options)
        out.append(Exercise(
            kind="sentence_complete", skill="grammar",
            prompt=r["target"].replace(answer, "____", 1),
            answer=answer,
            options=options if len(options) > 1 else [],
            audio=r["target"],
            explain=(blank.get("why") or "") + (
                f"  ({r['english']})" if r.get("english") else ""),
            data={"english": r.get("english", ""),
                  "grammar_ids": r.get("grammar_ids") or []},
            hints=spec.get("hints", True),
            item_type="sentence", item_id=r["id"],
        ))
    return out


# --------------------------------------------------------------------------
# Drills built from the curriculum's own error catalogue
#
# Every grammar point carries a `mistakes` list: the wrong sentence, the right
# one, and why. Those were authored by someone describing what learners of that
# language actually get wrong, and until now they were only ever *displayed*.
# Read as exercises they are better than anything a generator could assemble,
# because a plausible wrong answer is the hard part of writing a drill and these
# are not plausible — they are real.
#
# Two drills, deliberately in this order. Recognising the error is easier than
# producing the correction, so `spot_the_error` comes first and
# `fix_the_sentence` asks for the same knowledge with the scaffolding removed.
# --------------------------------------------------------------------------

def _error_pairs(spec: dict, ctx: GenContext) -> list[dict]:
    """Authored wrong/right pairs, optionally narrowed to one grammar point."""
    wanted = spec.get("grammar_id") or ""
    out = []
    for point in ctx.grammar:
        if wanted and point.get("id") != wanted:
            continue
        for m in point.get("mistakes") or []:
            if m.get("wrong") and m.get("right") and m["wrong"] != m["right"]:
                out.append({**m, "point": point})
    return out


def _no_error_pairs(kind: str, ctx: GenContext, wanted: str) -> list[Exercise]:
    """Say so, visibly, rather than returning an empty list.

    An empty list looks to the caller exactly like "this language has no such
    drill", and the two are different: one is a gap in the curriculum that
    someone can fill by authoring content.
    """
    where = f"the grammar point {wanted}" if wanted else "this language"
    return [Exercise(
        kind="unsupported", skill="grammar",
        prompt=f"No worked errors are written for {where} yet.",
        answer="",
        explain=("This drill is built from the wrong-versus-right pairs in the "
                 "curriculum. Where none are authored, there is nothing "
                 "honest to ask."),
        data={"missing": "error_pairs", "requested": kind, "grammar_id": wanted},
        item_type="", item_id="",
    )]


@register("spot_the_error", skill="grammar")
def gen_spot_the_error(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Which of these two sentences is right? — with the reason waiting."""
    pairs = _error_pairs(spec, ctx)
    if not pairs:
        return _no_error_pairs("spot_the_error", ctx, spec.get("grammar_id", ""))

    out = []
    for m in _sample(pairs, spec.get("count", 5), ctx.rng):
        options = [m["right"], m["wrong"]]
        ctx.rng.shuffle(options)
        out.append(Exercise(
            kind="spot_the_error", skill="grammar",
            prompt="Which one is correct?",
            answer=m["right"], options=options, audio=m["right"],
            explain=m.get("why", ""),
            data={"wrong": m["wrong"], "point": m["point"].get("name", ""),
                  "grammar_id": m["point"].get("id", "")},
            item_type="grammar", item_id=m["point"].get("id", ""),
        ))
    return out


@register("fix_the_sentence", skill="writing")
def gen_fix_the_sentence(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Here is the wrong sentence. Write the right one.

    Production, not recognition: there is nothing to pick from, so the learner
    has to know the correct form well enough to type it.
    """
    pairs = _error_pairs(spec, ctx)
    if not pairs:
        return _no_error_pairs("fix_the_sentence", ctx, spec.get("grammar_id", ""))

    out = []
    for m in _sample(pairs, spec.get("count", 5), ctx.rng):
        out.append(Exercise(
            kind="fix_the_sentence", skill="writing",
            prompt=f"This is wrong. Write it correctly:\n{m['wrong']}",
            answer=m["right"], audio=m["right"],
            explain=m.get("why", ""),
            data={"wrong": m["wrong"], "point": m["point"].get("name", ""),
                  "grammar_id": m["point"].get("id", "")},
            hints=spec.get("hints", ctx.hints),
            item_type="grammar", item_id=m["point"].get("id", ""),
        ))
    return out


@register("grammar_transform", skill="grammar")
def gen_grammar_transform(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Change one thing about a form, and say which thing.

    This is the one drill that reaches straight into each language's own
    grammar engine. Korean returns conjugations, Japanese returns て-forms and
    politeness registers, Mandarin — which has no conjugation at all — returns
    aspect particles and measure words. Same drill, three genuinely different
    grammars, and no shared code that has to know which is which.

    Authored sentence-level transforms are used first when a language has them,
    because "make this sentence past" teaches more than "make this word past".
    """
    out: list[Exercise] = []

    for r in [s for s in _sentence_pool(spec, ctx) if s.get("transforms")]:
        for t in r["transforms"]:
            if not t.get("answer"):
                continue
            out.append(Exercise(
                kind="grammar_transform", skill="grammar",
                prompt=f"{r['target']}  →  make it {t.get('to', 'different')}",
                answer=t["answer"], audio=t["answer"],
                explain=t.get("why", ""),
                data={"from": r["target"], "to": t.get("to", ""),
                      "english": r.get("english", "")},
                hints=spec.get("hints", True),
                item_type="sentence", item_id=r["id"],
            ))

    # Then word-level transforms, from whatever this language's grammar engine
    # says is worth practising about a word.
    try:
        grammar = registry.get(ctx.language).grammar
    except (ModuleNotFoundError, AttributeError):
        grammar = None

    if grammar is not None:
        rows = [v for v in ctx.vocab if v.get("pos")]
        for row in _sample(rows, spec.get("count", 6), ctx.rng):
            try:
                forms = grammar.drill_forms(dict(row))
            except Exception:
                continue
            usable = [f for f in forms if f.get("form") and f.get("label")
                      and f["form"] != row["term"]]
            if not usable:
                continue
            f = ctx.rng.choice(usable)
            out.append(Exercise(
                kind="grammar_transform", skill="grammar",
                prompt=f"{row['term']}  →  {f['label']}",
                answer=f["form"], audio=f["form"],
                explain=f.get("note", "") or f"{row['term']} — {row.get('meaning', '')}",
                data={"from": row["term"], "category": f.get("category", ""),
                      "meaning": row.get("meaning", "")},
                hints=spec.get("hints", True),
                item_type="vocab", item_id=row["id"],
            ))

    ctx.rng.shuffle(out)
    return out[: spec.get("count", 6)]


@register("sentence_order", skill="grammar")
def gen_sentence_order(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Rebuild a sentence from its parts."""
    rows = [r for r in _sentence_pool(spec, ctx)
            if len(r.get("chunks") or []) >= 3]
    if not rows:
        return _no_sentences("sentence_order", ctx)
    picks = _sample(rows, spec.get("count", 5), ctx.rng)
    out = []
    for r in picks:
        chunks = list(r["chunks"])
        ctx.rng.shuffle(chunks)
        out.append(Exercise(
            kind="sentence_order", skill="grammar",
            prompt=r.get("english") or "Put these in order",
            answer="".join(r["chunks"]) if not registry.get(ctx.language).uses_spaces
                   else " ".join(r["chunks"]),
            options=chunks, audio=r["target"],
            explain=_sentence_note(r),
            data={"target": r["target"], "chunks": r["chunks"]},
            item_type="sentence", item_id=r["id"],
        ))
    return out


def _no_sentences(kind: str, ctx: GenContext) -> list[Exercise]:
    """No sentence content for this language yet — say so.

    Returning an empty list would look identical to a bug. The same convention
    as an unregistered generator applies: a gap in the content is surfaced as a
    gap, never hidden behind a blank screen.
    """
    return [Exercise(
        kind="unsupported",
        prompt=f"No sentences are written for {ctx.language} yet, so "
               f"{kind.replace('_', ' ')} has nothing to draw on.",
        answer=None,
        explain="This is a gap in the curriculum rather than a bug. Korean is "
                "the reference implementation and has its sentence bank; the "
                "others are being written.",
        data={"requested_kind": kind, "language": ctx.language,
              "missing": "sentences"},
    )]


def _sentence_pool(spec: dict, ctx: GenContext) -> list[dict]:
    """Sentences for this drill, narrowed by whatever the caller asked for."""
    rows = spec.get("pool") or ctx.sentences
    if spec.get("level"):
        rows = [r for r in rows if r.get("level") == spec["level"]] or rows
    if spec.get("topic"):
        rows = [r for r in rows if r.get("topic") == spec["topic"]] or rows
    if spec.get("grammar_id"):
        wanted = spec["grammar_id"]
        narrowed = [r for r in rows if wanted in (r.get("grammar_ids") or [])]
        rows = narrowed or rows
    if spec.get("vocab_id"):
        wanted = spec["vocab_id"]
        narrowed = [r for r in rows if wanted in (r.get("vocab_ids") or [])]
        rows = narrowed or rows
    return [r for r in rows if r.get("target")]


def _sentence_note(r: dict) -> str:
    parts = [r.get("english", ""), r.get("note", "")]
    pron = r.get("pronunciation", "")
    if pron and pron != r.get("target"):
        parts.append(f"Said: {pron}")
    return "  ".join(p for p in parts if p)


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
