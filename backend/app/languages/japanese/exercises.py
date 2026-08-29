"""
Japanese exercise generators.

The distinctively Japanese drills are the timing ones. `mora_count` and
`mora_discriminate` have no Korean equivalent, because Korean rhythm is not
mora-timed — and Korean's `batchim_predict` has no Japanese equivalent, because
kana does not hide its pronunciation. Two languages, two sets of things that
have to be drilled.

`kana_typing` deserves a note: it is not a romanisation crutch. Typing Japanese
requires converting romaji to kana in your head at speed, and it is a real
skill a learner needs. It is the one place romaji earns its keep.
"""

from __future__ import annotations

from typing import Optional

from ...engines.exercises import Exercise, GenContext, _distractors, _sample, register
from . import kana as K
from . import romaji as R
from . import verbs as V

LANG = "ja"


def _kana_pool(spec: dict) -> list[dict]:
    """Kana units, filtered by whatever the lesson asked for."""
    units = K.inventory(include_yoon=spec.get("include_yoon", False))
    if spec.get("pool"):
        wanted = set(spec["pool"])
        units = [u for u in units
                 if u.hiragana in wanted or u.katakana in wanted]
    if spec.get("rows"):
        units = [u for u in units if u.row in spec["rows"]]
    if spec.get("group"):
        units = [u for u in units if u.group == spec["group"]]
    if spec.get("max_stage"):
        units = [u for u in units if u.teaching_stage <= spec["max_stage"]]
    return [{"hiragana": u.hiragana, "katakana": u.katakana, "romaji": u.romaji,
             "group": u.group, "note": u.note, "from_kana": u.from_kana}
            for u in units]


# ==========================================================================
# Kana
# ==========================================================================

@register("kana_recognition", LANG, skill="reading")
def kana_recognition(spec: dict, ctx: GenContext) -> list[Exercise]:
    """See a kana, choose its sound."""
    script = spec.get("script", "hiragana")
    pool = _kana_pool(spec)
    if not pool:
        return []
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    sounds = [u["romaji"] for u in pool]
    out = []
    for u in picks:
        char = u[script]
        out.append(Exercise(
            kind="kana_recognition", skill="reading",
            prompt=f"What sound does {char} make?", answer=u["romaji"],
            options=_distractors(u["romaji"], sounds, 3, ctx.rng),
            audio=char, explain=u["note"],
            hints=spec.get("hints", True),
            data={"script": script, "pair": u["katakana" if script == "hiragana"
                                              else "hiragana"]},
            item_type="script_unit", item_id=f"ja-{script}-{char}",
        ))
    return out


@register("kana_audio", LANG, skill="listening")
def kana_audio(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Hear a sound, choose the kana."""
    script = spec.get("script", "hiragana")
    pool = _kana_pool(spec)
    if len(pool) < 2:
        return []
    picks = _sample(pool, spec.get("count", 6), ctx.rng)
    chars = [u[script] for u in pool]
    return [Exercise(
        kind="kana_audio", skill="listening",
        prompt="Which one did you hear?", answer=u[script], audio=u[script],
        options=_distractors(u[script], chars, 3, ctx.rng),
        item_type="script_unit", item_id=f"ja-{script}-{u[script]}",
    ) for u in picks]


@register("kana_pair", LANG, skill="reading")
def kana_pair(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Hiragana to katakana and back — the same sound, two shapes."""
    pool = _kana_pool(spec)
    if not pool:
        return []
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    direction = spec.get("direction", "hira_to_kata")
    from_key, to_key = (("hiragana", "katakana") if direction == "hira_to_kata"
                        else ("katakana", "hiragana"))
    targets = [u[to_key] for u in pool]
    return [Exercise(
        kind="kana_pair", skill="reading",
        prompt=f"{u[from_key]} — what is this in {to_key}?",
        answer=u[to_key], options=_distractors(u[to_key], targets, 3, ctx.rng),
        audio=u["hiragana"],
        explain=f"Both are {u['romaji']}. Same sound, different script.",
        item_type="script_unit", item_id=f"ja-{to_key}-{u[to_key]}",
    ) for u in picks]


@register("dakuten", LANG, skill="reading")
def dakuten(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Two ticks voice the consonant. か becomes が."""
    pool = [u for u in _kana_pool({"group": "dakuten"})] + \
           [u for u in _kana_pool({"group": "handakuten"})]
    if not pool:
        return []
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    return [Exercise(
        kind="dakuten", skill="reading",
        prompt=f"{u['from_kana']} + ゛ or ゜ = ?", answer=u["hiragana"],
        options=_distractors(u["hiragana"], [p["hiragana"] for p in pool], 3, ctx.rng),
        audio=u["hiragana"],
        explain=f"{u['from_kana']} is {_romaji_of(u['from_kana'])}; "
                f"{u['hiragana']} is {u['romaji']}. The marks voice the consonant.",
        item_type="script_unit", item_id=f"ja-hiragana-{u['hiragana']}",
    ) for u in picks]


def _romaji_of(kana: str) -> str:
    return K.HIRAGANA_TO_ROMAJI.get(K.to_hiragana(kana), kana)


@register("kana_typing", LANG, skill="writing")
def kana_typing(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Type romaji, produce kana — the skill you need to write Japanese at all."""
    pool = spec.get("pool") or [v["term"] for v in ctx.vocab
                                if v.get("term") and not any(K.is_kanji(c) for c in v["term"])]
    if not pool:
        pool = ["にほん", "がっこう", "せんせい", "ともだち", "でんわ"]
    picks = _sample(pool, spec.get("count", 6), ctx.rng)
    return [Exercise(
        kind="kana_typing", skill="writing",
        prompt=f"Type this in kana: {R.romanize(w, 'wapuro')}",
        answer=w, audio=w,
        explain=f"{R.romanize(w, 'wapuro')} → {w}",
        data={"input_mode": "romaji", "wapuro": R.romanize(w, "wapuro")},
        item_type="sentence", item_id=w,
    ) for w in picks]


@register("trace", LANG, skill="writing")
def trace(spec: dict, ctx: GenContext) -> list[Exercise]:
    script = spec.get("script", "hiragana")
    pool = _kana_pool(spec)
    return [Exercise(
        kind="trace", skill="writing",
        prompt=f"Write {u[script]}", answer=u[script],
        data={"script": script, "romaji": u["romaji"]},
        item_type="script_unit", item_id=f"ja-{script}-{u[script]}",
    ) for u in pool]


# ==========================================================================
# Timing — the Japanese-specific drills
# ==========================================================================

@register("mora_count", LANG, skill="pronunciation")
def mora_count(spec: dict, ctx: GenContext) -> list[Exercise]:
    """How many beats? The single most useful Japanese pronunciation drill."""
    pool = spec.get("pool") or [
        "きょう", "がっこう", "せんせい", "コーヒー", "にほん", "しゃしん",
        "とうきょう", "ざっし", "ちょっと", "おばあさん", "きって", "ビール",
        "でんわ", "しんぶん", "べんきょう", "だいがく",
    ]
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    out = []
    for w in picks:
        d = K.mora_diagram(w)
        out.append(Exercise(
            kind="mora_count", skill="pronunciation",
            prompt=f"How many beats (mora) in {w}?",
            answer=d["count"],
            options=[str(n) for n in sorted({d["count"], d["count"] - 1,
                                             d["count"] + 1, len(w)}) if n > 0],
            audio=w,
            explain=f"{d['beats']} — {d['count']} beats. {d['note']}".strip(),
            data=d,
            item_type="pronunciation", item_id=w,
        ))
    return out


@register("mora_discriminate", LANG, skill="listening")
def mora_discriminate(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Long or short? These are different words, and English ears miss it."""
    pairs = spec.get("pairs") or K.minimal_pairs_by_mora()
    picks = _sample(pairs, spec.get("count", 8), ctx.rng)
    out = []
    for p in picks:
        a, b = p["pair"]
        heard = ctx.rng.choice([a, b])
        out.append(Exercise(
            kind="mora_discriminate", skill="listening",
            prompt="Which one did you hear?", answer=heard,
            options=[a, b], audio=heard,
            explain=(f"{a} = {p['meanings'][0]} ({K.count_mora(a)} beats); "
                     f"{b} = {p['meanings'][1]} ({K.count_mora(b)} beats). "
                     f"They differ in {p['differs']}."),
            data=p,
            item_type="pronunciation", item_id=f"{a}/{b}",
        ))
    return out


# ==========================================================================
# Grammar
# ==========================================================================

@register("conjugate", LANG)
def conjugate(spec: dict, ctx: GenContext) -> list[Exercise]:
    form = spec.get("form", "masu")
    rows = [v for v in ctx.vocab if v.get("pos") in
            ("verb", "i-adjective", "na-adjective")]
    if not rows:
        return []
    picks = _sample(rows, spec.get("count", 8), ctx.rng)
    out = []
    for r in picks:
        word = r["term"]
        try:
            table = V.conjugate(word, pos=r.get("pos") or None,
                                verb_class=r.get("irregular") or None)
        except (ValueError, KeyError):
            continue
        if form not in table:
            continue
        f = table[form]
        c = V.classify(word, pos=r.get("pos") or None)
        expl = V.CLASS_EXPLANATIONS.get(c.verb_class, {})
        out.append(Exercise(
            kind="conjugate", skill="grammar",
            prompt=f"{word} → ? ({f.label_en})", answer=f.japanese,
            audio=f.japanese,
            explain=f"{expl.get('name', '')}: {expl.get('simple', '')}".strip(": "),
            data={"dictionary_form": word, "verb_class": c.verb_class,
                  "form": form, "meaning": r.get("meaning", "")},
            hints=spec.get("hints", True),
            item_type="vocab", item_id=r["id"],
        ))
    return out


@register("particle_choice", LANG)
def particle_choice(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Japanese particles carry the grammar English does with word order."""
    items = spec.get("items") or [
        ("私___学生です。", "は", "Introducing yourself sets a topic."),
        ("誰___来ましたか。", "が", "The answer will be new information, so が."),
        ("パン___食べます。", "を", "The direct object."),
        ("学校___行きます。", "に", "A destination."),
        ("学校___勉強します。", "で", "The place the action happens."),
        ("電車___行きます。", "で", "で also marks the means."),
        ("友達___会います。", "に", "会う takes に, not を."),
        ("家___います。", "に", "いる and ある always take に."),
        ("日本___来ました。", "に", "A destination with 来る."),
        ("水___飲みたいです。", "が", "たい often takes が rather than を."),
        ("これ___私のです。", "は", "Already established — topic."),
        ("本___読みます。", "を", "Direct object."),
    ]
    picks = _sample(items, spec.get("count", 8), ctx.rng)
    options = spec.get("options") or ["は", "が", "を", "に", "で"]
    return [Exercise(
        kind="particle_choice", skill="grammar",
        prompt=q, answer=a, options=list(options), explain=why,
        audio=q.replace("___", a),
        item_type="grammar", item_id="ja-particles",
    ) for q, a, why in picks]


@register("verb_class", LANG)
def verb_class(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Godan or ichidan? The classification that drives every other form."""
    rows = [v for v in ctx.vocab if v.get("pos") == "verb"]
    if not rows:
        return []
    picks = _sample(rows, spec.get("count", 8), ctx.rng)
    out = []
    for r in picks:
        c = V.classify(r["term"], pos="verb", verb_class=r.get("irregular") or None)
        label = {"godan": "godan (u-verb)", "ichidan": "ichidan (ru-verb)",
                 "suru": "irregular (する)", "kuru": "irregular (来る)",
                 "aru": "irregular (ある)"}.get(c.verb_class, c.verb_class)
        expl = V.CLASS_EXPLANATIONS.get(c.verb_class, {})
        out.append(Exercise(
            kind="verb_class", skill="grammar",
            prompt=f"Is {r['term']} godan or ichidan?", answer=label,
            options=["godan (u-verb)", "ichidan (ru-verb)",
                     "irregular (する)", "irregular (来る)"],
            explain=f"{expl.get('example', '')} {c.note}".strip(),
            audio=r["term"],
            data={"meaning": r.get("meaning", ""), "class": c.verb_class},
            item_type="vocab", item_id=r["id"],
        ))
    return out


@register("counter_choice", LANG)
def counter_choice(spec: dict, ctx: GenContext) -> list[Exercise]:
    items = [
        ("Two people", "ふたり", "人 counts people, and two is irregular: ふたり."),
        ("Three bottles", "さんぼん", "本 counts long thin things, and shifts to ぼん."),
        ("One book", "いっさつ", "冊 counts bound things."),
        ("Two sheets of paper", "にまい", "枚 counts flat thin things."),
        ("Three apples", "みっつ", "つ is the general counter — always safe."),
        ("Twenty years old", "はたち", "歳 is regular except twenty, which is はたち."),
        ("One cat", "いっぴき", "匹 counts small animals, and shifts to ぴき."),
        ("Two cars", "にだい", "台 counts machines and vehicles."),
    ]
    picks = _sample(items, spec.get("count", 6), ctx.rng)
    answers = [a for _, a, _ in items]
    return [Exercise(
        kind="counter_choice", skill="grammar",
        prompt=q, answer=a, options=_distractors(a, answers, 3, ctx.rng),
        explain=why, audio=a,
        item_type="grammar", item_id="ja-counters",
    ) for q, a, why in picks]


# `confusion_drill` is registered once, in the shared engine: it reads this
# language's CONFUSIONS through the registry, so it needs no Japanese copy.
