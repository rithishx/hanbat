"""
Korean level ladder.

Korean learners are pulled between two schemes. CEFR (A1–C2) is what most
Western textbooks and the EU-aligned courses use. TOPIK (levels 1–6) is the
official Korean government proficiency exam and the one that actually matters
for university admission and visas in Korea. They map onto each other roughly
but not exactly, so this module carries both and shows the TOPIK equivalent
alongside the CEFR band rather than pretending one replaces the other.
"""

from __future__ import annotations

from dataclasses import dataclass

#: What Korean calls the skills — used on the progress screen.
SKILL_NAMES = {
    "reading": "읽기",
    "listening": "듣기",
    "writing": "쓰기",
    "speaking": "말하기",
    "grammar": "문법",
    "vocabulary": "어휘",
    "pronunciation": "발음",
}

LEVELS: tuple[str, ...] = ("pre-A1", "A1", "A2", "B1", "B2", "C1", "C2")

#: Approximate TOPIK equivalence. Deliberately approximate — TOPIK weights
#: reading and listening far more heavily than speaking, so the mapping is a
#: guide rather than a promise.
TOPIK_EQUIVALENT = {
    "pre-A1": "—",
    "A1": "TOPIK I, level 1",
    "A2": "TOPIK I, level 2",
    "B1": "TOPIK II, level 3",
    "B2": "TOPIK II, level 4",
    "C1": "TOPIK II, level 5",
    "C2": "TOPIK II, level 6",
}

#: (minimum vocabulary, minimum grammar points) to reach each band.
#: Vocabulary counts are of words genuinely *known* — cards in review or
#: mastered state, not cards merely introduced.
THRESHOLDS: list[tuple[str, int, int]] = [
    ("C1", 5000, 120),
    ("B2", 3000, 90),
    ("B1", 1500, 55),
    ("A2", 700, 30),
    ("A1", 150, 8),
]

DESCRIPTIONS: dict[str, dict] = {
    "pre-A1": {
        "name": "Before the beginning",
        "korean": "한글 배우기",
        "can_do": ["Recognise that Korean is written in blocks", "Work through the Hangul unit"],
        "milestone": "Read Hangul aloud without romanisation.",
    },
    "A1": {
        "name": "Beginner",
        "korean": "초급 1",
        "can_do": [
            "Introduce yourself and ask someone's name",
            "Order food and ask how much something costs",
            "Use 이에요/예요, 은/는, 이/가, 을/를, 에, 에서",
            "Talk about today and yesterday in the polite 해요 style",
        ],
        "milestone": "Survive a simple transaction entirely in Korean.",
        "vocabulary": "≈ 800 words",
    },
    "A2": {
        "name": "Elementary",
        "korean": "초급 2",
        "can_do": [
            "Describe your day, your family and your plans",
            "Use -아/어서, -(으)니까, -지만, -(으)면",
            "Handle a doctor's appointment or a lost item",
            "Switch between 해요체 and 합니다체 appropriately",
        ],
        "milestone": "Hold a five-minute conversation about familiar things.",
        "vocabulary": "≈ 1,500–2,000 words",
    },
    "B1": {
        "name": "Intermediate",
        "korean": "중급 1",
        "can_do": [
            "Use -는데 naturally to set up context",
            "Handle indirect speech (-다고 하다)",
            "Follow a slow news broadcast on a familiar topic",
            "Use honorifics correctly with someone senior",
        ],
        "milestone": "Say something complicated and be understood the first time.",
        "vocabulary": "≈ 3,000 words",
    },
    "B2": {
        "name": "Upper intermediate",
        "korean": "중급 2",
        "can_do": [
            "Argue a position and concede a point",
            "Read a newspaper article with occasional lookups",
            "Use passive and causative forms",
            "Notice when someone is being indirect or sarcastic",
        ],
        "milestone": "Work in Korean without constantly translating in your head.",
        "vocabulary": "≈ 5,000 words",
    },
    "C1": {
        "name": "Advanced",
        "korean": "고급 1",
        "can_do": [
            "Give a presentation and field questions",
            "Read essays and academic prose",
            "Use 한자어 vocabulary precisely",
            "Adjust register from a job interview to a group chat",
        ],
        "milestone": "Be treated as a competent adult rather than a language learner.",
        "vocabulary": "≈ 8,000–10,000 words",
    },
    "C2": {
        "name": "Proficient",
        "korean": "고급 2",
        "can_do": [
            "Understand idioms, proverbs and wordplay",
            "Read literature and legal or technical prose",
            "Recognise regional accents and generational slang",
            "Write in a register appropriate to any situation",
        ],
        "milestone": "Miss nothing that a native speaker would catch.",
        "vocabulary": "20,000+ words",
    },
}


@dataclass(frozen=True)
class KoreanLevels:
    levels: tuple[str, ...] = LEVELS
    scheme: str = "CEFR (with TOPIK equivalence)"

    def estimate(
        self,
        script_mastery: float,
        vocab_known: int,
        grammar_known: int,
        accuracy: float,
    ) -> str:
        """Deliberately conservative.

        Hangul gates everything: someone who cannot read yet is pre-A1 no
        matter how many words they have collected, because they cannot use
        any of them in the wild. Above that, vocabulary and grammar must BOTH
        clear a band, and sustained low accuracy pulls the estimate down.

        Erring low is the right bias. Being told you are B1 when you are A2
        sends you into material you cannot read, which reliably produces the
        conclusion that you have plateaued — when in fact you were mislabelled.
        """
        if script_mastery < 0.85:
            return "pre-A1"

        band = "pre-A1"
        for name, min_vocab, min_grammar in THRESHOLDS:
            if vocab_known >= min_vocab and grammar_known >= min_grammar:
                band = name
                break
        else:
            band = "pre-A1"

        if band == "pre-A1" and vocab_known >= 150:
            band = "A1"

        if accuracy and accuracy < 65 and band != "pre-A1":
            band = LEVELS[max(0, LEVELS.index(band) - 1)]
        return band

    def describe(self, level: str) -> dict:
        d = dict(DESCRIPTIONS.get(level, {}))
        d["level"] = level
        d["scheme"] = self.scheme
        d["topik"] = TOPIK_EQUIVALENT.get(level, "")
        d["index"] = LEVELS.index(level) if level in LEVELS else -1
        d["of"] = len(LEVELS) - 1
        return d

    def next_level(self, level: str) -> str | None:
        if level not in LEVELS:
            return None
        i = LEVELS.index(level)
        return LEVELS[i + 1] if i + 1 < len(LEVELS) else None


ENGINE = KoreanLevels()


#: Teaching notes handed to the AI tutor. Korean-specific pitfalls that a
#: general-purpose model reliably gets wrong when talking to a beginner.
TUTOR_NOTES = """\
Korean-specific things to get right:
- Default to 해요체 (-아/어요). Do not slip into 반말 unless the learner asks, \
and do not use 하십시오체 in casual conversation.
- Never use an honorific about the learner's own actions, and never about \
yourself. -(으)세요 is for what THEY do, not what you do.
- 은/는 versus 이/가 is the hardest thing at this level. If the learner picks \
wrong, ask whether the information is new or already known rather than \
stating the rule.
- Remember that 좋다 takes 이/가 but 좋아하다 takes 을/를, and that 있다's \
negative is the separate word 없다, not 안 있다.
- Korean word order is subject-object-verb and the verb is always last. If a \
learner writes English word order, that is the thing to fix first.
- Subjects are dropped constantly in natural Korean. Do not correct a learner \
for omitting 저는 when it is obvious.
- When you write example sentences, use natural Korean rather than textbook \
Korean, and say which one you are giving if they differ.
"""
