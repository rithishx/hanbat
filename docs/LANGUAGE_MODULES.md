# Language modules

Everything a language needs lives in `backend/app/languages/<name>/` plus
`backend/content/<code>/`. Nothing outside those two directories should need to
change when you add one — with the single exception of the registry entry.

## The contract

Six modules, each exposing a module-level `ENGINE` (or, for confusions, a
`CONFUSIONS` dict). All six are declared in the registry as dotted paths and
imported lazily on first use.

| Module | Exposes | Required? |
|---|---|---|
| `writing.py` | `ENGINE`, and `BY_ID` if the language has several scripts | yes |
| `pronunciation.py` | `ENGINE` | yes |
| `transliteration.py` | `ENGINE` | yes |
| `grammar.py` | `ENGINE` | yes |
| `levels.py` | `ENGINE`, `SKILL_NAMES`, `TUTOR_NOTES` | yes |
| `confusions.py` | `CONFUSIONS`, `INDEX` | optional |
| `exercises.py` | nothing; it registers generators as a side effect | optional |

**Confusions are the only optional-and-degrading one.** A missing
`confusions.py` returns `{}` and the adaptive engine falls back to generic
weakness tracking. Every other missing module raises `ModuleNotFoundError`
loudly, because a silently-stubbed pronunciation engine would produce a
language that appears to work and teaches nothing.

The protocols are in `app/languages/protocols.py`. They are `Protocol` classes,
checked structurally — you do not inherit from them, and there is no registration
step. If your class has the methods, it satisfies the protocol.

### `WritingSystemEngine`

```python
class MyWriting:
    language = "xx"
    id = "myscript"
    name = "My Script"
    is_closed_inventory = True          # False for character sets

    def units(self) -> list[dict]: ...  # every teachable atom
    def compose(self, parts) -> str: ...
    def decompose(self, text) -> list[dict]: ...
```

`units()` returns dicts with at least `id`, `unit`, `kind`, `name`,
`teaching_stage`. For an open inventory — kanji, hanzi — return `[]` until
content is authored. The loader warns visibly rather than showing a
permanently-zero progress bar.

`BY_ID` maps script id → engine when a language has several. Japanese has three
and they are learned separately, so **all** of them must be exposed: reading
only the default `ENGINE` once left katakana silently at zero units.

### `PronunciationEngine`

```python
def pronounce(self, text, hints=None) -> dict     # at least {"spoken": str}
def explain(self, text, hints=None) -> dict       # {"spoken", "steps": [...]}
def difficulty_points(self) -> list[dict]
def minimal_pairs(self) -> list[dict]
def rules(self) -> list[dict]                     # the rule index
```

The return shape of `explain()` is language-defined and genuinely differs
between the three. What is *not* optional is that every step carries both a
`child_explanation` and a `linguistic_explanation`, and that they differ. The
app's teaching philosophy is patient-teacher-first; a step with only the
technical version produces exactly the grammar reference the learner already
failed to understand.

`rules()` has a fixed shape, because the pronunciation lab renders all three
languages through it:

```python
{"id", "name", "native_name", "simple", "technical",
 "examples": [{"written", "spoken", "note", "verified": bool}]}
```

What fills it is completely different — Korean returns 14 sound-change rules,
Japanese returns 6 timing rules, Mandarin returns 5 tone rules — and that is the
architecture visible from the outside.

One requirement is absolute: **examples are computed, never authored.** The
example list holds inputs; the engine runs each one through `pronounce()` /
`count_mora()` / `apply_sandhi()` at call time and sets `verified` from whether
the rule actually fired. This is not ceremony. Building it caught four Korean
examples that no longer triggered the rule they were illustrating, and one —
의사 for vowel reduction — that was simply wrong, because word-initial 의 does
not reduce. An authored string would have taught that error indefinitely.

`rules()` is also what makes a language's sound rules *remediable*. The
remediation engine reads the rule index straight out of it — id, title, both
explanations, examples — and builds the "hear it, say it, use it" plan from
those examples. A language that publishes no rule index contributes no
pronunciation focus points and the rest of the app still works; it just cannot
tell that learner which specific rule they keep dropping. That is the single
highest-value thing a new language module can add after the writing system.

Anything genuinely specific to one language goes in an **optional** method the
lab checks for with `hasattr`. Japanese has `pitch_accent()`; Korean and Mandarin
do not, so the API omits the key and the UI renders one section fewer rather
than an empty panel explaining what the language does not have. That method also
shows the line to hold when a phenomenon is half rule and half fact: the pitch
*contour* is derived from an accent number by rule, while the accent numbers
themselves are lexical and are shipped only for the documented minimal pairs.
`accent_for()` returns `None` for everything else, and `None` never becomes `0`.

### `TransliterationEngine`

```python
scheme_name = "Pinyin"
fully_removable = False     # can this be faded to nothing?
remove_by_level = "B1"      # or None

def transliterate(self, text, **options) -> str
def fade(self, text, level: float, **options) -> str
def styles(self) -> list[dict]
```

`fully_removable` is the interesting field. Korean romanisation and Japanese
romaji are scaffolds that must disappear — a learner who still needs them at B1
has been failed by the app. Pinyin is not: it is how Chinese is typed and how
dictionaries are ordered, so it fades from *reading practice* but never
disappears from the application. Say which yours is.

If your transliteration cannot be derived from the script — Mandarin's cannot,
because 行 is xíng or háng depending on the word — return `""` and explain it in
`ambiguity_warnings()`. Do **not** echo the input back into a field the UI will
label as a reading.

### `GrammarEngine`

```python
def capabilities(self) -> frozenset[str]
def analyse(self, text) -> dict                   # shape is yours
def drill_forms(self, entry: dict) -> list[dict]  # shape is FIXED
```

`capabilities()` returns a subset of `KNOWN_CAPABILITIES` in `protocols.py`.
Declaring one you do not implement produces a UI tab that shows nothing useful;
declaring `conjugation` for a language without it produces a conjugation table
that returns the word unchanged. Both are worse than the feature's absence.

`drill_forms` is the one fixed shape, because the SRS and practice screens
consume it for every language:

```python
{"form_id": str, "form": str, "label": str, "category": str}
```

`form` is deliberately not named after any language.

`drill_forms` receives the whole vocabulary row, so reach for whatever column
you need: Korean uses `irregular`, Japanese uses `reading`, Mandarin uses
`counter` and `transliteration`.

### `LevelLadder`

```python
scheme = "HSK"
levels = ("pre-HSK1", "HSK1", ..., "HSK6")   # easiest first, always

def estimate(self, script_mastery, vocab_known, grammar_known, accuracy) -> str
def describe(self, level) -> dict
def next_level(self, level) -> str | None
```

Easiest first even when the scheme runs the other way — JLPT is written
`("pre-N5", "N5", "N4", "N3", "N2", "N1")` so shared code can index into it
without knowing which direction the exam numbering goes.

Gate on reading the script. Korean's ladder returns `pre-A1` for a learner with
5,000 words and 40% Hangul mastery, because vocabulary is worthless if you
cannot read.

`levels.py` also carries two module-level constants:

- `SKILL_NAMES` — the seven skill labels in the target language (읽기 / 読む / 阅读).
- `TUTOR_NOTES` — plain-text instructions appended to the AI tutor's system prompt. This is where you tell a local model that Mandarin has no conjugation, or that Korean speech levels are not optional politeness.

### `confusions.py`

```python
CONFUSIONS: dict[str, Confusion] = {...}
INDEX = index_confusions(CONFUSIONS, "xx")
```

A `Confusion` needs both `simple` (patient-teacher, no terminology) and `rule`
(precise). Examples use the key `target` for the text in the target language.
`a` and `b` may list allomorphs separated by `/` — `"은/는"` — and every
combination maps back to the same confusion.

**Confusion ids must not collide across languages.** A test asserts it. If two
languages have "the same" confusion, they almost certainly do not: 은/는 vs
이/가 and は vs が look parallel and are different problems with different
explanations.

### `exercises.py`

```python
from ...engines.exercises import Exercise, GenContext, register, _sample

@register("tone_pair", "zh", skill="speaking")
def tone_pair(spec: dict, ctx: GenContext) -> list[Exercise]:
    ...
```

`skill` is declared here so the four-skill tracker can classify an exercise
without running it. Registering with `language="*"` makes a generator shared —
do that only when the drill means the same thing in every language.

Read the existing three before writing yours. The distinctively-Korean,
distinctively-Japanese and distinctively-Mandarin generators have nothing in
common, and that is the point: `batchim_predict` exists because Hangul spelling
hides pronunciation, `mora_count` because Japanese rhythm is timed, and
`tone_sandhi_predict` because a Mandarin word is said differently from how it
is written.

---

## Adding a language, step by step

Say you are adding Vietnamese (`vi`).

### 1. Learn the language's actual difficulties first

Not the syllabus — the difficulties. What does a learner get wrong invisibly for
months? For Korean it is 받침 and speech levels; for Japanese, mora length and
は/が; for Mandarin, tones and 了. Whatever the answer is for Vietnamese —
probably the six tones and the vowel inventory — that is what the module has to
be built around. Everything else follows.

Write it down before you write any code. If you cannot name three of these, you
are not ready to write the module.

### 2. Create the package

```bash
mkdir -p backend/app/languages/vietnamese
touch backend/app/languages/vietnamese/__init__.py
mkdir -p backend/content/vi/{lessons,vocab,grammar,writing}
```

### 3. Write the linguistic core first, adapters second

Write the modules that encode what the language *is* — the Vietnamese
equivalents of `hangul.py` + `phonology.py`, or `kana.py` + `romaji.py`, or
`pinyin.py` + `tones.py`. Test them directly, with the real hard cases, before
writing a single adapter.

Then write the six adapter modules on top. They should be thin.

### 4. Register it

The only edit outside your two directories:

```python
VIETNAMESE = register(LanguageSpec(
    code="vi", name="Vietnamese", native_name="Tiếng Việt", flag="🇻🇳",
    iso3="vie",
    writing_systems=(WritingSystemSpec(id="quocngu", name="Quốc ngữ", ...),),
    capabilities=frozenset({"tone_sandhi", "measure_words", ...}),
    writing_module="app.languages.vietnamese.writing",
    pronunciation_module="app.languages.vietnamese.pronunciation",
    transliteration_module="app.languages.vietnamese.transliteration",
    grammar_module="app.languages.vietnamese.grammar",
    levels_module="app.languages.vietnamese.levels",
    confusions_module="app.languages.vietnamese.confusions",
    content_dir="vi",
    status="planned",
    status_note="Declared. Tones and the alphabet are being built.",
    uses_spaces=True,
))
```

Also add `"vi": "vietnamese"` to `_PACKAGE` in `engines/exercises.py` — the one
place that maps a code to a package name.

**Leave `status="planned"` until the work is done.** A planned language returns
409 everywhere with its `status_note`, which is the honest state. A test asserts
that every language declaring itself usable actually has importable engines.

### 5. Author content

Follow the shapes in `content/ko/`, `content/ja/` and `content/zh/`. Vocabulary
is columnar. Lessons are steps with generator specs. Everything in the target
language uses the key `term` or `target`, never a language name.

Consider writing a build script, as `scripts/build_zh_vocab.py` does: 150 rows
of JSON is unreviewable, and a script can validate every syllable against your
own pronunciation engine before writing the file. That script caught a
placeholder left in an example sentence and a wrong syllable count.

### 6. Write the tests

Copy the structure of `tests/test_mandarin.py`. Cover, at minimum:

- the writing system, including the traps (`nu` vs `nü`, `見る` vs `殴る`)
- the pronunciation engine's hardest rule, with the case you got wrong first
- what the language does **not** have, asserted explicitly
- that its level ladder produces a different answer from the others for the same learner
- that its confusion ids do not collide with any other language's

### 7. Promote the status, and expect breakage

When you flip `status` from `"planned"` to `"foundation"`, tests that asserted
your language was a stub will fail. That is the system working. Update them to
assert the new reality, and repoint the "unwritten language" properties at a
constructed spec rather than deleting them — `tests/test_registry.py`'s
`_unwritten_language()` and `tests/test_api.py`'s `planned_language` fixture
show how.

### 8. Run the whole suite

```bash
cd backend && python3 -m pytest
```

`test_language_isolation.py` and `test_registry.py` are the ones that matter.
The guard-rail test will tell you if you leaked a language name into shared
code.

---

## Things that have gone wrong before

Recorded because they will happen again.

**Assuming a rule applies more widely than it does.** Korean 닭고기 is 닭꼬기,
not 달꼬기: the ㄺ→ㄹ simplification before ㄱ applies only to *verb stems*
(표준발음법 §11 붙임). Fixed with an explicit closed list, not a broader rule.

**Getting the direction of a rule wrong.** Mandarin third-tone sandhi applied
right-to-left gives 3-2-3 for 我很好. It is left-to-right, against the
*underlying* tones, and the answer is 2-2-3.

**Being helpful where the data should decide.** An `ALWAYS_NEUTRAL` list
auto-neutralised every syllable "guo" and mispronounced 中国 as Zhōngguo. An
unmarked syllable already parses as neutral, so the content file decides and the
engine does not guess. The list survives as documentation only.

**"Fixing" behaviour that was already correct.** 결혼 is [결혼] in the
prescriptive standard; [겨론] is casual. The engine was right and the test was
wrong. The fix was an opt-in `Hints(casual=True)`, not a change to the rule.

**A cleanup script damaging code.** A string replacement across a Japanese
module stripped an argument from fourteen constructor calls. Prefer targeted
edits; if you must script one, read the diff before committing.

**Conflating two conditions that look alike.** Korean compound boundaries affect
liaison, and ㄴ-insertion is lexically conditioned. They are not the same signal
and needed two separate hint fields.


## What a language contributes to remediation

Nothing extra needs writing. The catalogue in `engines/remediation.py` is
assembled from three things a module already has, and each is optional:

| Source | Becomes | Needs |
|---|---|---|
| `pronunciation.rules()` | `pron:<rule_id>` focus points, skill `pronunciation` | a rule index with verified examples |
| the grammar JSON | `grammar:<point_id>` focus points, skill `grammar` | `simple`, `technical`, `examples`, and ideally `mistakes` |
| `confusions.py` | `confusion:<id>` focus points | the pairs the module already declares |

Two details are worth knowing when authoring for it.

**`mistakes` on a grammar point are drill material, not just prose.** The
wrong/right/why triples feed `spot_the_error` and `fix_the_sentence`, which
means the distractors in those drills are errors real learners of that language
make rather than plausible-looking strings a generator assembled. A point with
no `mistakes` still teaches; it just cannot be remediated that way, and the
drill says so rather than returning nothing.

**Confusion `tags` decide which kind of fix a pair gets.** A pair tagged with a
sound tag — `pronunciation`, `sounds`, `tones`, `vowels`, `listening` — is fixed
by hearing and saying it; anything else is fixed by telling the two apart and
then producing one. Shared code never inspects the pair itself, only whether any
of its tags is in that set, which is the same trick the diagnosis engine uses.
