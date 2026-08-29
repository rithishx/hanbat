"""
Mandarin exercise generators.

Almost nothing here has a Korean or Japanese counterpart, and that is the point.
Korean drills 받침 prediction because Hangul spelling hides pronunciation.
Japanese drills mora counting because Japanese rhythm is timed. Mandarin drills
*tones*, because in Mandarin a wrong tone is a wrong word — 买 and 卖 are "buy"
and "sell", one tone apart.

Three of these deserve a note.

`tone_pair` exists rather than a single-syllable tone drill because learners who
can produce four isolated tones and then cannot say 你好 are the norm. Tones
interact; the pair is the real unit of practice.

`tone_sandhi_predict` asks for the *spoken* tones of something whose *written*
tones are different. It is the only drill in the whole application where the
correct answer contradicts what is written on the page, and it exists because
third-tone sandhi is obligatory: 你好 written 3-3 is said 2-3, always.

`measure_word_choice` has no free-entry mode. Measure words are a closed
lexical set with genuinely arbitrary membership, and "type the measure word for
橋" is a memory test with no reasoning in it. Multiple choice with the reason
attached teaches the category; free entry just punishes.
"""

from __future__ import annotations

from ...engines.exercises import Exercise, GenContext, _distractors, _sample, register
from . import grammar as G
from . import pinyin as P
from . import tones as T

LANG = "zh"


# ==========================================================================
# Pinyin — the spelling system, which has to be learnt before anything else
# ==========================================================================

@register("pinyin_read", LANG, skill="reading")
def pinyin_read(spec: dict, ctx: GenContext) -> list[Exercise]:
    """See a pinyin syllable, say what it sounds like.

    The trap this drills is that pinyin letters do not have their English
    values. `q`, `x`, `c` and `zh` all mislead an English reader, so the note
    attached to the initial is the actual teaching content here.
    """
    inv = P.inventory()
    notes = {i["unit"]: i["note"] for i in inv["initials"] if i.get("note")}
    notes.update({f["unit"]: f["note"] for f in inv["finals"] if f.get("note")})
    pool = [u for u in (spec.get("pool") or notes) if notes.get(u)]
    if len(pool) < 2:
        return []
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    descriptions = [notes[u] for u in pool]
    return [Exercise(
        kind="pinyin_read", skill="reading",
        prompt=f"How is “{u}” pronounced?", answer=notes[u],
        options=_distractors(notes[u], descriptions, 3, ctx.rng),
        audio=u, explain=notes[u],
        data={"unit": u, "note": notes[u]},
        hints=spec.get("hints", True),
        item_type="script_unit", item_id=f"zh-pinyin-{u}",
    ) for u in picks]


@register("pinyin_build", LANG, skill="writing")
def pinyin_build(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Assemble initial + final + tone into a written syllable.

    Pinyin is not simply letters in a row: `i` becomes `yi` on its own, `ü`
    loses its dots after j/q/x, and the tone mark lands on a vowel chosen by
    rule. Building a syllable is where those rules become real.
    """
    pool = spec.get("pool") or [
        "mā", "nǐ", "hǎo", "xiè", "zhōng", "guó", "shuǐ", "jiā",
        "qù", "xué", "chī", "fàn", "péng", "yǒu", "lǎo", "shī",
    ]
    picks = _sample(pool, spec.get("count", 8), ctx.rng)
    out = []
    for word in picks:
        s = P.parse(word)
        if not s.valid:
            continue
        out.append(Exercise(
            kind="pinyin_build", skill="writing",
            prompt=(f"Write the syllable: initial “{s.initial or '–'}”, "
                    f"final “{s.final}”, tone {s.tone}."),
            answer=s.marked, audio=s.marked,
            explain=(f"{s.plain} + tone {s.tone} → {s.marked}. "
                     f"{P.TONE_NAMES[s.tone]['contour']}."),
            data={"initial": s.initial, "final": s.final, "tone": s.tone,
                  "numbered": s.numbered, "plain": s.plain},
            hints=spec.get("hints", True),
            item_type="script_unit", item_id=f"zh-pinyin-{s.plain}",
        ))
    return out


@register("initial_discriminate", LANG, skill="listening")
def initial_discriminate(spec: dict, ctx: GenContext) -> list[Exercise]:
    """j/zh, q/ch, x/sh — the contrasts English ears collapse."""
    pairs = spec.get("pairs") or P.HARD_CONTRASTS
    picks = _sample(pairs, spec.get("count", 6), ctx.rng)
    out = []
    for p in picks:
        a, b = p["pair"]
        heard = ctx.rng.choice([a, b])
        out.append(Exercise(
            kind="initial_discriminate", skill="listening",
            prompt="Which one did you hear?", answer=heard,
            options=[a, b], audio=heard, explain=p["why"],
            data=dict(p),
            item_type="pronunciation", item_id=f"{a}/{b}",
        ))
    return out


# ==========================================================================
# Tones — the drills with no equivalent in the other two languages
# ==========================================================================

@register("tone_identify", LANG, skill="listening")
def tone_identify(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Hear a syllable, name its tone."""
    sets = spec.get("pool") or T.minimal_pairs()
    flat: list[dict] = []
    for group in sets:
        for item in group.get("set", []):
            flat.append({**item, "note": group.get("note", "")})
    if not flat:
        return []
    picks = _sample(flat, spec.get("count", 8), ctx.rng)
    labels = {t: f"Tone {t} — {info['contour']}" for t, info in P.TONE_NAMES.items()}
    out = []
    for item in picks:
        tone = P.tone_of(item["pinyin"])
        answer = labels.get(tone, f"Tone {tone}")
        out.append(Exercise(
            kind="tone_identify", skill="listening",
            prompt="Which tone did you hear?", answer=answer,
            options=[labels[t] for t in (1, 2, 3, 4, 5)],
            audio=item["pinyin"],
            explain=(f"{item['pinyin']} ({item.get('hanzi', '')}) means "
                     f"“{item['meaning']}”. {item.get('note', '')}").strip(),
            data={"pinyin": item["pinyin"], "hanzi": item.get("hanzi", ""),
                  "tone": tone},
            item_type="pronunciation", item_id=item["pinyin"],
        ))
    return out


@register("tone_minimal_pair", LANG, skill="listening")
def tone_minimal_pair(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Same syllable, different tone, different word. Why tones are not optional."""
    groups = spec.get("pool") or T.minimal_pairs()
    picks = _sample(groups, spec.get("count", 6), ctx.rng)
    out = []
    for g in picks:
        members = g.get("set", [])
        if len(members) < 2:
            continue
        heard = ctx.rng.choice(members)
        out.append(Exercise(
            kind="tone_minimal_pair", skill="listening",
            prompt="Which word did you hear?", answer=heard["meaning"],
            options=[m["meaning"] for m in members], audio=heard["pinyin"],
            explain=("  ·  ".join(f"{m['pinyin']} {m.get('hanzi', '')} = {m['meaning']}"
                                  for m in members) + f"  {g.get('note', '')}").strip(),
            data={"syllable": g.get("syllable", ""), "set": members},
            item_type="pronunciation", item_id=g.get("syllable", ""),
        ))
    return out


@register("tone_pair", LANG, skill="speaking")
def tone_pair(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Produce a two-syllable word with the right tone contour.

    Filterable by difficulty, because 2-1 and 3-2 are genuinely harder than
    1-5 and deserve more of a learner's time.
    """
    drills = [d for d in T.tone_pair_drills() if d.get("pinyin")]
    if spec.get("difficulty"):
        wanted = spec["difficulty"]
        drills = [d for d in drills if d["difficulty"] == wanted] or drills
    if spec.get("pairs"):
        wanted_pairs = set(spec["pairs"])
        drills = [d for d in drills if d["pair"] in wanted_pairs] or drills
    picks = _sample(drills, spec.get("count", 8), ctx.rng)
    return [Exercise(
        kind="tone_pair", skill="speaking",
        prompt=f"Say “{d['meaning']}” — {d['hanzi']}",
        answer=d["pinyin"], audio=d["pinyin"],
        explain=(f"{d['hanzi']} {d['pinyin']} — tone pair {d['pair']}: "
                 f"{d['first']} then {d['second']}. {d.get('note', '')}").strip(),
        data={"scoring": "requires_stt_engine", **d},
        difficulty={"easy": 0.3, "medium": 0.5, "hard": 0.75}.get(d["difficulty"], 0.5),
        item_type="pronunciation", item_id=d["hanzi"],
    ) for d in picks]


@register("tone_sandhi_predict", LANG, skill="pronunciation")
def tone_sandhi_predict(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Written tones versus spoken tones.

    The only drill in the app whose right answer disagrees with the page. That
    is not a quirk to be smoothed over — it is the fact 你好 teaches on day one,
    and hiding it produces learners who say nǐ hǎo with two third tones for
    years.
    """
    pool = spec.get("pool") or [
        {"pinyin": "nǐ hǎo", "hanzi": "你好", "english": "hello"},
        {"pinyin": "hěn hǎo", "hanzi": "很好", "english": "very good"},
        {"pinyin": "wǒ hěn hǎo", "hanzi": "我很好", "english": "I'm fine"},
        {"pinyin": "shuǐ guǒ", "hanzi": "水果", "english": "fruit"},
        {"pinyin": "bù shì", "hanzi": "不是", "english": "is not"},
        {"pinyin": "bù hǎo", "hanzi": "不好", "english": "not good"},
        {"pinyin": "yī gè", "hanzi": "一个", "english": "one (of something)"},
        {"pinyin": "yī qǐ", "hanzi": "一起", "english": "together"},
        {"pinyin": "lǎo shǔ", "hanzi": "老鼠", "english": "mouse"},
        {"pinyin": "kě yǐ", "hanzi": "可以", "english": "can, may"},
    ]
    picks = _sample(pool, spec.get("count", 6), ctx.rng)
    out = []
    for item in picks:
        res = T.apply_sandhi(item["pinyin"])
        steps = [c.simple for c in res.changes]
        out.append(Exercise(
            kind="tone_sandhi_predict", skill="pronunciation",
            prompt=(f"{item['hanzi']} is written {item['pinyin']}. "
                    f"How is it actually said?"),
            answer=res.spoken, audio=res.spoken,
            options=([res.spoken, res.written] if res.changed else []),
            explain=(" ".join(steps) if steps else
                     f"No change — {res.written} is said as written."),
            data={"written": res.written, "spoken": res.spoken,
                  "written_tones": res.written_tones,
                  "spoken_tones": res.spoken_tones,
                  "changed": res.changed,
                  "hanzi": item["hanzi"], "english": item.get("english", "")},
            hints=spec.get("hints", True),
            item_type="pronunciation", item_id=item["hanzi"],
        ))
    return out


# ==========================================================================
# Grammar — measure words, aspect, word order. No conjugation.
# ==========================================================================

@register("measure_word_choice", LANG)
def measure_word_choice(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Which measure word does this noun take?"""
    entries = spec.get("pool") or G.MEASURE_WORDS
    words = [m["word"] for m in G.MEASURE_WORDS]
    flat: list[tuple[str, str, str]] = []
    for m in entries:
        for phrase in m.get("examples", []):
            flat.append((phrase, m["word"], f"{m['word']} ({m['pinyin']}) — "
                                            f"for {m['for']}."))
    if not flat:
        return []
    picks = _sample(flat, spec.get("count", 8), ctx.rng)
    out = []
    for phrase, correct, why in picks:
        blanked = phrase.replace(correct, "___", 1)
        out.append(Exercise(
            kind="measure_word_choice", skill="grammar",
            prompt=blanked, answer=correct,
            options=_distractors(correct, words, 3, ctx.rng),
            explain=why, audio=phrase,
            data={"phrase": phrase},
            item_type="grammar", item_id="zh-measure-words",
        ))
    return out


@register("aspect_choice", LANG)
def aspect_choice(spec: dict, ctx: GenContext) -> list[Exercise]:
    """了, 过, 着 or 在 — completion, experience, state or progress.

    Deliberately phrased as "which meaning" rather than "which tense", because
    the whole difficulty here is that learners arrive expecting tense.
    """
    items = spec.get("items") or [
        ("我吃___饭了。", "了", "Completed — the eating is finished."),
        ("我去___中国。", "过", "Experience — you have been there at some point."),
        ("门开___。", "着", "A state that continues — the door stands open."),
        ("我___吃饭。", "在", "In progress right now."),
        ("他睡___。", "着", "A state, not an action in progress."),
        ("下雨___。", "了", "A change of situation — it has started raining."),
        ("你看___这个电影吗？", "过", "Asking about lifetime experience."),
        ("他们___开会。", "在", "The meeting is happening now."),
    ]
    picks = _sample(items, spec.get("count", 6), ctx.rng)
    options = spec.get("options") or ["了", "过", "着", "在"]
    return [Exercise(
        kind="aspect_choice", skill="grammar",
        prompt=q, answer=a, options=list(options), explain=why,
        audio=q.replace("___", a),
        data={"reminder": "These mark aspect, not tense. Time comes from time words."},
        item_type="grammar", item_id="zh-aspect",
    ) for q, a, why in picks]


@register("word_order", LANG)
def word_order(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Rebuild a sentence. Mandarin word order is rigid and English's is not.

    Answers are checked against the exact string because in Mandarin the order
    genuinely is the grammar: 我明天去北京 is right and 我去北京明天 is wrong,
    with no shade of acceptability in between.
    """
    items = spec.get("items") or [
        {"chunks": ["我", "明天", "去", "北京"], "answer": "我明天去北京",
         "english": "I'm going to Beijing tomorrow.",
         "why": "Time goes before the verb, never after the object."},
        {"chunks": ["我", "在图书馆", "看书"], "answer": "我在图书馆看书",
         "english": "I read books at the library.",
         "why": "Place goes before the verb."},
        {"chunks": ["他", "每天", "早上", "跑步"], "answer": "他每天早上跑步",
         "english": "He runs every morning.",
         "why": "Bigger time unit first, then smaller."},
        {"chunks": ["我", "跟朋友", "一起", "吃饭"], "answer": "我跟朋友一起吃饭",
         "english": "I eat with friends.",
         "why": "Who-with comes before the verb too."},
        {"chunks": ["你", "为什么", "不", "来"], "answer": "你为什么不来",
         "english": "Why aren't you coming?",
         "why": "Question words stay where the answer would go — no fronting."},
    ]
    picks = _sample(items, spec.get("count", 5), ctx.rng)
    out = []
    for it in picks:
        chunks = list(it["chunks"])
        ctx.rng.shuffle(chunks)
        out.append(Exercise(
            kind="word_order", skill="grammar",
            prompt=f"Put these in order: {it['english']}",
            answer=it["answer"], options=chunks, audio=it["answer"],
            explain=it.get("why", G.WORD_ORDER["simple"]),
            data={"pattern": G.WORD_ORDER["full"], "chunks": it["chunks"]},
            hints=spec.get("hints", True),
            item_type="grammar", item_id="zh-word-order",
        ))
    return out


@register("structure_produce", LANG, skill="writing")
def structure_produce(spec: dict, ctx: GenContext) -> list[Exercise]:
    """把, 被, 比, 是…的 — the patterns that have no English equivalent."""
    wanted = spec.get("structures")
    entries = [s for s in G.STRUCTURES
               if not wanted or s["id"] in set(wanted)]
    flat: list[tuple[dict, dict]] = [
        (s, ex) for s in entries for ex in s.get("examples", [])]
    if not flat:
        return []
    picks = _sample(flat, spec.get("count", 6), ctx.rng)
    return [Exercise(
        kind="structure_produce", skill="writing",
        prompt=ex["english"], answer=ex["chinese"], audio=ex["chinese"],
        explain=f"{s['name']}: {s['simple']}"
                + (f"  {s['requires']}" if s.get("requires") else ""),
        data={"structure": s["id"], "pattern": s["pattern"],
              "shape": s["structure"], "pinyin": ex.get("pinyin", "")},
        hints=spec.get("hints", True),
        item_type="grammar", item_id=f"zh-{s['id']}",
    ) for s, ex in picks]


@register("hanzi_recognise", LANG, skill="reading")
def hanzi_recognise(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Character → meaning, with the pinyin shown separately.

    Kept separate from `vocab_recognise` because a Mandarin learner has two
    distinct problems: knowing the word, and knowing which character writes it.
    Showing the pinyin here isolates the second one.
    """
    rows = [v for v in ctx.vocab if v.get("term") and v.get("meaning")]
    if len(rows) < 4:
        return []
    picks = _sample(rows, spec.get("count", 8), ctx.rng)
    meanings = [r["meaning"] for r in rows]
    return [Exercise(
        kind="hanzi_recognise", skill="reading",
        prompt=r["term"], answer=r["meaning"],
        options=_distractors(r["meaning"], meanings, 3, ctx.rng),
        audio=r["term"],
        explain=f"{r['term']} — {r.get('transliteration') or r.get('romanization', '')}",
        data={"pinyin": r.get("transliteration") or r.get("romanization", ""),
              "strokes_unknown": True},
        item_type="vocab", item_id=r["id"],
    ) for r in picks]


@register("pinyin_type", LANG, skill="writing")
def pinyin_type(spec: dict, ctx: GenContext) -> list[Exercise]:
    """Type the pinyin, with the tone, for a character you are shown.

    This is not a romanisation crutch. Pinyin is how Chinese is typed on every
    keyboard in the world, and typing it *with the tone* is the drill that stops
    a learner storing words in their head without tones.
    """
    rows = [v for v in ctx.vocab
            if v.get("term") and (v.get("transliteration") or v.get("romanization"))]
    if not rows:
        return []
    picks = _sample(rows, spec.get("count", 6), ctx.rng)
    out = []
    for r in picks:
        py = r.get("transliteration") or r.get("romanization", "")
        out.append(Exercise(
            kind="pinyin_type", skill="writing",
            prompt=f"Type the pinyin, with tone marks, for {r['term']}",
            answer=py, audio=r["term"],
            explain=f"{r['term']} = {py} — {r.get('meaning', '')}",
            data={"numbered": P.to_numbered(py), "accepts": [py, P.to_numbered(py)],
                  "meaning": r.get("meaning", "")},
            hints=spec.get("hints", True),
            item_type="vocab", item_id=r["id"],
        ))
    return out
