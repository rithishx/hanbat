"""Author the HSK1 core vocabulary file.

Written as a script rather than by hand because 150 rows of JSON is
unreviewable, and because every pinyin string is checked against the pinyin
engine before the file is written. A typo in a tone mark is invisible in a diff
and very visible to a learner.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.languages.mandarin import pinyin as P  # noqa: E402

FIELDS = ["id", "term", "pinyin", "meaning", "pos", "topic", "level", "freq",
          "example_native", "example_en", "note", "counter"]

# term, pinyin, meaning, pos, topic, freq, example, example_en, note, measure word
W: list[tuple] = [
    # -- people and pronouns --------------------------------------------
    ("我", "wǒ", "I, me", "pronoun", "people", 8, "我是学生。", "I am a student.", "", ""),
    ("你", "nǐ", "you", "pronoun", "people", 12, "你好吗？", "How are you?", "", ""),
    ("您", "nín", "you (polite)", "pronoun", "people", 300, "您好！", "Hello (polite).",
     "Use it with elders, teachers, customers. Beijing speakers use it far more than southerners.", ""),
    ("他", "tā", "he, him", "pronoun", "people", 15, "他是老师。", "He is a teacher.", "", ""),
    ("她", "tā", "she, her", "pronoun", "people", 40, "她很高兴。", "She is happy.",
     "Identical in speech to 他. Only the writing distinguishes them.", ""),
    ("我们", "wǒmen", "we, us", "pronoun", "people", 60, "我们去学校。", "We're going to school.",
     "们 is neutral tone.", ""),
    ("谁", "shéi", "who", "pronoun", "question", 200, "他是谁？", "Who is he?",
     "Also read shuí in careful speech; shéi is what you will hear.", ""),
    ("人", "rén", "person", "noun", "people", 20, "那个人是我朋友。", "That person is my friend.", "", "个"),
    ("名字", "míngzi", "name", "noun", "people", 500, "你叫什么名字？", "What's your name?", "", "个"),
    ("朋友", "péngyou", "friend", "noun", "people", 250, "他是我的朋友。", "He is my friend.", "", "个"),
    ("老师", "lǎoshī", "teacher", "noun", "school", 400, "王老师很好。", "Teacher Wang is very good.",
     "Used as a title after the surname: 王老师, not 老师王.", "位"),
    ("学生", "xuésheng", "student", "noun", "school", 350, "我是学生。", "I am a student.", "", "个"),
    ("医生", "yīshēng", "doctor", "noun", "work", 800, "我要看医生。", "I need to see a doctor.", "", "位"),
    ("先生", "xiānsheng", "Mr; sir", "noun", "people", 600, "李先生在吗？", "Is Mr Li in?",
     "Goes after the surname, like 老师.", "位"),
    ("小姐", "xiǎojiě", "Miss", "noun", "people", 900, "王小姐。", "Miss Wang.",
     "Increasingly avoided in mainland China, where it can be read as an insult. 女士 is safer.", "位"),
    ("爸爸", "bàba", "dad", "noun", "family", 700, "我爸爸是医生。", "My dad is a doctor.", "", "个"),
    ("妈妈", "māma", "mum", "noun", "family", 650, "妈妈在家。", "Mum is at home.", "", "个"),
    ("儿子", "érzi", "son", "noun", "family", 900, "他有一个儿子。", "He has one son.", "", "个"),
    ("女儿", "nǚ'ér", "daughter", "noun", "family", 950, "我女儿六岁。", "My daughter is six.",
     "The apostrophe marks where one syllable ends and the next begins: nǚ-ér, not nǚr.", "个"),
    ("同学", "tóngxué", "classmate", "noun", "school", 1000, "他是我的同学。", "He's my classmate.", "", "个"),
    ("中国", "Zhōngguó", "China", "noun", "places", 100, "我去过中国。", "I've been to China.",
     "Written with a full second tone on 国 — not neutral, despite 'guo' being neutral elsewhere.", "个"),
    ("北京", "Běijīng", "Beijing", "noun", "places", 500, "我住在北京。", "I live in Beijing.", "", ""),

    # -- numbers --------------------------------------------------------
    ("一", "yī", "one", "number", "numbers", 5, "一个人", "one person",
     "Changes tone depending on what follows: yí before a fourth tone, yì before the others, yī when counting.", ""),
    ("二", "èr", "two", "number", "numbers", 30, "二十", "twenty",
     "For counting. To say 'two of something' you need 两, not 二.", ""),
    ("三", "sān", "three", "number", "numbers", 45, "三个人", "three people", "", ""),
    ("四", "sì", "four", "number", "numbers", 55, "四本书", "four books",
     "Avoided in some contexts — it sounds close to 死 sǐ, 'death'.", ""),
    ("五", "wǔ", "five", "number", "numbers", 60, "五点", "five o'clock", "", ""),
    ("六", "liù", "six", "number", "numbers", 90, "六个月", "six months", "", ""),
    ("七", "qī", "seven", "number", "numbers", 110, "七天", "seven days", "", ""),
    ("八", "bā", "eight", "number", "numbers", 100, "八个", "eight (of them)",
     "A lucky number — it sounds like 发 fā, 'to prosper'.", ""),
    ("九", "jiǔ", "nine", "number", "numbers", 120, "九月", "September", "", ""),
    ("十", "shí", "ten", "number", "numbers", 50, "十个人", "ten people", "", ""),
    ("零", "líng", "zero", "number", "numbers", 400, "二零二六年", "the year 2026", "", ""),
    ("几", "jǐ", "how many (small numbers)", "question", "numbers", 200,
     "你有几个？", "How many do you have?", "Expects an answer under about ten. For larger, use 多少.", ""),
    ("多少", "duōshao", "how many, how much", "question", "numbers", 300,
     "多少钱？", "How much money?", "少 is neutral here.", ""),
    ("两", "liǎng", "two (of something)", "number", "numbers", 150, "两个人", "two people",
     "Use 两 before a measure word, 二 for counting and numbers. 两个 is right; 二个 is not.", ""),

    # -- time -----------------------------------------------------------
    ("今天", "jīntiān", "today", "noun", "time", 200, "今天很热。", "It's hot today.", "", ""),
    ("明天", "míngtiān", "tomorrow", "noun", "time", 250, "明天见！", "See you tomorrow!", "", ""),
    ("昨天", "zuótiān", "yesterday", "noun", "time", 300, "昨天我去了学校。", "I went to school yesterday.", "", ""),
    ("年", "nián", "year", "noun", "time", 40, "今年", "this year", "", ""),
    ("月", "yuè", "month; moon", "noun", "time", 70, "三月", "March",
     "The months are just numbers: 一月 is January, 十二月 December.", "个"),
    ("日", "rì", "day; sun", "noun", "time", 80, "十月一日", "1 October",
     "Formal or written. In speech people say 号.", ""),
    ("号", "hào", "day of the month; number", "noun", "time", 200, "今天几号？", "What's the date today?", "", ""),
    ("星期", "xīngqī", "week", "noun", "time", 350, "星期一", "Monday",
     "Days are numbered: 星期一 Monday through 星期六 Saturday, then 星期天 for Sunday.", "个"),
    ("点", "diǎn", "o'clock; a dot", "noun", "time", 150, "三点", "three o'clock", "", ""),
    ("分钟", "fēnzhōng", "minute", "noun", "time", 600, "五分钟", "five minutes", "", ""),
    ("现在", "xiànzài", "now", "noun", "time", 180, "现在几点？", "What time is it now?", "", ""),
    ("时候", "shíhou", "time, moment", "noun", "time", 220, "什么时候？", "When?",
     "候 is neutral. 什么时候 is the normal way to ask 'when'.", ""),
    ("上午", "shàngwǔ", "morning", "noun", "time", 700, "上午九点", "9 a.m.", "", ""),
    ("中午", "zhōngwǔ", "noon", "noun", "time", 800, "中午吃饭", "eat lunch at noon", "", ""),
    ("下午", "xiàwǔ", "afternoon", "noun", "time", 650, "下午见。", "See you this afternoon.", "", ""),

    # -- core verbs -----------------------------------------------------
    ("是", "shì", "to be", "verb", "core", 4, "我是学生。", "I am a student.",
     "Only links nouns. With an adjective you use 很 instead: 我很高, never 我是高.", ""),
    ("有", "yǒu", "to have; there is", "verb", "core", 10, "我有一本书。", "I have a book.",
     "Its negative is always 没有, never 不有. It is the one verb that refuses 不.", ""),
    ("在", "zài", "at, in; to be at", "verb", "core", 6, "我在家。", "I'm at home.",
     "Also goes before a verb to mark an action in progress: 我在吃饭, 'I'm eating'.", ""),
    ("看", "kàn", "to look, to watch, to read", "verb", "core", 90, "我看书。", "I read books.", "", ""),
    ("听", "tīng", "to listen", "verb", "core", 200, "听音乐", "listen to music", "", ""),
    ("说", "shuō", "to speak, to say", "verb", "core", 30, "他说汉语。", "He speaks Chinese.", "", ""),
    ("读", "dú", "to read aloud", "verb", "school", 500, "读书", "to read; to study", "", ""),
    ("写", "xiě", "to write", "verb", "school", 400, "写字", "to write characters", "", ""),
    ("叫", "jiào", "to be called; to call", "verb", "core", 250, "我叫李明。", "My name is Li Ming.", "", ""),
    ("来", "lái", "to come", "verb", "core", 35, "他明天来。", "He's coming tomorrow.", "", ""),
    ("去", "qù", "to go", "verb", "core", 45, "我去学校。", "I'm going to school.", "", ""),
    ("回", "huí", "to return", "verb", "core", 300, "我回家。", "I'm going home.", "", ""),
    ("吃", "chī", "to eat", "verb", "food", 150, "我吃饭。", "I'm eating.", "", ""),
    ("喝", "hē", "to drink", "verb", "food", 400, "喝水", "drink water", "", ""),
    ("睡觉", "shuìjiào", "to sleep", "verb", "daily", 900, "我要睡觉了。", "I'm going to sleep.",
     "A verb-object compound: things go in the middle, as in 睡了三个小时的觉.", ""),
    ("做", "zuò", "to do, to make", "verb", "core", 100, "你做什么？", "What are you doing?", "", ""),
    ("买", "mǎi", "to buy", "verb", "shopping", 350, "我买了一本书。", "I bought a book.",
     "买 mǎi and 卖 mài differ by one tone and mean opposite things.", ""),
    ("开", "kāi", "to open; to drive", "verb", "core", 120, "开门", "open the door", "", ""),
    ("坐", "zuò", "to sit; to travel by", "verb", "core", 200, "坐飞机", "go by plane", "", ""),
    ("住", "zhù", "to live, to stay", "verb", "daily", 400, "我住在北京。", "I live in Beijing.", "", ""),
    ("学习", "xuéxí", "to study", "verb", "school", 300, "我学习汉语。", "I study Chinese.", "", ""),
    ("工作", "gōngzuò", "to work; work", "verb", "work", 250, "他在医院工作。", "He works at a hospital.", "", ""),
    ("认识", "rènshi", "to know (a person)", "verb", "core", 500, "很高兴认识你。", "Nice to meet you.",
     "For people and places. For facts you need 知道.", ""),
    ("想", "xiǎng", "to want; to think; to miss", "verb", "core", 110, "我想喝茶。", "I'd like some tea.", "", ""),
    ("爱", "ài", "to love", "verb", "core", 300, "我爱你。", "I love you.", "", ""),
    ("喜欢", "xǐhuan", "to like", "verb", "core", 400, "我喜欢猫。", "I like cats.", "欢 is neutral.", ""),
    ("请", "qǐng", "please; to invite", "verb", "courtesy", 200, "请坐。", "Please sit down.", "", ""),
    ("会", "huì", "can (learned skill); will", "verb", "core", 25, "我会说汉语。", "I can speak Chinese.",
     "For skills you acquired. For ability or permission, 能.", ""),
    ("能", "néng", "can, to be able to", "verb", "core", 40, "我今天不能来。", "I can't come today.", "", ""),
    ("下雨", "xià yǔ", "to rain", "verb", "weather", 900, "下雨了。", "It's started raining.",
     "Literally 'fall rain'. The 了 marks the change, not the past.", ""),
    ("打电话", "dǎ diànhuà", "to make a phone call", "verb", "daily", 800,
     "我给他打电话。", "I'll call him.", "Literally 'hit telephone'.", ""),

    # -- adjectives -----------------------------------------------------
    ("好", "hǎo", "good", "adjective", "core", 14, "很好。", "Very good.", "", ""),
    ("大", "dà", "big", "adjective", "core", 25, "很大", "very big", "", ""),
    ("小", "xiǎo", "small", "adjective", "core", 35, "很小", "very small", "", ""),
    ("多", "duō", "many, much", "adjective", "core", 20, "人很多。", "There are a lot of people.", "", ""),
    ("少", "shǎo", "few, little", "adjective", "core", 130, "很少", "very few",
     "Third tone here. In 多少 it is neutral.", ""),
    ("冷", "lěng", "cold", "adjective", "weather", 600, "今天很冷。", "It's cold today.", "", ""),
    ("热", "rè", "hot", "adjective", "weather", 500, "天气很热。", "The weather is hot.", "", ""),
    ("高兴", "gāoxìng", "happy, pleased", "adjective", "feelings", 700,
     "我很高兴。", "I'm very happy.", "", ""),
    ("漂亮", "piàoliang", "pretty, beautiful", "adjective", "description", 900,
     "她很漂亮。", "She's very pretty.", "亮 is neutral.", ""),

    # -- everyday nouns -------------------------------------------------
    ("家", "jiā", "home, family", "noun", "places", 60, "我在家。", "I'm at home.", "", "个"),
    ("学校", "xuéxiào", "school", "noun", "school", 300, "我去学校。", "I'm going to school.", "", "个"),
    ("饭馆", "fànguǎn", "restaurant", "noun", "places", 1200, "我们去饭馆吃饭。",
     "Let's eat at a restaurant.", "", "家"),
    ("商店", "shāngdiàn", "shop", "noun", "places", 900, "商店在那儿。", "The shop is over there.", "", "家"),
    ("医院", "yīyuàn", "hospital", "noun", "places", 800, "他在医院。", "He's at the hospital.", "", "家"),
    ("火车站", "huǒchēzhàn", "train station", "noun", "places", 1500,
     "火车站在哪儿？", "Where is the train station?", "", "个"),
    ("桌子", "zhuōzi", "table", "noun", "objects", 1000, "书在桌子上。", "The book is on the table.",
     "子 is neutral — it is a noun suffix, not a word.", "张"),
    ("椅子", "yǐzi", "chair", "noun", "objects", 1100, "两把椅子", "two chairs", "", "把"),
    ("书", "shū", "book", "noun", "objects", 200, "我看书。", "I'm reading.", "", "本"),
    ("电视", "diànshì", "television", "noun", "objects", 500, "看电视", "watch TV", "", "台"),
    ("电脑", "diànnǎo", "computer", "noun", "objects", 600, "我的电脑很新。", "My computer is new.",
     "Literally 'electric brain'.", "台"),
    ("电影", "diànyǐng", "film, movie", "noun", "leisure", 550, "看电影", "watch a film", "", "部"),
    ("天气", "tiānqì", "weather", "noun", "weather", 700, "今天天气很好。", "The weather is good today.", "", ""),
    ("猫", "māo", "cat", "noun", "animals", 1200, "我有一只猫。", "I have a cat.", "", "只"),
    ("狗", "gǒu", "dog", "noun", "animals", 1100, "那只狗很大。", "That dog is big.", "", "只"),
    ("东西", "dōngxi", "thing", "noun", "objects", 300, "买东西", "go shopping",
     "Literally 'east west'. 西 is neutral here; said with a full tone it means 'east and west'.", "个"),
    ("米饭", "mǐfàn", "cooked rice", "noun", "food", 1300, "一碗米饭", "a bowl of rice", "", "碗"),
    ("菜", "cài", "dish; vegetable", "noun", "food", 400, "这个菜很好吃。", "This dish is delicious.", "", "个"),
    ("水", "shuǐ", "water", "noun", "food", 150, "我要喝水。", "I want some water.", "", "杯"),
    ("水果", "shuǐguǒ", "fruit", "noun", "food", 900, "我喜欢吃水果。", "I like fruit.", "", ""),
    ("苹果", "píngguǒ", "apple", "noun", "food", 1400, "两个苹果", "two apples", "", "个"),
    ("茶", "chá", "tea", "noun", "food", 600, "喝茶", "drink tea", "", "杯"),
    ("杯子", "bēizi", "cup, glass", "noun", "objects", 1200, "一个杯子", "a cup", "", "个"),
    ("钱", "qián", "money", "noun", "shopping", 200, "多少钱？", "How much?", "", ""),
    ("飞机", "fēijī", "aeroplane", "noun", "travel", 800, "坐飞机", "go by plane", "", "架"),
    ("出租车", "chūzūchē", "taxi", "noun", "travel", 1600, "坐出租车", "take a taxi",
     "In speech, 打车 is far more common.", "辆"),
    ("衣服", "yīfu", "clothes", "noun", "objects", 700, "买衣服", "buy clothes", "服 is neutral.", "件"),
    ("字", "zì", "character", "noun", "school", 350, "这个字怎么读？", "How is this character read?", "", "个"),
    ("汉语", "Hànyǔ", "Chinese (language)", "noun", "school", 900, "我学汉语。", "I study Chinese.",
     "中文 is the other common word; 汉语 emphasises the spoken language.", ""),

    # -- position and direction -----------------------------------------
    ("上", "shàng", "on, above; to go up", "noun", "position", 15, "桌子上", "on the table", "", ""),
    ("下", "xià", "under, below; next", "noun", "position", 22, "椅子下", "under the chair", "", ""),
    ("里", "lǐ", "inside", "noun", "position", 30, "家里", "at home, inside the house", "", ""),
    ("前面", "qiánmiàn", "in front", "noun", "position", 600, "学校在前面。", "The school is up ahead.", "", ""),
    ("后面", "hòumiàn", "behind", "noun", "position", 650, "他在我后面。", "He's behind me.", "", ""),

    # -- question words and demonstratives ------------------------------
    ("什么", "shénme", "what", "question", "question", 50, "这是什么？", "What is this?",
     "么 is neutral. It stays where the answer would go — Mandarin does not front question words.", ""),
    ("怎么", "zěnme", "how", "question", "question", 100, "怎么去？", "How do we get there?", "", ""),
    ("怎么样", "zěnmeyàng", "how about it, how is it", "question", "question", 400,
     "今天天气怎么样？", "How's the weather today?", "", ""),
    ("为什么", "wèishénme", "why", "question", "question", 200, "你为什么不来？",
     "Why aren't you coming?", "", ""),
    ("哪", "nǎ", "which", "question", "question", 150, "哪个？", "Which one?", "", ""),
    ("哪儿", "nǎr", "where", "question", "question", 250, "你在哪儿？", "Where are you?",
     "Northern. In the south you will hear 哪里 nǎlǐ instead.", ""),
    ("这", "zhè", "this", "pronoun", "core", 18, "这是我的书。", "This is my book.", "", ""),
    ("那", "nà", "that", "pronoun", "core", 24, "那个人", "that person", "", ""),

    # -- adverbs and particles ------------------------------------------
    ("不", "bù", "not", "adverb", "grammar", 3, "我不去。", "I'm not going.",
     "Drops to bú before a fourth tone: 不是 is bú shì.", ""),
    ("没", "méi", "not (did not; do not have)", "adverb", "grammar", 26,
     "我没去。", "I didn't go.", "For things that did not happen, and always with 有.", ""),
    ("很", "hěn", "very", "adverb", "grammar", 28, "我很好。", "I'm fine.",
     "Often carries no real emphasis — it is what an adjective needs in order to stand as a predicate.", ""),
    ("太", "tài", "too, excessively", "adverb", "grammar", 90, "太贵了！", "Too expensive!",
     "Usually paired with a final 了.", ""),
    ("都", "dōu", "all, both", "adverb", "grammar", 45, "我们都是学生。", "We're all students.",
     "Goes before the verb, never after the subject it refers to.", ""),
    ("和", "hé", "and; with", "conjunction", "grammar", 16, "我和他", "he and I",
     "Joins nouns only. It cannot join two sentences the way English 'and' does.", ""),
    ("的", "de", "possessive / descriptive particle", "particle", "grammar", 1,
     "我的书", "my book", "The most common character in the language. Always neutral.", ""),
    ("了", "le", "completion / change particle", "particle", "grammar", 2,
     "我吃了。", "I've eaten.", "Not the past tense. It marks that something finished or changed.", ""),
    ("吗", "ma", "question particle", "particle", "grammar", 40, "你好吗？", "How are you?",
     "Turns a statement into a yes/no question without changing the word order.", ""),
    ("呢", "ne", "and you? / what about…", "particle", "grammar", 70, "我很好，你呢？",
     "I'm fine, and you?", "", ""),

    # -- measure words and courtesy -------------------------------------
    ("个", "gè", "general measure word", "measure", "grammar", 7, "三个人", "three people",
     "The default. When you do not know the right one, use 个.", ""),
    ("本", "běn", "measure word for books", "measure", "grammar", 300, "一本书", "one book", "", ""),
    ("些", "xiē", "some, a few", "measure", "grammar", 250, "这些书", "these books",
     "Only after 一, 这 and 那.", ""),
    ("岁", "suì", "years of age", "measure", "grammar", 400, "他六岁。", "He is six years old.", "", ""),
    ("块", "kuài", "unit of currency; piece", "measure", "shopping", 350, "十块钱", "ten yuan",
     "The spoken word for yuan. 元 is what is printed.", ""),
    ("谢谢", "xièxie", "thank you", "expression", "courtesy", 200, "谢谢你！", "Thank you!", "", ""),
    ("再见", "zàijiàn", "goodbye", "expression", "courtesy", 300, "再见！", "Goodbye!",
     "Literally 'again see'.", ""),
    ("对不起", "duìbuqǐ", "sorry", "expression", "courtesy", 500, "对不起！", "I'm sorry!", "", ""),
    ("没关系", "méi guānxi", "it doesn't matter", "expression", "courtesy", 700,
     "没关系。", "That's all right.", "The standard reply to 对不起.", ""),
    ("喂", "wéi", "hello (on the phone)", "expression", "courtesy", 800, "喂，你好。",
     "Hello?", "Said with a rising tone on the phone; the falling wèi is used to call out to someone.", ""),
]


def main() -> int:
    problems: list[str] = []
    seen: set[str] = set()
    words = []
    for i, row in enumerate(W, start=1):
        term, py, meaning, pos, topic, freq, ex, ex_en, note, counter = row
        wid = f"zh-v-{i:04d}"
        if term in seen:
            problems.append(f"{wid}: duplicate term {term}")
        seen.add(term)
        for syllable in P.segment(py):
            s = P.parse(syllable)
            if not s.valid:
                problems.append(f"{wid} ({term}): {syllable!r} in {py!r} is not "
                                f"valid pinyin — {s.note}")
        # One character, one syllable — except 儿化, where the 儿 is written as
        # a character but pronounced as an -r on the syllable before it.
        syllables = [P.parse(x) for x in P.segment(py)]
        expected = len(syllables) + sum(1 for s in syllables if s.erhua)
        characters = sum(1 for c in term if ord(c) > 0x2E80)
        if expected != characters:
            problems.append(f"{wid} ({term}): {py!r} accounts for {expected} "
                            f"characters but the term has {characters}")
        # Every column must be Chinese, pinyin or English. A stray Hangul or
        # kana character means a row was copied from the wrong language file.
        for col in (term, meaning, ex, ex_en, note):
            for ch in col:
                if "가" <= ch <= "힯" or "぀" <= ch <= "ヿ":
                    problems.append(f"{wid}: non-Chinese script {ch!r} in {col!r}")
                if "Ѐ" <= ch <= "ӿ":
                    problems.append(f"{wid}: Cyrillic {ch!r} in {col!r}")
        # The term and the Chinese example must contain no Latin letters. This
        # is the check that catches an English placeholder left in a sentence,
        # which reads as a real word to anyone who cannot yet read the rest.
        for col, label in ((term, "term"), (ex, "example")):
            if any(c.isascii() and c.isalpha() for c in col):
                problems.append(f"{wid}: Latin letters in the {label} {col!r}")
        words.append([wid, term, py, meaning, pos, topic, "HSK1", freq,
                      ex, ex_en, note, counter])

    if problems:
        for p in problems:
            print("PROBLEM:", p)
        return 1

    doc = {
        "language": "zh",
        "format": "columnar",
        "format_note": (
            "`pinyin` is authored rather than derived. Korean romanisation and "
            "Japanese romaji can be computed from the spelling; pinyin cannot be "
            "computed from characters, because 行 is xíng in 不行 and háng in "
            "银行. `counter` holds the word's usual measure word, which every "
            "counted Mandarin noun needs."
        ),
        "level": "HSK1",
        "fields": FIELDS,
        "words": words,
    }
    out = Path(__file__).resolve().parents[1] / "content/zh/vocab/core.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"wrote {len(words)} words to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
