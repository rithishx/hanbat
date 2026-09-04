"""
Japanese pitch accent: the part that is a rule, and the part that is a fact.

Two very different things get called "pitch accent", and conflating them is how
apps end up teaching learners to sound confidently wrong.

The first is a **rule**. Given a word's accent kernel — which mora the pitch
falls after — the entire high/low contour follows mechanically, and Tokyo
Japanese permits only four shapes. Nothing about that is lexical, so this module
computes it rather than storing it.

The second is a **fact**: which kernel a particular word actually has. That is
lexical, dialect-dependent, and not derivable from the spelling — 箸 and 橋 are
both はし and differ only in accent. So this module ships a small, deliberately
bounded set of words where the accent *is* the teaching point (the minimal pairs
every textbook uses), and reports "not known here" for everything else instead of
inventing one.

The notation is the standard accent-kernel number used by Japanese dictionaries:
0 means the pitch never falls, and n means it falls after mora n.
"""

from __future__ import annotations

from typing import Optional

from . import kana as K

#: The four shapes Tokyo Japanese allows. Nothing else is possible, which is
#: why the contour can be computed from one number.
KINDS: dict[str, dict[str, str]] = {
    "heiban": {
        "name": "平板 heiban — flat",
        "simple": "Starts low, goes up, and stays up. It never comes back down, "
                  "not even on the particle after it.",
        "technical": "Unaccented: no accent kernel, so no fall. The initial "
                     "low-high rise is automatic and not contrastive.",
    },
    "atamadaka": {
        "name": "頭高 atamadaka — high at the head",
        "simple": "The first beat is high and everything after it drops.",
        "technical": "Accent kernel on mora 1; the fall occurs between mora 1 "
                     "and mora 2.",
    },
    "nakadaka": {
        "name": "中高 nakadaka — high in the middle",
        "simple": "Starts low, rises, then falls again before the word ends.",
        "technical": "Accent kernel on a non-final, non-initial mora.",
    },
    "odaka": {
        "name": "尾高 odaka — high at the tail",
        "simple": "Stays up to the end of the word, then the particle after it "
                  "drops. You only hear the difference from flat when something "
                  "follows.",
        "technical": "Accent kernel on the final mora; the fall surfaces on the "
                     "following enclitic.",
    },
}


def kind_of(accent: int, mora_count: int) -> str:
    """Which of the four shapes an accent number produces at this length."""
    if accent == 0:
        return "heiban"
    if accent == 1:
        return "atamadaka"
    if accent >= mora_count:
        return "odaka"
    return "nakadaka"


def pattern(mora_count: int, accent: int) -> dict:
    """The high/low contour for a word of this length with this kernel.

    Two rules produce the whole thing:

    1. The pitch falls after mora `accent`, and never rises again.
    2. Mora 1 and mora 2 are always different — a word cannot start on two
       beats at the same pitch.

    Everything else, including the four traditional shape names, is a
    consequence of those two.
    """
    if mora_count < 1:
        raise ValueError("a word has at least one mora")
    if accent < 0 or accent > mora_count:
        raise ValueError(
            f"accent {accent} is impossible in a {mora_count}-mora word; "
            f"the kernel must be 0 (flat) or a mora position")

    highs: list[bool] = []
    for i in range(1, mora_count + 1):
        if accent == 1:
            highs.append(i == 1)
        else:
            highs.append(i != 1 and (accent == 0 or i <= accent))

    # The particle after the word only drops for odaka; for heiban it stays up,
    # which is the single audible difference between the two.
    particle_high = accent == 0

    return {
        "accent": accent,
        "kind": kind_of(accent, mora_count),
        "highs": highs,
        "shape": "".join("H" if h else "L" for h in highs),
        "particle": "high" if particle_high else "low",
        "with_particle": "".join("H" if h else "L" for h in highs)
                         + ("H" if particle_high else "L"),
    }


def contour(text: str, accent: int) -> dict:
    """`pattern`, attached to the actual mora of a word.

    The mora split comes from the kana engine, so a contour can never disagree
    with the beat count the timing rules teach — きょう is two beats here for
    exactly the same reason it is two beats there.
    """
    mora = K.split_mora(text)
    p = pattern(len(mora), accent)
    return {
        "text": text,
        "accent": accent,
        "kind": p["kind"],
        "kind_name": KINDS[p["kind"]]["name"],
        "shape": p["shape"],
        "particle": p["particle"],
        "with_particle": p["with_particle"],
        "mora": [
            {"text": m.text, "romaji": m.romaji, "pitch": "high" if h else "low"}
            for m, h in zip(mora, p["highs"])
        ],
        "drop_after": accent if accent else None,
    }


# ==========================================================================
# The lexical part — small, named, and not pretending to be a dictionary
# ==========================================================================

#: Words whose accent is itself the lesson: homophone sets that differ only in
#: pitch. These are the pairs every Japanese course teaches, which is why they
#: can be stated with confidence. This is not a general accent dictionary and is
#: not treated as one anywhere in the app.
DOCUMENTED: list[dict] = [
    {
        "reading": "はし",
        "senses": [
            {"word": "箸", "meaning": "chopsticks", "accent": 1},
            {"word": "橋", "meaning": "bridge", "accent": 2},
            {"word": "端", "meaning": "edge, end", "accent": 0},
        ],
        "note": "The classic three-way set. 橋 and 端 sound identical alone — "
                "the difference only appears once a particle follows: 橋が drops, "
                "端が does not.",
    },
    {
        "reading": "あめ",
        "senses": [
            {"word": "雨", "meaning": "rain", "accent": 1},
            {"word": "飴", "meaning": "sweet, candy", "accent": 0},
        ],
        "note": "High-then-low for the weather, low-then-high for the sweet.",
    },
    {
        "reading": "かき",
        "senses": [
            {"word": "牡蠣", "meaning": "oyster", "accent": 1},
            {"word": "柿", "meaning": "persimmon", "accent": 0},
        ],
        "note": "Same two shapes as あめ, on a different pair of words.",
    },
    {
        "reading": "かみ",
        "senses": [
            {"word": "神", "meaning": "god", "accent": 1},
            {"word": "紙", "meaning": "paper", "accent": 2},
            {"word": "髪", "meaning": "hair", "accent": 2},
        ],
        "note": "紙 and 髪 share an accent, so pitch does not separate them — "
                "context does. Pitch is not a magic disambiguator.",
    },
]


def accent_for(word: str) -> Optional[int]:
    """The documented accent for a written word, or None.

    None means "this app does not know", never "this word is flat". The
    distinction matters: heiban is a real pattern with a real sound, and
    defaulting unknown words to it would be a guess wearing a fact's clothes.
    """
    for entry in DOCUMENTED:
        for sense in entry["senses"]:
            if sense["word"] == word:
                return sense["accent"]
    return None


def pairs() -> list[dict]:
    """The documented sets, with every contour computed at call time."""
    out = []
    for entry in DOCUMENTED:
        senses = []
        for sense in entry["senses"]:
            c = contour(entry["reading"], sense["accent"])
            senses.append({**sense, "contour": c})
        out.append({**entry, "senses": senses,
                    "mora": K.count_mora(entry["reading"])})
    return out


def report() -> dict:
    """What the app can and cannot tell a learner about pitch."""
    return {
        "supported": True,
        "computed": ("Given an accent number, the full high/low contour is "
                     "derived from two rules and is always consistent with the "
                     "mora count the timing rules teach."),
        "not_stored": ("Accent numbers for general vocabulary are not shipped. "
                       "They are lexical and dialect-dependent, and a guessed "
                       "one teaches a confident error."),
        "kinds": KINDS,
        "documented_sets": len(DOCUMENTED),
        "documented_words": sum(len(e["senses"]) for e in DOCUMENTED),
        "pairs": pairs(),
    }
