# Architecture

## The shape of it

```
┌──────────────────────────────────────────────────────────────┐
│  frontend/          React + TypeScript + Tailwind (Vite)      │
│                     Talks to one origin. Knows no language.   │
└───────────────────────────────┬──────────────────────────────┘
                                │  HTTP, 127.0.0.1 only
┌───────────────────────────────┴──────────────────────────────┐
│  backend/app/api/         76 endpoints across 9 routers       │
│                           Every one takes ?lang=              │
├──────────────────────────────────────────────────────────────┤
│  backend/app/engines/     SRS · adaptive · diagnosis          │
│  SHARED CORE              remediation · session · exercises   │
│                           confusion index · AI tutor          │
│                           No language names appear here.      │
├──────────────────────────────────────────────────────────────┤
│  backend/app/languages/   registry.py  ← the only file that   │
│                           protocols.py    names languages     │
│         ┌─────────────────┼─────────────────┐                 │
│      korean/           japanese/         mandarin/            │
│      hangul            kana              pinyin               │
│      phonology         romaji            tones                │
│      conjugation       verbs             (no conjugation)     │
├──────────────────────────────────────────────────────────────┤
│  backend/app/db.py        SQLite. 23 tables carry `language`. │
│  backend/content/<code>/  JSON curriculum, the source of truth│
└──────────────────────────────────────────────────────────────┘
```

## The one decision everything follows from

**Korean, Japanese and Mandarin are not variations of one language.**

That sentence is the reason the language modules are `Protocol`s rather than
subclasses of a shared base. Look at what the three `explain()` methods return:

- Korean returns a chain of sound-change rules — 한국어 → 한구거, via liaison.
- Japanese returns a mora breakdown — きょ is one beat, っ is one silent beat.
- Mandarin returns a tone-change trace — nǐ hǎo is said ní hǎo, and here is why.

There is no useful superclass over those three. A shared `PronunciationEngine`
base class could only have offered `explain()` returning `Any`, which is a
`Protocol` with extra ceremony and a false promise of shared behaviour.

The same argument, more sharply, for grammar. `GrammarEngine` defines exactly
three methods — `capabilities()`, `analyse()`, `drill_forms()` — and
deliberately **does not define `conjugate()`**. Mandarin has no conjugation. A
base class with a `conjugate()` method would have forced Mandarin to implement
one that returns the word unchanged and calls it an answer. Instead, Mandarin
simply does not declare the `conjugation` capability, `/api/conjugate?lang=zh`
returns 409 with an explanation, and the UI never renders the tab.

`app/languages/protocols.py` opens with this argument in full. It is the file
to read first.

## What is shared, and why each thing is

Something belongs in the shared core when the *mechanism* is genuinely the same
across all three languages, even though the *data* is not.

| Shared | Why it survives all three languages |
|---|---|
| `engines/srs.py` | SM-2 scheduling is arithmetic on review history. It never sees a language; isolation is enforced by the queries that feed it, which is the right place for it. |
| `engines/adaptive.py` | "Which skill is weakest, which items keep failing, which pair keeps getting confused" is the same question everywhere. The *answers* come from each language's own `CONFUSIONS`. |
| `engines/diagnosis.py` | *Why* an answer was wrong is a question about the learner's behaviour — how long they took, whether they had this item right before, how far the answer was from correct — not about the language. The one place it needs language knowledge, "was this a sound-based item", it gets from the language's own confusion tags rather than from a list of scripts. |
| `engines/session.py` | The order to teach in — due reviews, then a chronic confusion, then weak skills, then new material, then production — is pedagogy, not linguistics. What fills each block is drawn from the language's own generators, and a block whose content does not exist for a language is not planned at all. |
| `engines/remediation.py` | "Which specific thing keeps failing, and how do I fix it" is the same question everywhere. Every *answer* is read from the language's own engines: the pronunciation rule index, the grammar curriculum, the confusion list. A language that publishes no rule index simply contributes no sound points, and the rest still works. |
| `engines/confusion.py` | The record type and the `(expected, given) → id` index. Not one pair is shared: Korean has 은/는 vs 이/가, Japanese has は vs が, Mandarin has 不 vs 没, and Mandarin has no particles of that kind at all. |
| `engines/exercises.py` | The generator registry, plus eleven drills that mean the same thing everywhere — "type what you hear", "how do you say X". Language-specific drills register themselves under their own code. |
| `engines/ai/` | The provider abstraction and the teaching contract. Language-specific instructions come from each `levels.py`'s `TUTOR_NOTES`. |
| `content/loader.py` | Walks `content/<code>/` by convention. A new language becomes loadable by creating a directory. |
| `db.py`, `store.py` | One schema, with `language` on every learner-data and content table. |

And what is *not* shared, with the reason:

| Not shared | Why not |
|---|---|
| Level ladders | CEFR, JLPT and HSK are different scales that run in different directions with different thresholds. The same learner — 1,600 words, 60 grammar points — is **B1, N5 and HSK3**. There is no conversion, so there is no shared ladder. |
| Writing-system engines | Korean composes syllable blocks algorithmically. Japanese has two closed syllabaries plus an open one. Mandarin has a closed sound system and an open character set. |
| Conjugation | Korean and Japanese have it and model it differently; Mandarin has none. |
| Exercise content | `batchim_predict` is meaningless outside Korean. `mora_count` is meaningless outside Japanese. `tone_sandhi_predict` is meaningless outside Mandarin. |
| Skill labels | 읽기 / 読む / 阅读. A language with none falls back to English — never to another language's. |

## The guard rail

Over-abstraction is not the only failure mode; the opposite one is worse and
happens gradually. Nobody hard-codes `"Korean"` into the SRS engine on purpose.
They add one small special case, and then another.

`tests/test_registry.py` greps the shared modules for language-specific string
literals in **executable lines only** — docstrings and comments are exempt,
because that is how the code explains itself:

```python
SHARED_MODULES = ["app/engines/srs.py", "app/engines/adaptive.py",
                  "app/engines/confusion.py", "app/engines/diagnosis.py",
                  "app/engines/session.py", "app/engines/remediation.py",
                  "app/db.py", "app/migrations.py",
                  "app/languages/protocols.py"]

FORBIDDEN = re.compile(r'"(Korean|Japanese|Mandarin|Hangul|hangul_mastery)"')
```

`registry.py` is deliberately absent from that list: naming the languages is its
entire job, and it is the one file allowed to.

The same pressure shows up in field names. An earlier version had `drill_forms`
returning `{"korean": ...}` from Korean, `{"japanese": ...}` from Japanese and
`{"chinese": ...}` from Mandarin — which meant every shared consumer had to know
all three names. The protocol now fixes that shape as
`{"form_id", "form", "label", "category"}` and says why.

## Progress isolation

The property the whole refactor exists to protect, enforced in three places:

1. **In the database.** `srs_card` is `UNIQUE(learner_id, language, item_type, item_id)`, so `v-0001` in Korean and `v-0001` in Japanese are two independent cards. `lesson_progress` is keyed on `(learner_id, language, lesson_id)`. Level, XP and script mastery live in `learner_language`, one row per language.

2. **In the adaptive engine.** `build_model(attempts, language=...)` filters the history before computing anything. A perfect Korean record cannot lift a poor Mandarin score.

3. **In the queries.** The SRS scheduler never receives a language at all. It grades whatever cards it is given, and the queries that build those card sets are language-scoped. That is deliberate: scheduling logic and access control are different concerns, and mixing them is how leaks get introduced.

One thing is shared on purpose. **The daily streak is global**, with a comment
in the schema saying so: level and XP measure progress *in a language*, but the
streak measures whether you sat down to study at all, and splitting it would
punish a learner for spending Tuesday on Japanese.

## Content is data, and exercises are specs

The JSON files under `backend/content/` are the source of truth. The database is
a queryable index of them, rebuilt on load, never edited by hand. Adding a
thousand lessons is a matter of dropping in files.

Lessons store *generator specs*, not questions:

```json
{"step": "practice", "type": "generated",
 "generator": {"type": "tone_sandhi_predict", "count": 6, "hints": true}}
```

expanded into concrete exercises at request time. That indirection buys three
things: a drill draws fresh items every session, so a learner cannot memorise
that question four is always ㅗ; the content files stay small — nineteen Korean
lessons produce 88 specs rather than 800 hand-written questions; and a generator
improvement reaches every lesson at once.

A spec whose type nobody has registered returns a visible `unsupported` marker
rather than an empty list, so a half-built language module surfaces as a gap
instead of a lesson that silently renders nothing.

**Derived fields are computed at load time, never stored.** Korean pronunciation
and romanisation come from the phonology engine on every reload, so a correction
to a sound-change rule propagates to every example sentence instead of leaving
300 hand-written strings quietly wrong.

The exception proves the rule. Mandarin pinyin **cannot** be derived from
characters — 行 is xíng in 不行 and háng in 银行 — so the vocabulary file authors
it, and `MandarinTransliteration.transliterate()` returns `""` for hanzi input
rather than echoing the characters back into a field the UI will label "pinyin".

## Lexical ambiguity, handled the same way three times

Some things cannot be derived from spelling, in any of the three languages:

- Korean 걷다 is "to walk" (ㄷ-irregular) or "to roll up" (regular).
- Japanese 見る is ichidan and 殴る is godan; the kanji hides which.
- Mandarin 书 takes 本 and 水 takes 杯, and no rule predicts it.

Every one is handled identically: an explicit closed list, plus a `confident`
flag or an authored field, and **never a silent guess**. `verbs.classify()`
reports `confident=False` for an unlisted kanji-る verb rather than conjugating
it wrong. `drill_forms` falls back to 个 — the measure word a native speaker
reaches for when unsure — rather than inventing a specific one.

## Honesty as an architectural constraint

The brief said: no fake functionality. That turns into concrete decisions.

- Pronunciation **scoring** requires a speech-to-text engine. Without one, the exercise still works as listen-and-repeat and reports `{"scoring": "requires_stt_engine"}`. It does not invent a score.
- The AI tutor returns `available: false` with the reason when no provider is reachable. It never returns canned text dressed up as a model response.
- A language that is not ready returns **409 with its `status_note`**, not an empty array. An empty list reads as a bug; a 409 with a reason reads as a roadmap.
- `hanzi` and `kanji` report zero units and log "no content authored yet (open inventory)" rather than showing a permanently-zero progress bar.
- The tutor has a regex guard, `looks_like_a_giveaway()`, because prompting alone does not reliably stop a small local model from being helpful too fast.
- Mistakes recorded before diagnosis existed are shown as **undiagnosed**, and migration 3 deliberately does not back-fill them. The signals a diagnosis needs — response time, prior history — were not recorded at the time, so any reason assigned now would be a guess presented as a fact.
- Sentence-based drills return a visible `unsupported` exercise carrying `data["missing"] = "sentences"` for a language with no sentence bank, and the session planner excludes those kinds entirely, so the learner never meets an empty drill.
- Japanese **pitch accent** is split along the same line: the contour is computed from the accent number by rule, and accent numbers are shipped only for the documented minimal pairs. `accent_for()` returns `None` for everything else, and `None` never becomes `0` — heiban is a real pattern with a real sound, so defaulting to it would be a guess wearing a fact's clothes.
- Every worked example in the pronunciation lab is computed by the engine at request time and carries a `verified` flag. An example that stops illustrating its own rule is **marked**, not hidden. Two Mandarin examples carry `shows_the_limit` because they deliberately demonstrate where a rule stops applying.
- A mistake is attributed to a specific rule only when the evidence isolates one. Two sound rules fired and the answer does not say which broke? Then `NOT_ATTRIBUTED`, and the mistakes screen reports how many could not be pinned down. Sending a learner to fix the wrong rule is worse than not naming one.
- Remediation is offered only past a stated threshold, and the screen says how far off a near-miss is rather than silently withholding.
- The session planner claims "your weakest skill" only when the block actually landed on it. Drills are drawn with weights and a floor, so sometimes it does not — and the ranked focus list is on the same screen, which would make an overstated claim visibly false.

## Database and migrations

Plain `sqlite3` — no ORM. WAL mode, `busy_timeout = 5000`,
`synchronous = NORMAL`. `SCHEMA_VERSION = 3`.

The multi-language migration (`migrations.py`, `migrate_002_multilanguage`) was
written under an explicit instruction not to recreate the database. It backs up
first — copying the `-wal` and `-shm` files too, or the backup is not a backup —
runs inside a transaction, and compares row counts before and after, raising
`MigrationDataLoss` if anything went missing.

`migrate_003_mistake_reasons` adds the diagnosis columns and nothing else. It is
additive and cannot lose data, which is the shape every migration should have
where it can.

`migrate_004_mistake_focus` adds the attribution columns and **does** back-fill,
which looks inconsistent next to migration 3 until you see why. A *reason* could
not be back-filled: deciding whether an answer was a careless slip needs the
response time and the item's prior history, and neither was recorded on old rows,
so any value would have been invented. A *focus* is different — attribution runs
on `expected`, `given`, `skill` and `item_id`, every one of which is already
stored, and it is the identical function that will run on the next answer. Re-
deriving it is not a guess. Rows it cannot isolate stay empty, exactly as a new
one would. The back-fill is also isolated in its own function, so a language
module that no longer imports cannot take the schema change down with it.

**Content tables need no migration; learner tables do.** Vocabulary, lessons and
sentences are a rebuildable index over `content/`, so `init_db` applies the
schema unconditionally and the loader repopulates them. Only tables holding the
learner's own history are ever migrated. That rule was learned the hard way: an
earlier `init_db` applied the schema only when the version changed, which meant
a newly added content table never appeared on an existing database.

Two bugs worth recording:

- The first migration assumed every v1 table existed and aborted partway through on databases that lacked one — which is to say, on exactly the databases most in need of migrating. Every index creation is now guarded on `_table_exists`.
- Backup filenames were timestamped to the second, so two backups in the same second collided. That turned restore into a silent no-op: the safety backup taken before restoring overwrote the very file being restored. `backup()` now uniquifies with a `-2`, `-3` counter, and a test restores five wrong answers back to zero and then undoes that too.

## Performance

The target is an 8 GB laptop.

Engines load lazily. `import registry` does not import Korean phonology, and a
learner who only studies Japanese never pays for Mandarin's tone tables. The
registry resolves dotted module paths through `functools.cached_property`, so
each engine is imported at most once, on first use.

Content is cached in SQLite with FTS5 for search. Exercises are generated on
demand rather than materialised. Audio is streamed from disk.
