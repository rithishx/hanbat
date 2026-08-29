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
    db.py                schema (v2), connection, 19 tables
    migrations.py        versioned, backed up, row-count guarded
    store.py             every SQL statement lives here
    api/                 8 routers, 68 endpoints
    content/loader.py    JSON -> SQLite, convention-driven
    engines/             SRS, adaptive model, exercises, confusion, AI
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
python3 -m pytest                    # 638 tests, ~3 seconds
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
walk, and stops the server. Screenshots land in `frontend/ui-smoke-shots/`,
which is worth a look after a UI change — several layout problems are obvious
in a screenshot and invisible to an assertion.

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
