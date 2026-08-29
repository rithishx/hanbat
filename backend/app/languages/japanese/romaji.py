"""
Romaji (Hepburn), and typing kana from romaji.

Three output styles, because they are genuinely used for different things:

    hepburn  Tōkyō     macrons. What you see on signs and in dictionaries.
    simple   Tokyo     no macrons. Passports, most English-language writing.
    wapuro   toukyou   what you type to get とうきょう on a keyboard.

The wapuro form is not a lesser romanisation — it is the one a learner must
actually be able to produce to write Japanese on a computer, and it encodes
vowel length faithfully where the other two blur it. Hepburn's Tokyo hides
that the word is four beats.
"""

from __future__ import annotations

import re
from typing import Optional

from . import kana as K

MACRON = {"a": "ā", "i": "ī", "u": "ū", "e": "ē", "o": "ō"}

#: ん is written m before a bilabial in traditional Hepburn (Shimbashi), and
#: n in the revised standard (Shinbashi). Both are current; revised is the
#: default here because it round-trips back to kana unambiguously.
BILABIALS = ("b", "p", "m")


def romanize(text: str, style: str = "hepburn", capitalize: bool = False) -> str:
    """Kana to romaji. Kanji and other characters pass through unchanged."""
    mora = K.split_mora(text)
    out: list[str] = []
    i = 0
    while i < len(mora):
        m = mora[i]
        nxt = mora[i + 1] if i + 1 < len(mora) else None

        if m.kind == "sokuon":
            # っ doubles the next consonant. ch is the exception: まっちゃ
            # is matcha, not macCha.
            if nxt and nxt.romaji:
                r = nxt.romaji
                out.append("t" if r.startswith("ch") else r[0])
            i += 1
            continue

        if m.kind == "long_vowel":
            prev = out[-1] if out else ""
            v = prev[-1] if prev and prev[-1] in "aiueo" else ""
            if style == "wapuro":
                out.append(v or "-")
            elif style == "simple":
                pass                        # Tokyo, not Tookyo
            elif v:
                out[-1] = prev[:-1] + MACRON[v]
            i += 1
            continue

        if m.kind == "moraic_n":
            following = nxt.romaji if nxt else ""
            if style != "wapuro" and following[:1] in BILABIALS:
                out.append("n")             # revised Hepburn keeps n
            elif following and (following[0] in "aiueo" or following.startswith("y")):
                out.append("n'" if style != "wapuro" else "nn")
            else:
                out.append("n")
            i += 1
            continue

        if not m.romaji:
            out.append(m.text)
            i += 1
            continue

        r = m.romaji
        # Long vowels written with a following kana: おう, うう, ああ...
        if nxt and nxt.kind == "normal" and r and r[-1] in "aiueo":
            nv = nxt.romaji
            if nv in ("u", "o") and _makes_long_vowel(r[-1], nv):
                if style == "wapuro":
                    out.append(r + nv)
                elif style == "simple":
                    out.append(r)
                else:
                    out.append(r[:-1] + MACRON[r[-1]])
                i += 2
                continue
            if nv == r[-1]:                 # ああ, いい, うう
                if style == "wapuro":
                    out.append(r + nv)
                elif style == "simple":
                    out.append(r if r[-1] != "i" else r + "i")
                else:
                    out.append(r[:-1] + MACRON[r[-1]] if r[-1] != "i" else r + "i")
                i += 2
                continue
        out.append(r)
        i += 1

    s = "".join(out)
    return s[:1].upper() + s[1:] if capitalize and s else s


def _makes_long_vowel(vowel: str, following: str) -> bool:
    """おう and こう are long o; うう is long u. あう and いう are not long."""
    return (vowel == "o" and following == "u") or (vowel == "u" and following == "u")


# --------------------------------------------------------------------------
# Romaji -> kana, for typing practice
# --------------------------------------------------------------------------

def _reverse_table() -> dict[str, str]:
    table: dict[str, str] = {}
    for hira, romaji, _, _ in K.ALL_BASIC:
        table.setdefault(romaji, hira)
    for pair, r in K.YOON_ROMAJI.items():
        table.setdefault(r, pair)
    for base in K.YOON_BASES:
        for small, v in (("ゃ", "a"), ("ゅ", "u"), ("ょ", "o")):
            pair = base + small
            table.setdefault(K._yoon_romaji(pair), pair)
    for combo, r in K.FOREIGN_COMBOS.items():
        table.setdefault(r, combo)
    # Common alternative spellings a learner will type.
    table.update({
        "si": "し", "ti": "ち", "tu": "つ", "hu": "ふ", "zi": "じ",
        "sya": "しゃ", "syu": "しゅ", "syo": "しょ",
        "tya": "ちゃ", "tyu": "ちゅ", "tyo": "ちょ",
        "jya": "じゃ", "jyu": "じゅ", "jyo": "じょ",
        "nn": "ん", "wo": "を", "n": "ん",
    })
    return table


ROMAJI_TO_KANA = _reverse_table()
_MAX_KEY = max(len(k) for k in ROMAJI_TO_KANA)


def to_kana(romaji: str, katakana: bool = False) -> str:
    """Type romaji, get kana — the wapuro input rules.

    Doubled consonants become っ, so "kitte" gives きって. This is exactly
    what a Japanese IME does, which is what makes it useful for practice:
    the learner is rehearsing the skill they will actually use.
    """
    s = romaji.lower()
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        # "tch" is Hepburn's spelling of っ + ち: matcha -> まっちゃ.
        if s[i] == "t" and s[i + 1:i + 3] == "ch":
            out.append(K.SOKUON)
            i += 1
            continue
        # Any other doubled consonant -> sokuon. "n" is excluded because
        # "nn" is how you type ん, not a geminate.
        if (i + 1 < n and s[i] == s[i + 1] and s[i] not in "aiueon"
                and s[i].isalpha()):
            out.append(K.SOKUON)
            i += 1
            continue
        # A single "n" before another "n" resolves to ん and lets the second
        # one start a fresh mora — konnichiha is こんにちは, not こんいちは.
        # Only a trailing "nn" is consumed whole.
        if s[i] == "n" and s[i + 1:i + 2] == "n" and i + 2 < n and s[i + 2] in "aiueoy":
            out.append("ん")
            i += 1
            continue
        matched = False
        for size in range(min(_MAX_KEY, n - i), 0, -1):
            chunk = s[i:i + size]
            if chunk in ROMAJI_TO_KANA:
                # A lone "n" must not swallow a following vowel: "na" is な.
                if chunk == "n" and i + 1 < n and s[i + 1] in "aiueoy":
                    continue
                out.append(ROMAJI_TO_KANA[chunk])
                i += size
                matched = True
                break
        if not matched:
            out.append(s[i])
            i += 1
    result = "".join(out)
    return K.to_katakana(result) if katakana else result


def fade(text: str, level: float, seed: Optional[int] = None, **kw) -> str:
    """Partial romanisation, mora by mora.

    Fading by mora rather than by character keeps きょ intact — showing "kyo"
    for one half of a mora and ょ for the other would teach the wrong unit.
    """
    import random

    level = max(0.0, min(1.0, level))
    if level >= 1.0:
        return romanize(text, **kw)
    if level <= 0.0:
        return text
    rng = random.Random(seed if seed is not None else hash(text) & 0xFFFF)
    return "".join(
        romanize(m.text, **kw) if rng.random() < level else m.text
        for m in K.split_mora(text)
    )


def ambiguity_warnings(text: str) -> list[str]:
    """What romaji cannot tell a learner."""
    out = []
    hira = K.to_hiragana(text)
    if any(m.kind == "long_vowel" for m in K.split_mora(text)) or "う" in hira:
        out.append("Hepburn writes long vowels with a macron (ō) that is usually "
                   "dropped in English text, hiding a whole beat: Tokyo is four "
                   "mora, not three.")
    if "は" in hira or "へ" in hira:
        out.append("は and へ are read wa and e as particles. Romaji spells what "
                   "is said, so it hides which kana was written.")
    if "じ" in hira or "ぢ" in hira or "ず" in hira or "づ" in hira:
        out.append("じ/ぢ and ず/づ are pronounced identically but spelled "
                   "differently. Romaji cannot show you which one to write.")
    return out
