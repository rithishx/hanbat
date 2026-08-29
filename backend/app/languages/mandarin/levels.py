"""
Mandarin level ladder: HSK.

HSK runs 1 to 6 upward — the opposite direction from JLPT, which is a small
thing that confuses anyone studying both. The vocabulary thresholds are also
much lower than CEFR's or JLPT's at comparable-sounding levels: HSK 4 expects
around 1,200 words where CEFR B1 expects 3,000. Anyone tempted to map these
scales onto each other should look at that number first.

Character count is tracked separately from vocabulary, because in Mandarin
they come apart: you can know 好 and 学 and still not know 好学.
"""

from __future__ import annotations

from dataclasses import dataclass

SKILL_NAMES = {
    "reading": "阅读", "listening": "听力", "writing": "写作", "speaking": "口语",
    "grammar": "语法", "vocabulary": "词汇", "pronunciation": "发音",
}

LEVELS: tuple[str, ...] = ("pre-HSK1", "HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6")

#: (vocabulary, grammar points). The official HSK word counts, which are far
#: lower than the equivalent-sounding CEFR or JLPT bands.
THRESHOLDS: list[tuple[str, int, int]] = [
    ("HSK6", 5000, 200),
    ("HSK5", 2500, 150),
    ("HSK4", 1200, 100),
    ("HSK3", 600, 60),
    ("HSK2", 300, 30),
    ("HSK1", 150, 12),
]

DESCRIPTIONS: dict[str, dict] = {
    "pre-HSK1": {
        "name": "Before HSK 1", "chinese": "拼音学习中",
        "can_do": ["Learn pinyin initials and finals", "Hear and produce the four tones"],
        "milestone": "Read any pinyin syllable aloud with the right tone.",
        "characters": "0",
    },
    "HSK1": {
        "name": "Beginner", "chinese": "一级",
        "can_do": ["Use simple phrases about yourself and immediate needs",
                   "Recognise around 150 characters",
                   "Use 是, 有, 在 and basic measure words",
                   "Ask and answer with 吗 and question words"],
        "milestone": "Introduce yourself and buy something.",
        "vocabulary": "150 words", "characters": "≈ 170",
    },
    "HSK2": {
        "name": "Elementary", "chinese": "二级",
        "can_do": ["Talk about routine matters in simple terms",
                   "Use 了 for completed actions", "Use comparisons with 比",
                   "Handle time, dates and simple directions"],
        "milestone": "Get through a day of simple transactions.",
        "vocabulary": "300 words", "characters": "≈ 350",
    },
    "HSK3": {
        "name": "Intermediate", "chinese": "三级",
        "can_do": ["Handle most situations while travelling in China",
                   "Use resultative and directional complements",
                   "Use 把 for handling and disposal",
                   "Read short passages without pinyin"],
        "milestone": "Travel independently.",
        "vocabulary": "600 words", "characters": "≈ 620",
    },
    "HSK4": {
        "name": "Upper intermediate", "chinese": "四级",
        "can_do": ["Discuss a range of topics fluently",
                   "Use 被 for the passive", "Follow conversation at natural speed",
                   "Read newspapers with a dictionary"],
        "milestone": "Study or work in Chinese with support.",
        "vocabulary": "1,200 words", "characters": "≈ 1,070",
    },
    "HSK5": {
        "name": "Advanced", "chinese": "五级",
        "can_do": ["Read newspapers and magazines",
                   "Watch films and follow the dialogue",
                   "Give a full-length talk", "Use 成语 appropriately"],
        "milestone": "Function in a Chinese-language workplace.",
        "vocabulary": "2,500 words", "characters": "≈ 1,700",
    },
    "HSK6": {
        "name": "Proficient", "chinese": "六级",
        "can_do": ["Understand written and spoken Chinese with ease",
                   "Express yourself fluently on any topic",
                   "Read literature and technical writing",
                   "Catch idiom, irony and register"],
        "milestone": "Miss nothing an educated native speaker would catch.",
        "vocabulary": "5,000+ words", "characters": "≈ 2,600",
    },
}


@dataclass(frozen=True)
class MandarinLevels:
    levels: tuple[str, ...] = LEVELS
    scheme: str = "HSK"

    def estimate(self, script_mastery: float, vocab_known: int,
                 grammar_known: int, accuracy: float) -> str:
        """Pinyin gates the ladder, as kana and Hangul do elsewhere.

        Someone who cannot produce the tones has not learned any of the words
        they think they have — a toneless word is a word that will not be
        understood, so counting it would be flattering nonsense.
        """
        if script_mastery < 0.85:
            return "pre-HSK1"
        band = "pre-HSK1"
        for name, min_vocab, min_grammar in THRESHOLDS:
            if vocab_known >= min_vocab and grammar_known >= min_grammar:
                band = name
                break
        if band == "pre-HSK1" and vocab_known >= 80:
            band = "HSK1"
        if accuracy and accuracy < 65 and band != "pre-HSK1":
            band = LEVELS[max(0, LEVELS.index(band) - 1)]
        return band

    def describe(self, level: str) -> dict:
        d = dict(DESCRIPTIONS.get(level, {}))
        d["level"] = level
        d["scheme"] = self.scheme
        d["index"] = LEVELS.index(level) if level in LEVELS else -1
        d["of"] = len(LEVELS) - 1
        return d

    def next_level(self, level: str) -> str | None:
        if level not in LEVELS:
            return None
        i = LEVELS.index(level)
        return LEVELS[i + 1] if i + 1 < len(LEVELS) else None


ENGINE = MandarinLevels()

TUTOR_NOTES = """\
Mandarin-specific things to get right:
- ALWAYS write pinyin with tone marks. A toneless word is not a word — the \
learner will memorise it wrong and have to relearn it.
- Mandarin has no conjugation. Do not invent tense endings. Time is carried by \
time words (昨天, 明天) and aspect particles (了, 过, 着), and the verb never \
changes shape.
- Every counted noun needs a measure word: 三本书, not 三书. If the learner \
omits one, that is usually the thing to fix first.
- Word order does the work that particles do in Korean and Japanese. \
Subject-verb-object, with time and place before the verb, not after it.
- 了 is the hardest thing at every level. It marks completion, not past tense. \
Do not call it "the past tense marker" — that sets up a misunderstanding the \
learner will fight for years.
- Remember third-tone sandhi when you write example sentences: 你好 is written \
nǐ hǎo and said ní hǎo. Say which you are giving.
- Do not use 成语 or literary phrasing with a beginner, however elegant.
"""
