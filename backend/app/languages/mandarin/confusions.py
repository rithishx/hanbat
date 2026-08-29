"""
Mandarin confusion pairs.

None of these look like Korean's or Japanese's, because Mandarin's difficulties
are somewhere else entirely: tones, aspect versus tense, and measure words.
There is no 은/는 versus 이/가 here and no は versus が, because Mandarin has no
particles of that kind at all.
"""

from __future__ import annotations

from ...engines.confusion import Confusion, index_confusions

CONFUSIONS: dict[str, Confusion] = {
    "le_is_not_past": Confusion(
        id="le_is_not_past",
        a="了", b="past tense",
        title="了 is not the past tense",
        one_line="了 marks completion or change, not time. Time comes from time words.",
        simple=(
            "This is the one that costs learners years. 了 does not mean 'past'. "
            "It means something finished, or something changed.\n\n"
            "明天我就走了 is about tomorrow and still has 了 — because by then, "
            "the leaving will be done.\n"
            "我昨天去学校 is about yesterday and has no 了 at all — because it "
            "describes a habit, not a completed event.\n\n"
            "If you want to say when something happened, use a time word. That "
            "is the whole system."
        ),
        rule=(
            "了 is an aspect marker with two uses: verb-final 了 marks completed "
            "action, sentence-final 了 marks a changed state or new situation. "
            "Mandarin has no tense morphology; temporal reference comes from "
            "adverbials."
        ),
        examples=[
            {"target": "我吃了饭。", "english": "I've eaten.", "why": "Completed action."},
            {"target": "下雨了。", "english": "It's started raining.",
             "why": "A change of state, happening right now — nothing past about it."},
            {"target": "明天我就走了。", "english": "I'm leaving tomorrow.",
             "why": "Future, and still takes 了."},
            {"target": "我昨天去学校。", "english": "I went to school yesterday.",
             "why": "Past, and takes no 了 — 昨天 already says when."},
        ],
        drill_prompt="Ask: is something finished or changed? Not: is this the past?",
        tags=("aspect", "HSK2"),
    ),
    "bu_vs_mei": Confusion(
        id="bu_vs_mei",
        a="不", b="没",
        title="不 versus 没",
        one_line="不 is about will and habit. 没 is about things that did not happen.",
        simple=(
            "不 says you don't, won't, or never do something — a choice or a "
            "habit. 我不吃肉 means you're vegetarian.\n\n"
            "没 says a specific thing did not happen. 我没吃饭 means you haven't "
            "eaten yet today.\n\n"
            "And 有 only ever takes 没: 没有, never 不有."
        ),
        rule=(
            "不 negates habitual, volitional and future situations, and all "
            "adjectival predicates. 没(有) negates the completion of an event and "
            "the existence of something. 没 and 了 never co-occur."
        ),
        examples=[
            {"target": "我不吃肉。", "english": "I don't eat meat.", "why": "A habit."},
            {"target": "我没吃饭。", "english": "I haven't eaten.", "why": "Did not happen."},
            {"target": "我没有钱。", "english": "I don't have money.", "why": "有 always takes 没."},
            {"target": "他不来。", "english": "He isn't coming.", "why": "Future intention."},
        ],
        drill_prompt="Choice and habit, or a thing that didn't happen?",
        tags=("negation", "HSK1"),
    ),
    "tone_2_vs_3": Confusion(
        id="tone_2_vs_3",
        a="second tone", b="third tone",
        title="Second versus third tone",
        one_line="Second rises from the middle. Third drops low and mostly stays there.",
        simple=(
            "These two are confused far more than any other pair, because "
            "textbooks draw the third tone as a dip AND a rise — and learners "
            "hear the rise and think 'second tone'.\n\n"
            "In real speech, a third tone before another tone only does the "
            "first half: it drops low and stops. The rise happens only when the "
            "syllable stands completely alone.\n\n"
            "So: think of the third tone as LOW, not as dipping. Then it stops "
            "sounding like the second."
        ),
        rule=(
            "Tone 2 is a mid-to-high rise (35). Tone 3 is a low dip (214) in "
            "isolation but surfaces as a low-falling half-third (21) before "
            "tones 1, 2, 4 and neutral, and as tone 2 before another tone 3."
        ),
        examples=[
            {"target": "má / mǎ", "english": "hemp / horse", "why": ""},
            {"target": "shí / shǐ", "english": "ten / history", "why": ""},
            {"target": "nǐ hǎo", "english": "hello",
             "why": "Written with two third tones, said as ní hǎo. The first one "
                    "really is a second tone here."},
        ],
        drill_prompt="Low, or rising? Do not listen for a dip — listen for the floor.",
        tags=("tones", "HSK1"),
    ),
    "j_vs_zh": Confusion(
        id="j_vs_zh",
        a="j / q / x", b="zh / ch / sh",
        title="j q x versus zh ch sh",
        one_line="Tongue flat and forward for j q x; curled back for zh ch sh.",
        simple=(
            "English hears both groups as j, ch and sh, so learners produce one "
            "sound where Mandarin has two.\n\n"
            "For j, q and x, put your tongue tip down behind your bottom teeth "
            "and smile slightly. For zh, ch and sh, curl the tip up toward the "
            "roof of your mouth.\n\n"
            "A shortcut: j, q and x are only ever followed by i or ü. If you see "
            "any other vowel, it must be the retroflex group."
        ),
        rule=(
            "j/q/x are alveolo-palatal and occur only before high front vowels; "
            "zh/ch/sh are retroflex and never occur before them. They are in "
            "complementary distribution, which is why the spelling never needs "
            "to disambiguate."
        ),
        examples=[
            {"target": "jī / zhī", "english": "chicken / to know", "why": ""},
            {"target": "qī / chī", "english": "seven / to eat", "why": ""},
            {"target": "xī / shī", "english": "west / teacher", "why": ""},
        ],
        drill_prompt="Where is your tongue tip — down at the front, or curled up?",
        tags=("pronunciation", "HSK1"),
    ),
    "measure_words": Confusion(
        id="measure_words",
        a="个", b="specific measure word",
        title="Which measure word?",
        one_line="Every counted noun needs one, and 个 is the safe default when you don't know.",
        simple=(
            "You cannot say 'three books' in Mandarin. You say 'three [bound-thing] "
            "books' — 三本书.\n\n"
            "There are dozens, and which one a noun takes is something you learn "
            "with the noun, not from a rule. The good news: 个 works for a huge "
            "range of things, and using it where a more specific one exists sounds "
            "casual rather than wrong.\n\n"
            "Omitting the measure word entirely is the error that actually sounds "
            "broken."
        ),
        rule=(
            "Numerals and demonstratives require a classifier before a noun. "
            "Classifier choice is lexical, generally motivated by shape or "
            "category. 个 is the default general classifier."
        ),
        examples=[
            {"target": "三本书", "english": "three books", "why": "本 for bound things."},
            {"target": "两张纸", "english": "two sheets of paper", "why": "张 for flat things."},
            {"target": "一只猫", "english": "one cat", "why": "只 for animals."},
            {"target": "三个人", "english": "three people", "why": "个 — the default."},
        ],
        drill_prompt="Is it flat, long, bound, or an animal? If none of those, use 个.",
        tags=("measure_words", "HSK1"),
    ),
    "zai_vs_zhe": Confusion(
        id="zai_vs_zhe",
        a="在", b="着",
        title="在 versus 着",
        one_line="在 is an action in progress. 着 is a state that is holding.",
        simple=(
            "在 goes before the verb and means you are in the middle of doing "
            "something: 我在开门 — I'm opening the door.\n\n"
            "着 goes after the verb and means something is staying that way: "
            "门开着 — the door is open, and it's staying open.\n\n"
            "One is a film; the other is a photograph."
        ),
        rule=(
            "在 (preverbal) marks progressive aspect; 着 (postverbal) marks "
            "durative or resultative state. Only 着 can describe a static "
            "situation."
        ),
        examples=[
            {"target": "我在吃饭。", "english": "I'm eating.", "why": "In progress."},
            {"target": "他坐着。", "english": "He is sitting.", "why": "A state that holds."},
            {"target": "窗户开着。", "english": "The window is open.", "why": "State."},
        ],
        drill_prompt="Is it happening, or is it just staying that way?",
        tags=("aspect", "HSK3"),
    ),
    "word_order_time": Confusion(
        id="word_order_time",
        a="time before the verb", b="time after the object",
        title="Where time and place go",
        one_line="Everything that sets the scene goes before the verb, not at the end.",
        simple=(
            "English says 'I'm going to Beijing tomorrow'. Mandarin says "
            "'I tomorrow go Beijing' — 我明天去北京.\n\n"
            "Time first, then place, then how, then the verb. Putting a time "
            "phrase at the end is one of the few things in Mandarin that is "
            "simply wrong rather than merely unnatural."
        ),
        rule="Subject — Time — Place — Manner — Verb — Object. Adverbials are "
             "strictly preverbal.",
        examples=[
            {"target": "我明天去北京。", "english": "I'm going to Beijing tomorrow.", "why": ""},
            {"target": "我在图书馆看书。", "english": "I read at the library.", "why": ""},
            {"target": "我每天早上跑步。", "english": "I run every morning.", "why": ""},
        ],
        drill_prompt="Front-load everything except the verb and its object.",
        tags=("word_order", "HSK1"),
    ),
    "n_vs_ng": Confusion(
        id="n_vs_ng",
        a="-n", b="-ng",
        title="-n versus -ng",
        one_line="Tongue tip forward for -n; back of the tongue for -ng, tip touching nothing.",
        simple=(
            "English blurs these at the end of a word, so learners produce one "
            "sound for both. Mandarin keeps them apart, and they distinguish "
            "real words: 山 shān is a mountain and 商 shāng is commerce.\n\n"
            "For -n, your tongue tip touches the ridge behind your top teeth. "
            "For -ng it does not touch anything — the back of your tongue rises "
            "instead, as in English 'sing'."
        ),
        rule="Alveolar versus velar nasal coda. Both are phonemic and contrastive.",
        examples=[
            {"target": "shān / shāng", "english": "mountain / commerce", "why": ""},
            {"target": "bān / bāng", "english": "class / to help", "why": ""},
            {"target": "xìn / xìng", "english": "letter / surname", "why": ""},
        ],
        drill_prompt="Does your tongue tip touch? Then it is -n.",
        tags=("pronunciation", "HSK1"),
    ),
}

PAIR_INDEX = index_confusions(CONFUSIONS, "zh")
