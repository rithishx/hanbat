"""
Japanese confusion pairs.

These are Japanese mistakes, with Japanese explanations. は versus が looks
superficially like Korean's 은/는 versus 이/가 and the two are NOT the same
distinction — treating them as one would teach both wrongly, which is why each
language owns this file.
"""

from __future__ import annotations

from ...engines.confusion import Confusion, index_confusions

CONFUSIONS: dict[str, Confusion] = {
    "wa_vs_ga": Confusion(
        id="wa_vs_ga",
        a="は", b="が",
        title="は versus が",
        one_line="は sets up what you are talking about. が points at the new thing.",
        simple=(
            "Think of は as putting something on the table: 'right, this thing — '. "
            "Everyone already knows what it is. が is pointing your finger at "
            "something that has just arrived in the conversation. If it answers "
            "'who?' or 'what?', it takes が."
        ),
        rule=(
            "は marks the topic: known information, contrast, or a general "
            "statement. が marks the grammatical subject, typically new or "
            "focused information, and is required inside a subordinate clause "
            "where は cannot appear."
        ),
        examples=[
            {"target": "私は学生です。", "english": "I am a student.",
             "why": "Introducing yourself. Everyone knows who 'I' is — topic."},
            {"target": "誰が来ましたか。— 田中さんが来ました。",
             "english": "Who came? — Tanaka came.",
             "why": "The answer to 'who?' is new information, so が."},
            {"target": "猫は好きですが、犬は好きじゃないです。",
             "english": "I like cats, but I don't like dogs.",
             "why": "Two things held against each other — は does contrast."},
            {"target": "雨が降っています。", "english": "It's raining.",
             "why": "Announcing something happening now."},
        ],
        drill_prompt="Ask yourself: is this new, or already on the table?",
        tags=("particles", "N5"),
    ),
    "ni_vs_de": Confusion(
        id="ni_vs_de",
        a="に", b="で",
        title="に versus で",
        one_line="に is a point. で is a stage.",
        simple=(
            "に is a pin stuck in a place or a time — where something IS, or "
            "where you are going. で is the stage an action happens on. If you "
            "could film someone doing the verb there, use で."
        ),
        rule=(
            "に marks a destination, a point in time, an indirect object, or the "
            "location of existence with いる/ある. で marks the location of a "
            "dynamic activity, or the means by which something is done."
        ),
        examples=[
            {"target": "学校に行きます。", "english": "I go to school.", "why": "Destination."},
            {"target": "学校で勉強します。", "english": "I study at school.",
             "why": "The studying happens there."},
            {"target": "家にいます。", "english": "I'm at home.",
             "why": "いる and ある always take に, never で."},
            {"target": "電車で行きます。", "english": "I go by train.",
             "why": "で also marks the means."},
        ],
        drill_prompt="Is this a point you are pointing at, or a place you are acting in?",
        tags=("particles", "N5"),
    ),
    "aru_vs_iru": Confusion(
        id="aru_vs_iru",
        a="ある", b="いる",
        title="ある versus いる",
        one_line="いる is for things that can move themselves. ある is for everything else.",
        simple=(
            "Can it decide to walk away? Then いる. People and animals use いる; "
            "books, buildings and trees use ある. A car uses ある — until someone "
            "is driving it, and even then most people still say ある."
        ),
        rule=(
            "いる takes animate subjects, ある inanimate. ある is also irregular "
            "in the negative: its negative is ない, not あらない."
        ),
        examples=[
            {"target": "猫がいます。", "english": "There's a cat.", "why": "Animate."},
            {"target": "本があります。", "english": "There's a book.", "why": "Inanimate."},
            {"target": "時間がありません。", "english": "I don't have time.",
             "why": "Abstract things take ある."},
        ],
        drill_prompt="Can it move on its own?",
        tags=("verbs", "N5"),
    ),
    "mora_length": Confusion(
        id="mora_length",
        a="short vowel", b="long vowel",
        title="Long versus short",
        one_line="Vowel length changes the word. おばさん is your aunt; おばあさん is your grandmother.",
        simple=(
            "English does not use vowel length to tell words apart, so English "
            "ears simply do not hear this at first. Japanese does, constantly. "
            "Count the beats: おばさん is four taps, おばあさん is five."
        ),
        rule=(
            "Vowel length is phonemic in Japanese. Each mora carries roughly "
            "equal duration, and a long vowel occupies two mora."
        ),
        examples=[
            {"target": "おばさん / おばあさん", "english": "aunt / grandmother", "why": ""},
            {"target": "ビル / ビール", "english": "building / beer", "why": ""},
            {"target": "ここ / こうこう", "english": "here / high school", "why": ""},
        ],
        drill_prompt="Tap the beats on the table while you say it.",
        tags=("pronunciation", "N5"),
    ),
    "sokuon": Confusion(
        id="sokuon",
        a="きて", b="きって",
        title="The small っ",
        one_line="っ is a beat of silence, not a doubled letter.",
        simple=(
            "Stop completely. Hold for one beat. Then carry on. Learners skip it "
            "because there is nothing to pronounce — but the silence is the sound, "
            "and きて (come) and きって (stamp) are different words."
        ),
        rule="The sokuon is a moraic obstruent occupying one full mora.",
        examples=[
            {"target": "きて / きって", "english": "come / stamp", "why": ""},
            {"target": "おと / おっと", "english": "sound / husband", "why": ""},
            {"target": "かこ / かっこ", "english": "the past / brackets", "why": ""},
        ],
        drill_prompt="Say the first half, stop dead for a beat, then finish.",
        tags=("pronunciation", "N5"),
    ),
    "godan_vs_ichidan": Confusion(
        id="godan_vs_ichidan",
        a="godan", b="ichidan",
        title="Godan versus ichidan verbs",
        one_line="Ichidan verbs just drop る. Godan verbs shift their last kana up and down a column.",
        simple=(
            "食べる is ichidan: chop off る and add whatever you need — 食べます, "
            "食べない, 食べて. 取る is godan: the る moves through ら り る れ ろ "
            "depending on the ending — 取ります, 取らない, 取って.\n\n"
            "The trap is that both end in る. If the sound before る is an i or e "
            "sound it is usually ichidan — but 帰る, 走る and 知る are godan "
            "despite looking ichidan, and you simply have to learn those."
        ),
        rule=(
            "Ichidan (一段) verbs have an invariant stem. Godan (五段) verbs shift "
            "the stem-final mora across the five vowel grades of its consonant "
            "row. Verbs ending in る with a preceding i- or e-row kana are usually "
            "ichidan; the exceptions are a closed, memorisable list."
        ),
        examples=[
            {"target": "食べる → 食べます", "english": "eat", "why": "Ichidan: drop る."},
            {"target": "取る → 取ります", "english": "take", "why": "Godan: る becomes り."},
            {"target": "帰る → 帰ります", "english": "go home",
             "why": "Looks ichidan (え before る) but is godan. A known exception."},
        ],
        drill_prompt="Say the ます form. If る became り, it is godan.",
        tags=("verbs", "N5"),
    ),
    "keigo_direction": Confusion(
        id="keigo_direction",
        a="尊敬語", b="謙譲語",
        title="Respectful versus humble keigo",
        one_line="尊敬語 raises them. 謙譲語 lowers you. Using the wrong one reverses your meaning.",
        simple=(
            "Two separate sets of words, and which you use depends on WHOSE "
            "action it is. If your boss is eating, they 召し上がる. If you are "
            "eating in front of your boss, you いただく. Saying 召し上がります "
            "about yourself claims you are the important one in the room."
        ),
        rule=(
            "尊敬語 elevates the referent of the subject; 謙譲語 lowers the speaker "
            "or the speaker's in-group. Many common verbs use suppletive forms "
            "rather than the regular お〜になる / お〜する patterns."
        ),
        examples=[
            {"target": "部長が召し上がりました。", "english": "The manager ate.",
             "why": "Their action → respectful."},
            {"target": "私がいただきました。", "english": "I ate.",
             "why": "Your own action → humble."},
        ],
        drill_prompt="Whose action is it? That decides which set you reach for.",
        tags=("keigo", "N3"),
    ),
    "ha_reading": Confusion(
        id="ha_reading",
        a="は as ha", b="は as wa",
        title="When は is read wa",
        one_line="The topic particle は is read wa. Everywhere else は is ha.",
        simple=(
            "This is a historical spelling that never got updated. As a particle, "
            "は is said wa and へ is said e. Inside a word they are read normally: "
            "はな is hana, へや is heya."
        ),
        rule="Historical kana orthography preserved for the particles は, へ and を.",
        examples=[
            {"target": "私は学生です。", "english": "I am a student.",
             "why": "Particle — read wa."},
            {"target": "はな", "english": "flower", "why": "Inside a word — read ha."},
        ],
        drill_prompt="Is it doing a grammatical job, or is it part of a word?",
        tags=("pronunciation", "N5"),
    ),
}

PAIR_INDEX = index_confusions(CONFUSIONS, "ja")
