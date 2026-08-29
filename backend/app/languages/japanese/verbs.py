"""
Japanese verb and adjective conjugation.

Nothing here is shared with Korean, and the two should not be made to look
alike. Korean conjugation is driven by vowel harmony and eleven irregular stem
classes. Japanese conjugation is driven by which of five vowel *rows* the stem
shifts into, and has essentially two regular classes plus two irregular verbs.
The engines are different shapes because the languages are.

The one hard part is 音便 — the sound changes in the て/た forms, where
書く becomes 書いて but 行く becomes 行って. Those are handled by table, and
行く is listed as the exception it is.

Classifying a verb ending in る is genuinely ambiguous from spelling alone
(帰る is godan, 食べる is ichidan), so the engine uses a closed exception list
and reports its confidence, exactly as the Korean engine does for 걷다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal, Optional

from . import kana as K

VerbClass = Literal["godan", "ichidan", "suru", "kuru", "aru", ""]
PartOfSpeech = Literal["i-adjective", "na-adjective", "noun", "unknown"]

# --------------------------------------------------------------------------
# The five-row shift that drives everything
# --------------------------------------------------------------------------

#: dictionary-final kana -> (a, i, u, e, o) forms of that row.
#: う is the odd one: its a-form is わ, not あ — 買う becomes 買わない.
ROWS: dict[str, tuple[str, str, str, str, str]] = {
    "う": ("わ", "い", "う", "え", "お"),
    "く": ("か", "き", "く", "け", "こ"),
    "ぐ": ("が", "ぎ", "ぐ", "げ", "ご"),
    "す": ("さ", "し", "す", "せ", "そ"),
    "つ": ("た", "ち", "つ", "て", "と"),
    "ぬ": ("な", "に", "ぬ", "ね", "の"),
    "ぶ": ("ば", "び", "ぶ", "べ", "ぼ"),
    "む": ("ま", "み", "む", "め", "も"),
    "る": ("ら", "り", "る", "れ", "ろ"),
}

A, I, U, E, O = 0, 1, 2, 3, 4

#: 音便 — the て-form sound changes, by dictionary-final kana.
TE_ENDINGS: dict[str, str] = {
    "う": "って", "つ": "って", "る": "って",
    "ぬ": "んで", "ぶ": "んで", "む": "んで",
    "く": "いて", "ぐ": "いで",
    "す": "して",
}
TA_ENDINGS: dict[str, str] = {k: v.replace("て", "た").replace("で", "だ")
                              for k, v in TE_ENDINGS.items()}

#: Verbs ending in る that are godan despite looking ichidan. A closed class:
#: listing it is exact, guessing would be wrong several times a page.
GODAN_RU_EXCEPTIONS: frozenset[str] = frozenset({
    "帰る", "かえる", "入る", "はいる", "走る", "はしる", "知る", "しる",
    "切る", "きる", "要る", "いる", "減る", "へる", "滑る", "すべる",
    "喋る", "しゃべる", "蹴る", "ける", "握る", "にぎる", "参る", "まいる",
    "混じる", "まじる", "限る", "かぎる", "散る", "ちる", "練る", "ねる",
    "照る", "てる", "焦る", "あせる", "遮る", "さえぎる", "湿る", "しめる",
})

#: Common ichidan verbs whose stem vowel is hidden inside a kanji. 見る is
#: ichidan but its spelling shows only 見, so no rule can recover that — the
#: same lexical ambiguity Korean has with 걷다. Listing the common ones is
#: exact where guessing would be wrong on the most frequent verbs in the
#: language.
ICHIDAN_KANJI: frozenset[str] = frozenset({
    "見る", "着る", "似る", "煮る", "居る", "射る", "鋳る", "率いる", "用いる",
    "食べる", "寝る", "出る", "得る", "経る", "起きる", "生きる", "落ちる", "過ぎる", "信じる", "感じる", "閉じる",
    "借りる", "足りる", "降りる", "浴びる", "延びる", "伸びる",
    "開ける", "閉める", "教える", "覚える", "忘れる", "考える", "答える",
    "始める", "続ける", "集める", "決める", "入れる", "受ける", "分ける",
    "助ける", "育てる", "建てる", "捨てる", "調べる", "比べる", "並べる",
    "見せる", "見つける", "気をつける", "見える", "聞こえる", "疲れる", "遅れる", "生まれる", "現れる", "別れる", "慣れる", "壊れる",
    "変える", "数える", "迎える", "植える", "与える", "支える", "抱える",
    "できる", "出来る", })

#: The i-row and e-row kana. A る-verb is ichidan when the kana before る is
#: one of these — みる, たべる — and godan otherwise: とる, つくる.
I_ROW = frozenset("いきしちにひみりぎじぢびぴ")
E_ROW = frozenset("えけせてねへめれげぜでべぺ")

IRREGULAR: dict[str, VerbClass] = {
    "する": "suru", "くる": "kuru", "来る": "kuru", "ある": "aru",
}

#: -する compounds: 勉強する, 電話する. Thousands of them, all regular once
#: you know that する is irregular.
SURU_SUFFIX = "する"

I_ADJ_IRREGULAR = {"いい": "よ", "良い": "良", "かっこいい": "かっこよ"}


@dataclass
class Classification:
    dictionary_form: str
    stem: str
    pos: PartOfSpeech
    verb_class: VerbClass
    confident: bool
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def classify(word: str, pos: Optional[PartOfSpeech] = None,
             verb_class: Optional[VerbClass] = None) -> Classification:
    w = word.strip()
    if not w:
        raise ValueError("empty word")

    if verb_class:
        return Classification(w, w[:-1], pos or "verb", verb_class, True,
                              "declared by content")

    if w in IRREGULAR:
        cls = IRREGULAR[w]
        return Classification(w, w[:-1], "verb", cls, True)

    if w.endswith(SURU_SUFFIX) and len(w) > 2:
        return Classification(w, w[:-2], "verb", "suru", True,
                              "a -する compound; conjugates like する")

    if w.endswith("くる") or w.endswith("来る"):
        return Classification(w, w[:-2], "verb", "kuru", True)

    last = w[-1]

    # i-adjectives end in い but so do many ichidan verbs' dictionary forms
    # never do — verbs end in an u-row kana. い is not one.
    if pos == "i-adjective" or (pos is None and last == "い" and w not in ("いい",)):
        if w in I_ADJ_IRREGULAR or w == "いい":
            return Classification(w, I_ADJ_IRREGULAR.get(w, w[:-1]), "i-adjective", "",
                                  True, "いい is irregular: its stem is よ")
        return Classification(w, w[:-1], "i-adjective", "", True)
    if w == "いい":
        return Classification(w, "よ", "i-adjective", "", True,
                              "いい is irregular: よくない, よかった")

    if last not in ROWS:
        return Classification(w, w, pos or "na-adjective", "", False,
                              "does not end in an u-row kana; treated as a "
                              "na-adjective or noun")

    if last != "る":
        return Classification(w, w[:-1], "verb", "godan", True)

    # ...ends in る. This is the ambiguous case.
    if w in GODAN_RU_EXCEPTIONS:
        return Classification(w, w[:-1], "verb", "godan", True,
                              "looks ichidan but is godan — a known exception")
    if w in ICHIDAN_KANJI:
        return Classification(w, w[:-1], "verb", "ichidan", True)
    before = w[-2] if len(w) >= 2 else ""
    before_kana = K.to_hiragana(before)
    if before_kana in I_ROW or before_kana in E_ROW:
        return Classification(w, w[:-1], "verb", "ichidan", True)
    if K.is_kanji(before):
        return Classification(
            w, w[:-1], "verb", "godan", False,
            "the vowel before る is hidden inside the kanji, so the class "
            "cannot be read off the spelling; assumed godan. Declare it in "
            "the vocabulary entry to be certain.")
    return Classification(w, w[:-1], "verb", "godan", True)


# --------------------------------------------------------------------------
# Stems
# --------------------------------------------------------------------------

def _row_form(word: str, index: int) -> str:
    """Shift a godan verb's final kana into another vowel row."""
    last = word[-1]
    return word[:-1] + ROWS[last][index]


def stem_masu(word: str, cls: VerbClass) -> str:
    """The i-row stem that ます attaches to."""
    if cls == "ichidan":
        return word[:-1]
    if cls == "suru":
        return (word[:-2] + "し") if word.endswith(SURU_SUFFIX) else "し"
    if cls == "kuru":
        # 来ます is written with 来 but read kimasu; くる gives きます. Same
        # verb, and the kanji hides all three of its readings.
        return word[:-2] + ("来" if word.endswith("来る") else "き")
    return _row_form(word, I)


def stem_nai(word: str, cls: VerbClass) -> str:
    """The a-row stem that ない attaches to."""
    if cls == "ichidan":
        return word[:-1]
    if cls == "suru":
        return (word[:-2] + "し") if word.endswith(SURU_SUFFIX) else "し"
    if cls == "kuru":
        return word[:-2] + ("来" if word.endswith("来る") else "こ")
    if cls == "aru":
        return ""                      # ある's negative is simply ない
    return _row_form(word, A)


def te_form(word: str, cls: VerbClass) -> str:
    if cls == "ichidan":
        return word[:-1] + "て"
    if cls == "suru":
        return (word[:-2] + "して") if word.endswith(SURU_SUFFIX) else "して"
    if cls == "kuru":
        return word[:-2] + ("来て" if word.endswith("来る") else "きて")
    if word in ("行く", "いく"):        # the one godan く that goes って
        return word[:-1] + "って"
    return word[:-1] + TE_ENDINGS[word[-1]]


def ta_form(word: str, cls: VerbClass) -> str:
    te = te_form(word, cls)
    return te[:-1] + ("た" if te.endswith("て") else "だ")


# --------------------------------------------------------------------------
# Forms
# --------------------------------------------------------------------------

@dataclass
class Form:
    id: str
    japanese: str
    label_en: str
    label_ja: str
    category: str
    politeness: str
    note: str = ""

    def to_dict(self) -> dict:
        """See the note on Korean's `Form.to_dict`: `form` and `label_native`
        are the language-neutral aliases every table provides."""
        d = asdict(self)
        d["form"] = self.japanese
        d["label_native"] = self.label_ja
        return d


POLITENESS = {
    "teinei": {"ja": "丁寧語", "en": "Polite (ます)",
               "when": "The default with anyone you are not close to. Learn this first."},
    "futsuu": {"ja": "普通体", "en": "Plain",
               "when": "Close friends, family, and all writing — books, articles, notes."},
    "sonkei": {"ja": "尊敬語", "en": "Respectful keigo",
               "when": "Raising someone above you: a customer, a superior."},
    "kenjou": {"ja": "謙譲語", "en": "Humble keigo",
               "when": "Lowering yourself when describing your own actions to a superior."},
    "none": {"ja": "—", "en": "Not politeness-marked",
             "when": "Connective and modifying forms take their level from the final verb."},
}

#: Suppletive keigo. These are separate words, not conjugations — the same
#: shape of problem as Korean's 드시다, and just as easy to get wrong.
KEIGO: dict[str, dict[str, str]] = {
    "する": {"sonkei": "なさる", "kenjou": "いたす"},
    "行く": {"sonkei": "いらっしゃる", "kenjou": "参る"},
    "来る": {"sonkei": "いらっしゃる", "kenjou": "参る"},
    "いる": {"sonkei": "いらっしゃる", "kenjou": "おる"},
    "見る": {"sonkei": "ご覧になる", "kenjou": "拝見する"},
    "食べる": {"sonkei": "召し上がる", "kenjou": "いただく"},
    "飲む": {"sonkei": "召し上がる", "kenjou": "いただく"},
    "言う": {"sonkei": "おっしゃる", "kenjou": "申す"},
    "聞く": {"sonkei": "お聞きになる", "kenjou": "伺う"},
    "知る": {"sonkei": "ご存じだ", "kenjou": "存じる"},
    "もらう": {"sonkei": "", "kenjou": "いただく"},
    "あげる": {"sonkei": "", "kenjou": "差し上げる"},
}


def conjugate(word: str, pos: Optional[PartOfSpeech] = None,
              verb_class: Optional[VerbClass] = None) -> dict[str, Form]:
    c = classify(word, pos, verb_class)
    if c.pos == "i-adjective":
        return _conjugate_i_adjective(word, c)
    if c.pos in ("na-adjective", "noun"):
        return _conjugate_na_adjective(word, c)
    return _conjugate_verb(word, c)


def _conjugate_verb(word: str, c: Classification) -> dict[str, Form]:
    cls = c.verb_class
    forms: dict[str, Form] = {}

    def add(fid, ja, en, jal, cat, pol, note=""):
        forms[fid] = Form(fid, ja, en, jal, cat, pol, note)

    masu = stem_masu(word, cls)
    nai = stem_nai(word, cls)
    te = te_form(word, cls)
    ta = ta_form(word, cls)

    # -- polite -----------------------------------------------------------
    add("masu", masu + "ます", "Present, polite", "ます形", "tense", "teinei",
        "The form to learn first. Present and future both.")
    add("masen", masu + "ません", "Negative, polite", "ません", "tense", "teinei")
    add("mashita", masu + "ました", "Past, polite", "ました", "tense", "teinei")
    add("masendeshita", masu + "ませんでした", "Past negative, polite",
        "ませんでした", "tense", "teinei")
    add("mashou", masu + "ましょう", "Let's / shall we", "ましょう", "mood", "teinei")
    add("masenka", masu + "ませんか", "Would you like to?", "ませんか", "mood", "teinei",
        "Softer than ましょう — it leaves room to decline.")

    # -- plain ------------------------------------------------------------
    add("dictionary", word, "Dictionary form", "辞書形", "tense", "futsuu")
    if cls == "aru":
        add("nai", "ない", "Negative, plain", "ない形", "tense", "futsuu",
            "ある is irregular here: the negative is simply ない, not あらない.")
        add("nakatta", "なかった", "Past negative, plain", "なかった", "tense", "futsuu")
    else:
        add("nai", nai + "ない", "Negative, plain", "ない形", "tense", "futsuu")
        add("nakatta", nai + "なかった", "Past negative, plain", "なかった",
            "tense", "futsuu")
    add("ta", ta, "Past, plain", "た形", "tense", "futsuu")

    # -- て form and what hangs off it ------------------------------------
    add("te", te, "て form", "て形", "connective", "none",
        "The hinge of Japanese grammar. Dozens of structures attach here.")
    add("te_kudasai", te + "ください", "Please do", "てください", "request", "teinei")
    add("te_iru", te + "いる", "Is doing / is in a state", "ている", "aspect", "futsuu")
    add("te_imasu", te + "います", "Is doing, polite", "ています", "aspect", "teinei")
    add("te_mo_ii", te + "もいい", "May / it's okay to", "てもいい", "modal", "none")
    add("te_wa_ikenai", te + "はいけない", "Must not", "てはいけない", "modal", "none")
    add("te_kara", te + "から", "After doing", "てから", "connective", "none")
    add("te_shimau", te + "しまう", "Do completely / regrettably", "てしまう",
        "aspect", "futsuu")

    # -- た form derivatives ----------------------------------------------
    add("tara", ta + "ら", "If / when", "たら", "conditional", "none",
        "The most versatile conditional. Usable almost anywhere.")
    add("tari", ta + "り", "Doing things like", "たり", "connective", "none")
    add("ta_koto_ga_aru", ta + "ことがある", "Have ever done", "たことがある",
        "experience", "none")

    # -- potential, volitional, imperative --------------------------------
    if cls == "ichidan":
        add("potential", word[:-1] + "られる", "Can do", "可能形", "modal", "futsuu",
            "In casual speech the ら is often dropped: 食べれる. Common, and "
            "still considered non-standard in writing.")
        add("volitional", word[:-1] + "よう", "Let's / I shall", "意向形", "mood", "futsuu")
        add("imperative", word[:-1] + "ろ", "Do it (blunt)", "命令形", "mood", "futsuu",
            "Very direct. Shouting, instructions, or anger.")
        add("passive", word[:-1] + "られる", "Passive", "受身形", "voice", "futsuu",
            "Identical to the potential for ichidan verbs — context decides.")
        add("causative", word[:-1] + "させる", "Make/let someone do", "使役形",
            "voice", "futsuu")
        add("ba", word[:-1] + "れば", "If", "ば形", "conditional", "none")
    elif cls == "suru":
        base = word[:-2] if word.endswith(SURU_SUFFIX) else ""
        add("potential", base + "できる", "Can do", "可能形", "modal", "futsuu",
            "する's potential is the separate verb できる.")
        add("volitional", base + "しよう", "Let's", "意向形", "mood", "futsuu")
        add("imperative", base + "しろ", "Do it (blunt)", "命令形", "mood", "futsuu")
        add("passive", base + "される", "Passive", "受身形", "voice", "futsuu")
        add("causative", base + "させる", "Make/let someone do", "使役形", "voice", "futsuu")
        add("ba", base + "すれば", "If", "ば形", "conditional", "none")
    elif cls == "kuru":
        base = word[:-2]
        ko = base + ("来" if word.endswith("来る") else "こ")
        ku = base + ("来" if word.endswith("来る") else "く")
        reading = (" Written with 来 throughout; only the reading changes."
                   if word.endswith("来る") else "")
        add("potential", ko + "られる", "Can come", "可能形", "modal", "futsuu", reading)
        add("volitional", ko + "よう", "Let's come", "意向形", "mood", "futsuu", reading)
        add("imperative", ko + "い", "Come! (blunt)", "命令形", "mood", "futsuu", reading)
        add("passive", ko + "られる", "Passive", "受身形", "voice", "futsuu")
        add("causative", ko + "させる", "Make/let come", "使役形", "voice", "futsuu")
        add("ba", ku + "れば", "If", "ば形", "conditional", "none")
    else:
        add("potential", _row_form(word, E) + "る", "Can do", "可能形", "modal", "futsuu")
        add("volitional", _row_form(word, O) + "う", "Let's / I shall", "意向形",
            "mood", "futsuu")
        add("imperative", _row_form(word, E), "Do it (blunt)", "命令形", "mood", "futsuu",
            "Very direct. Shouting, instructions, or anger.")
        add("passive", nai + "れる", "Passive", "受身形", "voice", "futsuu")
        add("causative", nai + "せる", "Make/let someone do", "使役形", "voice", "futsuu")
        add("ba", _row_form(word, E) + "ば", "If", "ば形", "conditional", "none")

    # -- from the masu stem -----------------------------------------------
    add("tai", masu + "たい", "Want to", "たい形", "modal", "futsuu",
        "Only your own wants. Someone else's needs たがっている.")
    add("nagara", masu + "ながら", "While doing", "ながら", "connective", "none")
    add("ni_iku", masu + "に行く", "Go in order to", "に行く", "purpose", "none")
    add("yasui", masu + "やすい", "Easy to do", "やすい", "modal", "none")
    add("nikui", masu + "にくい", "Hard to do", "にくい", "modal", "none")
    add("sugiru", masu + "すぎる", "Do too much", "すぎる", "modal", "none")

    # -- obligation --------------------------------------------------------
    if cls != "aru":
        add("nakereba", nai + "ければならない", "Must", "なければならない",
            "modal", "futsuu", "Colloquially shortened to なきゃ.")
        add("nakute_mo_ii", nai + "くてもいい", "Don't have to", "なくてもいい",
            "modal", "none")
        add("naide_kudasai", nai + "ないでください", "Please don't", "ないでください",
            "request", "teinei")

    # -- keigo -------------------------------------------------------------
    k = KEIGO.get(word)
    if k:
        if k.get("sonkei"):
            add("sonkei", k["sonkei"], "Respectful", "尊敬語", "keigo", "sonkei",
                f"A separate word, not a conjugation. Use for someone else's actions.")
        if k.get("kenjou"):
            add("kenjou", k["kenjou"], "Humble", "謙譲語", "keigo", "kenjou",
                f"A separate word. Use for your own actions toward a superior.")
    else:
        add("sonkei", "お" + masu + "になる", "Respectful", "尊敬語", "keigo", "sonkei",
            "The regular pattern. Many common verbs use a special word instead.")
        add("kenjou", "お" + masu + "する", "Humble", "謙譲語", "keigo", "kenjou",
            "The regular pattern.")

    return forms


def _conjugate_i_adjective(word: str, c: Classification) -> dict[str, Form]:
    stem = c.stem
    f: dict[str, Form] = {}

    def add(fid, ja, en, jal, cat, pol, note=""):
        f[fid] = Form(fid, ja, en, jal, cat, pol, note)

    irregular_note = ("いい is the one irregular i-adjective: every form except "
                      "the dictionary form is built on よ." if word in ("いい", "良い")
                      else "")

    add("dictionary", word, "Present, plain", "辞書形", "tense", "futsuu", irregular_note)
    add("desu", word + "です", "Present, polite", "です", "tense", "teinei",
        "です here is only politeness — the adjective is already the predicate.")
    add("negative", stem + "くない", "Negative", "くない", "tense", "futsuu", irregular_note)
    add("negative_polite", stem + "くないです", "Negative, polite", "くないです",
        "tense", "teinei", "Also ありません: " + stem + "くありません")
    add("past", stem + "かった", "Past", "かった", "tense", "futsuu")
    add("past_polite", stem + "かったです", "Past, polite", "かったです", "tense", "teinei")
    add("past_negative", stem + "くなかった", "Past negative", "くなかった",
        "tense", "futsuu")
    add("te", stem + "くて", "て form", "くて", "connective", "none",
        "Joins to another clause: 安くて美味しい.")
    add("adverb", stem + "く", "As an adverb", "連用形", "modifier", "none",
        "早い becomes 早く: 早く食べる, eat quickly.")
    add("sugiru", stem + "すぎる", "Too much", "すぎる", "modal", "none")
    add("naru", stem + "くなる", "Become", "くなる", "modal", "none")
    add("sou", stem + "そう", "Looks / seems", "そう", "modal", "none")
    add("ba", stem + "ければ", "If", "ば形", "conditional", "none")
    return f


def _conjugate_na_adjective(word: str, c: Classification) -> dict[str, Form]:
    w = word[:-1] if word.endswith("な") else word
    f: dict[str, Form] = {}

    def add(fid, ja, en, jal, cat, pol, note=""):
        f[fid] = Form(fid, ja, en, jal, cat, pol, note)

    add("dictionary", w + "だ", "Present, plain", "だ", "tense", "futsuu")
    add("desu", w + "です", "Present, polite", "です", "tense", "teinei")
    add("negative", w + "じゃない", "Negative", "じゃない", "tense", "futsuu",
        "ではない in writing; じゃない in speech.")
    add("negative_polite", w + "じゃないです", "Negative, polite", "じゃないです",
        "tense", "teinei", "Also ではありません, which is more formal.")
    add("past", w + "だった", "Past", "だった", "tense", "futsuu")
    add("past_polite", w + "でした", "Past, polite", "でした", "tense", "teinei")
    add("past_negative", w + "じゃなかった", "Past negative", "じゃなかった",
        "tense", "futsuu")
    add("te", w + "で", "て form", "で", "connective", "none")
    add("modifier", w + "な", "Before a noun", "連体形", "modifier", "none",
        "This is where the name comes from: 静かな部屋.")
    add("adverb", w + "に", "As an adverb", "に", "modifier", "none",
        "静かに, quietly.")
    add("naru", w + "になる", "Become", "になる", "modal", "none")
    add("ba", w + "ならば", "If", "ば形", "conditional", "none")
    return f


CLASS_EXPLANATIONS: dict[str, dict[str, str]] = {
    "godan": {
        "name": "Godan (五段) — u-verb",
        "simple": "The last letter slides up and down its column. 書く becomes "
                  "書か, 書き, 書く, 書け, 書こ depending on what comes next.",
        "technical": "Five-grade conjugation: the stem-final mora shifts across "
                     "the a/i/u/e/o row of its consonant series.",
        "example": "書く → 書きます / 書かない / 書いて",
    },
    "ichidan": {
        "name": "Ichidan (一段) — ru-verb",
        "simple": "The easy one. Drop る and attach whatever you need.",
        "technical": "Single-grade conjugation: the stem is invariant and the "
                     "final る simply drops.",
        "example": "食べる → 食べます / 食べない / 食べて",
    },
    "suru": {
        "name": "する — irregular",
        "simple": "One of only two truly irregular verbs — but it powers "
                  "thousands of words, because any noun plus する becomes a verb.",
        "technical": "Suppletive throughout. Its potential is the separate verb できる.",
        "example": "する → します / しない / して;  勉強する → 勉強します",
    },
    "kuru": {
        "name": "来る — irregular",
        "simple": "The other irregular verb. The kanji stays put while the "
                  "reading underneath changes: き, こ, く.",
        "technical": "Suppletive. 来ます is kimasu, 来ない is konai, 来る is kuru — "
                     "same kanji, three readings.",
        "example": "来る → 来ます (kimasu) / 来ない (konai) / 来て (kite)",
    },
    "aru": {
        "name": "ある — irregular in the negative only",
        "simple": "Regular everywhere except its negative, which is simply ない.",
        "technical": "Suppletive negation: *あらない does not exist.",
        "example": "ある → あります / ない / あって",
    },
    "": {
        "name": "Adjective or noun",
        "simple": "Not a verb — conjugates on its own pattern.",
        "technical": "",
        "example": "",
    },
}


def conjugation_table(word: str, pos: Optional[PartOfSpeech] = None,
                      verb_class: Optional[VerbClass] = None) -> dict:
    c = classify(word, pos, verb_class)
    forms = conjugate(word, pos, verb_class)
    grouped: dict[str, list[dict]] = {}
    for f in forms.values():
        grouped.setdefault(f.category, []).append(f.to_dict())

    stems = {}
    if c.pos == "verb":
        stems = {
            "masu": stem_masu(word, c.verb_class),
            "nai": stem_nai(word, c.verb_class),
            "te": te_form(word, c.verb_class),
            "ta": ta_form(word, c.verb_class),
        }

    return {
        "dictionary_form": word,
        "stem": c.stem,
        "part_of_speech": c.pos,
        "verb_class": c.verb_class or "—",
        "class_explained": CLASS_EXPLANATIONS.get(c.verb_class, CLASS_EXPLANATIONS[""]),
        "confident": c.confident,
        "note": c.note,
        "stems": stems,
        "categories": grouped,
        "politeness_levels": POLITENESS,
        "mora": K.count_mora(K.to_hiragana(word)) if not any(
            K.is_kanji(ch) for ch in word) else None,
    }
