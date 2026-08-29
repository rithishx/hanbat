# Hanbat

A local, offline-first platform for learning East Asian languages — Korean,
Japanese and Mandarin Chinese — from zero to advanced.

Everything runs on your own machine. No account, no cloud service, no paid API,
and no internet connection required to study. The database is a SQLite file you
can copy onto a USB stick.

---

## What it actually is

Three things, honestly described:

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

---

## Status, honestly

| | Korean | Japanese | Mandarin |
|---|---|---|---|
| Status | in progress | foundation | foundation |
| Writing system | Hangul — complete, 40 units | Hiragana + katakana — complete, 214 units | Pinyin — complete, 62 units |
| | | Kanji — **no content yet** | Hanzi — **no content yet** |
| Pronunciation engine | 표준 발음법, 11 rule families | mora timing, pitch notes | tone sandhi (3rd tone, 不, 一) |
| Conjugation | full, 11 irregular classes | godan/ichidan + irregulars | **none — Mandarin has no conjugation** |
| Level ladder | CEFR + TOPIK mapping | JLPT N5–N1 | HSK 1–6 |
| Lessons | 19 (Hangul path) | 9 (kana path) | 10 (pinyin and tones path) |
| Vocabulary | 267 | 124 | 153 |
| Grammar points | 20 (A1) | 10 (N5) | 12 (HSK1) |
| Confusion pairs | 10 | 8 | 8 |
| Exercise generators | 15 + 11 shared | 13 + 11 shared | 13 + 11 shared |

Korean is the reference implementation and is deliberately the most complete.
Japanese and Mandarin have finished foundations — a learner can go from zero to
reading the script and holding a first exchange — and their intermediate
curricula are not written yet. The app says so in the interface rather than
showing an empty list.

**Things that are not built yet and are not pretended to be:** the kanji and
hanzi curricula, the A2+/N4+/HSK2+ content, and recorded human audio (the app
uses your browser's speech synthesis unless you install a local TTS engine).

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

Run the tests with `cd backend && python3 -m pytest` (640 of them, about three
seconds). There is a browser walkthrough too — see `docs/DEVELOPMENT.md`.

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
