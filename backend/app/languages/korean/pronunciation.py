"""Korean pronunciation as a PronunciationEngine."""

from __future__ import annotations

from typing import Any, Optional

from . import phonology as P


class KoreanPronunciation:
    language = "ko"
    name = "Korean pronunciation"
    #: Korean's spelling-to-sound gap is rule-governed rather than lexical, so
    #: the engine can genuinely derive pronunciation instead of storing it.
    is_rule_derived = True

    def pronounce(self, text: str, **options: Any) -> dict:
        hints = options.get("hints")
        override = options.get("override")
        result = P.pronounce_phrase(text, hints, override)
        return result.to_dict()

    def explain(self, text: str, **options: Any) -> dict:
        return P.explain(text, options.get("hints"))

    def final_sound(self, final: str) -> str:
        """Which of the seven audible codas a written batchim produces."""
        return P.batchim_sound(final)

    def are_minimal_pairs(self, a: str, b: str) -> bool:
        return P.minimal_pairs(a, b)

    def difficulty_points(self) -> list[dict]:
        """What English speakers reliably get wrong in Korean.

        Ordered by how much damage each does. The three-way obstruent
        contrast comes first because it produces genuine misunderstandings
        (불/풀/뿔 are three different words); ㅐ/ㅔ comes last because even
        native speakers have merged them.
        """
        return [
            {
                "id": "three_way_obstruents",
                "title": "ㄱ/ㅋ/ㄲ and friends",
                "contrast": ["ㄱ ㅋ ㄲ", "ㄷ ㅌ ㄸ", "ㅂ ㅍ ㅃ", "ㅈ ㅊ ㅉ"],
                "why_hard": "English distinguishes two of these; Korean distinguishes three. Untrained English ears hear all three as one sound.",
                "fix": "Hold a hand in front of your mouth. Aspirated blows air, plain barely does, tense blows none and tightens the throat.",
                "minimal_pairs": [["불", "풀", "뿔"], ["달", "탈", "딸"], ["자다", "차다", "짜다"]],
                "severity": "high",
                "causes_misunderstanding": True,
            },
            {
                "id": "eo_vs_o",
                "title": "ㅓ versus ㅗ",
                "contrast": ["ㅓ", "ㅗ"],
                "why_hard": "Both are romanised with an 'o' shape ('eo' and 'o'), which hides that one is rounded and one is not.",
                "fix": "Watch your lips in a mirror. If they push forward, you said ㅗ.",
                "minimal_pairs": [["서", "소"], ["멀다", "몰라"]],
                "severity": "high",
                "causes_misunderstanding": True,
            },
            {
                "id": "eu_vowel",
                "title": "ㅡ",
                "contrast": ["ㅡ", "ㅜ"],
                "why_hard": "English has no unrounded high back vowel, so learners substitute 'oo' or the u of 'put'.",
                "fix": "Say 'ee', then pull your lips flat and wide without moving your tongue.",
                "minimal_pairs": [["그", "구"], ["느리다", "누리다"]],
                "severity": "high",
                "causes_misunderstanding": True,
            },
            {
                "id": "rieul",
                "title": "ㄹ",
                "contrast": ["ㄹ initial", "ㄹ final"],
                "why_hard": "One letter covers a tapped flap and a clear l, and neither is the English r.",
                "fix": "Say 'butter' quickly and notice the tongue tap in the middle. That tap is initial ㄹ.",
                "minimal_pairs": [],
                "severity": "medium",
                "causes_misunderstanding": False,
            },
            {
                "id": "unreleased_finals",
                "title": "Unreleased 받침",
                "contrast": ["옷", "옫"],
                "why_hard": "English releases final stops with a small puff. Korean does not, and releasing them sounds foreign immediately.",
                "fix": "Say 'cat' but freeze before the t escapes.",
                "minimal_pairs": [],
                "severity": "medium",
                "causes_misunderstanding": False,
            },
            {
                "id": "ae_vs_e",
                "title": "ㅐ versus ㅔ",
                "contrast": ["ㅐ", "ㅔ"],
                "why_hard": "They have merged for most speakers under forty — there is nothing left to hear.",
                "fix": "Do not train your ear. Learn which spelling each word takes.",
                "minimal_pairs": [["개", "게"]],
                "severity": "low",
                "causes_misunderstanding": False,
                "note": "A spelling problem, not a pronunciation one. Listed so learners stop trying to hear a contrast that is not there.",
            },
        ]

    #: One or two words per rule that actually trigger it, with the hints that
    #: rule needs. Kept as bare strings: the spoken form is *computed* when the
    #: index is built, never written out here, so a change to the phonology can
    #: never leave a worked example contradicting the engine that produced it.
    #:
    #: Four of these rules only fire with a hint, because they are
    #: morphologically or lexically conditioned rather than automatic —
    #: ㄴ-insertion, the two conditioned tensifications, and 의 reduction. That
    #: is a fact about Korean, not a shortcoming: 첫인상 is [천닌상] and 첫아들
    #: is [처다들], and no amount of looking at the spelling distinguishes them.
    RULE_EXAMPLES: dict[str, list[tuple[str, str, dict]]] = {
        "liaison": [
            ("한국어", "The ㄱ underneath 한 slides into the empty ㅇ.", {}),
            ("꽃이", "The original ㅊ survives — it is not flattened first.", {}),
        ],
        "cluster_simplification": [
            ("읽다", "Two consonants underneath, only one can be said.", {}),
            ("앉다", "The ㅈ is dropped and the ㄷ tenses.", {}),
        ],
        "neutralisation": [
            ("꽃", "Seven sounds are all a final consonant can be.", {}),
            ("옷", "ㅅ underneath is heard as an unreleased ㄷ.", {}),
        ],
        "aspiration": [
            ("좋다", "ㅎ meets ㄷ and they fuse into ㅌ.", {}),
            ("입학", "ㅂ meets ㅎ and becomes ㅍ.", {}),
        ],
        "h_deletion": [("좋아요", "ㅎ between vowels simply disappears.", {})],
        "nasalisation": [
            ("한국말", "ㄱ before ㅁ cannot stay a stop.", {}),
            ("입니다", "ㅂ before ㄴ becomes ㅁ — the first one every learner meets.", {}),
        ],
        "lateral_nasalisation": [("정리", "ㄹ after ㅇ becomes ㄴ.", {})],
        "lateralisation": [("신라", "ㄴ next to ㄹ gives way and becomes ㄹ.", {})],
        "tensification": [
            ("학교", "A stop after a stop is tensed.", {}),
            ("먹다", "The ㄷ tightens to ㄸ.", {}),
        ],
        "tensification_morphological": [
            ("신다", "A verb stem ending in ㄴ tenses the ending. The noun 신도 "
                    "does not, which is why this needs to know it is a verb.",
             {"verb_stem_ends_at": [0]}),
        ],
        "tensification_sino": [
            ("발달", "Sino-Korean ㄹ + ㄷ. Native words do not do this.",
             {"sino_korean": True}),
        ],
        "palatalisation": [
            ("같이", "ㅌ before 이 becomes ㅊ, not ㅌ.", {}),
            ("닫히다", "Palatalisation wins over aspiration here.", {}),
        ],
        "n_insertion": [
            ("첫인상", "A ㄴ appears that is written nowhere. 첫아들 does not do "
                     "this — the spelling cannot tell you which.",
             {"n_insertion_after": [0]}),
        ],
        "ui_reduction": [
            ("민주주의", "Non-initial 의 relaxes to 이 or, as the possessive, 에.",
             {"genitive_ui": [3]}),
        ],
    }

    def rules(self) -> list[dict]:
        """Every sound-change rule, with worked examples the engine verifies.

        The examples are run through `pronounce()` here rather than being
        written out as text. That costs a few milliseconds and buys the
        guarantee that the lab can never show a worked example the engine
        disagrees with — which is exactly the drift that makes reference
        material untrustworthy.
        """
        out = []
        for rule_id, info in P.RULES.items():
            examples = []
            for word, note, hints in self.RULE_EXAMPLES.get(rule_id, []):
                result = P.explain(word, hints=hints or None)
                fired = any(step.get("rule_id") == rule_id
                            for step in result.get("steps", []))
                examples.append({
                    "written": word,
                    "spoken": result.get("spoken", word),
                    "note": note,
                    "hints": hints,
                    # Surfaced rather than hidden: an example that stopped
                    # triggering its own rule is a bug worth seeing.
                    "verified": fired,
                })
            out.append({
                "id": rule_id,
                "name": info.get("en", rule_id),
                "native_name": info.get("ko", ""),
                "simple": info.get("simple", ""),
                "technical": info.get("technical", ""),
                "examples": examples,
            })
        return out


ENGINE = KoreanPronunciation()
