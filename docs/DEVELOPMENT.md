# Development

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest                                   # should be all green
python3 -m uvicorn app.main:app --reload --port 8756
```

```bash
cd frontend
npm install
npm run dev                                         # http://127.0.0.1:5173
```

The dev server proxies `/api` to port 8756. In production the backend serves
`frontend/dist` directly, so there is one process and one origin.

Interactive API docs are at http://127.0.0.1:8756/docs while the server runs.

## Layout

```
backend/
  app/
    main.py              app factory, lifespan, static mounts
    config.py            everything env-configurable; local defaults
    db.py                schema (v4), connection, 23 tables
    migrations.py        versioned, backed up, row-count guarded
    store.py             every SQL statement lives here
    api/                 9 routers, 76 endpoints
    content/loader.py    JSON -> SQLite, convention-driven
    engines/             SRS, adaptive model, diagnosis, remediation,
                         session planner, exercises, confusion, AI
    languages/
      protocols.py       the contract — read this first
      registry.py        the only file that names languages
      korean/ japanese/ mandarin/
  app.backup-preR1/      pre-refactor snapshot, kept deliberately
  content/
    ko/ ja/ zh/          the curriculum, as JSON
  scripts/               content build and validation scripts
  tests/
frontend/                React + TypeScript + Tailwind (Vite)
data/                    SQLite file, audio, recordings — gitignored
docs/
```

`backend/app.backup-preR1/` is the Korean-only code as it stood before the multi-language
refactor. It is not imported by anything and is kept as a reference for
comparing behaviour.

## Testing

```bash
python3 -m pytest                    # 963 tests, ~6 seconds
python3 -m pytest tests/test_mandarin.py -v
python3 -m pytest -k sandhi
```

| File | What it protects |
|---|---|
| `test_hangul.py` | Unicode composition, jamo, syllable blocks |
| `test_phonology.py` | 표준 발음법 — the biggest and most valuable file |
| `test_conjugation.py` | Korean's 11 irregular classes |
| `test_japanese.py` | kana, mora timing, verb classes, romaji round-trips |
| `test_mandarin.py` | pinyin, tone sandhi, and what Mandarin does **not** have |
| `test_srs.py` | scheduling, including the anti-cramming guards |
| `test_registry.py` | the language contract, and the shared-code guard rail |
| `test_language_isolation.py` | **the one that matters** — no progress leaks between languages |
| `test_migrations.py` | backup, upgrade, and the data-loss guard |
| `test_diagnosis.py` | *why* an answer was wrong, and the near-miss rule's boundaries |
| `test_session.py` | the daily plan: order, budget, and refusing to pad |
| `test_sentence_drills.py` | the sentence-based generators, and what they do without a sentence bank |
| `test_pronunciation_lab.py` | the rule index, and that every example still triggers its own rule |
| `test_pitch_accent.py` | the Japanese contour rule, and the boundary of what is shipped |
| `test_pronunciation_edge_cases.py` | rule ordering, declared limits, and junk input in all three engines |
| `test_remediation.py` | attributing a mistake to a rule, and refusing to when it cannot |
| `test_review_and_practice.py` | weakness-aware review modes, and practising your own mistakes |
| `test_data_safety.py` | backup, restore, and that restoring is itself undoable |
| `test_api.py` | the whole flow end to end against a real database |

### The browser smoke test

`pytest` covers the backend. The frontend has a Playwright walkthrough that
starts at first run and asserts the things a unit test cannot: that onboarding
completes, that switching language switches *everything*, that a lesson plays,
and that the honest messages ("No model is running", "An open set") actually
reach the screen.

```bash
npm --prefix frontend install --no-save playwright
frontend/run-smoke.sh
```

It starts a backend on a throwaway database, builds the frontend, runs the
walk, and stops the server. 63 assertions, and any browser console error fails
the run. Screenshots land in `frontend/ui-smoke-shots/`, which is worth a look
after a UI change — several layout problems are obvious in a screenshot and
invisible to an assertion.

If the run dies immediately on a locator that used to pass, check for a stray
server first: `pkill -f "uvicorn [a]pp.main"`. A previous run left holding port
8756 makes the smoke test walk a stale build, and the failure surfaces
somewhere unrelated to whatever you just changed.

### How to write a test here

Two conventions, both load-bearing.

**Name the property, not the function.** `test_third_tone_sandhi_runs_left_to_right`
tells you what breaks. `test_apply_sandhi_2` does not.

**Say why in the docstring, especially after a bug.** Every non-obvious test in
this suite records the wrong answer it was written to prevent:

```python
def test_third_tone_sandhi_runs_left_to_right():
    """我很好 is 2-2-3, not 3-2-3.

    The rule applies against the *underlying* tones, left to right. Running it
    right to left — or against tones already changed by an earlier step — gives
    3-2-3, which is wrong and is the mistake this test was written to catch.
    """
```

Six months later that comment is the difference between a fix and a regression.

### When a test disagrees with the engine

Check the engine is wrong before you change it. Three times in this project the
test was the thing that was wrong:

- 결혼 → [결혼] is the prescriptive standard. The engine was right.
- 멀다 is an adjective, so `modifier_present` is 먼, not 머는. The test was wrong.
- JLPT gives N5 for 1,600 words and 60 grammar points, because N4 needs 65. The expectation was wrong.

Look up the rule. Then fix whichever one is actually wrong.

## Authoring content

Content lives in `backend/content/<code>/<kind>/*.json`, dispatched by directory
name. The recognised kinds are `vocab`, `grammar`, `lessons`, `culture`,
`slang`, `conversations`, plus the writing-system directories.

Reload without restarting:

```bash
curl -X POST http://127.0.0.1:8756/api/content/reload
```

The response is a `LoadReport`: counts per language per kind, warnings, errors,
files read. Warnings are visible on purpose — "no content authored yet (open
inventory)" is how kanji and hanzi announce themselves.

### Vocabulary

Columnar, because 300 rows of repeated key names is unreadable and un-diffable:

```json
{"language": "zh", "format": "columnar",
 "fields": ["id", "term", "pinyin", "meaning", "pos", "topic", "level",
            "freq", "example_native", "example_en", "note", "counter"],
 "words": [["zh-v-0001", "我", "wǒ", "I, me", "pronoun", "people",
            "HSK1", 8, "我是学生。", "I am a student.", "", ""]]}
```

Anything needing more than the shared columns goes in a `detail` object keyed by
id, merged in at load.

Derived fields — pronunciation, transliteration — are **not** authored; they are
computed at load from the language's engines, so a rule fix propagates
everywhere. The exception is where derivation is impossible: Mandarin pinyin is
authored, because it cannot be computed from characters. Authored values always
win over derived ones.

### Lessons

Ten steps, in this order, though not every lesson uses all of them:

`warmup → learn → understand → hear → repeat → practice → recall → apply → review → summary`

`learn` and `understand` carry prose. `practice`, `recall` and `hear` carry
generator specs. `apply` uses real words. `review` enqueues into the SRS.

```json
{"step": "practice", "type": "generated",
 "generator": {"type": "tone_sandhi_predict", "count": 6, "hints": true}}
```

Two rules that are not negotiable:

**Explain simply first, then name it.** Every concept gets the patient-teacher
version before the terminology. The order is the pedagogy.

**Hints off by the `recall` step.** A lesson where every step has `hints: true`
teaches recognition, not recall, and recognition does not survive a conversation.

### Sentences

The sentence bank is what connects vocabulary to grammar, and it is what the
translation, completion and word-order drills are generated from. One file per
level under `content/<code>/sentences/`:

```json
{"language": "ko", "note": "…", "sentences": [
  {"id": "ko-s-0001", "target": "저는 학생이에요.", "english": "I am a student.",
   "level": "A1", "topic": "introductions",
   "vocab": ["ko-v-0010"], "grammar": ["ko-g-001", "ko-g-002"],
   "chunks": ["저는", "학생", "이에요"],
   "blanks": [{"answer": "이에요", "options": ["이에요", "예요", "이예요"],
               "why": "학생 ends in the consonant ㅇ, so it takes 이에요."}],
   "transforms": [{"to": "formal (합니다체)", "answer": "저는 학생입니다.",
                   "why": "이에요 → 입니다. Same meaning, different register."}]}
]}
```

Four things earn their place here:

- **`chunks`** are the word-order drill. They must reassemble into `target` exactly, which is checked at build time.
- **`blanks`** are authored, not chosen at random, and each carries `why` its answer is right. A gap-fill without a reason teaches pattern-matching.
- **`transforms`** are the grammar drill: the same sentence in another form, also with a `why`.
- **`vocab` / `grammar`** are id lists, and they are what let a drill be selected because you are weak at a specific point rather than at "grammar" in general. They are validated against the vocabulary and grammar files.

Pronunciation and transliteration are **derived at load** from the language's
engines, exactly as for vocabulary, so a phonology fix propagates through the
sentence bank without re-authoring anything.

`scripts/build_ko_sentences.py` writes the Korean bank and validates all of it —
every id exists, every blank appears in its own sentence, every chunk list
reassembles, and the phonology engine can pronounce every sentence. Japanese and
Mandarin have no bank yet; the drills that need one are simply not planned for
them, which is checked in `test_sentence_drills.py`.

### Writing a content build script

For anything over about fifty rows, write the data as Python and generate the
JSON — see `scripts/build_zh_vocab.py`. The value is not the formatting; it is
that the script validates against the engines before writing:

- every pinyin syllable parses
- the syllable count matches the character count (allowing for 儿化)
- no Latin letters in a Chinese term or example sentence
- no Cyrillic, Hangul or kana anywhere in a Mandarin file

Those checks are not hypothetical. They caught `他six岁` (an English placeholder
left in an example), `коーヒー` (a Cyrillic к in a Japanese word), a placeholder
row reading `매usa`, and a topic slug in the wrong language.

## Conventions

**Comments say why, not what.** `add_tone_mark` does not need a comment saying
it adds a tone mark. It needs the one explaining that `iu` → `iù` and `ui` →
`uì` because the mark goes on the last vowel, which learners get wrong
constantly.

**Record the reasoning behind a non-obvious decision in the file that
implements it.** `protocols.py` argues for `Protocol` over inheritance.
`transliteration.py` argues why pinyin never fully disappears. `db.py` argues
why the streak is global. Those arguments are the difference between a design
and an accident.

**Never fake a capability.** If it needs an engine that is not installed, say
so in the response. If it is not built, return 409 with a reason. An empty
array reads as a bug.

**Small, targeted edits.** A blanket string replacement across a language module
once stripped an argument from fourteen constructor calls.

## Working on the learning engine

Four modules, in the order data flows through them.

**`engines/diagnosis.py`** turns one answer into a reason. It is pure — no
database, no language imports — so it is cheap to test and hard to break. Adding
a signal means adding it to `diagnose()` and to `Diagnosis.evidence`, and then
writing the test that proves the *old* signals still win where they should.

Two constants there are load-bearing and were both learned from a failing test:

- `NEAR_MISS_MIN_LENGTH = 3`. On a one-character answer, edit distance 1 means *completely different* — and 은 vs 는 is the most consequential distinction in Korean grammar. Excusing it as a typo would have quietly deleted the app's best signal.
- `counts_as_weakness`. A careless slip is recorded, shown, and never fed to the adaptive engine. A learner with thirty slips and two real gaps needs to slow down, not to be drilled on words they already know.

**`engines/adaptive.py`** turns reasons and scores into skill weights. It blends
by confidence, so two answers cannot outvote thirty, and `UNMEASURED_WEIGHT`
keeps unmeasured skills in the running rather than at zero.

**`engines/exercises.py`** turns weights into a list of drill kinds.
`choose_kinds` is weighted but floored at `0.12`, deliberately: a session that
is entirely your weakest skill teaches worse than one that is 40%, because
interleaving beats blocking. New shared generators must declare a skill and
degrade visibly — see `_no_sentences`, which returns an `unsupported` exercise
carrying `data["missing"]` rather than raising or silently producing nothing.

**`engines/remediation.py`** turns repeated failures into a fix. It sits one
level below the adaptive engine: where that answers "which skill is weakest",
this answers "which rule, and what do I do about it". Three parts, and the
boundary between them is the interesting bit.

- The **catalogue** is assembled from what a language publishes — its rule index, its grammar rows, its confusion list. Nothing here knows what a 받침 or a mora or a tone is, and a language that publishes no rule index contributes no sound points rather than breaking.
- **Attribution** re-runs the language's own phonology on the expected answer and reads which rules fired. Rules *chain* — each one's output is the next one's input — so the learner's answer is read as a position on that chain, not as independent checks. Getting that wrong blamed the first rule on every correct answer; `test_remediation.py` has the case.
- The **plan** is four steps built from the point's own examples. Sound points are fixed by hearing and saying; grammar points by spotting and correcting the curriculum's authored errors; a confusion pair by its own drill, because it has no grammar id to hand to the error drills.

Two rules when editing it. Never attribute when the evidence does not isolate
one point — `NOT_ATTRIBUTED` is a valid, common and *useful* answer, because
sending a learner to fix the wrong rule is worse than naming none. And never
plan a drill without checking it can be built: `test_remediation.py` runs every
spec every plan can produce through the real practice endpoint, because a fix
that opens onto an empty step is worse than no fix offered.

**`engines/session.py`** turns all of it into one ordered plan. Two rules when
editing it: never plan a block whose content might not exist (pass in a flag
saying whether it does, as `has_sentences` does), and never write copy that
claims more than the data supports — the plan renders its own ranked focus list
on the same screen, so an overstated block is visibly wrong.

A generator that must behave differently per language does **not** branch on the
language code. It asks the language's own engine — `grammar_transform` calls
`registry.get(lang).grammar.drill_forms()` and gets conjugations for Korean,
particles for Japanese and aspect particles for Mandarin, without knowing which
is which.

## Database work

Schema changes need a migration. `SCHEMA_VERSION` is in `db.py`; migrations are
numbered functions in `migrations.py` registered in the `MIGRATIONS` dict.

A migration must:

1. back up first — including the `-wal` and `-shm` files, or it is not a backup
2. run in a transaction
3. guard every `CREATE INDEX` on `_table_exists`, because a v1 database may be missing tables
4. compare row counts before and after and raise `MigrationDataLoss` if anything vanished

Never recreate the database. A learner's review history is the most valuable
thing the application holds and it exists nowhere else.

## Adding an API endpoint

Routers are in `app/api/`. Use the annotated dependencies in `deps.py`:

```python
from .deps import Lang, UsableLang, Learner

@router.get("/thing")
def get_thing(spec: UsableLang, learner: Learner) -> dict:
    ...
```

`Lang` resolves `?lang=` (or the learner's active language) and 404s on an
unknown code, naming the known ones. `UsableLang` additionally 409s on a
language whose status says it is not ready, returning its `status_note`. Use
`UsableLang` for anything content-facing.

All SQL goes in `store.py`, and every learner-data function takes `language`.

## Adding a language

See [`LANGUAGE_MODULES.md`](LANGUAGE_MODULES.md).
