"""
Japanese level ladder: JLPT.

Japanese learners think in JLPT levels, not CEFR. N5 is the entry level and N1
the highest — the numbering runs downward, which surprises everyone once. The
vocabulary thresholds are very different from Korean's CEFR bands, which is
precisely why each language owns its ladder.
"""

from __future__ import annotations

from dataclasses import dataclass

SKILL_NAMES = {
    "reading": "読む", "listening": "聞く", "writing": "書く", "speaking": "話す",
    "grammar": "文法", "vocabulary": "語彙", "pronunciation": "発音",
}

#: Easiest first, so the shared core can index into it. Note this is the
#: reverse of how JLPT levels are spoken about — N5 is the beginner exam.
LEVELS: tuple[str, ...] = ("pre-N5", "N5", "N4", "N3", "N2", "N1")

#: (vocabulary, grammar points) needed for each band. These come from the
#: published JLPT guidelines and are far apart from CEFR's: N3 expects around
#: 3,700 words where CEFR B1 expects around 3,000, and the jump from N3 to N2
#: is the steepest in the whole ladder.
THRESHOLDS: list[tuple[str, int, int]] = [
    ("N1", 10000, 250),
    ("N2", 6000, 180),
    ("N3", 3700, 120),
    ("N4", 1500, 65),
    ("N5", 800, 30),
]

DESCRIPTIONS: dict[str, dict] = {
    "pre-N5": {
        "name": "Before N5", "japanese": "かな学習中",
        "can_do": ["Learn hiragana", "Learn katakana", "Read simple kana words"],
        "milestone": "Read all 107 kana without hesitating.",
        "kanji": "0",
    },
    "N5": {
        "name": "Beginner", "japanese": "N5",
        "can_do": ["Read hiragana, katakana and basic kanji",
                   "Introduce yourself and talk about daily routine",
                   "Use は, が, を, に, で and the ます form",
                   "Understand slow, simple conversation"],
        "milestone": "Hold a self-introduction and order in a restaurant.",
        "vocabulary": "≈ 800 words", "kanji": "≈ 100",
    },
    "N4": {
        "name": "Elementary", "japanese": "N4",
        "can_do": ["Use plain form and て-form structures",
                   "Talk about past experience and plans",
                   "Read simple everyday material",
                   "Follow conversation on familiar topics at slow speed"],
        "milestone": "Get through a day in Japan without English.",
        "vocabulary": "≈ 1,500 words", "kanji": "≈ 300",
    },
    "N3": {
        "name": "Intermediate", "japanese": "N3",
        "can_do": ["Use keigo appropriately in common situations",
                   "Read newspaper headlines and simple articles",
                   "Follow everyday conversation at near-natural speed",
                   "Use conditional and passive forms comfortably"],
        "milestone": "The bridge level. Most learners find this the hardest jump.",
        "vocabulary": "≈ 3,700 words", "kanji": "≈ 650",
    },
    "N2": {
        "name": "Upper intermediate", "japanese": "N2",
        "can_do": ["Read newspapers and general-interest writing",
                   "Follow news broadcasts and films",
                   "Handle workplace Japanese",
                   "Understand nuance and implication"],
        "milestone": "The level most employers in Japan ask for.",
        "vocabulary": "≈ 6,000 words", "kanji": "≈ 1,000",
    },
    "N1": {
        "name": "Advanced", "japanese": "N1",
        "can_do": ["Read abstract, structurally complex writing",
                   "Follow any conversation, including regional speech",
                   "Understand literary and classical references",
                   "Use the full keigo system correctly"],
        "milestone": "Function as an adult in any Japanese setting.",
        "vocabulary": "≈ 10,000+ words", "kanji": "≈ 2,000 (常用漢字)",
    },
}


@dataclass(frozen=True)
class JapaneseLevels:
    levels: tuple[str, ...] = LEVELS
    scheme: str = "JLPT"

    def estimate(self, script_mastery: float, vocab_known: int,
                 grammar_known: int, accuracy: float) -> str:
        """Kana gates everything, exactly as Hangul does for Korean.

        Conservative for the same reason: JLPT levels are what learners put on
        CVs, and telling someone they are N3 when they are N4 sends them into
        material that will convince them they have stopped improving.
        """
        if script_mastery < 0.85:
            return "pre-N5"
        band = "pre-N5"
        for name, min_vocab, min_grammar in THRESHOLDS:
            if vocab_known >= min_vocab and grammar_known >= min_grammar:
                band = name
                break
        if band == "pre-N5" and vocab_known >= 150:
            band = "N5"
        if accuracy and accuracy < 65 and band != "pre-N5":
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


ENGINE = JapaneseLevels()

TUTOR_NOTES = """\
Japanese-specific things to get right:
- Default to the polite ます form. Do not switch to plain form unless the \
learner asks about it, and never use casual speech with someone you are \
teaching unless they ask you to.
- Keigo is a separate vocabulary, not a conjugation. 食べる becomes 召し上がる \
for someone else and いただく for yourself. Never apply 尊敬語 to your own \
actions or the learner's own actions.
- Japanese word order is subject-object-verb and the verb is always last. \
Particles do the work English does with word order.
- Subjects are dropped constantly. Do not correct a learner for omitting 私は \
when it is obvious — adding it everywhere sounds like a textbook.
- は versus が is the hardest thing at this level. If the learner picks wrong, \
ask whether the information is new or already established.
- Watch for mora timing errors in anything they write in kana: きて and きって \
are different words.
- Write example sentences with kanji plus furigana readings where the learner \
is below N4, not in kana alone — kana-only Japanese is harder to read, not \
easier.
"""
