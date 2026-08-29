"""
Korean grammar as a GrammarEngine.

This class exposes far more than the shared `GrammarEngine` protocol requires,
and that is the point of the design: shared code calls only `capabilities()`,
`analyse()` and `drill_forms()`, while Korean-specific code (the conjugation
screen, the particle drills, the honorific lessons) reaches for the richer
methods directly. Neither Japanese nor Mandarin is forced to pretend it has a
`conjugate()`.
"""

from __future__ import annotations

from typing import Any, Optional

from . import conjugation as C
from . import hangul as H


class KoreanGrammar:
    language = "ko"

    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "conjugation",     # eleven irregular stem classes
            "particles",       # allomorphs selected by batchim
            "honorifics",      # -(으)시- plus suppletive stems
            "speech_levels",   # 해요체 / 합니다체 / 반말 / 한다체
            "counters",        # native and Sino numerals with counter words
        })

    # -- protocol surface --------------------------------------------------

    def analyse(self, text: str) -> dict:
        """Best-effort breakdown of a Korean phrase.

        Honest about its limits: this is not a full morphological analyser.
        It identifies particles by surface match and reports batchim facts,
        which is enough for the tutor to give useful feedback on a beginner
        sentence, and it says so rather than implying deeper parsing.
        """
        words = text.split()
        out = []
        for w in words:
            stripped, particle = self._split_particle(w)
            out.append({
                "surface": w,
                "stem_guess": stripped,
                "particle": particle,
                "ends_with_batchim": H.ends_with_batchim(stripped) if stripped else None,
                "final": H.final_of(stripped) if stripped else "",
            })
        return {
            "language": "ko",
            "words": out,
            "depth": "surface",
            "note": "Surface segmentation only — particles are matched by form, not parsed morphologically.",
        }

    def drill_forms(self, entry: dict) -> list[dict]:
        """Which forms of this word are worth practising?

        For a verb or adjective that is the conjugation table, filtered to the
        forms a learner at this level has actually met. For a noun it is the
        particle set, because choosing 은/는 versus 이/가 is what Korean noun
        practice actually consists of.
        """
        korean = entry.get("korean") or entry.get("term") or ""
        pos = entry.get("pos", "")
        if not korean:
            return []

        if pos in ("verb", "adjective") and korean.endswith("다"):
            table = C.conjugate(korean, pos=pos, irregular=entry.get("irregular") or None)
            wanted = ("present_polite", "past_polite", "present_formal",
                      "negative_short", "future_polite", "connect_and",
                      "modifier_present", "aux_want")
            return [
                {"form_id": f, "form": table[f].korean, "label": table[f].label_en,
                 "category": table[f].category}
                for f in wanted if f in table
            ]

        if pos in ("noun", "pronoun"):
            return [
                {"form_id": "topic", "form": H.attach_particle(korean, H.TOPIC),
                 "label": "with the topic particle", "category": "particle"},
                {"form_id": "subject", "form": H.attach_particle(korean, H.SUBJECT),
                 "label": "with the subject particle", "category": "particle"},
                {"form_id": "object", "form": H.attach_particle(korean, H.OBJECT),
                 "label": "with the object particle", "category": "particle"},
                {"form_id": "copula", "form": H.attach_particle(korean, H.COPULA),
                 "label": "'is a ...'", "category": "copula"},
            ]
        return []

    # -- Korean-specific surface, called only by Korean code ---------------

    def conjugate(self, dictionary_form: str, pos: Optional[str] = None,
                  irregular: Optional[str] = None) -> dict:
        return {k: v.to_dict() for k, v in
                C.conjugate(dictionary_form, pos, irregular).items()}

    def conjugation_table(self, dictionary_form: str, pos: Optional[str] = None,
                          irregular: Optional[str] = None) -> dict:
        return C.conjugation_table(dictionary_form, pos, irregular)

    def classify(self, dictionary_form: str) -> dict:
        return C.classify(dictionary_form).to_dict()

    def attach_particle(self, word: str, which: str) -> str:
        pairs = {"topic": H.TOPIC, "subject": H.SUBJECT, "object": H.OBJECT,
                 "and": H.AND_NOUN, "copula": H.COPULA}
        if which not in pairs:
            raise ValueError(f"unknown particle {which!r}; expected one of {sorted(pairs)}")
        return H.attach_particle(word, pairs[which])

    def speech_levels(self) -> dict:
        return C.SPEECH_LEVELS

    def irregular_classes(self) -> dict:
        return C.IRREGULAR_EXPLANATIONS

    # -- internals ---------------------------------------------------------

    #: Longest first, so 에서 is matched before 에.
    _PARTICLES = (
        "에서는", "에서", "에게서", "에게", "한테서", "한테", "께서", "께",
        "으로는", "으로", "로는", "로", "와는", "과는", "와", "과", "하고",
        "이라고", "라고", "부터", "까지", "마다", "처럼", "보다", "만큼",
        "은", "는", "이", "가", "을", "를", "도", "만", "의",
    )

    def _split_particle(self, word: str) -> tuple[str, str]:
        for p in sorted(self._PARTICLES, key=len, reverse=True):
            if word.endswith(p) and len(word) > len(p):
                return word[: -len(p)], p
        return word, ""


ENGINE = KoreanGrammar()
