"""Author the Korean A1 sentence bank.

Sentences rather than word pairs, because a learner who can pair 먹다 with
"to eat" and cannot say "I already ate" has learned a flashcard, not a
language. Each sentence carries the vocabulary and grammar ids it uses, so a
drill can be built around the exact point someone just got wrong.

Written as a script for the same reason the vocabulary is: every sentence is
checked against the real engines before the file is written — the pronunciation
engine must be able to say it, every referenced vocabulary and grammar id must
exist, and every authored blank must actually appear in its own sentence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.languages.korean import phonology as P  # noqa: E402

# target, english, level, topic, vocab ids, grammar ids, chunks,
# blanks [(answer, options, why)], transforms [(to, answer, why)], note
S: list[dict] = [
    {
        "target": "저는 학생이에요.", "english": "I am a student.",
        "level": "A1", "topic": "introductions",
        "vocab": ["ko-v-0010"], "grammar": ["ko-g-001", "ko-g-002"],
        "chunks": ["저는", "학생", "이에요"],
        "blanks": [
            {"answer": "이에요", "options": ["이에요", "예요", "이예요"],
             "why": "학생 ends in the consonant ㅇ, so it takes 이에요. A word "
                    "ending in a vowel would take 예요."},
            {"answer": "저는", "options": ["저는", "저가", "제가"],
             "why": "Introducing yourself sets a topic, which is 은/는. 제가 "
                    "would answer the question 'who?'."},
        ],
        "transforms": [
            {"to": "formal (합니다체)", "answer": "저는 학생입니다.",
             "why": "이에요 → 입니다. Same meaning, used in presentations, "
                    "announcements and to customers."},
            {"to": "a question", "answer": "학생이에요?",
             "why": "Korean asks by raising the intonation. Nothing moves."},
        ],
        "note": "저 is the humble 'I'. 나 is the casual one and would be rude here.",
    },
    {
        "target": "이것은 책이에요.", "english": "This is a book.",
        "level": "A1", "topic": "objects",
        "vocab": ["ko-v-0113"], "grammar": ["ko-g-001"],
        "chunks": ["이것은", "책", "이에요"],
        "blanks": [{"answer": "이에요", "options": ["이에요", "예요"],
                    "why": "책 ends in ㄱ — a consonant — so 이에요."}],
        "transforms": [{"to": "negative", "answer": "이것은 책이 아니에요.",
                        "why": "The negative of 이에요 is 이/가 아니에요, and the "
                               "noun takes 이/가 rather than staying bare."}],
        "note": "이것 is 'this thing'. In speech it usually shortens to 이거.",
    },
    {
        "target": "저는 한국어를 공부해요.", "english": "I study Korean.",
        "level": "A1", "topic": "study",
        "vocab": [], "grammar": ["ko-g-002", "ko-g-004"],
        "chunks": ["저는", "한국어를", "공부해요"],
        "blanks": [{"answer": "를", "options": ["를", "을", "가", "는"],
                    "why": "한국어 ends in a vowel, so the object particle is 를. "
                           "A consonant ending would take 을."}],
        "transforms": [
            {"to": "past", "answer": "저는 한국어를 공부했어요.",
             "why": "해요 → 했어요. 하다 verbs are regular in the past."},
            {"to": "negative", "answer": "저는 한국어를 공부 안 해요.",
             "why": "공부하다 splits: 안 goes between 공부 and 해요, not in front "
                    "of the whole thing."},
        ],
        "note": "",
    },
    {
        "target": "밥을 먹어요.", "english": "I'm eating.",
        "level": "A1", "topic": "food",
        "vocab": ["ko-v-0302"], "grammar": ["ko-g-004"],
        "chunks": ["밥을", "먹어요"],
        "blanks": [{"answer": "을", "options": ["을", "를"],
                    "why": "밥 ends in ㅂ, so 을."}],
        "transforms": [
            {"to": "past", "answer": "밥을 먹었어요.", "why": "먹어요 → 먹었어요."},
            {"to": "want to", "answer": "밥을 먹고 싶어요.",
             "why": "-고 싶다 attaches to the plain stem: 먹 + 고 싶어요."},
            {"to": "formal", "answer": "밥을 먹습니다.",
             "why": "The stem ends in a consonant, so -습니다 rather than -ㅂ니다."},
        ],
        "note": "밥 is literally cooked rice and colloquially 'a meal'.",
    },
    {
        "target": "물 좀 주세요.", "english": "Some water, please.",
        "level": "A1", "topic": "restaurant",
        "vocab": ["ko-v-0082"], "grammar": [],
        "chunks": ["물", "좀", "주세요"],
        "blanks": [{"answer": "주세요", "options": ["주세요", "줘요", "줍니다"],
                    "why": "주세요 is the standard polite request. 줘요 is casual "
                           "and 줍니다 is a statement, not a request."}],
        "transforms": [],
        "note": "좀 softens a request. Leaving it out is not rude, but adding it "
                "is how people actually speak.",
    },
    {
        "target": "학교에 가요.", "english": "I'm going to school.",
        "level": "A1", "topic": "places",
        "vocab": ["ko-v-0110"], "grammar": ["ko-g-005"],
        "chunks": ["학교에", "가요"],
        "blanks": [{"answer": "에", "options": ["에", "에서", "을"],
                    "why": "에 marks where you are going. 에서 would mark where "
                           "something happens — 학교에서 공부해요."}],
        "transforms": [{"to": "past", "answer": "학교에 갔어요.",
                        "why": "가 + 았어요 contracts to 갔어요."}],
        "note": "",
    },
    {
        "target": "학교에서 공부해요.", "english": "I study at school.",
        "level": "A1", "topic": "places",
        "vocab": ["ko-v-0110"], "grammar": ["ko-g-005"],
        "chunks": ["학교에서", "공부해요"],
        "blanks": [{"answer": "에서", "options": ["에서", "에"],
                    "why": "The studying happens at school, so 에서. 에 would "
                           "mean you are going there."}],
        "transforms": [],
        "note": "에 versus 에서 is the single most useful place distinction in "
                "Korean: destination against location of an action.",
    },
    {
        "target": "오늘 날씨가 좋아요.", "english": "The weather is nice today.",
        "level": "A1", "topic": "weather",
        "vocab": ["ko-v-0180"], "grammar": ["ko-g-003"],
        "chunks": ["오늘", "날씨가", "좋아요"],
        "blanks": [{"answer": "가", "options": ["가", "이", "는"],
                    "why": "날씨 ends in a vowel, so the subject particle is 가."}],
        "transforms": [{"to": "past", "answer": "오늘 날씨가 좋았어요.",
                        "why": "좋 + 았어요. The stem vowel ㅗ is bright, so 아."}],
        "note": "",
    },
    {
        "target": "저는 커피를 안 마셔요.", "english": "I don't drink coffee.",
        "level": "A1", "topic": "food",
        "vocab": ["ko-v-0090"], "grammar": ["ko-g-004"],
        "chunks": ["저는", "커피를", "안", "마셔요"],
        "blanks": [{"answer": "안", "options": ["안", "못", "아니"],
                    "why": "안 is 'don't', a choice. 못 would be 'can't' — "
                           "something is stopping you."}],
        "transforms": [{"to": "can't", "answer": "저는 커피를 못 마셔요.",
                        "why": "못 replaces 안 when you are unable rather than "
                               "unwilling."}],
        "note": "",
    },
    {
        "target": "이거 얼마예요?", "english": "How much is this?",
        "level": "A1", "topic": "shopping",
        "vocab": [], "grammar": ["ko-g-001"],
        "chunks": ["이거", "얼마", "예요"],
        "blanks": [{"answer": "예요", "options": ["예요", "이에요"],
                    "why": "얼마 ends in the vowel ㅏ, so 예요."}],
        "transforms": [],
        "note": "The single most useful sentence in any shop or market.",
    },
    {
        "target": "친구를 만나러 가요.", "english": "I'm going to meet a friend.",
        "level": "A2", "topic": "people",
        "vocab": ["ko-v-0008"], "grammar": [],
        "chunks": ["친구를", "만나러", "가요"],
        "blanks": [{"answer": "만나러", "options": ["만나러", "만나서", "만나고"],
                    "why": "-(으)러 means 'in order to', and only works with a "
                           "movement verb after it. -아서 would mean 'and then'."}],
        "transforms": [{"to": "past", "answer": "친구를 만나러 갔어요.",
                        "why": "Only the final verb changes. -러 never conjugates."}],
        "note": "만나다 takes 를, unlike English 'meet with'.",
    },
    {
        "target": "한국 음식을 먹어 봤어요?", "english": "Have you tried Korean food?",
        "level": "A2", "topic": "food",
        "vocab": [], "grammar": [],
        "chunks": ["한국", "음식을", "먹어", "봤어요"],
        "blanks": [{"answer": "봤어요", "options": ["봤어요", "밨어요", "했어요"],
                    "why": "-아/어 보다 is 'try doing'. In the past it becomes "
                           "봤어요, and it is the normal way to ask about "
                           "experience."}],
        "transforms": [],
        "note": "",
    },
    {
        "target": "시간이 없어서 못 갔어요.",
        "english": "I couldn't go because I didn't have time.",
        "level": "A2", "topic": "time",
        "vocab": [], "grammar": [],
        "chunks": ["시간이", "없어서", "못", "갔어요"],
        "blanks": [{"answer": "없어서", "options": ["없어서", "없으니까", "없지만"],
                    "why": "-아/어서 gives a reason and cannot be used with a "
                           "command. -(으)니까 also gives a reason and can."}],
        "transforms": [],
        "note": "Note that only the final verb carries the past tense. 없어서 "
                "stays in its plain form — Korean marks tense once, at the end.",
    },
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems: list[str] = []

    vocab_ids = _ids(root / "content/ko/vocab/core.json", "words", 0)
    grammar_ids = _ids(root / "content/ko/grammar/a1.json", "points", "id")

    out = []
    for i, s in enumerate(S, start=1):
        sid = f"ko-s-{i:04d}"
        target = s["target"]

        # Every authored blank must actually occur in its own sentence, or the
        # drill would render a sentence with nothing blanked out.
        for b in s.get("blanks", []):
            if b["answer"] not in target:
                problems.append(f"{sid}: blank {b['answer']!r} is not in {target!r}")
            if b["answer"] not in b.get("options", []):
                problems.append(f"{sid}: {b['answer']!r} missing from its own options")

        # Chunks must reassemble into the sentence, ignoring spacing.
        joined = "".join(s.get("chunks", [])).replace(" ", "")
        if joined and joined != target.replace(" ", "").rstrip(".?!"):
            problems.append(f"{sid}: chunks {joined!r} do not rebuild {target!r}")

        for ref in s.get("vocab", []):
            if ref not in vocab_ids:
                problems.append(f"{sid}: references unknown vocab {ref}")
        for ref in s.get("grammar", []):
            if ref not in grammar_ids:
                problems.append(f"{sid}: references unknown grammar {ref}")

        for t in s.get("transforms", []):
            if not t.get("answer") or not t.get("why"):
                problems.append(f"{sid}: a transform has no answer or no reason")

        # The pronunciation engine must be able to say it. A sentence it chokes
        # on would render with an empty "how it sounds" line.
        try:
            P.pronounce(target)
        except Exception as e:                          # noqa: BLE001 - reported
            problems.append(f"{sid}: pronunciation failed: {e}")

        out.append({
            "id": sid, "target": target, "english": s["english"],
            "level": s["level"], "topic": s["topic"],
            "vocab": s.get("vocab", []), "grammar": s.get("grammar", []),
            "chunks": s.get("chunks", []), "blanks": s.get("blanks", []),
            "transforms": s.get("transforms", []), "note": s.get("note", ""),
        })

    if problems:
        for p in problems:
            print("PROBLEM:", p)
        return 1

    doc = {
        "language": "ko",
        "note": ("Sentences, not word pairs. Each carries the vocabulary and "
                 "grammar ids it uses, so a drill can be built around the exact "
                 "point a learner just got wrong. Pronunciation is derived at "
                 "load time from the phonology engine, never authored."),
        "sentences": out,
    }
    path = root / "content/ko/sentences/a1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"wrote {len(out)} sentences to {path}")
    return 0


def _ids(path: Path, key: str, index) -> set[str]:
    if not path.exists():
        return set()
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get(key) or doc.get("words") or []
    if isinstance(index, int):
        return {r[index] for r in rows if isinstance(r, list)}
    return {r[index] for r in rows if isinstance(r, dict) and index in r}


if __name__ == "__main__":
    raise SystemExit(main())
