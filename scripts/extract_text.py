"""
Automated Text Extractor for Rosario + Vampire Capu 2: Koi to Yume no Rhapsodia (PS2, SLPM_551.89).
Extracts all real dialogue, branching choices, location banners, custom-encoded UI/save/menu strings,
and Shift-JIS system strings into structured, human-readable JSON files in extracted_text/.
Pre-populates a playable English Vertical Slice (Opening scripts e100000..e101000 + Menus/UI/Save).
Pure Python - zero external dependencies.
"""

import re
import struct
from pathlib import Path
from typing import Dict, List, Tuple
from iso_tool import IsoHandler
from afs_tool import AfsArchive
from pac_tool import PacArchive
from lzr_tool import decompress_lzr, extract_evb_strings
from font_mapper import decode_game_string
from translation_manager import TranslationProject, DEFAULT_LANGUAGES


# Full English & Multi-Language Dictionary and Grammar Engine for UI / Menu / Save / Chapter strings
EXACT_UI_MAP: Dict[str, str] = {
    "このデータをワードしてよろしいですか？": "Load data?",
    "データをワードしています": "Loading...",
    "データのワードに成光しました": "Load failed.",
    "上書きしてよろしいですか？": "Overwrite?",
    "この場所にセーブしますか？": "Save here?",
    "データをセーブしました．": "Data saved.",
    "セーブしておりませんが，次に進みますか？": "No save. Continue?",
    "変更したプヮイ甘境をセーブしますか？": "Save settings?",
    "システムデータを保存しますか？": "Save sys data?",
    "クルア情褒を保存しますか？": "Save clear?",
    "タイトロに戻りますか？": "To Title?",
    "０１２３４５６７８９": "0123456789",
    "データがありません": "No Data",
    "６月１５日": "Jun15",
    "６月１６日": "Jun16",
    "６月１７日": "Jun17",
    "６月１８日": "Jun18",
    "６月１９日": "Jun19",
    "６月２０日": "Jun20",
    "６月２１日": "Jun21",
    "６月２２日": "Jun22",
    "６月２３日": "Jun23",
    "６月２４日": "Jun24",
    "陽海学園全継": "School",
    "渡り廊下": "Hall",
    "新聞部部室": "Club",
    "ファンクリブ連合部室": "Fan Club",
    "月音の部屋": "Room",
    "学生食堂": "Cafe",
    "調理実習室": "Cook",
    "学校近くの池": "Pond",
    "西洋墓地": "Tomb",
    "リイブステージ": "Stage",
    "エンディング": "Ending",
    "システム（メッセージなし）": "System (No Message)",
}

TERM_UI_MAP: Dict[str, str] = {
    "６月１５日": "Jun 15",
    "６月１６日": "Jun 16",
    "６月１７日": "Jun 17",
    "６月１８日": "Jun 18",
    "６月19日": "Jun 19",
    "６月１９日": "Jun 19",
    "６月２０日": "Jun 20",
    "６月２１日": "Jun 21",
    "６月２２日": "Jun 22",
    "６月２３日": "Jun 23",
    "６月２４日": "Jun 24",
    "放課後": "After School",
    "逆転": "Turnabout",
    "いつもの朝": "Morning",
    "生活指輩": "Guidance",
    "スタート": "Start",
    "くじびき": "Lottery",
    "ボーカロ": "Vocal",
    "歌詞": "Lyrics",
    "素直": "Honest",
    "限界": "Limit",
    "下校": "Going Home",
    "夜": "Night",
    "シロエット": "Silhouette",
    "テヮビ": "TV",
    "セーブ": "Save",
    "無人": "Alone",
    "朝": "Morning",
    "知らない姿": "Secret Form",
    "エスケープ": "Escape",
    "奉返し": "Repay",
    "誤解": "Mistake",
    "媚薬": "Love Potion",
    "極がり街": "City",
    "デート": "Date",
    "対立": "Rivalry",
    "休日": "Holiday",
    "お掃姿": "Cleaning",
    "ノート": "Notebook",
    "炎日": "Hot Day",
    "ドリム": "Dream",
    "おんぶ": "Piggyback",
    "不良": "Delinquent",
    "海": "Beach",
    "自信": "Confidence",
    "報伝": "Tradition",
    "ヘッドフォン": "Headphones",
    "リジカセ": "Boombox",
    "バイト": "Part-Time",
    "ケンカ": "Brawl",
    "新生日": "New Day",
    "禁血": "Taboo Blood",
    "直前": "Eve",
    "手紙": "Letter",
    "新婚": "Newlywed",
    "本番": "Showtime",
    "リイブ": "Live",
    "ストーカー": "Stalker",
    "終終": "Finale",
    "暗闇": "Darkness",
    "怪談": "Ghost Story",
    "さよなら": "Farewell",
    "旅行": "Trip",
    "遭謎": "Mystery",
    "太鼓": "Drums",
    "毒然": "Sudden",
    "暴走": "Rampage",
    "輩入": "Enter",
    "新聞部編": "News Club Arc",
    "コウモル": "Bat",
    "バンパイア": "Vampire",
    "新聞部": "News Club",
    "カリス": "Karis",
    "雪女": "Snow Woman",
    "妹": "Sister",
    "御人父": "Father",
    "月音": "Tsukune",
    "セイヮーン": "Siren",
    "三姉妹": "3 Sisters",
    "ウェアウロフ": "Werewolf",
    "オーク": "Orc",
    "師弟": "Master",
    "カリカサ": "Karikasa",
    "ワクワ酒": "Wine",
    "のっぺら坊": "Faceless",
    "焼血": "Blood",
    "サキュバス": "Succubus",
    "インタビュー": "Interview",
    "オタク": "Otaku",
    "化け猫": "Bakeneko",
    "噂転手さん": "Driver",
    "ペッタンコ": "Flatty",
    "次女": "2nd Sister",
    "三女": "3rd Sister",
    "鬼教師": "Ogre Teacher",
    "魔女": "Witch",
    "ケンカ友達": "Rival",
    "ファン": "Fan",
    "パシル": "Pacil",
    "ＳとＭ": "S & M",
    "プリス": "Pris",
}


def translate_ui_string(ja: str, max_bytes: int) -> str:
    """
    Translates custom 16-bit encoded UI, menu, save prompt, or chapter title string
    and guarantees it fits within max_bytes.
    """
    if ja in EXACT_UI_MAP:
        res = EXACT_UI_MAP[ja]
    elif "と" in ja:
        parts = ja.split("と", 1)
        p1, p2 = parts[0], parts[1]
        num_suffix = ""
        m_num = re.search(r"[：:]\s*([０-９0-9’']+)", p2)
        if m_num:
            raw_num = m_num.group(1)
            trans_num = "".join(chr(ord(c) - 0xFEE0) if "０" <= c <= "９" else c for c in raw_num)
            num_suffix = f": {trans_num}"
            p2 = p2[:m_num.start()]
        t1 = TERM_UI_MAP.get(p1, p1)
        t2 = TERM_UI_MAP.get(p2, p2)
        res = f"{t1} & {t2}{num_suffix}"
    else:
        res = TERM_UI_MAP.get(ja, ja)

    res_clean = []
    for c in res:
        if "０" <= c <= "９":
            res_clean.append(chr(ord(c) - 0xFEE0))
        elif "Ａ" <= c <= "Ｚ":
            res_clean.append(chr(ord(c) - 0xFEE0))
        elif "ａ" <= c <= "ｚ":
            res_clean.append(chr(ord(c) - 0xFEE0))
        elif c == "：":
            res_clean.append(":")
        else:
            res_clean.append(c)
    res = "".join(res_clean)

    max_chars = max_bytes // 2
    if len(res) > max_chars:
        res = (
            res.replace(" & ", "&")
            .replace("After School", "AfterSch")
            .replace("Little Sister", "Sister")
            .replace("Snow Woman", "Yukionna")
            .replace("News Club", "News")
        )
        if len(res) > max_chars:
            res = res[:max_chars]
    return res


# Playable Vertical Slice: Opening Chapters (e100000.evb .. e101000.evb)
VERTICAL_SLICE_DIALOGUE: Dict[Tuple[str, str], Dict[str, str]] = {
    # e100000.evb (Title Call / Prologue)
    ("e100000.evb", "0x0044"): {
        "en": "Music Festival in the Blink of a Chu!",
        "es": "¡Festival de Musica en un Chu!",
        "fr": "Festival de Musique en un Chu !",
    },
    # e100010.evb (Opening Dream / Inner & Outer Moka)
    ("e100010.evb", "0x0080"): {
        "en": "Taking Moka hostage...\nHow cowardly,[RUBY]you bastard!",
        "es": "Tomar a Moka como rehen...\n¡Que cobarde,[RUBY]maldito!",
        "fr": "Prendre Moka en otage...\nQuel lache,[RUBY]enfoire !",
    },
    ("e100010.evb", "0x00BC"): {
        "en": "Shut your trap and\nquit whining!",
        "es": "¡Cierra la boca y\ndeja de quejarte!",
        "fr": "Ferme-la et\narrete de pleurnicher !",
    },
    ("e100010.evb", "0x0104"): {
        "en": "Kyaaa!?",
        "es": "¡¿Kyaaa?!",
        "fr": "Kyaaa !?",
    },
    ("e100010.evb", "0x013C"): {
        "en": "Moka!",
        "es": "¡Moka!",
        "fr": "Moka !",
    },
    ("e100010.evb", "0x01B4"): {
        "en": "Run away...\nAt least save yourself, Tsukune...",
        "es": "Huye...\nAl menos salvate tu, Tsukune...",
        "fr": "Fuis...\nSauve-toi au moins, Tsukune...",
    },
    ("e100010.evb", "0x01DC"): {
        "en": "Ah...",
        "es": "Ah...",
        "fr": "Ah...",
    },
    ("e100010.evb", "0x01F8"): {
        "en": "Moka-san's hand is\nreaching for my Rosario...",
        "es": "La mano de Moka-san\ntoca mi Rosario...",
        "fr": "La main de Moka-san\ntouche mon Rosaire...",
    },
    ("e100010.evb", "0x0234"): {
        "en": "The Rosario...\ncame off!?",
        "es": "¿¡El Rosario...\nse solto!?",
        "fr": "Le Rosaire...\ns'est detache !?",
    },
    ("e100010.evb", "0x02B8"): {
        "en": "Silver hair, crimson eyes,\nand overwhelming Yoki!",
        "es": "¡Cabello plateado, ojos carmesi,\ny una energia abrumadora!",
        "fr": "Cheveux d'argent, yeux pourpres,\net une aura ecrasante !",
    },
    ("e100010.evb", "0x02F0"): {
        "en": "So this is the legendary\nS-Class monster...",
        "es": "Asi que este es el monstruo\nde Clase S...",
        "fr": "Voici donc le legendaire\nmonstre de classe S...",
    },
    ("e100010.evb", "0x0320"): {
        "en": "...",
        "es": "...",
        "fr": "...",
    },
    ("e100010.evb", "0x0334"): {
        "en": "A vampire!?",
        "es": "¡¿Un vampiro?!",
        "fr": "Un vampire !?",
    },
    ("e100010.evb", "0x035C"): {
        "en": "Are you the one who\ndared disturb my slumber?",
        "es": "¿Eres tu quien oso\nperturbar mi sueno?",
        "fr": "Est-ce toi qui oses\ntroubler mon sommeil ?",
    },
    ("e100010.evb", "0x038C"): {
        "en": "W-What!? My body won't move!\nNo way...",
        "es": "¡¿Que?! ¡Mi cuerpo no se mueve!\nNo puede ser...",
        "fr": "Quoi !? Mon corps ne bouge plus !\nImpossible...",
    },
    ("e100010.evb", "0x03B8"): {
        "en": "Just from being\nglared at!?",
        "es": "¡¿Solo con\nmirarme?!",
        "fr": "Juste d'un simple\nregard !?",
    },
    ("e100010.evb", "0x03EC"): {
        "en": "Hmph.\nAre you trembling?",
        "es": "Ja.\n¿Estas temblando?",
        "fr": "Hmph.\nTu trembles ?",
    },
    ("e100010.evb", "0x0414"): {
        "en": "You pathetic,\ninsignificant fool.",
        "es": "Que patetico y\nmiserable necio.",
        "fr": "Pathetique et\nmiserable idiot.",
    },
    ("e100010.evb", "0x0440"): {
        "en": "Me!? Trembling!?\nDon't make me laugh!",
        "es": "¡¿Yo, temblando?!\n¡No me hagas reir!",
        "fr": "Moi !? Trembler !?\nNe me fais pas rire !",
    },
    ("e100010.evb", "0x0484"): {
        "en": "Don't screw with meee!",
        "es": "¡No te burles de miii!",
        "fr": "Te fous pas de moiii !",
    },
    ("e100010.evb", "0x04AC"): {
        "en": "Know your place.",
        "es": "Conoce tu lugar.",
        "fr": "Connais ta place.",
    },
    ("e100010.evb", "0x0520"): {
        "en": "Gwaaaaah!?",
        "es": "¡¿Gwaaaaah?!",
        "fr": "Gwaaaaah !?",
    },
    ("e100010.evb", "0x05C4"): {
        "en": "So I really was a vampire...",
        "es": "Asi que realmente era un vampiro...",
        "fr": "J'etais donc vraiment un vampire...",
    },
    ("e100010.evb", "0x05F8"): {
        "en": "I'm sorry for hiding it, Moka...\nAre you hurt anywhere?",
        "es": "Perdon por ocultarlo, Moka...\n¿Te duele algo?",
        "fr": "Desole de te l'avoir cache, Moka...\nTu es blessee ?",
    },
    ("e100010.evb", "0x0690"): {
        "en": "I'm alright, really...",
        "es": "Estoy bien, de verdad...",
        "fr": "Je vais bien, vraiment...",
    },
    ("e100010.evb", "0x06B8"): {
        "en": "You scraped your knee...\nYou shouldn't lie to me.",
        "es": "Te raspaste la rodilla...\nNo debes mentirme.",
        "fr": "Ton genou est ecorche...\nTu ne dois pas mentir.",
    },
    ("e100010.evb", "0x06F8"): {
        "en": "I'm sorry...\nI just didn't want you to worry...",
        "es": "Lo siento...\nNo queria preocuparte...",
        "fr": "Pardon...\nJe ne voulais pas t'inquieter...",
    },
    ("e100010.evb", "0x073C"): {
        "en": "Please don't hold back with me...",
        "es": "No te contengas conmigo...",
        "fr": "Ne te retiens pas avec moi...",
    },
    ("e100010.evb", "0x076C"): {
        "en": "Thank you...",
        "es": "Gracias...",
        "fr": "Merci...",
    },
    ("e100010.evb", "0x0790"): {
        "en": "(What is this sweet scent...?)",
        "es": "(¿Que es este dulce aroma...?)",
        "fr": "(Quel est ce doux parfum... ?)",
    },
    ("e100010.evb", "0x07C4"): {
        "en": "We can't let germs get in...\nLet me disinfect it.",
        "es": "No dejemos que se infecte...\nLo desinfectare.",
        "fr": "Il faut desinfecter la plaie...",
    },
    ("e100010.evb", "0x0808"): {
        "en": "Ngh...",
        "es": "Ngh...",
        "fr": "Ngh...",
    },
    ("e100010.evb", "0x0824"): {
        "en": "Does it hurt?",
        "es": "¿Te duele?",
        "fr": "Ca fait mal ?",
    },
    ("e100010.evb", "0x0844"): {
        "en": "It's fine, I'm happy...",
        "es": "Esta bien, estoy feliz...",
        "fr": "Ca va, je suis heureuse...",
    },
    ("e100010.evb", "0x0870"): {
        "en": "Right now, you're looking only at me...",
        "es": "Ahora mismo, solo me miras a mi...",
        "fr": "En cet instant, tu ne regardes que moi...",
    },
    ("e100010.evb", "0x08B0"): {
        "en": "Moka...",
        "es": "Moka...",
        "fr": "Moka...",
    },
    ("e100010.evb", "0x08CC"): {
        "en": "(Wait... that's the scent of Moka's blood!\n[RUBY]Why is it so intoxicating...!?)",
        "es": "(Es el aroma de la sangre de Moka...\n[RUBY]¿Por que es tan embriagador?)",
        "fr": "(C'est l'odeur du sang de Moka...\n[RUBY]Pourquoi est-ce si enivrant !?)",
    },
    ("e100010.evb", "0x0920"): {
        "en": "This wound is deeper than I thought...",
        "es": "La herida es mas profunda de lo que pensaba...",
        "fr": "La blessure est plus profonde que prevu...",
    },
    ("e100010.evb", "0x0948"): {
        "en": "It might leave a scar...\nWhat should I do?",
        "es": "Podria dejar cicatriz...\n¿Que hare?",
        "fr": "Ca pourrait laisser une cicatrice...",
    },
    ("e100010.evb", "0x0988"): {
        "en": "(There's only one thing a man can do...)",
        "es": "(En ese caso, no hay opcion...)",
        "fr": "(Dans ce cas, je n'ai pas le choix...)",
    },
    ("e100010.evb", "0x09D0"): {
        "en": "I'll take responsibility...\nLet's get married, Moka!!",
        "es": "¡Me hare responsable!\n¡¡Casemonos, Moka!!",
        "fr": "J'assume mes responsabilites...\nMarions-nous, Moka !!",
    },
    ("e100010.evb", "0x0A3C"): {
        "en": "...I'm so happy.",
        "es": "...Que feliz soy.",
        "fr": "...Je suis si heureuse.",
    },
    ("e100010.evb", "0x0A5C"): {
        "en": "I've been waiting so long\nfor you to say that...",
        "es": "He esperado tanto tiempo\npara que dijeras eso...",
        "fr": "J'attendais ce moment\ndepuis si longtemps...",
    },
    ("e100010.evb", "0x0AA4"): {
        "en": "I love you, Tsukune!",
        "es": "¡Te amo, Tsukune!",
        "fr": "Je t'aime, Tsukune !",
    },
    ("e100010.evb", "0x0ACC"): {
        "en": "I love you too, Moka!",
        "es": "¡Yo tambien, Moka!",
        "fr": "Moi aussi, Moka !",
    },
    ("e100010.evb", "0x0AF0"): {
        "en": "Tsukune...",
        "es": "Tsukune...",
        "fr": "Tsukune...",
    },
    ("e100010.evb", "0x0B0C"): {
        "en": "Moka...",
        "es": "Moka...",
        "fr": "Moka...",
    },
    ("e100010.evb", "0x0B28"): {
        "en": "Tsukune...",
        "es": "Tsukune...",
        "fr": "Tsukune...",
    },
    ("e100010.evb", "0x0B44"): {
        "en": "(No good... I can't hold back anymore...)",
        "es": "(No puedo aguantar mas...)",
        "fr": "(Impossible... Je ne peux plus resister...)",
    },
    ("e100010.evb", "0x0B7C"): {
        "en": "Tsukune!?",
        "es": "¡¿Tsukune?!",
        "fr": "Tsukune !?",
    },
    ("e100010.evb", "0x0B98"): {
        "en": "Ah... This scent is driving me crazy.\nForgive me, Moka!",
        "es": "Ah... Este aroma me vuelve loco.\n¡Perdoname, Moka!",
        "fr": "Ce parfum me rend fou.\nPardonne-moi, Moka !",
    },
    ("e100010.evb", "0x0BDC"): {
        "en": "E-Eh, wait... Too fast, Tsukune!\n[RUBY]At least wait until graduation...",
        "es": "¡Espera, muy rapido, Tsukune!\n[RUBY]Esperemos a graduarnos...",
        "fr": "Attends, Tsukune !\n[RUBY]Attendons au moins le diplome...",
    },
    ("e100010.evb", "0x0C3C"): {
        "en": "Kyaaaaaaaaaaaaa!?",
        "es": "¡¿Kyaaaaaaaaaaaaa?!",
        "fr": "Kyaaaaaaaaaaaaa !?",
    },
    # e100020.evb (Waking up in the dorm / Girls' brawl)
    ("e100020.evb", "0x0048"): {
        "en": "Owowow...\nI rolled right off my bed\nin my sleep...",
        "es": "Ayayay...\nMe cai de la cama\nmedio dormido...",
        "fr": "Aie aie...\nJe suis tombe du lit\nen dormant...",
    },
    ("e100020.evb", "0x0098"): {
        "en": "...Huh?",
        "es": "...¿Eh?",
        "fr": "...Hein ?",
    },
    ("e100020.evb", "0x00C0"): {
        "en": "There's something soft\nunderneath me...",
        "es": "Hay algo suave\ndebajo de mi...",
        "fr": "Il y a quelque chose de doux\nsous moi...",
    },
    ("e100020.evb", "0x00EC"): {
        "en": "Tsukune...",
        "es": "Tsukune...",
        "fr": "Tsukune...",
    },
    ("e100020.evb", "0x0144"): {
        "en": "Eh!?",
        "es": "¡¿Eh?!",
        "fr": "Hein !?",
    },
    ("e100020.evb", "0x015C"): {
        "en": "Naughty things aren't allowed...",
        "es": "No hagas cosas pervertidas...",
        "fr": "Pas de choses perverses...",
    },
    ("e100020.evb", "0x018C"): {
        "en": "(How did we end up like this...!?)",
        "es": "(¿Como terminamos asi...!?)",
        "fr": "(Comment en est-on arrive la... !?)",
    },
    ("e100020.evb", "0x01C0"): {
        "en": "(Right, I was half-asleep...)",
        "es": "(Claro, estaba medio dormido...)",
        "fr": "(Ah oui, j'etais a moitie endormi...)",
    },
    ("e100020.evb", "0x01EC"): {
        "en": "Hurry and get off...\nEveryone's going to see us!",
        "es": "Bajate rapido...\n¡Todos nos veran!",
        "fr": "leve-toi vite...\nTout le monde va nous voir !",
    },
    ("e100020.evb", "0x0220"): {
        "en": "(Wait... nobody else is here yet...)",
        "es": "(Es verdad... no hay nadie...)",
        "fr": "(Attends... il n'y a personne...)",
    },
    ("e100020.evb", "0x0254"): {
        "en": "(This might be my big chance!)",
        "es": "(¡Pero esta es mi oportunidad!)",
        "fr": "(Mais c'est ma chance !)",
    },
    ("e100020.evb", "0x02A0"): {
        "en": "Moka-san... please hear me out...",
        "es": "Moka-san... escuchame por favor...",
        "fr": "Moka-san... ecoute-moi s'il te plait...",
    },
    ("e100020.evb", "0x02D4"): {
        "en": "Oh my, what's wrong? Why so serious...?",
        "es": "¿Que pasa? ¿Por que esa cara...?",
        "fr": "Qu'y a-t-il ? Pourquoi cet air serieux... ?",
    },
    ("e100020.evb", "0x030C"): {
        "en": "I know this is awkward, but... I'm dead serious...",
        "es": "Se que es repentino, pero... hablo en serio...",
        "fr": "C'est maladroit, mais... je suis serieux...",
    },
    ("e100020.evb", "0x0348"): {
        "en": "Tsukune...",
        "es": "Tsukune...",
        "fr": "Tsukune...",
    },
    ("e100020.evb", "0x0364"): {
        "en": "Moka-san, I really...",
        "es": "Moka-san, yo te...",
        "fr": "Moka-san, je...",
    },
    ("e100020.evb", "0x0394"): {
        "en": "Hold it right there, Moka!",
        "es": "¡Alto ahi, Moka!",
        "fr": "Halte-la, Moka !",
    },
    ("e100020.evb", "0x0464"): {
        "en": "Are you okay,[RUBY]Tsukune?\nDid she do anything weird to you?",
        "es": "¿Estas bien,[RUBY]Tsukune?\n¿Te hizo algo raro?",
        "fr": "Tu vas bien,[RUBY]Tsukune ?\nElle ne t'a rien fait de bizarre ?",
    },
    ("e100020.evb", "0x04A4"): {
        "en": "Did she suck\nall kinds of things out of you?",
        "es": "¿Te chupo la sangre?",
        "fr": "Elle t'a suce le sang ?",
    },
    ("e100020.evb", "0x04D0"): {
        "en": "K-[RUBY]Kurumu-chan...",
        "es": "K-[RUBY]Kurumu-chan...",
        "fr": "K-[RUBY]Kurumu-chan...",
    },
    ("e100020.evb", "0x0500"): {
        "en": "I misjudged you, Moka!\nSeducing my Tsukune like that...",
        "es": "¡Me decepcionas, Moka!\nSeduciendo a mi Tsukune...",
        "fr": "Tu me decois, Moka !\nSeduire mon Tsukune ainsi...",
    },
    ("e100020.evb", "0x0540"): {
        "en": "You've got it wrong, Kurumu-chan!\nTsukune fell on me...",
        "es": "¡Te equivocas, Kurumu-chan!\nTsukune se cayo...",
        "fr": "Tu te trompes, Kurumu-chan !\nC'est Tsukune qui...",
    },
    ("e100020.evb", "0x0578"): {
        "en": "I don't wanna hear\nyour excuses!",
        "es": "¡No quiero escuchar\nexcusas!",
        "fr": "Je ne veux pas entendre\ntes excuses !",
    },
    ("e100020.evb", "0x05C4"): {
        "en": "My Tsukune would never\ndo something like that!",
        "es": "¡Tsukune nunca haria\nalgo asi!",
        "fr": "Tsukune ne ferait jamais\nune chose pareille !",
    },
    ("e100020.evb", "0x05F8"): {
        "en": "You thieving vampire!",
        "es": "¡Vampira ladrona!",
        "fr": "Vampire voleuse !",
    },
    # e100030.evb (Hitomi / Transfer students)
    ("e100030.evb", "0x00A8"): {
        "en": "Summer training camp, huh...",
        "es": "Campamento de verano, eh...",
        "fr": "Le camp d'ete, hein...",
    },
    ("e100030.evb", "0x00C4"): {
        "en": "Last year's summer camp is\nwhere we met Midou-san...",
        "es": "El ano pasado conocimos\na Midou-san en el campamento...",
        "fr": "C'est au camp de l'an dernier\nqu'on a rencontre Midou-san...",
    },
    ("e100030.evb", "0x0150"): {
        "en": "Let's begin!\nCome now, let's get started!",
        "es": "¡Let's begin!\n¡Vamos, empecemos!",
        "fr": "Let's begin !\nAllez, commencons !",
    },
    ("e100030.evb", "0x01A8"): {
        "en": "Oh... Tsukune-san?",
        "es": "Oh... ¿Tsukune-san?",
        "fr": "Oh... Tsukune-san ?",
    },
    # e100040.evb (Nekonome-sensei & Club Budget / Music Festival)
    ("e100040.evb", "0x00A0"): {
        "en": "Sensei, you look\nin a great mood today!",
        "es": "¡Sensei, se ve de\nmuy buen humor!",
        "fr": "Sensei, vous avez l'air\nde bonne humeur !",
    },
    ("e100040.evb", "0x00C8"): {
        "en": "Of course I'm happy, nya~!",
        "es": "¡Claro que estoy feliz, nya~!",
        "fr": "Bien sur que je suis ravie, nya~ !",
    },
    ("e100040.evb", "0x0210"): {
        "en": "Are you sure it's okay to spend\nour entire club budget on this?",
        "es": "¿Seguro que esta bien gastar\ntodo el presupuesto del club?",
        "fr": "Vous etes sur de vouloir depenser\ntout le budget du club ?",
    },
    ("e100040.evb", "0x0278"): {
        "en": "No, silly~!\nI'm talking about the Music Festival!",
        "es": "¡No, tontito~!\n¡Hablo del Festival de Musica!",
        "fr": "Mais non~ !\nJe parle du Festival de Musique !",
    },
    ("e100040.evb", "0x02AC"): {
        "en": "The Youkai Fest!",
        "es": "¡El Youkai Fest!",
        "fr": "Le Youkai Fest !",
    },
    ("e100040.evb", "0x0530:0"): {"en": "Ask about Summer Camp", "es": "Preguntar por el campamento", "fr": "Demander pour le camp"},
    ("e100040.evb", "0x0530:1"): {"en": "Stay silent", "es": "Callar", "fr": "Garder le silence"},
    ("e100040.evb", "0x0C44:0"): {"en": "Accept", "es": "Aceptar", "fr": "Accepter"},
    ("e100040.evb", "0x0C44:1"): {"en": "Refuse", "es": "Rechazar", "fr": "Refuser"},
    # e101000.evb (Newspaper Club forms a Band)
    ("e101000.evb", "0x009C"): {
        "en": "How am I going to explain\nthis to everyone...?",
        "es": "¿Como les explicare\nesto a todas...?",
        "fr": "Comment vais-je expliquer\nca a tout le monde... ?",
    },
    ("e101000.evb", "0x00D8"): {
        "en": "Uh-oh,[RUBY]if I don't hurry,\nI'm gonna be late!",
        "es": "Uy,[RUBY]¡si no me apuro\nllegare tarde!",
        "fr": "Mince,[RUBY]si je ne me depeche pas,\nje vais etre en retard !",
    },
    ("e101000.evb", "0x0154"): {
        "en": "Ah,[RUBY]good morning, everyone...",
        "es": "Ah,[RUBY]buenos dias a todas...",
        "fr": "Ah,[RUBY]bonjour tout le monde...",
    },
    ("e101000.evb", "0x01C0"): {
        "en": "Good morning, Tsukune!",
        "es": "¡Buenos dias, Tsukune!",
        "fr": "Bonjour, Tsukune !",
    },
    ("e101000.evb", "0x0890"): {
        "en": "It's simple!\nWe just win the Music Festival!",
        "es": "¡Es simple!\n¡Ganemos el Festival de Musica!",
        "fr": "C'est simple !\nGagnons le Festival de Musique !",
    },
    ("e101000.evb", "0x0AAC"): {
        "en": "Let's form a band and\nstorm the Music Festival!",
        "es": "¡Formemos una banda y\nganemos el Festival!",
        "fr": "Formons un groupe pour\nle Festival de Musique !",
    },
    ("e101000.evb", "0x1420:0"): {"en": "Eeeeh!?", "es": "¡¿Eeeeh?!", "fr": "Eeeeh !?"},
    ("e101000.evb", "0x1420:1"): {"en": "No way!", "es": "¡De ninguna manera!", "fr": "Pas question !"},
    # e101010.evb (Eyecatch)
    ("e101010.evb", "0x0044"): {
        "en": "After School in the Blink of a Chu!",
        "es": "¡Despues de clases en un Chu!",
        "fr": "Apres les cours en un Chu !",
    },
}


def search_shift_jis_strings(data: bytes, min_chars: int = 2) -> List[Tuple[int, str, int]]:
    """
    Extracts readable Shift-JIS strings with offsets.
    """
    results = []
    pos = 0
    while pos < len(data):
        end = pos
        while end < len(data) and data[end] >= 0x20:
            end += 1
        if end - pos >= min_chars:
            chunk = data[pos:end]
            try:
                s = chunk.decode("shift_jis")
                has_jp = any("\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff" for c in s)
                if has_jp or (len(s) >= 4 and any(w in s.lower() for w in ["press", "load", "save", "start", "select", "option"])):
                    results.append((pos, s, len(chunk)))
            except Exception:
                pass
        pos = end + 1
    return results


def search_custom_elf_strings(elf: bytes, start_off: int = 0x13C000, end_off: int = 0x143000) -> List[Tuple[int, str, int]]:
    """
    Extracts custom 16-bit font-encoded UI/save/location/event strings from SLPM_551.89 (.rodata/.data).
    """
    results = []
    pos = start_off
    limit = min(len(elf), end_off)
    while pos < limit:
        if 0x80 <= elf[pos] <= 0x87:
            end = pos
            while end < limit and elf[end] != 0:
                end += 1
            chunk = elf[pos:end]
            if len(chunk) >= 4 and len(chunk) % 2 == 0 and all(0x80 <= chunk[i] <= 0x87 for i in range(0, len(chunk), 2)):
                ja = decode_game_string(chunk)
                results.append((pos, ja, len(chunk)))
            pos = end + 1
        else:
            pos += 1
    return results


def _load_existing_translations(filename: str, dirs: List[Path]) -> Dict[Tuple[str, str], Dict[str, str]]:
    """
    Loads any existing non-empty translations from translations/ and extracted_text/
    so user/community edits are preserved when re-extracting or syncing.
    """
    merged: Dict[Tuple[str, str], Dict[str, str]] = {}
    for d in dirs:
        json_path = d / filename
        if not json_path.exists():
            continue
        try:
            proj = TranslationProject.load(json_path)
            for s in proj.strings:
                key = (s.source_file, s.offset_hex)
                if key not in merged:
                    merged[key] = {}
                for lang, val in s.translations.items():
                    if val and val.strip():
                        merged[key][lang] = val
        except Exception:
            pass
    return merged


def _merge_trans(
    default_trans: Dict[str, str],
    existing_map: Dict[Tuple[str, str], Dict[str, str]],
    source_file: str,
    offset_hex: str,
) -> Dict[str, str]:
    result = {lang: default_trans.get(lang, "") for lang in DEFAULT_LANGUAGES}
    for lang, val in default_trans.items():
        if val:
            result[lang] = val
    saved = existing_map.get((source_file, offset_hex), {})
    for lang, val in saved.items():
        if val and val.strip():
            result[lang] = val
    return result


def sync_translations(
    extracted_dir: Path | str = "extracted_text",
    redist_dir: Path | str = "translations",
):
    """
    Syncs translations edited in extracted_text/*.json into redistributable translations/*.json
    (stripping original_ja so translations/ remains copyright-safe for GitHub distribution).
    """
    extracted_dir = Path(extracted_dir)
    redist_dir = Path(redist_dir)
    redist_dir.mkdir(parents=True, exist_ok=True)

    for fname in ("strings_executable.json", "strings_system.json", "strings_dialogue.json"):
        src_path = extracted_dir / fname
        dst_path = redist_dir / fname
        if not src_path.exists():
            continue
        existing = _load_existing_translations(fname, [redist_dir, extracted_dir])
        proj = TranslationProject.load(src_path)
        for s in proj.strings:
            saved = existing.get((s.source_file, s.offset_hex), {})
            for lang, val in saved.items():
                if val and val.strip():
                    s.translations[lang] = val
        proj.save(src_path, include_original=True, only_translated=False)
        proj.save(dst_path, include_original=False, only_translated=False)
        print(f"Synced: {src_path} -> {dst_path} (redistributable, no original_ja)")


def extract_all_text(
    iso_path: Path | str,
    output_dir: Path | str = "extracted_text",
    redist_dir: Path | str = "translations",
):
    iso_path = Path(iso_path)
    output_dir = Path(output_dir)
    redist_dir = Path(redist_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    redist_dir.mkdir(parents=True, exist_ok=True)

    search_dirs = [redist_dir, output_dir]
    existing_exec = _load_existing_translations("strings_executable.json", search_dirs)
    existing_sys = _load_existing_translations("strings_system.json", search_dirs)
    existing_diag = _load_existing_translations("strings_dialogue.json", search_dirs)

    print(f"Opening ISO: {iso_path}")
    iso = IsoHandler(iso_path)

    # 1. Extract strings from SLPM_551.89 (Both Custom-Encoded UI/Save strings & Shift-JIS strings)
    print("\n--- Extracting Main Executable (SLPM_551.89) ---")
    slpm_proj = TranslationProject(game_title="Rosario + Vampire PS2", version="1.0")
    if "SLPM_551.89" in iso.entries:
        entry = iso.entries["SLPM_551.89"]
        with open(iso_path, "rb") as f:
            f.seek(entry.offset)
            slpm_data = f.read(entry.size)

        custom_strings = search_custom_elf_strings(slpm_data)
        print(f"Found {len(custom_strings)} custom-encoded UI/menu/save strings in SLPM_551.89")
        str_idx = 1
        for off, text, length in custom_strings:
            off_hex = f"0x{off:08X}"
            auto_en = translate_ui_string(text, length)
            base_trans = {
                "en": auto_en,
                "es": auto_en,
                "fr": auto_en,
            }
            trans = _merge_trans(base_trans, existing_exec, "SLPM_551.89", off_hex)
            if text in EXACT_UI_MAP or len(trans.get("en", "")) * 2 > length:
                trans["en"] = auto_en
                trans["es"] = auto_en
                trans["fr"] = auto_en
            slpm_proj.add_string(
                string_id=f"slpm_ui_{str_idx:04d}",
                source_file="SLPM_551.89",
                offset_hex=off_hex,
                original_ja=text,
                translations=trans,
                context=f"Custom-encoded UI string (encoding=custom, max_bytes={length})",
            )
            str_idx += 1

        sjis_strings = search_shift_jis_strings(slpm_data, min_chars=3)
        print(f"Found {len(sjis_strings)} Shift-JIS strings in SLPM_551.89")
        for off, text, length in sjis_strings:
            off_hex = f"0x{off:08X}"
            base_trans = {lang: "" for lang in DEFAULT_LANGUAGES}
            trans = _merge_trans(base_trans, existing_exec, "SLPM_551.89", off_hex)
            slpm_proj.add_string(
                string_id=f"slpm_sjis_{str_idx:04d}",
                source_file="SLPM_551.89",
                offset_hex=off_hex,
                original_ja=text,
                translations=trans,
                context=f"Executable Shift-JIS string (encoding=sjis, max_bytes={length})",
            )
            str_idx += 1

        slpm_proj.save(output_dir / "strings_executable.json", include_original=True)
        slpm_proj.save(redist_dir / "strings_executable.json", include_original=False)
        print(f"Saved full reference:   {output_dir / 'strings_executable.json'}")
        print(f"Saved redistributable:  {redist_dir / 'strings_executable.json'}")

    # 2. Extract System Containers & All 619 .evb Scripts from RVCAPU2.AFS -> 1.afs -> pac000999.pac
    print("\n--- Extracting System & Event Dialogue Containers (pac000999.pac) ---")
    sys_proj = TranslationProject(game_title="Rosario + Vampire PS2", version="1.0")
    dialogue_proj = TranslationProject(game_title="Rosario + Vampire PS2", version="1.0")

    if "RVCAPU2.AFS" in iso.entries:
        rv_entry = iso.entries["RVCAPU2.AFS"]
        with open(iso_path, "rb") as f:
            rv_afs = AfsArchive(f, base_offset=rv_entry.offset)
            afs1_info = [e for e in rv_afs.entries if "1.afs" in e.name.lower()]
            if afs1_info:
                afs1_entry = afs1_info[0]
                afs1_base = rv_entry.offset + afs1_entry.offset
                afs1 = AfsArchive(f, base_offset=afs1_base)

                # Real System strings: PS2 Save Icon Title, Character Names, Minor Speakers, Map Locations
                sys_title_trans = {lang: "Rosario + Vampire: Capu 2" for lang in DEFAULT_LANGUAGES}
                sys_proj.add_string(
                    string_id="sys_title",
                    source_file="afstmp/dat/sys001.bin",
                    offset_hex="0x0000C0",
                    original_ja="ロザリオとバンパイア恋と夢の狂想曲",
                    translations=_merge_trans(sys_title_trans, existing_sys, "afstmp/dat/sys001.bin", "0x0000C0"),
                    context="PS2 Memory Card Save Icon Title in sys001.bin (max_bytes=34)",
                )

                # Character Names table in SLPM_551.89 (pointed by table at 0x1047B8)
                char_names = [
                    ("sys_char_01", "0x0014F898", "月音", "Tsukune"),
                    ("sys_char_02", "0x0014F8A0", "萌香", "Moka"),
                    ("sys_char_03", "0x0014F8A8", "胡夢", "Kurumu"),
                    ("sys_char_04", "0x0014F8B0", "紫", "Yukari"),
                    ("sys_char_05", "0x0014F8B8", "みぞれ", "Mizore"),
                    ("sys_char_06", "0x0014F8C0", "緑妃", "Midou"),
                    ("sys_char_07", "0x0014F8C8", "心愛", "Kokoa"),
                    ("sys_char_08", "0x0014F8D0", "静", "Shizuka"),
                    ("sys_char_09", "0x0014F8D8", "凛", "Rin"),
                    ("sys_char_10", "0x0014F8E0", "瞳", "Hitomi"),
                    ("sys_char_11", "0x0014F8E8", "銀影", "Ginei"),
                    ("sys_char_12", "0x0014F8F0", "猫目", "Nekonome"),
                    ("sys_char_13", "0x0014F8F8", "貴様", "Bastard"),
                    ("sys_char_14", "0x0014F900", "交太郎", "Koutarou"),
                    ("sys_char_15", "0x0014F908", "笠原", "Kasahara"),
                    ("sys_char_16", "0x0014F910", "坊三郎", "Bouzaburou"),
                    ("sys_char_17", "0x0014F918", "酒作", "Sakasaku"),
                    ("sys_char_18", "0x0014F920", "纏の声", "Voice"),
                    ("sys_char_19", "0x0014F928", "カリス", "Karis"),
                    ("sys_char_20", "0x0014F930", "外国人", "Foreigner"),
                    ("sys_char_21", "0x0014F938", "？？？", "???"),
                ]
                for cid, coff, cja, cen in char_names:
                    ctrans = {lang: cen for lang in DEFAULT_LANGUAGES}
                    sys_proj.add_string(
                        string_id=cid,
                        source_file="SLPM_551.89",
                        offset_hex=coff,
                        original_ja=cja,
                        translations=_merge_trans(ctrans, existing_sys, "SLPM_551.89", coff),
                        context=f"Character Name Speaker Box (encoding=custom, table_idx={int(cid.split('_')[-1])-1})",
                    )

                # Minor Speaker Names in SLPM_551.89 (0x139910..0x139960, 16 bytes each)
                spk_names = [
                    ("sys_spk_01", "0x00139910", "こーちゃん", "Ko-chan", 16),
                    ("sys_spk_02", "0x00139920", "噂転手さん", "Driver", 16),
                    ("sys_spk_03", "0x00139930", "男姿生徒", "Boy", 16),
                    ("sys_spk_04", "0x00139940", "女姿生徒", "Girl", 16),
                    ("sys_spk_05", "0x00139950", "リジオの音", "Radio", 16),
                    ("sys_spk_06", "0x00139960", "マスコット", "Mascot", 16),
                ]
                for sid, soff, sja, sen, smb in spk_names:
                    strans = {lang: sen for lang in DEFAULT_LANGUAGES}
                    sys_proj.add_string(
                        string_id=sid,
                        source_file="SLPM_551.89",
                        offset_hex=soff,
                        original_ja=sja,
                        translations=_merge_trans(strans, existing_sys, "SLPM_551.89", soff),
                        context=f"Minor Speaker Name (encoding=custom, max_bytes={smb})",
                    )

                # Map Locations in SLPM_551.89 (0x1531E0..0x153210, 8 bytes each)
                map_names = [
                    ("sys_map_01", "0x001531E0", "校門", "Gate", 8),
                    ("sys_map_02", "0x001531E8", "教室", "Class", 8),
                    ("sys_map_03", "0x001531F0", "屋上", "Roof", 8),
                    ("sys_map_04", "0x001531F8", "保健室", "Clinic", 8),
                    ("sys_map_05", "0x00153200", "売店", "Shop", 8),
                    ("sys_map_06", "0x00153208", "廊下", "Hall", 8),
                    ("sys_map_07", "0x00153210", "校舎裏", "Yard", 8),
                ]
                for mid, moff, mja, men, mmb in map_names:
                    mtrans = {lang: men for lang in DEFAULT_LANGUAGES}
                    sys_proj.add_string(
                        string_id=mid,
                        source_file="SLPM_551.89",
                        offset_hex=moff,
                        original_ja=mja,
                        translations=_merge_trans(mtrans, existing_sys, "SLPM_551.89", moff),
                        context=f"Map Location (encoding=custom, max_bytes={mmb})",
                    )

                sys_proj.save(output_dir / "strings_system.json", include_original=True)
                sys_proj.save(redist_dir / "strings_system.json", include_original=False)
                print(f"Saved full reference:   {output_dir / 'strings_system.json'}")
                print(f"Saved redistributable:  {redist_dir / 'strings_system.json'}")

                # Event scripts inside pac000999.pac
                pac_info = [e for e in afs1.entries if "pac000999.pac" in e.name.lower()]
                if pac_info:
                    pac_entry = pac_info[0]
                    f.seek(afs1_base + pac_entry.offset)
                    pac_bytes = f.read(pac_entry.size)
                    pac = PacArchive(pac_bytes)
                    print(f"Parsing {len(pac.entries)} .evb event scripts in {pac_entry.name}...")

                    d_idx = 1
                    vs_count = 0
                    for evb_entry in pac.entries:
                        evb_raw = decompress_lzr(evb_entry.data) if evb_entry.is_compressed else evb_entry.data
                        extracted = extract_evb_strings(evb_raw, script_name=evb_entry.name)
                        src_path = f"afstmp/1.afs:{pac_entry.name}:{evb_entry.name}"
                        for item in extracted:
                            off_hex = item["offset_hex"]
                            vs_trans = VERTICAL_SLICE_DIALOGUE.get((evb_entry.name, off_hex), {})
                            trans_dict = _merge_trans(vs_trans, existing_diag, src_path, off_hex)
                            if any(v.strip() for v in trans_dict.values()):
                                vs_count += 1

                            dialogue_proj.add_string(
                                string_id=f"dialogue_{d_idx:05d}",
                                source_file=src_path,
                                offset_hex=off_hex,
                                original_ja=item["original_ja"],
                                translations=trans_dict,
                                context=item["context"],
                            )
                            d_idx += 1

                    dialogue_proj.save(output_dir / "strings_dialogue.json", include_original=True)
                    dialogue_proj.save(redist_dir / "strings_dialogue.json", include_original=False)
                    print(
                        f"Saved full reference:   {output_dir / 'strings_dialogue.json'} "
                        f"({len(dialogue_proj.strings)} total strings, {vs_count} translated)"
                    )
                    print(f"Saved redistributable:  {redist_dir / 'strings_dialogue.json'}")

    print("\nText extraction complete!")
    print(f"  - Local full reference (with Japanese text, git-ignored): {output_dir}/")
    print(f"  - Redistributable patch files (pointers + translations):  {redist_dir}/")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract Japanese text from Rosario + Vampire Capu 2 ISO or sync translations."
    )
    parser.add_argument(
        "--iso",
        type=str,
        default="iso/Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso",
        help="Path to clean Japanese PS2 ISO",
    )
    parser.add_argument(
        "--out-extracted",
        type=str,
        default="extracted_text",
        help="Output folder for full reference JSONs (includes original_ja, git-ignored)",
    )
    parser.add_argument(
        "--out-translations",
        type=str,
        default="translations",
        help="Output folder for redistributable JSONs (no original_ja, safe for GitHub)",
    )
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="Sync translations from extracted_text/ to translations/ without needing the ISO",
    )
    args = parser.parse_args()

    if args.sync_only:
        sync_translations(args.out_extracted, args.out_translations)
    else:
        extract_all_text(args.iso, args.out_extracted, args.out_translations)

