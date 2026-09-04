# Hanbat

A local, offline-first platform for learning East Asian languages — Korean,
Japanese and Mandarin Chinese — from zero to advanced.

Everything runs on your own machine. No account, no cloud service, no paid API,
and no internet connection required to study. The database is a SQLite file you
can copy onto a USB stick.

---

## What it actually is

Four things, honestly described:

**A pronunciation engine per language, built from the real rules.** Korean
pronunciation is computed from 표준 발음법 — liaison, tensification,
nasalisation, palatalisation and the rest — so 한국어 is shown as 한구거 with the
rule that produced it. Japanese counts mora, so きって and きて are visibly
different lengths. Mandarin applies tone sandhi, so 你好 is written nǐ hǎo and
said ní hǎo, with the reason attached. None of these are lookup tables of
pre-written answers; they are the rules, applied.

**A curriculum that teaches like a patient teacher and then names things.**
Every explanation exists twice. First: *"Sometimes a Korean syllable has a
little consonant sitting underneath."* Then, when you are ready: *"받침 is a
final consonant in a Korean syllable block."* The app never opens with the
terminology.

**A spaced-repetition system that tracks each language separately.** Being B1
in Korean does not make you B1 in Mandarin, a bad week of tone drills does not
drag down your Korean listening score, and a Korean review session never serves
you a Japanese card.

**A learning engine that works out *why* an answer was wrong.** Not just that
you missed 사람, but whether you did not know the word, knew it and mistyped it,
misheard it, or got the grammar around it wrong. Those are four different
problems and only three of them are worth practising — so careless slips are
counted separately and are deliberately never scheduled. Everything downstream
follows from that diagnosis: which drills you are given, what "Today's session"
contains, and what My Mistakes tells you to do about it.

---

## How the learning engine works

Five pieces, each deterministic and each explainable on screen:

**Diagnosis.** Every answer carries how long you took and what you typed. A
one-character miss on a long word you have had right before, answered in well
under your own median time, is a slip. A blank is not a slip. A wrong option on
a multiple-choice question is never a slip, because there was nothing to mistype.
Seven reasons — vocabulary, grammar, pronunciation, listening, reading, writing,
careless — and the one that does not count as a weakness is named as such.

**Adaptation.** Skill weights blend your score with how confident the app is
that it has measured you at all, so two answers do not outvote thirty. Recent
mistakes lift the skills they belong to. Nothing has to be configured.

**Remediation, at the level of the actual rule.** "Pronunciation is your weakest
skill" is a diagnosis nobody can act on. So every wrong answer is also attributed
to the *specific point* behind it — one pronunciation rule, one grammar point,
one confusion pair — by re-running the language's own phonology on the expected
answer and reading which rules fired. Get 한국어 wrong and the app records 연음,
not "pronunciation". Three failures on the same point and it stops asking the
same question and builds a fix instead: read the rule, hear it, say it, use it in
a sentence — all drilled from that rule's own examples. Where the evidence does
not isolate one rule, nothing is attributed; a guess stored as a fact would send
the learner to fix the wrong thing.

**Review that asks, not just schedules.** The scheduler decides *when* a card
comes back. What it is asked is chosen from your weak skills: weak at listening
and some of your due vocabulary arrives as dictation; weak at production and it
arrives meaning-first. Same cards, same intervals, aimed at the half you are
losing. Cards still being learned are never made harder — you cannot recall what
you met four minutes ago — and most reviews stay ordinary, because forty
production tests in a row is a queue nobody finishes.

**Exercise variety.** Thirty-two generators for Korean, thirty for Japanese and
thirty-one for Mandarin, across recognition, recall, translation in both
directions, sentence completion, grammar transformation, word order, error
correction, listening, writing and speaking. Selection is weighted but floored,
because interleaving beats blocking — a session that is 100% your weakest skill
teaches worse than one that is 40%.

Two of those drills are built from the curriculum's own error catalogue. Every
grammar point ships the wrong sentences learners of that language actually write,
with the reason each is wrong; **spot the error** asks you to pick the right one
and **fix the sentence** removes the choice and makes you produce it. Their
distractors are not plausible-looking — they are real.

**Practise my mistakes.** Your own recorded errors, re-asked in the direction
that proves they are fixed: a vocabulary gap comes back as recall rather than
recognition, a listening mistake as dictation, a pronunciation one to be said out
loud. Careless slips are excluded by default and the screen says so — thirty
words you already know is exactly the busywork this app exists to avoid.

**Sentences, not just flashcards.** Vocabulary and grammar are linked through
real sentences, which is what the translation, completion and word-order drills
are built from. Korean has an authored A1 sentence bank; Japanese and Mandarin
do not yet, so those drills are simply not planned for them rather than being
generated empty.

**Today's session.** One ordered plan inside the minutes you set: reviews first
(capped, so a backlog cannot eat the whole session), then one chronic confusion,
then weak-skill drills, then something new, then production. It does not pad. A
learner with nothing due gets a short session and a sentence explaining why.

Every one of those explains itself in the interface, and none of them claims
more than it knows: before anything has been measured the session says it is
calibrating rather than naming a "weakest skill", and older mistakes recorded
before diagnosis existed are shown as undiagnosed rather than given a guessed
reason after the fact.

---

## Status, honestly

| | Korean | Japanese | Mandarin |
|---|---|---|---|
| Status | in progress | foundation | foundation |
| Writing system | Hangul — complete, 40 units | Hiragana + katakana — complete, 214 units | Pinyin — complete, 62 units |
| | | Kanji — **no content yet** | Hanzi — **no content yet** |
| Pronunciation engine | 표준 발음법, 14 documented rules | mora timing, 6 rules | tone sandhi, 5 rules |
| Pitch accent | — (Korean has none) | contour computed; accents shipped for 4 documented pairs only | — (tones instead) |
| Sentence bank | 13 (A1) | **none yet** | **none yet** |
| Conjugation | full, 11 irregular classes | godan/ichidan + irregulars | **none — Mandarin has no conjugation** |
| Level ladder | CEFR + TOPIK mapping | JLPT N5–N1 | HSK 1–6 |
| Lessons | 19 (Hangul path) | 9 (kana path) | 10 (pinyin and tones path) |
| Vocabulary | 267 | 124 | 153 |
| Grammar points | 20 (A1) | 10 (N5) | 12 (HSK1) |
| Confusion pairs | 10 | 8 | 8 |
| Exercise kinds | 32 | 30 | 31 |
| Teachable points a mistake can be pinned to | 44 | 24 | 25 |
| Authored wrong→right pairs | 57 | 25 | 11 |

Korean is the reference implementation and is deliberately the most complete.
Japanese and Mandarin have finished foundations — a learner can go from zero to
reading the script and holding a first exchange — and their intermediate
curricula are not written yet. The app says so in the interface rather than
showing an empty list.

**Things that are not built yet and are not pretended to be:** the kanji and
hanzi curricula, the A2+/N4+/HSK2+ content, Japanese and Mandarin sentence banks
(so the sentence-based drills are Korean-only for now), pitch accents for
general Japanese vocabulary, and recorded human audio (the app uses your
browser's speech synthesis unless you install a local TTS engine).

Pronunciation scoring is the sharpest example of the rule this project follows.
With no speech-to-text engine installed, recording still works and the app tells
you to compare your voice against the model by ear — which is what a teacher
would have you do — instead of inventing a percentage. Install `faster-whisper`
and select it in Settings, and the same screens start scoring for real, entirely
on your machine.

---

## What needs the network, and what does not

Nothing about normal study needs the network. Three optional features do, all
off by default, all listed in Settings, and all named at the point of use:

| Feature | What leaves your machine | Default |
|---|---|---|
| AI tutor via a **non-local** provider | Your questions and the sentences you write | **off** |
| Downloading an audio pack | Nothing about you — only a request for the file | **off** |
| Downloading a local TTS/STT model | Nothing about you — only a request for the model | **off** |

Ollama, LM Studio and llama.cpp run on your own machine, so talking to them is
a loopback request and is not in that table. The AI tutor is entirely optional:
with no provider configured, every AI endpoint returns `available: false` with
the reason, and no part of the curriculum depends on it.

The server binds to `127.0.0.1` only. Overriding that is possible and logs a
loud warning, because binding to `0.0.0.0` would expose your study history —
and any local model you have running — to everything on your network.

---

## Running it

Requires Python 3.11+ and Node 18+.

One command, which builds the frontend on first run and then serves
everything from a single process:

```bash
./run.sh          # http://127.0.0.1:8756
```

Or, for frontend development with hot reload:

```bash
cd backend && pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8756

cd frontend && npm install && npm run dev    # http://127.0.0.1:5173
```

Run the tests with `cd backend && python3 -m pytest` (963 of them, about six
seconds). There is a browser walkthrough too — 63 assertions against a real
headless Chromium, see `docs/DEVELOPMENT.md`.

### Configuration

Every setting is an environment variable with a local default.

| Variable | Default | What it is |
|---|---|---|
| `HANBAT_HOST` | `127.0.0.1` | Bind address. Changing it logs a warning. |
| `HANBAT_PORT` | `8756` | Port. |
| `HANBAT_DB` | `data/hanbat.sqlite3` | The database file. Copy it to back up. |
| `HANBAT_CONTENT_DIR` | `backend/content` | The JSON curriculum. |
| `HANBAT_DATA_DIR` | `data/` | Audio, recordings, backups. |
| `HANBAT_FRONTEND` | `frontend/dist` | Built frontend, served if present. |

---

## Your data

It is a SQLite file. Copy it, move it, open it in any SQLite browser.
`GET /api/data/export` gives you everything as JSON; there is also a CSV
vocabulary export and an Anki-compatible export. Import restores from any of
these. Nothing is uploaded anywhere, ever, without an explicit setting.

Settings has a backup panel, because there is no copy of this anywhere else:

- **Back up now** snapshots the database into `data/backups/`. Automatic
  backups also happen before every schema migration.
- **Restore** saves your current state first, so restoring is itself undoable,
  and refuses a backup that fails an integrity check rather than writing it over
  good data.
- **Health** reports the schema version, how many rows are yours, and the result
  of SQLite's own integrity check.

Migrations run on startup and are versioned. Content tables — vocabulary,
lessons, sentences — are a rebuildable cache and are recreated from the JSON
curriculum, so only the tables holding your own history are ever migrated.

---

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how the system is put
  together and why it is split the way it is
- [`docs/LANGUAGE_MODULES.md`](docs/LANGUAGE_MODULES.md) — the language module
  contract, and a step-by-step guide to adding a fourth language
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — running, testing, authoring
  content, and the conventions that keep this maintainable

---

## The name

한밭 (Hanbat) is the old Korean name for Daejeon — literally "large field". The
project started as a Korean-only app and kept the name when it grew.
