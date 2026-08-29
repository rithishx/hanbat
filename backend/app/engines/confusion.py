"""
The shape of a "confusion pair" — shared across languages, filled in by them.

Most mistakes a language learner makes are not random. They are a systematic
choice of the wrong member of a pair the learner has not yet separated:
은/는 versus 이/가 in Korean, は versus が in Japanese, 了 placement in
Mandarin. Detecting *which* pair someone keeps confusing is far more useful
than knowing they got 30% of the particle questions wrong.

The mechanism is shared; the pairs are not. This module owns only the record
type and the index that maps a wrong answer back to a pair. Each language
module supplies its own `CONFUSIONS` dict, and the adaptive engine reaches
them through the registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Confusion:
    """One pair of things a learner reliably mixes up, and how to fix it.

    `simple` and `rule` are both required, and the split matters: the app's
    teaching philosophy is to explain like a patient teacher first and reach
    for terminology second. A confusion entry with only the technical rule
    would produce a mini-course that reads like the grammar reference the
    learner already failed to understand.
    """

    id: str
    #: The two things being confused, as the learner sees them written.
    a: str
    b: str
    title: str
    #: One sentence a learner could memorise and act on.
    one_line: str
    #: The patient-teacher explanation. No terminology.
    simple: str
    #: The precise version, for when the learner is ready for it.
    rule: str
    examples: list[dict] = field(default_factory=list)
    drill_prompt: str = ""
    tags: tuple[str, ...] = ()
    #: Which language this belongs to. Filled in by `index_confusions`.
    language: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def index_confusions(confusions: dict[str, Confusion], language: str) -> dict[frozenset, str]:
    """Build the (expected, given) -> confusion-id lookup for one language.

    Both `a` and `b` may list several surface forms separated by "/", because
    Korean particles come in allomorph pairs (은/는) and a learner may type
    either half. Every combination maps back to the same confusion.
    """
    index: dict[frozenset, str] = {}
    for c in confusions.values():
        c.language = language
        for x in _forms(c.a):
            for y in _forms(c.b):
                if x and y and x != y:
                    index[frozenset((x, y))] = c.id
    return index


def _forms(side: str) -> list[str]:
    """'은/는' -> ['은', '는'];  '하나, 둘, 셋' -> ['하나', '둘', '셋']."""
    parts: list[str] = []
    for chunk in side.split(","):
        for form in chunk.split("/"):
            form = form.strip()
            if form:
                parts.append(form)
    return parts
