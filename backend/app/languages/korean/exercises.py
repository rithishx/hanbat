"""
Korean exercise generators.

These are the drills that only make sense for Hangul: recognising jamo,
assembling syllable blocks, predicting what a 받침 will actually sound like,
and choosing between particle allomorphs. None of them transfer to Japanese or
Mandarin, which is why they live here rather than in the shared engine.

Every generator draws its correct answers from the engines rather than from
stored strings, so a fix to a phonology rule immediately fixes every drill
built on it.
"""

from __future__ import annotations

import random
from typing import Optional

from ...engines.exercises import Exercise, GenContext, _distractors, _sample, register
from . import conjugation as C
from . import hangul as H
from . import phonology as P
from . import romanization as R

LANG = "ko"


def _pool_jamo(spec: dict, kinds=("consonant", "vowel")) -> list[str]:
    pool = spec.get("pool")
    if pool:
        return list(pool)
    out: list[str] = []
    if "consonant" in kinds:
        out += list(H.BASIC_CONSONANTS) + list(H.TENSE_CONSONANTS)
    if "vowel" in kinds:
        out += list(H.BASIC_VOWELS) + list(H.COMPLEX_VOWELS)
    return out


def _sound_of(jamo: str) -> str:
    """The romanised sound of a single letter, for the answer key."""
    if jamo in H.MEDIAL_INDEX:
        return R.MEDIAL_ROMAN[jamo]
    return R.INITIAL_ROMAN.get(jamo, jamo) or "(silent)"


# ==========================================================================
# Letters
# ==========================================================================

@register("jamo_recognition", LANG, skill="reading")
def jamo_recognition(spec: dict, ctx: GenContext) -> list[Exercise]:
    """See a letter, choose its sound."""
    pool = _pool_jamo(spec)
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    sounds = [_sound_of(j) for j in pool]
    out = []
    for j in picks:
        correct = _sound_of(j)
        out.append(Exercise(
            kind="jamo_recognition", skill="reading",
            prompt=f"What sound does {j} make?", answer=correct,
            options=_distractors(correct, sounds, 3, ctx.rng),
            audio=H.compose("ㅇ", j) if j in H.MEDIAL_INDEX else H.compose(j, "ㅏ"),
            explain=_jamo_note(j),
            hints=spec.get("hints", True),
            item_type="script_unit", item_id=f"ko-jamo-{j}",
        ))
    return out


@register("jamo_audio", LANG, skill="listening")
def jamo_audio(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Hear a sound, choose the letter."""
    pool = spec.get("pool") or _pool_jamo(spec)
    picks = _sample(pool, spec.get("count", 6), ctx.rng)
    out = []
    for item in picks:
        # The pool may hold letters (ㅏ) or whole syllables (아).
        syllable = item if H.is_hangul_syllable(item) else (
            H.compose("ㅇ", item) if item in H.MEDIAL_INDEX else H.compose(item, "ㅏ"))
        out.append(Exercise(
            kind="jamo_audio", skill="listening",
            prompt="Which one did you hear?", answer=item, audio=syllable,
            options=_distractors(item, list(pool), 3, ctx.rng),
            item_type="script_unit", item_id=f"ko-jamo-{item}",
        ))
    return out


def _jamo_note(j: str) -> str:
    if j == "ㅇ":
        return "Silent at the start of a block; 'ng' underneath one."
    if j in H.CONSONANT_NAMES:
        cls = H.CONSONANT_CLASS.get(j, "")
        name = H.CONSONANT_NAMES[j]
        if cls == "tense":
            return f"{name} — the tight version. No air at all."
        if cls == "aspirated":
            return f"{name} — the breathy version. A strong puff of air."
        return f"{name}."
    return ""


@register("trace", LANG, skill="writing")
def trace(spec: dict, ctx: GenContext) -> list[Exercise]:
    pool = _pool_jamo(spec)
    return [Exercise(
        kind="trace", skill="writing",
        prompt=f"Write {j}", answer=j,
        data={"stroke_count": None, "letter": j},
        item_type="script_unit", item_id=f"ko-jamo-{j}",
    ) for j in pool]


# ==========================================================================
# Syllable blocks
# ==========================================================================

def _syllable_pool(spec: dict, ctx: GenContext) -> list[str]:
    initials = spec.get("initials") or list(H.BASIC_CONSONANTS)
    medials = spec.get("medials") or list(H.BASIC_VOWELS)
    finals = ([""] + [f for f in H.SEVEN_FINAL_SOUNDS]) if spec.get("with_final") else [""]
    out = []
    for i in initials:
        for m in medials:
            for f in finals:
                try:
                    out.append(H.compose(i, m, f))
                except ValueError:
                    continue
    return out


@register("syllable_read", LANG, skill="reading")
def syllable_read(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Read a block and choose how it sounds."""
    pool = spec.get("pool") or _syllable_pool(spec, ctx)
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    readings = [R.romanize(s) for s in pool]
    out = []
    for s in picks:
        correct = R.romanize(s)
        syl = H.decompose(s)
        out.append(Exercise(
            kind="syllable_read", skill="reading",
            prompt=s, answer=correct, audio=s,
            options=_distractors(correct, readings, 3, ctx.rng),
            explain=" + ".join(syl.parts()) + f" = {s}",
            data=H.describe_syllable(s),
            hints=spec.get("hints", True),
            item_type="syllable", item_id=s,
        ))
    return out


@register("syllable_build", LANG, skill="writing")
def syllable_build(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Given jamo, assemble the block."""
    pool = spec.get("pool") or _syllable_pool(spec, ctx)
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    out = []
    for s in picks:
        syl = H.decompose(s)
        parts = syl.parts()
        out.append(Exercise(
            kind="syllable_build", skill="writing",
            prompt=" + ".join(parts) + " = ?", answer=s, audio=s,
            explain=f"{' + '.join(parts)} = {s}",
            data={"parts": parts, "layout": syl.layout},
            item_type="syllable", item_id=s,
        ))
    return out


@register("syllable_decompose", LANG, skill="reading")
def syllable_decompose(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Given a block, name its parts."""
    pool = spec.get("pool") or _syllable_pool({**spec, "with_final": True}, ctx)
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    out = []
    for s in picks:
        syl = H.decompose(s)
        out.append(Exercise(
            kind="syllable_decompose", skill="reading",
            prompt=f"Which letters make up {s}?", answer=syl.parts(), audio=s,
            data={"layout": syl.layout, "has_batchim": syl.has_batchim},
            explain=f"{' + '.join(syl.parts())} = {s}",
            item_type="syllable", item_id=s,
        ))
    return out


# ==========================================================================
# 받침 and sound changes
# ==========================================================================

_RULE_WORDS: dict[str, list[str]] = {
    "liaison": ["한국어", "책을", "음악을", "꽃이", "밭에", "옷을", "앞에", "집에",
                "밖에", "값이", "맛있어요", "있어요", "먹어요", "읽어요"],
    "tensification": ["학교", "먹다", "국밥", "입다", "책상", "숟가락", "읽다", "학생"],
    "nasalisation": ["국물", "한국말", "먹는", "있는", "합니다", "감사합니다",
                     "작년", "식물", "법률", "국립"],
    "aspiration": ["축하", "좋고", "많다", "입학", "좁히다", "놓다", "급히"],
    "lateralisation": ["신라", "설날", "연락", "관리", "칼날"],
    "palatalisation": ["같이", "굳이", "해돋이", "닫히다", "붙이다"],
}
_ALL_RULE_WORDS = sorted({w for ws in _RULE_WORDS.values() for w in ws})


@register("batchim_predict", LANG, skill="pronunciation")
def batchim_predict(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Given the spelling, predict the pronunciation — and see why.

    The answer key comes from the phonology engine, so these drills can never
    drift away from what the app teaches in the 받침 lessons.
    """
    if spec.get("pool"):
        pool = list(spec["pool"])
    elif spec.get("rule"):
        pool = _RULE_WORDS.get(spec["rule"], _ALL_RULE_WORDS)
    elif spec.get("rules"):
        pool = [w for r in spec["rules"] for w in _RULE_WORDS.get(r, [])]
    elif spec.get("cluster_only"):
        pool = ["값", "값이", "닭", "닭이", "앉다", "앉아", "삶", "젊어",
                "여덟", "없어", "읽다", "읽어", "넓다", "핥다", "몫을"]
    else:
        pool = _ALL_RULE_WORDS

    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    spokens = [P.pronounce(w).spoken for w in pool]
    out = []
    for w in picks:
        res = P.pronounce(w)
        steps = [f"{c.rule_ko} ({c.rule_en}): {c.before} → {c.after}" for c in res.changes]
        out.append(Exercise(
            kind="batchim_predict", skill="pronunciation",
            prompt=f"How is {w} actually pronounced?",
            answer=res.spoken, audio=w,
            options=_distractors(res.spoken, spokens, 3, ctx.rng)
                     if spec.get("hints", True) else [],
            explain=(" · ".join(steps) if steps
                     else "No sound change — it is said exactly as written."),
            data={"written": w, "spoken": res.spoken,
                  "changes": [c.to_dict() for c in res.changes]},
            hints=spec.get("hints", True),
            item_type="pronunciation", item_id=w,
        ))
    return out


@register("listen_discriminate", LANG, skill="listening")
def listen_discriminate(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Same or different? The drill that builds the three-way contrast."""
    out: list[Exercise] = []
    count = spec.get("count", 8)

    triples = spec.get("triples") or []
    pairs = spec.get("pairs") or []

    if spec.get("mode") == "standard_vs_casual":
        for w in _sample(spec.get("pool", []), count, ctx.rng):
            std = P.pronounce(w).spoken
            casual = P.pronounce(w, P.Hints(casual=True)).spoken
            out.append(Exercise(
                kind="listen_discriminate", skill="listening",
                prompt=f"Both are {w}. Which did you hear?",
                answer="standard" if ctx.rng.random() < 0.5 else "casual",
                options=["standard", "casual"],
                audio=w,
                explain=f"Careful speech: [{std}].  Everyday speech: [{casual}]. "
                        f"Say the first, expect the second.",
                data={"standard": std, "casual": casual},
            ))
        return out

    units = [list(t) for t in triples] + [list(p) for p in pairs]
    if not units:
        return []

    for group in _sample(units, count, ctx.rng):
        # A group may hold jamo (ㄱ) or whole words (달). Make syllables of jamo.
        shown = [g if len(g) > 1 or H.is_hangul_syllable(g)
                 else (H.compose("ㅇ", g) if g in H.MEDIAL_INDEX else H.compose(g, "ㅏ"))
                 for g in group]
        heard = ctx.rng.choice(shown)
        same = len(set(P.pronounce(s).spoken for s in shown)) == 1
        out.append(Exercise(
            kind="listen_discriminate", skill="listening",
            prompt="Which one did you hear?" if not same
                   else "Do these two sound the same or different?",
            answer=heard if not same else "same",
            options=shown if not same else ["same", "different"],
            audio=heard,
            explain=("These are spelled differently but pronounced identically."
                     if same else
                     f"The three differ only in how much air you release: "
                     f"{' / '.join(shown)}."),
            data={"group": shown, "identical": same},
        ))
    return out


# ==========================================================================
# Grammar
# ==========================================================================

@register("particle_choice", LANG)
def particle_choice(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Choose the right particle, with the batchim rule as the explanation."""
    options = spec.get("options") or ["은", "는"]
    rows = [v for v in ctx.vocab if v.get("term") and v.get("pos") in ("noun", "pronoun")]
    if not rows:
        return []
    picks = _sample(rows, spec.get("count", 8), ctx.rng)

    pairs = {("은", "는"): H.TOPIC, ("이", "가"): H.SUBJECT,
             ("을", "를"): H.OBJECT, ("과", "와"): H.AND_NOUN}
    pair = next((v for k, v in pairs.items() if set(k) <= set(options)), None)

    out = []
    for r in picks:
        word = r["term"]
        if pair:
            correct = H.pick_particle(word, *pair)
            has = H.ends_with_batchim(word)
            explain = (f"{word} ends in the batchim {H.final_of(word)}, so {correct}."
                       if has else f"{word} ends in a vowel, so {correct}.")
        else:
            correct = options[0]
            explain = ""
        out.append(Exercise(
            kind="particle_choice", skill="grammar",
            prompt=f"{word} ___", answer=correct,
            options=list(options), explain=explain,
            audio=word + correct,
            data={"word": word, "meaning": r.get("meaning", "")},
            item_type="grammar", item_id="particles",
        ))
    return out


@register("batchim_choice", LANG)
def batchim_choice(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Explicit word/ending pairs from a grammar point's practice spec."""
    pairs = spec.get("pairs") or []
    picks = _sample(pairs, spec.get("count", len(pairs)), ctx.rng)
    endings = sorted({p[1] for p in pairs})
    out = []
    for word, ending in picks:
        has = H.ends_with_batchim(word)
        out.append(Exercise(
            kind="batchim_choice", skill="grammar",
            prompt=f"{word} + ?", answer=ending, options=endings,
            audio=word + ending,
            explain=(f"{word} ends in {H.final_of(word)}, so {ending}." if has
                     else f"{word} ends in a vowel, so {ending}."),
            item_type="grammar", item_id="batchim_alternation",
        ))
    return out


@register("conjugate", LANG)
def conjugate(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Conjugation drill, drawn from real vocabulary and answered by the engine."""
    form = spec.get("form", "present_polite")
    rows = [v for v in ctx.vocab
            if v.get("pos") in ("verb", "adjective") and v.get("term", "").endswith("다")]
    if spec.get("include_irregulars"):
        # Weight irregulars up: they are where learners actually go wrong.
        irregular = [r for r in rows
                     if C.classify(r["term"]).irregular not in ("", "ㄹ")]
        rows = rows + irregular
    if not rows:
        return []

    picks = _sample(rows, spec.get("count", 8), ctx.rng)
    out = []
    for r in picks:
        word = r["term"]
        try:
            table = C.conjugate(word, pos=r.get("pos") or None,
                                irregular=r.get("irregular") or None)
        except ValueError:
            continue
        if form not in table:
            continue
        f = table[form]
        cls = C.classify(word, pos=r.get("pos") or None)
        note = C.IRREGULAR_EXPLANATIONS.get(cls.irregular, {})
        out.append(Exercise(
            kind="conjugate", skill="grammar",
            prompt=f"{word} → ? ({f.label_en})", answer=f.korean,
            audio=f.korean,
            explain=(f"{note.get('name', 'Regular')}: {note.get('simple', '')}"
                     if cls.irregular else "Regular — the stem does not change."),
            data={"dictionary_form": word, "form": form,
                  "irregular": cls.irregular, "meaning": r.get("meaning", "")},
            hints=spec.get("hints", True),
            item_type="vocab", item_id=r["id"],
        ))
    return out


@register("choose_negation", LANG)
def choose_negation(spec: dict, ctx: GenContext) -> list[Exercise]:
    items = [
        ("저는 술을 ___ 마셔요.", "안", "A choice — you decided not to drink."),
        ("매운 음식을 ___ 먹어요.", "못", "Inability — you physically cannot."),
        ("오늘은 ___ 가요.", "못", "Something is preventing you."),
        ("저는 고기를 ___ 먹어요.", "안", "A choice — you are vegetarian."),
        ("시간이 없어서 ___ 갔어요.", "못", "Circumstance blocked it."),
        ("그 영화를 ___ 봤어요.", "안", "You chose not to watch it."),
        ("한국어를 ___ 읽어요.", "못", "You are not able to read it yet."),
        ("아침을 ___ 먹어요.", "안", "You skip breakfast by choice."),
    ]
    picks = _sample(items, spec.get("count", 8), ctx.rng)
    return [Exercise(
        kind="choose_negation", skill="grammar",
        prompt=q, answer=a, options=["안", "못"], explain=why,
        audio=q.replace("___", a),
        item_type="grammar", item_id="ko-g-015",
    ) for q, a, why in picks]


@register("number_choice", LANG)
def number_choice(spec: dict, ctx: GenContext) -> list[Exercise]:
    items = [
        ("커피 ___ 잔 주세요. (2)", "두", "Counting objects uses native numbers, and 둘 shortens to 두."),
        ("___ 분이에요. (30)", "삼십", "Minutes are always Sino-Korean."),
        ("___ 시예요. (3)", "세", "Hours use native numbers; 셋 shortens to 세."),
        ("___ 원이에요. (5000)", "오천", "Money is Sino-Korean."),
        ("___ 살이에요. (20)", "스무", "Age uses native numbers; 스물 shortens to 스무."),
        ("___ 명 왔어요. (4)", "네", "People are counted with native numbers; 넷 → 네."),
        ("___ 월이에요. (4)", "사", "Months are Sino-Korean."),
        ("책 ___ 권 있어요. (5)", "다섯", "Native, and 다섯 does not shorten."),
    ]
    picks = _sample(items, spec.get("count", 8), ctx.rng)
    return [Exercise(
        kind="number_choice", skill="grammar",
        prompt=q, answer=a, explain=why, audio=q.replace("___", a),
        item_type="grammar", item_id="ko-g-020",
    ) for q, a, why in picks]


# `confusion_drill` lives in the shared engine — see app/engines/exercises.py.


@register("count_syllables", LANG, skill="reading")
def count_syllables(spec: dict, ctx: GenContext) -> list[Exercise]:
    return [Exercise(
        kind="count_syllables", skill="reading",
        prompt=f"How many blocks are in {i['target']}?",
        answer=i["answer"], audio=i["target"],
        explain="One block is one syllable, always.",
    ) for i in spec.get("items", [])]
