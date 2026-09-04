"""Mandarin pronunciation: tones, and the sounds English has no equivalent for."""

from __future__ import annotations

from typing import Any

from . import pinyin as P
from . import tones as T


class MandarinPronunciation:
    language = "zh"
    name = "Mandarin pronunciation"
    #: Tone sandhi genuinely is rule-derived, so the engine computes it.
    #: Character readings are not — those come from the vocabulary entry.
    is_rule_derived = True

    def pronounce(self, text: str, **options: Any) -> dict:
        return T.apply_sandhi(text, options.get("hints")).to_dict()

    def explain(self, text: str, **options: Any) -> dict:
        return T.explain(text, options.get("hints"))

    def tone_pairs(self) -> list[dict]:
        return T.tone_pair_drills()

    def minimal_pairs(self) -> list[dict]:
        return T.minimal_pairs()

    def tones(self) -> dict:
        return P.TONE_NAMES

    def difficulty_points(self) -> list[dict]:
        """What English speakers reliably get wrong in Mandarin.

        Tones lead, and by a wide margin. In Korean a pronunciation error
        makes you sound foreign; in Mandarin it makes you say a different
        word. 买 and 卖 are 'buy' and 'sell', one tone apart.
        """
        return [
            {
                "id": "tones",
                "title": "The four tones",
                "contrast": ["mā", "má", "mǎ", "mà"],
                "why_hard": "English uses pitch for emotion and emphasis, not to "
                            "distinguish words. Learners hear tone as attitude and "
                            "filter it out.",
                "fix": "Never learn a word without its tone attached. A word learned "
                       "toneless has to be relearned, and that is twice the work.",
                "minimal_pairs": [["mǎi", "mài"], ["shuǐ", "shuì"], ["wèn", "wěn"]],
                "severity": "high",
                "causes_misunderstanding": True,
            },
            {
                "id": "third_tone_reality",
                "title": "The third tone almost never dips and rises",
                "contrast": ["hǎo alone", "hǎo chī", "nǐ hǎo"],
                "why_hard": "Textbooks teach the full dip-and-rise, which only "
                            "happens on an isolated syllable. In connected speech it "
                            "is either a low flat tone or a rising one.",
                "fix": "Learn it as a LOW tone. The rise is the exception.",
                "minimal_pairs": [],
                "severity": "high",
                "causes_misunderstanding": False,
            },
            {
                "id": "retroflex_vs_palatal",
                "title": "j/q/x versus zh/ch/sh",
                "contrast": ["jī / zhī", "qī / chī", "xī / shī"],
                "why_hard": "English hears both groups as j, ch and sh. Mandarin "
                            "keeps them apart by where the tongue sits.",
                "fix": "For j/q/x the tongue is flat and forward, almost touching the "
                       "bottom teeth. For zh/ch/sh it curls back toward the roof.",
                "minimal_pairs": [["jī", "zhī"], ["qī", "chī"], ["xī", "shī"]],
                "severity": "high",
                "causes_misunderstanding": True,
            },
            {
                "id": "aspiration",
                "title": "b/p, d/t, g/k are about air, not voicing",
                "contrast": ["bā / pā", "dà / tà", "gē / kē"],
                "why_hard": "English separates these by voicing. Mandarin separates "
                            "them by aspiration — b is unvoiced too, just without "
                            "the puff.",
                "fix": "Hold a hand in front of your mouth. p, t and k should move "
                       "it; b, d and g should not.",
                "minimal_pairs": [["bā", "pā"], ["dà", "tà"]],
                "severity": "medium",
                "causes_misunderstanding": True,
            },
            {
                "id": "u_umlaut",
                "title": "ü",
                "contrast": ["nǔ / nǚ", "lù / lǜ"],
                "why_hard": "English has no front rounded vowel, and after j/q/x/y "
                            "pinyin does not even write the umlaut.",
                "fix": "Say 'ee'. Hold your tongue exactly there and round your lips.",
                "minimal_pairs": [["nǔ", "nǚ"], ["lù", "lǜ"]],
                "severity": "medium",
                "causes_misunderstanding": True,
            },
            {
                "id": "syllabic_i",
                "title": "The 'i' in zhi, chi, shi, ri, zi, ci, si",
                "contrast": ["shī / xī"],
                "why_hard": "Pinyin reuses the letter i for a sound that is not 'ee' "
                            "at all — it is a buzz held in the position of the initial.",
                "fix": "Say the initial and just keep going. Do not add a vowel.",
                "minimal_pairs": [],
                "severity": "medium",
                "causes_misunderstanding": False,
            },
            {
                "id": "final_n_ng",
                "title": "-n versus -ng",
                "contrast": ["shān / shāng", "bān / bāng"],
                "why_hard": "English blurs these at the end of a word. Mandarin does not.",
                "fix": "For -n the tongue tip touches behind the teeth. For -ng the "
                       "back of the tongue rises and the tip touches nothing.",
                "minimal_pairs": [["shān", "shāng"], ["bān", "bāng"]],
                "severity": "medium",
                "causes_misunderstanding": True,
            },
            {
                "id": "e_vowel",
                "title": "e",
                "contrast": ["gē", "hē"],
                "why_hard": "Not the e of 'bed'. An unrounded back vowel, closer to "
                            "the 'u' in 'duh'.",
                "fix": "Relax your mouth completely and make a sound from the back "
                       "of your throat.",
                "minimal_pairs": [],
                "severity": "low",
                "causes_misunderstanding": False,
            },
        ]


    #: Which pinyin actually triggers each rule, and why it matters. The spoken
    #: form is computed by `apply_sandhi` when the index is built, never written
    #: here — the same guarantee Korean's rule index gives.
    RULE_EXAMPLES: dict[str, list[tuple[str, str, dict]]] = {
        "third_tone_sandhi": [
            ("nǐ hǎo", "The first word you learn, and it is not said as written.", {}),
            ("wǒ hěn hǎo", "Left to right against the underlying tones: 2-2-3, "
                           "not 3-2-3.", {}),
        ],
        "half_third": [
            ("hǎo chī", "A third tone before any other tone only dips; it never "
                        "rises back up. The textbook rise happens only when the "
                        "syllable stands alone.", {}),
        ],
        "bu_sandhi": [
            ("bù shì", "不 rises to bú before a fourth tone.", {}),
            ("bù hǎo", "And stays bù before everything else.", {}),
        ],
        "yi_sandhi": [
            ("yī gè", "一 falls to yí before a fourth tone.", {}),
            ("yī qǐ", "And rises to yì before the others.", {}),
            ("yī", "Counting, or as an ordinal, it does not change at all.",
             {"yi_is_ordinal": True}),
        ],
        "neutral_tone": [
            ("xièxie", "The second syllable carries no tone at all — that is "
                       "what the missing mark means.", {}),
        ],
    }

    def rules(self) -> list[dict]:
        """Tone-change rules, with every example run through the engine.

        `verified` says whether the example actually triggered the rule it
        illustrates. Two of them deliberately do not — bù hǎo and the ordinal
        一 are there to show where the rule *stops*, which is the half of a
        rule learners are never taught.
        """
        out = []
        for rule_id, info in T.RULES.items():
            examples = []
            for text, note, hints in self.RULE_EXAMPLES.get(rule_id, []):
                res = T.apply_sandhi(text, hints=hints or None)
                fired = any(c.rule == rule_id for c in res.changes)
                examples.append({
                    "written": res.written,
                    "spoken": res.spoken,
                    "note": note,
                    "changed": res.changed,
                    "verified": fired,
                    "shows_the_limit": not fired,
                })
            out.append({
                "id": rule_id,
                "name": info.get("en", rule_id),
                "native_name": info.get("zh", ""),
                "simple": info.get("simple", ""),
                "technical": info.get("technical", ""),
                "examples": examples,
            })
        return out


ENGINE = MandarinPronunciation()
