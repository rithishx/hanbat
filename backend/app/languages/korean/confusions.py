"""
Korean confusion pairs.

Every entry here is a mistake Korean learners make repeatedly and predictably,
paired with the explanation that actually resolves it. When the adaptive engine
sees the same pair missed three times it stops the curriculum and builds a
mini-course from this data.

These are Korean-specific by nature. Japanese learners confuse は with が for
reasons that have nothing to do with 은/는 versus 이/가, and Mandarin has no
particles of this kind at all — so each language owns its own file.
"""

from __future__ import annotations

from ...engines.confusion import Confusion, index_confusions

CONFUSIONS: dict[str, Confusion] = {
    "topic_vs_subject": Confusion(
        id="topic_vs_subject",
        a="은/는", b="이/가",
        title="은/는 versus 이/가",
        one_line="은/는 says what the sentence is *about*. 이/가 says who *did* it.",
        simple=(
            "Imagine you are pointing at things. 이/가 is your finger pointing "
            "straight at who did something — 'THIS one did it'. 은/는 is you "
            "setting the topic down on the table first — 'as for this thing...' "
            "— usually to compare it with something else."
        ),
        rule=(
            "은/는 marks the topic: old information, contrast, or general truths. "
            "이/가 marks the grammatical subject: new information, the answer to "
            "'who?' or 'what?', and the subject inside a subordinate clause."
        ),
        examples=[
            {"target": "제 이름은 리티시예요.", "english": "My name is Rithish.",
             "why": "Introducing yourself sets a topic — 'as for my name'."},
            {"target": "누가 왔어요? — 친구가 왔어요.",
             "english": "Who came? — A friend came.",
             "why": "The answer to 'who?' is new information, so 이/가."},
            {"target": "커피는 좋아하는데 차는 안 좋아해요.",
             "english": "I like coffee but I don't like tea.",
             "why": "Two things being contrasted — that is 은/는's job."},
            {"target": "비가 와요.", "english": "It's raining.",
             "why": "Announcing something new happening right now."},
        ],
        drill_prompt="Choose 은/는 or 이/가 and say why before you check.",
        tags=("particles", "A1"),
    ),
    "e_vs_eseo": Confusion(
        id="e_vs_eseo",
        a="에", b="에서",
        title="에 versus 에서",
        one_line="에 is where you go or where something sits. 에서 is where you *do* something.",
        simple=(
            "에 is an arrow pointing at a place, or a pin stuck in it. 에서 is a "
            "little stage — the place the action happens on. If the verb is "
            "something you can watch someone doing, use 에서."
        ),
        rule=(
            "에 marks a destination (가다, 오다), a location of existence "
            "(있다, 없다), or a time. 에서 marks the location of an activity, "
            "or a starting point ('from')."
        ),
        examples=[
            {"target": "학교에 가요.", "english": "I go to school.",
             "why": "Destination — the arrow points at 학교."},
            {"target": "학교에서 공부해요.", "english": "I study at school.",
             "why": "The studying happens there — 학교 is the stage."},
            {"target": "집에 있어요.", "english": "I'm at home.",
             "why": "있다 always takes 에, never 에서."},
            {"target": "한국에서 왔어요.", "english": "I came from Korea.",
             "why": "에서 also means 'from' with 오다."},
        ],
        drill_prompt="Ask yourself: am I pointing at the place, or acting in it?",
        tags=("particles", "A1"),
    ),
    "isseoyo_vs_ieyo": Confusion(
        id="isseoyo_vs_ieyo",
        a="있어요", b="이에요/예요",
        title="있어요 versus 이에요",
        one_line="있어요 = it exists / I have it. 이에요 = it *is* that thing.",
        simple=(
            "이에요 is an equals sign: A = B. 있어요 is a box with something in "
            "it. 'I am a student' uses the equals sign. 'I have a pen' uses the box."
        ),
        rule=(
            "이에요/예요 is the copula, joining a noun to the subject. 있다 is a "
            "verb of existence or possession, and takes 이/가 or 은/는, never a "
            "direct object with 을/를."
        ),
        examples=[
            {"target": "저는 학생이에요.", "english": "I am a student.", "why": "A = B."},
            {"target": "펜이 있어요.", "english": "I have a pen. / There's a pen.",
             "why": "Existence, not identity."},
            {"target": "화장실이 어디에 있어요?", "english": "Where is the toilet?",
             "why": "Asking about location always uses 있다."},
        ],
        drill_prompt="Can you replace it with 'equals'? Then it is 이에요.",
        tags=("copula", "A1"),
    ),
    "an_vs_mot": Confusion(
        id="an_vs_mot",
        a="안", b="못",
        title="안 versus 못",
        one_line="안 = I don't. 못 = I can't.",
        simple=(
            "안 is a choice — you decided not to. 못 is a wall — something is "
            "stopping you. 'I don't eat meat' is 안. 'I can't eat spicy food' is 못."
        ),
        rule=(
            "안 negates the action itself (simple negation, choice). 못 negates "
            "ability or possibility, whether from skill, circumstance or "
            "permission. 못 cannot be used with adjectives."
        ),
        examples=[
            {"target": "저는 술을 안 마셔요.", "english": "I don't drink alcohol.",
             "why": "A choice."},
            {"target": "오늘은 못 가요.", "english": "I can't go today.",
             "why": "Something is preventing it."},
            {"target": "매운 음식을 못 먹어요.", "english": "I can't eat spicy food.",
             "why": "Inability, not preference."},
        ],
        drill_prompt="Is this a decision, or is something in your way?",
        tags=("negation", "A1"),
    ),
    "aseo_vs_nikka": Confusion(
        id="aseo_vs_nikka",
        a="-아/어서", b="-(으)니까",
        title="-아/어서 versus -(으)니까",
        one_line="-아/어서 states a plain cause. -(으)니까 gives *your* reason for saying it.",
        simple=(
            "-아/어서 is like saying 'because it rained, I stayed home' — a fact. "
            "-(으)니까 is 'since it's raining, let's stay home' — you are using "
            "the reason to make a point."
        ),
        rule=(
            "-아/어서 cannot carry a tense marker and cannot precede a command "
            "or suggestion. -(으)니까 can do both. For thanks and apologies "
            "Korean strongly prefers -아/어서."
        ),
        examples=[
            {"target": "비가 와서 못 갔어요.", "english": "I couldn't go because it rained.",
             "why": "Plain cause, past tense sits on the final verb only."},
            {"target": "비가 오니까 우산을 가져가세요.",
             "english": "Since it's raining, take an umbrella.",
             "why": "A command follows, so -아/어서 is impossible here."},
            {"target": "늦어서 죄송합니다.", "english": "I'm sorry for being late.",
             "why": "Apologies take -아/어서. -(으)니까 would sound like an excuse."},
        ],
        drill_prompt="Is a command or suggestion coming next? Then it must be -(으)니까.",
        tags=("connectives", "A2"),
    ),
    "native_vs_sino_numbers": Confusion(
        id="native_vs_sino_numbers",
        a="하나, 둘, 셋", b="일, 이, 삼",
        title="Native versus Sino-Korean numbers",
        one_line="Count things with 하나 둘 셋. Read numbers with 일 이 삼.",
        simple=(
            "Korean has two sets of numbers and uses both every day. The native "
            "ones (하나, 둘, 셋) are for counting things you can see. The "
            "Chinese-derived ones (일, 이, 삼) are for anything written down: "
            "money, dates, phone numbers, minutes."
        ),
        rule=(
            "Native numerals are used with counters for objects, people, age and "
            "hours. Sino-Korean numerals are used for dates, money, minutes, "
            "phone numbers, floors, and any number above 99 in most contexts."
        ),
        examples=[
            {"target": "커피 두 잔 주세요.", "english": "Two coffees, please.",
             "why": "Counting objects — native, and 둘 shortens to 두 before a counter."},
            {"target": "삼십 분", "english": "thirty minutes", "why": "Minutes are Sino-Korean."},
            {"target": "두 시 삼십 분", "english": "2:30",
             "why": "The hour is native, the minutes are Sino. Both in one phrase."},
        ],
        drill_prompt="Are you counting things, or reading a number off a page?",
        tags=("numbers", "A1"),
    ),
    "aspirated_tense_plain": Confusion(
        id="aspirated_tense_plain",
        a="ㄱ / ㅋ / ㄲ", b="ㄷ / ㅌ / ㄸ, ㅂ / ㅍ / ㅃ, ㅈ / ㅊ / ㅉ",
        title="The three-way consonant contrast",
        one_line="Plain, breathy, and tight — English only has two of the three.",
        simple=(
            "Hold your hand in front of your mouth. ㅋ blows air onto it. ㄱ "
            "barely does. ㄲ blows none at all and your throat feels squeezed, "
            "like you are about to lift something heavy."
        ),
        rule=(
            "Korean distinguishes lax, aspirated and tense obstruents. English "
            "has only a two-way voiced/voiceless contrast, so English speakers "
            "hear all three as the same consonant until trained."
        ),
        examples=[
            {"target": "불 / 풀 / 뿔", "english": "fire / grass / horn",
             "why": "Three different words that English ears hear as one."},
            {"target": "달 / 탈 / 딸", "english": "moon / mask / daughter", "why": ""},
            {"target": "자다 / 차다 / 짜다", "english": "sleep / kick / salty", "why": ""},
        ],
        drill_prompt="Listen first, then produce. Recognition has to come before production.",
        tags=("pronunciation", "hangul"),
    ),
    "eo_vs_o": Confusion(
        id="eo_vs_o",
        a="ㅓ", b="ㅗ",
        title="ㅓ versus ㅗ",
        one_line="ㅗ rounds your lips. ㅓ does not.",
        simple=(
            "Say 'oh' with your lips pushed forward into a circle — that is ㅗ. "
            "Now relax your lips completely, drop your jaw, and make a sound "
            "somewhere between 'uh' and 'aw' — that is ㅓ. Watch your mouth in a "
            "mirror: if your lips move, you said ㅗ."
        ),
        rule="ㅗ is a rounded back mid vowel; ㅓ is unrounded. Romanisation writes them 'o' and 'eo', which hides how different they are.",
        examples=[
            {"target": "서울 / 소울", "english": "Seoul / soul", "why": "First vowel unrounded vs rounded."},
            {"target": "먹다 / 목", "english": "to eat / neck", "why": ""},
            {"target": "정 / 종", "english": "affection / bell", "why": ""},
        ],
        drill_prompt="Use a mirror. Your lips are the giveaway.",
        tags=("pronunciation", "vowels"),
    ),
    "ae_vs_e": Confusion(
        id="ae_vs_e",
        a="ㅐ", b="ㅔ",
        title="ㅐ versus ㅔ",
        one_line="Almost nobody in Seoul distinguishes these any more — but they are spelled differently.",
        simple=(
            "Good news: these two sound nearly identical in modern Korean, and "
            "native speakers mix them up too. The bad news is that spelling "
            "still keeps them apart, so this is a memorisation problem, not a "
            "listening one. Learn it per word."
        ),
        rule=(
            "Historically /ɛ/ versus /e/. The contrast has merged for most "
            "speakers under 40. Spelling remains distinct, so it must be learned "
            "lexically: 개 (dog) versus 게 (crab)."
        ),
        examples=[
            {"target": "개 / 게", "english": "dog / crab", "why": "Identical in speech, distinct in writing."},
            {"target": "네 / 내", "english": "yes, your / my",
             "why": "Speakers often say 니 for 네 just to keep these apart."},
        ],
        drill_prompt="Do not try to hear the difference. Learn which spelling each word takes.",
        tags=("pronunciation", "spelling"),
    ),
    "go_itda_vs_a_itda": Confusion(
        id="go_itda_vs_a_itda",
        a="-고 있다", b="-아/어 있다",
        title="-고 있다 versus -아/어 있다",
        one_line="-고 있다 is doing it. -아/어 있다 is the state left behind.",
        simple=(
            "앉고 있어요 means you are in the middle of lowering yourself onto "
            "the chair. 앉아 있어요 means you already sat down and you are "
            "sitting there now."
        ),
        rule=(
            "-고 있다 marks progressive aspect. -아/어 있다 marks a resultant "
            "state and only attaches to intransitive verbs of change "
            "(가다, 오다, 앉다, 서다, 열리다)."
        ),
        examples=[
            {"target": "문을 열고 있어요.", "english": "I'm opening the door.", "why": "In progress."},
            {"target": "문이 열려 있어요.", "english": "The door is open.", "why": "The resulting state."},
        ],
        drill_prompt="In the middle of it, or finished and still like that?",
        tags=("aspect", "B1"),
    ),
}


#: (expected, given) -> confusion id, for every allomorph combination.
PAIR_INDEX = index_confusions(CONFUSIONS, "ko")
