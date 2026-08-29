"""
Japanese grammar as a GrammarEngine.

Exposes the same three protocol methods the shared core calls, and a much
richer Japanese-specific surface underneath — conjugation, particles, keigo —
that only Japanese code touches. The capability set differs from Korean's:
Japanese declares `keigo` where Korean declares `speech_levels`, because they
are not the same system and pretending otherwise would produce a lesson that
teaches neither correctly.
"""

from __future__ import annotations

from typing import Any, Optional

from . import kana as K
from . import verbs as V

#: Japanese particles, longest first so は is not matched inside には.
PARTICLES = (
    "には", "では", "とは", "から", "まで", "より", "だけ", "しか", "でも",
    "など", "ばかり", "ながら", "ので", "のに", "けど", "が", "を", "に",
    "へ", "と", "で", "は", "も", "の", "や", "か", "ね", "よ", "な",
)

PARTICLE_NOTES: dict[str, str] = {
    "は": "Topic. What the sentence is about — and often an implied contrast.",
    "が": "Subject. New information, or the answer to 'who?'.",
    "を": "Direct object.",
    "に": "Destination, time, indirect object, existence location.",
    "で": "Where an action happens, or the means by which.",
    "へ": "Direction. Read 'e'. Softer than に — more 'towards' than 'to'.",
    "と": "With, and (exhaustive list), or quotation.",
    "も": "Also. Replaces は, が and を rather than stacking with them.",
    "の": "Possession, or turning a clause into a noun modifier.",
    "から": "From, or because.",
    "まで": "Until, as far as.",
    "や": "And (a non-exhaustive list — 'things like').",
    "ね": "Seeking agreement. 'isn't it?'",
    "よ": "Telling someone something they do not know.",
}


class JapaneseGrammar:
    language = "ja"

    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "conjugation",   # godan / ichidan / two irregulars
            "particles",     # は/が/を/に/で...
            "honorifics",    # -(ら)れる respectful, お...になる
            "keigo",         # 尊敬語 / 謙譲語 as separate vocabulary
            "counters",      # 一つ / 一本 / 一枚 / 一人...
            "pitch_accent",
            "mora_timing",
        })

    # -- protocol surface --------------------------------------------------

    def analyse(self, text: str) -> dict:
        """Surface segmentation. Honest about being shallow.

        Japanese is written without spaces, so real segmentation needs a
        morphological analyser and a dictionary. This splits off recognisable
        trailing particles and reports the mora count, which is enough for the
        tutor to give useful beginner feedback — and it says so rather than
        implying it parsed the sentence.
        """
        chunks = []
        for token in text.replace("、", " ").replace("。", " ").split():
            stem, particle = self._split_particle(token)
            chunks.append({
                "surface": token,
                "stem_guess": stem,
                "particle": particle,
                "particle_note": PARTICLE_NOTES.get(particle, ""),
                "mora": K.count_mora(K.to_hiragana(token)) if not any(
                    K.is_kanji(c) for c in token) else None,
            })
        return {
            "language": "ja",
            "words": chunks,
            "depth": "surface",
            "note": ("Trailing particles only. Japanese has no spaces, so proper "
                     "segmentation needs a morphological analyser this app does "
                     "not bundle."),
        }

    def drill_forms(self, entry: dict) -> list[dict]:
        word = entry.get("term") or entry.get("japanese") or ""
        pos = entry.get("pos", "")
        if not word:
            return []

        if pos in ("verb", "i-adjective", "na-adjective") or pos == "":
            try:
                table = V.conjugate(word, pos=pos or None,
                                    verb_class=entry.get("verb_class") or None)
            except (ValueError, KeyError):
                return []
            wanted = ("masu", "nai", "te", "ta", "past", "negative",
                      "tai", "potential", "masen", "dictionary")
            return [
                {"form_id": f, "form": table[f].japanese,
                 "label": table[f].label_en, "category": table[f].category}
                for f in wanted if f in table
            ]

        if pos == "noun":
            return [
                {"form_id": "topic", "form": word + "は",
                 "label": "as the topic", "category": "particle"},
                {"form_id": "subject", "form": word + "が",
                 "label": "as the subject", "category": "particle"},
                {"form_id": "object", "form": word + "を",
                 "label": "as the object", "category": "particle"},
                {"form_id": "copula", "form": word + "です",
                 "label": "'is a ...'", "category": "copula"},
            ]
        return []

    # -- Japanese-specific -------------------------------------------------

    def conjugate(self, word: str, pos: Optional[str] = None,
                  verb_class: Optional[str] = None) -> dict:
        return {k: v.to_dict() for k, v in
                V.conjugate(word, pos, verb_class).items()}

    def conjugation_table(self, word: str, pos: Optional[str] = None,
                          verb_class: Optional[str] = None) -> dict:
        return V.conjugation_table(word, pos, verb_class)

    def classify(self, word: str) -> dict:
        return V.classify(word).to_dict()

    def particles(self) -> dict:
        return PARTICLE_NOTES

    def keigo(self) -> dict:
        return V.KEIGO

    def politeness_levels(self) -> dict:
        return V.POLITENESS

    def verb_classes(self) -> dict:
        return V.CLASS_EXPLANATIONS

    def counters(self) -> list[dict]:
        """Japanese counters. A learner needs a handful, not all two hundred."""
        return [
            {"counter": "つ", "for": "general objects, when no specific counter fits",
             "readings": ["ひとつ", "ふたつ", "みっつ", "よっつ", "いつつ"],
             "note": "Native numbers, and only up to ten. The safe default."},
            {"counter": "人", "for": "people",
             "readings": ["ひとり", "ふたり", "さんにん", "よにん", "ごにん"],
             "note": "One and two are irregular: ひとり and ふたり, not いちにん."},
            {"counter": "本", "for": "long thin things — bottles, pens, umbrellas",
             "readings": ["いっぽん", "にほん", "さんぼん", "よんほん", "ごほん"],
             "note": "The reading changes between ほん, ぼん and ぽん. Learn the set."},
            {"counter": "枚", "for": "flat thin things — paper, plates, shirts",
             "readings": ["いちまい", "にまい", "さんまい"], "note": "Regular."},
            {"counter": "冊", "for": "bound things — books, magazines",
             "readings": ["いっさつ", "にさつ", "さんさつ"], "note": ""},
            {"counter": "匹", "for": "small animals",
             "readings": ["いっぴき", "にひき", "さんびき"], "note": "Same ひ/び/ぴ shift as 本."},
            {"counter": "台", "for": "machines and vehicles",
             "readings": ["いちだい", "にだい", "さんだい"], "note": ""},
            {"counter": "歳", "for": "age",
             "readings": ["いっさい", "にさい", "はたち"],
             "note": "Twenty is はたち, completely irregular."},
        ]

    def _split_particle(self, token: str) -> tuple[str, str]:
        for p in sorted(PARTICLES, key=len, reverse=True):
            if token.endswith(p) and len(token) > len(p):
                return token[: -len(p)], p
        return token, ""


ENGINE = JapaneseGrammar()
