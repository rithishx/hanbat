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


ENGINE = MandarinPronunciation()
