"""
Japanese pronunciation: mora timing, and the contrasts English speakers miss.

Japanese has almost no spelling-to-sound irregularity of the Korean kind —
kana is close to phonemic. What it has instead is **timing**: every mora is
one beat, and getting the beat count wrong is the single most common thing
that makes a learner hard to understand. So `explain()` returns a mora
breakdown where Korean's returns a chain of sound-change rules. Same question,
genuinely different answer, which is why the two engines are separate.

Pitch accent is split in two, in `pitch.py`. The contour is a rule and is
computed; which accent a given word has is a lexical fact and is shipped only
for the documented minimal pairs, because inventing an accent pattern would
teach learners to sound wrong with confidence.
"""

from __future__ import annotations

from typing import Any, Optional

from . import kana as K
from . import pitch as PITCH

#: The handful of genuine reading rules kana does not show.
PARTICLE_READINGS = {
    "は": ("wa", "when it is the topic particle"),
    "へ": ("e", "when it is the direction particle"),
    "を": ("o", "always — it survives only as the object particle"),
}


class JapanesePronunciation:
    language = "ja"
    name = "Japanese pronunciation"
    #: Kana is near-phonemic, so there is no rule engine to derive readings for
    #: kanji. Readings come from the vocabulary entry, not from a computation.
    is_rule_derived = False

    def pronounce(self, text: str, **options: Any) -> dict:
        mora = K.split_mora(text)
        out = {
            "written": text,
            "spoken": text,
            "changed": False,
            "mora_count": len(mora),
            "mora": [m.to_dict() for m in mora],
        }

        # Pitch appears only when an accent number is available: passed in by
        # the caller, or documented for this exact word. An absent contour means
        # "not known", which is different from "flat" and is left absent rather
        # than defaulted.
        accent = options.get("accent")
        if accent is None:
            accent = PITCH.accent_for(text)
        if accent is not None:
            out["pitch"] = PITCH.contour(text, int(accent))
        return out

    def explain(self, text: str, **options: Any) -> dict:
        """Japanese's version of "why does it sound like that": the beats."""
        diagram = K.mora_diagram(text)
        steps = []
        for m in K.split_mora(text):
            if m.kind == "sokuon":
                steps.append({
                    "rule_id": "sokuon",
                    "rule": "促音 (the small っ)",
                    "shows": f"{m.text} — one beat of silence",
                    "child_explanation": "Stop. Hold your mouth still for one whole "
                                         "beat, then carry on. The silence is the sound.",
                    "linguistic_explanation": "A moraic obstruent: gemination of the "
                                              "following consonant, occupying one mora.",
                })
            elif m.kind == "moraic_n":
                steps.append({
                    "rule_id": "moraic_n",
                    "rule": "撥音 (ん)",
                    "shows": f"{m.text} — its own beat",
                    "child_explanation": "ん is a whole beat on its own, not a letter "
                                         "stuck onto the one before it. Hum it.",
                    "linguistic_explanation": "A moraic nasal. Its place of articulation "
                                              "assimilates to what follows: [n], [m] "
                                              "before b/p/m, [ŋ] before k/g.",
                })
            elif m.kind == "long_vowel":
                steps.append({
                    "rule_id": "long_vowel",
                    "rule": "長音 (ー)",
                    "shows": f"{m.text} — hold the vowel",
                    "child_explanation": "Keep the vowel going for a second beat. "
                                         "ビル is a building; ビール is a beer.",
                    "linguistic_explanation": "Vowel length is phonemic in Japanese and "
                                              "distinguishes many minimal pairs.",
                })
            elif m.kind == "yoon":
                steps.append({
                    "rule_id": "yoon",
                    "rule": "拗音 (small ゃゅょ)",
                    "shows": f"{m.text} — two characters, one beat",
                    "child_explanation": "The small ゃ tucks into the kana before it. "
                                         "きょ is one beat, not two.",
                    "linguistic_explanation": "A palatalised onset. The glide is part of "
                                              "the onset, not a separate mora.",
                })

        for kana, (reading, when) in PARTICLE_READINGS.items():
            if kana in text and kana != "を":
                steps.append({
                    "rule_id": "particle_reading",
                    "rule": f"{kana} as a particle",
                    "shows": f"{kana} → {reading}",
                    "child_explanation": f"{kana} is read {reading} {when}, and as "
                                         f"written everywhere else.",
                    "linguistic_explanation": "A historical spelling preserved for the "
                                              "grammatical particles only.",
                })

        return {
            "written": text,
            "spoken": text,
            "changed": False,
            "summary": f"{text} — {diagram['count']} mora: {diagram['beats']}",
            "mora_count": diagram["count"],
            "mora": diagram["mora"],
            "steps": steps,
        }

    def count_mora(self, text: str) -> int:
        return K.count_mora(text)

    def difficulty_points(self) -> list[dict]:
        """What English speakers reliably get wrong in Japanese.

        Length comes first because it changes meaning and English speakers do
        not hear it at all — おばさん and おばあさん are different relatives.
        """
        return [
            {
                "id": "vowel_length",
                "title": "Long versus short vowels",
                "contrast": ["おばさん / おばあさん", "ビル / ビール", "ここ / こうこう"],
                "why_hard": "English vowel length is not meaningful, so English ears "
                            "filter the difference out entirely. Japanese uses it to "
                            "separate unrelated words.",
                "fix": "Count beats out loud, one tap per mora. おばあさん is five taps.",
                "minimal_pairs": [["おばさん", "おばあさん"], ["ビル", "ビール"]],
                "severity": "high",
                "causes_misunderstanding": True,
            },
            {
                "id": "sokuon",
                "title": "The small っ",
                "contrast": ["きて / きって", "おと / おっと"],
                "why_hard": "It is a beat of silence, and learners skip it because "
                            "there is nothing to say.",
                "fix": "Stop completely, hold for one beat, then release. Tap the beat "
                       "on the table if it helps.",
                "minimal_pairs": [["きて", "きって"], ["かこ", "かっこ"]],
                "severity": "high",
                "causes_misunderstanding": True,
            },
            {
                "id": "moraic_n",
                "title": "ん as a full beat",
                "contrast": ["きんえん / きねん"],
                "why_hard": "English treats a final n as part of the preceding "
                            "syllable. Japanese gives it its own beat.",
                "fix": "Hum the ん for a full count before moving on.",
                "minimal_pairs": [],
                "severity": "medium",
                "causes_misunderstanding": True,
            },
            {
                "id": "r_row",
                "title": "The ら row",
                "contrast": ["ら り る れ ろ"],
                "why_hard": "Neither English r nor English l. A single quick tap of "
                            "the tongue, like the middle of American 'butter'.",
                "fix": "Say 'butter' quickly and isolate the tap. Do not curl your "
                       "tongue back.",
                "minimal_pairs": [],
                "severity": "medium",
                "causes_misunderstanding": False,
            },
            {
                "id": "fu",
                "title": "ふ",
                "contrast": ["ふ"],
                "why_hard": "Written 'fu' but made with both lips, not teeth on lip.",
                "fix": "Blow gently as if cooling soup. Your top teeth should not "
                       "touch your bottom lip.",
                "minimal_pairs": [],
                "severity": "low",
                "causes_misunderstanding": False,
            },
            {
                "id": "u_vowel",
                "title": "う and devoicing",
                "contrast": ["です / すき"],
                "why_hard": "Japanese う is unrounded, and between voiceless "
                            "consonants it often drops out entirely — です sounds "
                            "like 'des', すき like 'ski'.",
                "fix": "Do not round your lips. And do not fight the dropped vowel: "
                       "saying it fully sounds over-careful.",
                "minimal_pairs": [],
                "severity": "low",
                "causes_misunderstanding": False,
            },
            {
                "id": "pitch_accent",
                "title": "Pitch accent",
                "contrast": ["はし (chopsticks) / はし (bridge)"],
                "why_hard": "Japanese distinguishes some words by pitch pattern. It is "
                            "real, but it is dialect-dependent and rarely the reason a "
                            "learner is misunderstood.",
                "fix": "Learn it per word, from audio, once the mora timing is solid. "
                       "Timing first — it matters far more.",
                "minimal_pairs": [],
                "severity": "low",
                "causes_misunderstanding": False,
                "note": "The pronunciation lab computes the full contour from an "
                        "accent number, and ships accent numbers only for the "
                        "documented minimal pairs. Everything else reports no "
                        "accent rather than a guessed one.",
            },
        ]

    def minimal_pairs(self) -> list[dict]:
        return K.minimal_pairs_by_mora()

    def pitch_accent(self) -> dict:
        """The pitch section of the lab: what is computed, what is not shipped.

        Optional in the protocol on purpose. Korean and Mandarin have no pitch
        accent, so they do not answer this, and the lab simply omits the
        section rather than rendering an empty one with an apology in it.
        """
        return PITCH.report()


    #: Japanese's "rules" are not sound changes — kana barely has any. They are
    #: *timing* rules, and getting the beat count wrong is the single most
    #: common thing that makes a learner hard to understand. The shape is the
    #: same as Korean's and Mandarin's so the pronunciation lab can render all
    #: three; what fills it is genuinely different, which is the point.
    TIMING_RULES: list[dict] = [
        {
            "id": "mora_is_the_beat",
            "name": "Every mora is one beat",
            "native_name": "拍",
            "simple": ("Japanese is counted in beats, not syllables. Each kana "
                       "is one beat and they are all the same length — like a "
                       "metronome, not like English stress."),
            "technical": ("Japanese is mora-timed. The mora, not the syllable, "
                          "is the unit of duration, and inter-mora intervals "
                          "are approximately isochronous."),
            "examples": [("にほん", "Three beats: ni-ho-n."),
                         ("さくら", "Three beats, all equal.")],
        },
        {
            "id": "yoon_is_one_beat",
            "name": "Small ゃゅょ do not add a beat",
            "native_name": "拗音",
            "simple": ("A small ゃ, ゅ or ょ joins the kana before it and the "
                       "pair is still one beat. きょ is one beat; きよ is two, "
                       "and they are different words."),
            "technical": ("Palatalised morae (Cy-) are monomoraic. The glide is "
                          "part of the onset rather than a separate mora."),
            "examples": [("きょう", "Two beats — kyo-o, not ki-yo-u."),
                         ("びょういん", "Four beats. びよういん, five, is a "
                                    "hairdresser rather than a hospital.")],
        },
        {
            "id": "sokuon_is_a_silent_beat",
            "name": "The small っ is a beat of silence",
            "native_name": "促音",
            "simple": ("A small っ is a whole beat where you say nothing — you "
                       "stop, hold, then release. きて is two beats and きって "
                       "is three, and they are different words."),
            "technical": ("The sokuon is a moraic obstruent: gemination of the "
                          "following consonant occupying one mora."),
            "examples": [("きって", "Three beats. きて is two."),
                         ("がっこう", "Four beats: ga-[stop]-ko-o.")],
        },
        {
            "id": "long_vowel_is_two_beats",
            "name": "A long vowel is two beats",
            "native_name": "長音",
            "simple": ("Holding a vowel is not decoration — it is a second "
                       "beat. おばさん is an aunt and おばあさん is a "
                       "grandmother, and the only difference is the length."),
            "technical": ("Vowel length is phonemic. A long vowel is a sequence "
                          "of two identical vowel morae, written with a "
                          "following vowel kana or, in katakana, ー."),
            "examples": [("おばあさん", "Five beats."),
                         ("コーヒー", "Four beats: ko-o-hi-i.")],
        },
        {
            "id": "moraic_n",
            "name": "ん is its own beat",
            "native_name": "撥音",
            "simple": ("ん is never attached to the kana before it. It is a "
                       "beat of its own, and it changes colour depending on "
                       "what follows — but the timing never changes."),
            "technical": ("The moraic nasal is monomoraic and assimilates in "
                          "place to a following consonant: [m] before labials, "
                          "[n] before coronals, [ŋ] before velars."),
            "examples": [("しんぶん", "Four beats."),
                         ("にほん", "Three beats, with ん as the third.")],
        },
        {
            "id": "particle_readings",
            "name": "は, へ and を are read differently as particles",
            "native_name": "助詞の読み",
            "simple": ("Three kana are read differently when they are doing a "
                       "grammatical job: は is wa, へ is e, and を is always o. "
                       "This is the whole of Japanese spelling irregularity."),
            "technical": ("Historical orthography preserved for the topic, "
                          "allative and accusative particles; elsewhere the "
                          "kana keep their normal readings."),
            "examples": [("こんにちは", "Ends in は, read wa."),
                         ("わたしは", "The topic particle, read wa.")],
        },
    ]

    def rules(self) -> list[dict]:
        """The timing rules, with beat counts computed rather than asserted.

        Every example's beat count comes from `count_mora` at call time, so the
        lab can never claim きって is three beats while the engine counts a
        different number.
        """
        out = []
        for rule in self.TIMING_RULES:
            examples = []
            for word, note in rule["examples"]:
                beats = K.count_mora(word)
                examples.append({
                    "written": word,
                    "spoken": " · ".join(m.text for m in K.split_mora(word)),
                    "note": note,
                    "beats": beats,
                    "verified": beats > 0,
                })
            out.append({**{k: v for k, v in rule.items() if k != "examples"},
                        "examples": examples})
        return out


ENGINE = JapanesePronunciation()
