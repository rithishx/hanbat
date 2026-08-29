"""
Mandarin grammar as a GrammarEngine.

This is the module that proves the architecture. It implements the same three
protocol methods as Korean and Japanese, and it has **no `conjugate()`** —
because Mandarin has no conjugation. Verbs do not change shape for tense,
person, number, mood or politeness. Ever.

`capabilities()` therefore does not include "conjugation", the UI renders no
conjugation tab for Mandarin, and `/api/conjugate?lang=zh` returns a 409 that
says why. A shared grammar base class would have forced a `conjugate()` here
that returned the word unchanged and called it an answer — which is exactly
the over-abstraction this design was built to avoid.

What Mandarin has instead, and what `drill_forms()` returns, is: the measure
word a noun takes, the aspect particles a verb combines with, and its tone
pairs. Those are the things a learner actually has to practise about a
Mandarin word.
"""

from __future__ import annotations

from typing import Any, Optional

from . import pinyin as P
from . import tones as T

#: Measure words. Every counted noun needs one, and picking the wrong one is
#: the most audible beginner error in the language.
MEASURE_WORDS: list[dict] = [
    {"word": "个", "pinyin": "gè", "for": "the general-purpose one — people and most objects",
     "examples": ["三个人", "一个问题", "两个苹果"],
     "note": "When you do not know the right measure word, use 个. You will be "
             "understood, and you will be right more often than not."},
    {"word": "本", "pinyin": "běn", "for": "bound things — books, magazines",
     "examples": ["一本书", "三本杂志"], "note": ""},
    {"word": "张", "pinyin": "zhāng", "for": "flat things — paper, tables, tickets, beds",
     "examples": ["一张纸", "两张票", "一张床"], "note": ""},
    {"word": "只", "pinyin": "zhī", "for": "most animals, and one of a pair",
     "examples": ["一只猫", "三只鸟", "一只手"], "note": ""},
    {"word": "条", "pinyin": "tiáo", "for": "long flexible things — roads, rivers, fish, trousers",
     "examples": ["一条路", "两条鱼", "一条裤子"], "note": ""},
    {"word": "杯", "pinyin": "bēi", "for": "cups and glasses of something",
     "examples": ["一杯水", "两杯咖啡"], "note": ""},
    {"word": "件", "pinyin": "jiàn", "for": "clothing (upper body), matters, affairs",
     "examples": ["一件衣服", "一件事"], "note": ""},
    {"word": "辆", "pinyin": "liàng", "for": "wheeled vehicles",
     "examples": ["一辆车", "两辆自行车"], "note": ""},
    {"word": "位", "pinyin": "wèi", "for": "people, politely",
     "examples": ["三位老师", "一位先生"],
     "note": "The respectful alternative to 个 for people. Use it for teachers, "
             "guests and customers."},
    {"word": "些", "pinyin": "xiē", "for": "an indefinite plural — 'some'",
     "examples": ["一些人", "这些书"], "note": "Only with 一, 这 and 那."},
]

#: Aspect particles. These are what Mandarin has instead of tense, and
#: describing them as tense markers is the single most damaging thing a
#: textbook can do to a learner.
ASPECT: list[dict] = [
    {"particle": "了", "pinyin": "le", "marks": "completion",
     "simple": "了 says an action is finished or a situation has changed. It does "
               "NOT mean past tense. 明天我就走了 is about tomorrow.",
     "examples": [
         {"chinese": "我吃了饭。", "pinyin": "wǒ chī le fàn", "english": "I ate. / I've eaten."},
         {"chinese": "下雨了。", "pinyin": "xià yǔ le", "english": "It's started raining.",
          "note": "A change of situation, happening right now."},
     ],
     "warning": "Calling 了 'the past tense' is the most common way learners are "
                "set up to fail. Completion and past are different ideas."},
    {"particle": "过", "pinyin": "guo", "marks": "experience",
     "simple": "过 says you have done something at least once in your life.",
     "examples": [
         {"chinese": "我去过中国。", "pinyin": "wǒ qù guo Zhōngguó",
          "english": "I've been to China (at some point)."},
     ], "warning": ""},
    {"particle": "着", "pinyin": "zhe", "marks": "ongoing state",
     "simple": "着 says something is in a continuing state — the door is standing open.",
     "examples": [
         {"chinese": "门开着。", "pinyin": "mén kāi zhe", "english": "The door is open."},
     ], "warning": ""},
    {"particle": "在", "pinyin": "zài", "marks": "action in progress",
     "simple": "在 before the verb says the action is happening right now.",
     "examples": [
         {"chinese": "我在吃饭。", "pinyin": "wǒ zài chī fàn", "english": "I'm eating."},
     ], "warning": "着 is a state; 在 is an action in progress. Not the same thing."},
]

STRUCTURES: list[dict] = [
    {"id": "ba", "pattern": "把", "pinyin": "bǎ",
     "name": "The 把 construction",
     "simple": "把 moves the object in front of the verb, and says you did "
               "something TO it that changed it. 我把书放在桌子上 — I took the "
               "book and put it on the table.",
     "structure": "Subject + 把 + object + verb + result",
     "requires": "The verb must have a result attached — a complement, 了, or a "
                 "location. A bare verb after 把 is ungrammatical.",
     "examples": [
         {"chinese": "我把门关了。", "pinyin": "wǒ bǎ mén guān le", "english": "I closed the door."},
         {"chinese": "他把钱花完了。", "pinyin": "tā bǎ qián huā wán le",
          "english": "He spent all the money."},
     ]},
    {"id": "bei", "pattern": "被", "pinyin": "bèi",
     "name": "The 被 passive",
     "simple": "被 makes the subject the one something happened to. Unlike English, "
               "it carries a slight sense that the thing was unwelcome.",
     "structure": "Subject + 被 + (agent) + verb + result",
     "requires": "The verb needs a result, as with 把.",
     "examples": [
         {"chinese": "我的车被偷了。", "pinyin": "wǒ de chē bèi tōu le",
          "english": "My car was stolen."},
     ]},
    {"id": "bi", "pattern": "比", "pinyin": "bǐ",
     "name": "Comparison with 比",
     "simple": "A 比 B + adjective. No 'more' and no 'than' — the 比 does all of it.",
     "structure": "A + 比 + B + adjective",
     "requires": "Do not put 很 in front of the adjective; 比 already carries the comparison.",
     "examples": [
         {"chinese": "他比我高。", "pinyin": "tā bǐ wǒ gāo", "english": "He is taller than me."},
     ]},
    {"id": "shi_de", "pattern": "是…的", "pinyin": "shì...de",
     "name": "The 是…的 construction",
     "simple": "Used to ask or state HOW, WHEN or WHERE something already-known "
               "happened. 你是怎么来的? — how did you get here?",
     "structure": "Subject + 是 + [when/where/how] + verb + 的",
     "requires": "Only for events both speakers already know happened.",
     "examples": [
         {"chinese": "我是坐飞机来的。", "pinyin": "wǒ shì zuò fēijī lái de",
          "english": "I came by plane."},
     ]},
    {"id": "resultative", "pattern": "verb + complement",
     "name": "Resultative complements",
     "simple": "Mandarin glues a result onto the verb: 看 is 'look', 看见 is "
               "'look and see'. 听 is 'listen', 听懂 is 'listen and understand'.",
     "structure": "verb + result verb/adjective",
     "requires": "",
     "examples": [
         {"chinese": "我听懂了。", "pinyin": "wǒ tīng dǒng le", "english": "I understood (what I heard)."},
         {"chinese": "我没看见。", "pinyin": "wǒ méi kàn jiàn", "english": "I didn't see it."},
     ]},
    {"id": "directional", "pattern": "verb + 来/去",
     "name": "Directional complements",
     "simple": "来 and 去 attach to a verb to say whether the motion is toward "
               "the speaker or away.",
     "structure": "verb + 来 (toward) / 去 (away)",
     "requires": "",
     "examples": [
         {"chinese": "进来。", "pinyin": "jìn lái", "english": "Come in."},
         {"chinese": "出去。", "pinyin": "chū qù", "english": "Go out."},
     ]},
]

WORD_ORDER = {
    "basic": "Subject — Verb — Object",
    "full": "Subject — Time — Place — Manner — Verb — Object",
    "simple": "Everything that sets the scene comes BEFORE the verb. English puts "
              "time and place at the end of a sentence; Mandarin puts them at the "
              "front. 我明天在家看书 is literally 'I tomorrow at home read books'.",
    "examples": [
        {"chinese": "我明天去北京。", "pinyin": "wǒ míngtiān qù Běijīng",
         "english": "I'm going to Beijing tomorrow.",
         "note": "Time before the verb, not after the object."},
        {"chinese": "我在图书馆看书。", "pinyin": "wǒ zài túshūguǎn kàn shū",
         "english": "I read books at the library.",
         "note": "Place before the verb."},
    ],
    "warning": "This is where Korean and Japanese learners have an advantage and "
               "English speakers do not: Mandarin word order is rigid, and moving "
               "a time phrase to the end makes a sentence simply wrong.",
}


class MandarinGrammar:
    language = "zh"

    def capabilities(self) -> frozenset[str]:
        """Note what is absent.

        No "conjugation" — Mandarin verbs never change shape. No "honorifics"
        or "speech_levels" — politeness is carried by word choice (您 for 你,
        请 for requests), not by a grammatical system. Declaring either would
        put a tab in the UI with nothing true to show in it.
        """
        return frozenset({
            "tone_sandhi",
            "measure_words",
            "aspect_particles",
            "character_components",
            "stroke_order",
        })

    # -- protocol surface --------------------------------------------------

    def analyse(self, text: str) -> dict:
        """Surface analysis: function words, aspect particles, measure words.

        Chinese is written without spaces and segmentation needs a dictionary,
        so this identifies the closed-class words it can recognise and says so.
        """
        found_aspect = [a for a in ASPECT if a["particle"] in text]
        found_measures = [m for m in MEASURE_WORDS if m["word"] in text]
        found_structures = [s for s in STRUCTURES
                            if s["pattern"] in text and len(s["pattern"]) == 1]

        out: dict[str, Any] = {
            "language": "zh",
            "depth": "surface",
            "note": ("Function words only. Chinese has no spaces, so full "
                     "segmentation needs a dictionary this app does not bundle."),
            "aspect_particles": [{"particle": a["particle"], "marks": a["marks"],
                                  "simple": a["simple"]} for a in found_aspect],
            "measure_words": [{"word": m["word"], "for": m["for"]}
                              for m in found_measures],
            "structures": [{"pattern": s["pattern"], "name": s["name"]}
                           for s in found_structures],
        }
        # If it looks like pinyin rather than characters, add the tone reading.
        syllables = P.parse_phrase(text)
        if syllables and all(s.valid for s in syllables):
            out["tones"] = T.apply_sandhi(text).to_dict()
        return out

    def drill_forms(self, entry: dict) -> list[dict]:
        """What is worth practising about a Mandarin word.

        Not conjugations — there are none. For a noun it is the measure word;
        for a verb it is the aspect particles; for anything it is the tones,
        which is the thing that most needs drilling.
        """
        term = entry.get("term") or entry.get("target") or ""
        reading = (entry.get("pinyin") or entry.get("transliteration")
                   or entry.get("reading") or "")
        pos = entry.get("pos", "")
        if not term:
            return []

        out: list[dict] = []

        if reading:
            sandhi = T.apply_sandhi(reading)
            out.append({"form_id": "tones", "form": term,
                        "pinyin": sandhi.spoken,
                        "label": "as it is actually said" if sandhi.changed
                                 else "tones", "category": "pronunciation"})
            if sandhi.changed:
                out.append({"form_id": "tones_written", "form": term,
                            "pinyin": reading, "label": "as it is written",
                            "category": "pronunciation"})

        if pos == "noun":
            measure = entry.get("counter") or entry.get("measure_word") or "个"
            mw = next((m for m in MEASURE_WORDS if m["word"] == measure), None)
            out.append({"form_id": "measure", "form": f"一{measure}{term}",
                        "label": f"with its measure word {measure}",
                        "category": "measure_word",
                        "note": mw["for"] if mw else ""})
            out.append({"form_id": "demonstrative", "form": f"这{measure}{term}",
                        "label": "this one", "category": "measure_word"})

        if pos == "verb":
            for particle, label in (("了", "completed"), ("过", "ever done"),
                                    ("在", "in progress")):
                form = (f"在{term}" if particle == "在" else f"{term}{particle}")
                out.append({"form_id": f"aspect_{particle}", "form": form,
                            "label": label, "category": "aspect"})
            out.append({"form_id": "negative", "form": f"不{term}",
                        "label": "negative (habitual)", "category": "negation"})
            out.append({"form_id": "negative_past", "form": f"没{term}",
                        "label": "negative (did not happen)", "category": "negation",
                        "note": "没 negates completion; 不 negates habit or intention."})

        return out

    # -- Mandarin-specific -------------------------------------------------

    def measure_words(self) -> list[dict]:
        return MEASURE_WORDS

    def aspect_particles(self) -> list[dict]:
        return ASPECT

    def structures(self) -> list[dict]:
        return STRUCTURES

    def word_order(self) -> dict:
        return WORD_ORDER

    def measure_word_for(self, noun: str, entry: Optional[dict] = None) -> dict:
        """The measure word a noun takes.

        Lexical, so it comes from the vocabulary entry. Where none is recorded
        the engine says 个 and says that it is a fallback rather than a fact.
        """
        declared = (entry or {}).get("counter") or (entry or {}).get("measure_word")
        if declared:
            mw = next((m for m in MEASURE_WORDS if m["word"] == declared), None)
            return {"noun": noun, "measure_word": declared, "confident": True,
                    "for": mw["for"] if mw else ""}
        return {
            "noun": noun, "measure_word": "个", "confident": False,
            "for": "the general-purpose measure word",
            "note": "No measure word is recorded for this noun, so 个 is shown as "
                    "the safe default. It is right most of the time and never "
                    "unintelligible, but check before relying on it.",
        }


ENGINE = MandarinGrammar()
