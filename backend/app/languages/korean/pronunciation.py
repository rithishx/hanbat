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

    def rules(self) -> dict:
        """Every sound-change rule, with both explanation registers."""
        return P.RULES


ENGINE = KoreanPronunciation()
