"""
The tutor: one shared framework, language-specific instructions.

The prompt is assembled from three layers:

    1. A teaching contract that is identical for every language — never hand
       over the answer, ask one question at a time, correct kindly.
    2. What the registry knows about the target language.
    3. What the learner model knows about this learner: level, known
       vocabulary, grammar met, and the mistakes they keep making.

There is deliberately no per-language tutor class. The pedagogy is the same
whether someone is confusing 은/는 or 는 versus は; only the facts differ, and
facts belong in the prompt rather than in a class hierarchy.

The Socratic rule is enforced in the prompt AND checked afterwards: if the
model dumps the answer immediately, `looks_like_a_giveaway` flags it so the UI
can collapse the answer behind a reveal rather than showing it. Prompting alone
does not reliably stop a small local model from being helpful too fast.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ...languages import registry
from .base import ChatResult, Message, Provider

TEACHING_CONTRACT = """\
You are a patient language teacher working one-to-one with a learner. You are \
not a translator, an answer key, or a chatbot.

How you teach:
- Never give the answer first. When the learner makes a mistake, point at the \
part that is wrong and ask a question that helps them find it themselves.
- One thing at a time. If a sentence has three errors, address the one that \
matters most and let the others go for now.
- Only reveal the answer after the learner has tried at least twice, or if \
they explicitly ask you to just tell them.
- Explain simply first. Reach for grammatical terminology only after the \
simple explanation has landed, and introduce the term as a name for something \
they already understand.
- Be specific in praise. "Your particle choice was right there" teaches; \
"Great job!" does not.
- Keep replies short. Two or three sentences is usually right. This is a \
conversation, not a lecture.
- Mistakes are information, not failures. Never make the learner feel stupid.
- If you are not sure something is correct, say so. Do not invent a rule, an \
idiom, or a word. A learner cannot tell the difference between a real \
expression and one you made up, and they will repeat it.
"""

SOCRATIC_RULE = """\
The learner has just produced something with a mistake in it. Do NOT write the \
corrected sentence. Ask one question that points them at the error. Wait for \
their second attempt before saying anything more.
"""

DIRECT_RULE = """\
The learner has asked a direct question about how the language works. Answer \
it clearly and briefly, then give one example, then ask them to try producing \
something similar.
"""


@dataclass
class LearnerContext:
    """What the tutor is told about who it is talking to."""

    language: str
    level: str = ""
    goal: str = ""
    known_vocab: list[str] = field(default_factory=list)
    known_grammar: list[str] = field(default_factory=list)
    recent_mistakes: list[dict] = field(default_factory=list)
    current_lesson: str = ""
    explanation_language: str = "en"
    romanization: bool = False

    def to_prompt(self) -> str:
        spec = registry.try_get(self.language)
        name = spec.name if spec else self.language
        native = spec.native_name if spec else ""

        parts = [f"The learner is studying {name} ({native})."]
        if self.level:
            parts.append(f"Their level is roughly {self.level}. "
                         f"Stay inside vocabulary and grammar they plausibly know.")
        if self.goal:
            parts.append(f"They are learning it because: {self.goal}.")
        if self.current_lesson:
            parts.append(f"They are currently working through: {self.current_lesson}.")

        if self.known_grammar:
            parts.append("Grammar they have met: " + ", ".join(self.known_grammar[:40]) + ".")
        if self.known_vocab:
            sample = ", ".join(self.known_vocab[:60])
            parts.append(f"Some vocabulary they know: {sample}.")
            parts.append("Prefer these words. If you need a new one, gloss it.")

        if self.recent_mistakes:
            lines = []
            for m in self.recent_mistakes[:6]:
                seen = m.get("times_seen", 1)
                lines.append(
                    f"- wrote {m.get('given','')!r} where {m.get('expected','')!r} "
                    f"belonged ({seen}x)")
            parts.append("Mistakes they keep making:\n" + "\n".join(lines))
            parts.append("Watch for these specifically. If one appears again, "
                         "that is the one to address.")

        if self.explanation_language == "target":
            parts.append(f"Explain in {name} where you can, with an English "
                         f"fallback for anything they would not follow.")
        else:
            parts.append(f"Explain in English. Write example sentences in {name}.")

        if not self.romanization:
            parts.append(f"Do not use romanisation. The learner can read the script.")
        else:
            parts.append("The learner is still learning the script. You may add "
                         "romanisation in brackets after new words.")

        # Language-specific teaching notes, supplied by the language module.
        extra = _language_notes(self.language)
        if extra:
            parts.append(extra)

        return "\n\n".join(parts)


def _language_notes(language: str) -> str:
    """Teaching notes the language module wants the tutor to know.

    A language module may define TUTOR_NOTES in its levels module — things
    like Korean's speech-level minefield, or Mandarin's tone requirements —
    without any change to this file.
    """
    import importlib
    spec = registry.try_get(language)
    if spec is None or not spec.levels_module:
        return ""
    try:
        module = importlib.import_module(spec.levels_module)
    except ModuleNotFoundError:
        return ""
    return getattr(module, "TUTOR_NOTES", "")


def build_messages(
    ctx: LearnerContext,
    history: list[dict],
    user_message: str,
    socratic: bool = True,
    mode: str = "auto",
) -> list[Message]:
    """Assemble the full prompt."""
    system = TEACHING_CONTRACT + "\n\n" + ctx.to_prompt()
    if socratic and mode != "explain":
        system += "\n\n" + (SOCRATIC_RULE if mode == "correct" else DIRECT_RULE)

    msgs = [Message("system", system)]
    for h in history[-12:]:
        role = h.get("role", "user")
        if role in ("user", "assistant"):
            msgs.append(Message(role, h.get("content", "")))
    msgs.append(Message("user", user_message))
    return msgs


def ask(
    provider: Provider,
    ctx: LearnerContext,
    history: list[dict],
    user_message: str,
    socratic: bool = True,
    mode: str = "auto",
) -> ChatResult:
    return provider.chat(build_messages(ctx, history, user_message, socratic, mode))


# ==========================================================================
# Guarding the Socratic rule
# ==========================================================================

_GIVEAWAY_PATTERNS = [
    re.compile(r"\b(the )?correct (sentence|form|answer) (is|would be)\b", re.I),
    re.compile(r"\bit should (be|say)\b", re.I),
    re.compile(r"\byou should (have )?(write|written|say|said)\b", re.I),
    re.compile(r"\bthe answer is\b", re.I),
    re.compile(r"^\s*(corrected?|fixed)\s*[:：]", re.I | re.M),
]


def looks_like_a_giveaway(text: str) -> bool:
    """Did the model hand over the answer despite being told not to?

    Small local models are eager to be helpful and routinely ignore the
    instruction. Rather than trust the prompt, the reply is checked and the UI
    collapses a giveaway behind a "show me anyway" control — so the learner
    still gets a chance to think first.
    """
    if not text:
        return False
    return any(p.search(text) for p in _GIVEAWAY_PATTERNS)


def conversation_opener(language: str, level: str, scenario: Optional[dict] = None) -> str:
    """The system instruction for roleplay mode."""
    spec = registry.try_get(language)
    name = spec.name if spec else language
    if scenario:
        return (
            f"{TEACHING_CONTRACT}\n\n"
            f"You are roleplaying a scene in {name}: {scenario.get('title','')}. "
            f"Setting: {scenario.get('setting','')}. "
            f"You play {', '.join(r for r in scenario.get('roles', [])[:1]) or 'the other person'}. "
            f"Stay in character and speak in {name} at a {level} level. "
            f"If the learner is stuck for more than one turn, drop out of character "
            f"briefly to help, then resume. Never switch to English for the whole scene."
        )
    return (
        f"{TEACHING_CONTRACT}\n\n"
        f"Have a simple conversation in {name} at a {level} level. Keep your turns "
        f"to one or two sentences and always end with a question, so the learner "
        f"has something to answer."
    )
