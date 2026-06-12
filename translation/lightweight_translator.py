import string
import unicodedata

_PHRASE_ALIASES = {
    "thankyou": "thank you",
    "thankyouverymuch": "thank you very much",
    "goodmorning": "good morning",
    "goodnight": "good night",
    "goodafternoon": "good afternoon",
    "howareyou": "how are you",
    "ineedhelp": "i need help",
    "idontunderstand": "i don't understand",
    "whereisthebathroom": "where is the bathroom",
    "canyouhelpme": "can you help me",
    "ineedadoctor": "i need a doctor",
    "callthepolice": "call the police",
    "whereisthehospital": "where is the hospital",
    "buenosdias": "buenos dias",
    "buenasnoches": "buenas noches",
    "buenastardes": "buenas tardes",
    "comoestas": "como estas",
    "muchasgracias": "muchas gracias",
    "porfavor": "por favor",
    "s'ilvousplait": "s il vous plait",
    "mercibeaucoup": "merci beaucoup",
    "commentallezvous": "comment allez vous",
    "gutenmorgen": "guten morgen",
    "gutenabend": "guten abend",
    "wiegehtesihnen": "wie geht es ihnen",
    "vielendank": "vielen dank",
    "dankje": "dank je",
    "mesianpil": "mesi anpil",
    "kijanouye": "kijan ou ye",
    "mwenbezened": "mwen bezwen ed",
    "mwenpakonprann": "mwen pa konprann",
    "kotetwaletl a": "kote twalet la",
    "dospeakenglish": "do you speak english",
    "doyouspeakenglish": "do you speak english",
    "idontspeakenglish": "i dont speak english",
    "slowdownplease": "slow down please",
    "pleaserepeat": "please repeat",
    "howmuchdoesitcost": "how much does it cost",
    "whereisthepharmacy": "where is the pharmacy",
    "iamlost": "i am lost",
    "mynameis": "my name is",
    "nicetomeetyou": "nice to meet you",
    "whattimeisit": "what time is it",
    "iamallergic": "i am allergic",
    "waterplease": "water please",
    "foodplease": "food please",
    "hablaingles": "habla ingles",
    "nohabloingles": "no hablo ingles",
    "eskeoupaleangle": "eske ou pale angle",
    "mwenpapaleangle": "mwen pa pale angle",
    "turnleft": "turn left",
    "turnright": "turn right",
    "gostraight": "go straight",
    "stophere": "stop here",
    "whereisthebusstop": "where is the bus stop",
    "ineedataxi": "i need a taxi",
    "howdoigetthere": "how do i get there",
    "isitfar": "is it far",
    "girealaizquierda": "gire a la izquierda",
    "tournezalagauche": "tournez a gauche",
    "biegenlinksab": "biegen sie links ab",
    "iamhungry": "i am hungry",
    "thecheckplease": "the check please",
    "iwouldlikewater": "i would like water",
    "iamvegetarian": "i am vegetarian",
    "iamallergictonuts": "i am allergic to nuts",
    "whatdoyourecommend": "what do you recommend",
    "isthisglutenfree": "is this gluten free",
    "nospicyplease": "no spicy please",
    "ifeelsick": "i feel sick",
    "ihaveafever": "i have a fever",
    "ihaveaheadache": "i have a headache",
    "ihavechestpain": "i have chest pain",
    "iamdiabetic": "i am diabetic",
    "callanambulance": "call an ambulance",
    "tengohambre": "tengo hambre",
    "mwengrangou": "mwen grangou",
    "howmuchisthis": "how much is this",
    "doyouacceptcards": "do you accept cards",
    "iamjustlooking": "i am just looking",
    "canitrythison": "can i try this on",
    "tooexpensive": "too expensive",
    "seeyoulater": "see you later",
    "happybirthday": "happy birthday",
    "goodluck": "good luck",
    "ihaveareservation": "i have a reservation",
    "whatisthewifipassword": "what is the wifi password",
    "ineedaroom": "i need a room",
    "checkinplease": "check in please",
    "checkoutplease": "check out please",
    "idontknow": "i dont know",
    "iunderstand": "i understand",
    "speakslowly": "speak slowly",
    "whereareyoufrom": "where are you from",
    "ilostmypassport": "i lost my passport",
    "ilostmywallet": "i lost my wallet",
    "ineedmedicine": "i need medicine",
    "callmyfamily": "call my family",
    "myphonenumberis": "my phone number is",
    "goodevening": "good evening",
    "iamsorry": "i am sorry",
    "youarewelcome": "you are welcome",
    "howmuch": "how much",
    "openthedoor": "open the door",
    "closethewindow": "close the window",
    "ithurtshere": "it hurts here",
    "icannotbreathe": "i cannot breathe",
    "mychildissick": "my child is sick",
    "isitsafe": "is it safe",
    "whereistheembassy": "where is the embassy",
    "buenasnoches": "buenas noches",
    "losiento": "lo siento",
    "bonsoir": "bonsoir",
    "bonswa": "bon swa",
    "iamastudent": "i am a student",
    "iamateacher": "i am a teacher",
    "iworkhere": "i work here",
    "whatisyourjob": "what is your job",
    "iamtired": "i am tired",
    "iamcold": "i am cold",
    "iamhot": "i am hot",
    "mywife": "my wife",
    "myhusband": "my husband",
    "myson": "my son",
    "mydaughter": "my daughter",
    "mybaby": "my baby",
    "myparents": "my parents",
    "itisraining": "it is raining",
    "itiscoldtoday": "it is cold today",
    "itishottoday": "it is hot today",
    "niceweather": "nice weather",
    "doyouhavewifi": "do you have wifi",
    "caniuseyourphone": "can i use your phone",
    "ihavenomoney": "i have no money",
    "ineedcash": "i need cash",
    "whereistheatm": "where is the atm",
}


def _normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = ascii_text.translate(str.maketrans("", "", string.punctuation))
    stripped = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in stripped)
    return " ".join(stripped.strip().split())


class LightweightTranslator:
    def __init__(self):
        self._phrases = {
            ("en", "es"): {
                "hello": "hola",
                "hello world": "hola mundo",
                "good morning": "buenos d\u00edas",
                "good night": "buenas noches",
                "thank you": "gracias",
                "how are you": "c\u00f3mo est\u00e1s",
                "hello how are you": "Hola, \u00bfc\u00f3mo est\u00e1s?",
                "i need help": "necesito ayuda",
                "where is the bathroom": "d\u00f3nde est\u00e1 el ba\u00f1o",
            },
            ("en", "ht"): {
                "hello": "bonjou",
                "where is the nearest hospital": "Kote lopital ki pi pre a ye?",
                "thank you": "mèsi",
                "thank you very much": "mèsi anpil",
                "i need help": "mwen bezwen èd",
                "good morning": "Bonjou.",
                "good night": "Bòn nuit.",
                "how are you": "Kijan ou ye?",
                "yes": "Wi.",
                "no": "Non.",
                "please": "Tanpri.",
                "excuse me": "Eskize mwen.",
                "goodbye": "Orevwa.",
                "i don't understand": "Mwen pa konprann.",
                "where is the bathroom": "Kote twalèt la?",
            },
            ("ht", "en"): {
                "bonjou": "Hello.",
                "mesi": "Thank you.",
                "mesi anpil": "Thank you very much.",
                "mwen bezwen ed": "I need help.",
                "mwen bezwen ede": "I need help.",
                "mwen bezwen yon dokte": "I need a doctor.",
                "mesi anpil pou ed ou": "Thank you very much for your help.",
                "kijan ou ye": "How are you?",
                "wi": "Yes.",
                "non": "No.",
                "tanpri": "Please.",
                "eskize mwen": "Excuse me.",
                "orevwa": "Goodbye.",
                "mwen pa konprann": "I don't understand.",
                "kote twalet la": "Where is the bathroom?",
            },
            ("es", "en"): {
                "hola": "hello",
                "hola mundo": "hello world",
                "buenos dias": "good morning",
                "buenas noches": "good night",
                "gracias": "thank you",
                "como estas": "how are you",
                "hola como estas": "hello, how are you?",
                "necesito ayuda": "i need help",
                "donde esta el bano": "where is the bathroom",
            },
            ("ht", "ru"): {
                "bonjou": "Привет.",
                "bonjou kijan ou ye": "Привет, как дела?",
                "kijan ou ye": "Как дела?",
                "mesi": "Спасибо.",
                "mesi anpil": "Большое спасибо.",
                "tanpri": "Пожалуйста.",
                "wi": "Да.",
                "non": "Нет.",
                "orevwa": "До свидания.",
                "eskize mwen": "Извините.",
                "mwen bezwen ed": "Мне нужна помощь.",
                "mwen bezwen ede": "Мне нужна помощь.",
                "mwen pa konprann": "Я не понимаю.",
                "kote twalet la": "Где туалет?",
                "ou pale angle": "Вы говорите по-английски?",
                "mwen renmen ou": "Я тебя люблю.",
            },
        }
        self._add_common_english_phrases()
        self._add_conversation_phrases()
        self._add_travel_phrases()
        self._add_direction_phrases()
        self._add_food_phrases()
        self._add_medical_phrases()
        self._add_daily_phrases()
        self._add_number_phrases()
        self._add_essential_phrases()
        self._add_courtesy_safety_phrases()
        self._add_life_context_phrases()
        self._add_emergency_phrases()
        self._add_barrier_phrases()
        self._add_common_to_english_phrases()
        self._build_english_pivot_phrases()

    def _build_english_pivot_phrases(self) -> None:
        """Derive source->target phrases from source->en plus en->target tables."""
        en_targets = {
            target: phrases
            for (source, target), phrases in self._phrases.items()
            if source == "en" and target != "en"
        }
        for (source, bridge), source_to_en in list(self._phrases.items()):
            if bridge != "en" or source == "en":
                continue
            for native_phrase, english_text in source_to_en.items():
                english_key = _normalize_text(english_text)
                if not english_key:
                    continue
                for target, english_to_target in en_targets.items():
                    if target in {source, "en"}:
                        continue
                    translated = english_to_target.get(english_key)
                    if translated:
                        self._phrases.setdefault((source, target), {}).setdefault(native_phrase, translated)

    def _add_common_english_phrases(self) -> None:
        common = {
            "fr": {
                "hello": "Bonjour.",
                "thank you": "Merci.",
                "good morning": "Bonjour.",
                "good night": "Bonne nuit.",
                "how are you": "Comment allez-vous ?",
                "i need help": "J'ai besoin d'aide.",
            },
            "de": {
                "hello": "Hallo.",
                "thank you": "Danke.",
                "good morning": "Guten Morgen.",
                "good night": "Gute Nacht.",
                "how are you": "Wie geht es Ihnen?",
                "i need help": "Ich brauche Hilfe.",
            },
            "it": {
                "hello": "Ciao.",
                "thank you": "Grazie.",
                "good morning": "Buongiorno.",
                "good night": "Buona notte.",
                "how are you": "Come sta?",
                "i need help": "Ho bisogno di aiuto.",
            },
            "pt": {
                "hello": "Ol\u00e1.",
                "thank you": "Obrigado.",
                "good morning": "Bom dia.",
                "good night": "Boa noite.",
                "how are you": "Como voc\u00ea est\u00e1?",
                "i need help": "Preciso de ajuda.",
            },
            "nl": {
                "hello": "Hallo.",
                "thank you": "Dank u.",
                "good morning": "Goedemorgen.",
                "good night": "Goedenacht.",
                "how are you": "Hoe gaat het met u?",
                "i need help": "Ik heb hulp nodig.",
            },
            "ru": {
                "hello": "\u041f\u0440\u0438\u0432\u0435\u0442.",
                "thank you": "\u0421\u043f\u0430\u0441\u0438\u0431\u043e.",
                "good morning": "\u0414\u043e\u0431\u0440\u043e\u0435 \u0443\u0442\u0440\u043e.",
                "good night": "\u0421\u043f\u043e\u043a\u043e\u0439\u043d\u043e\u0439 \u043d\u043e\u0447\u0438.",
                "how are you": "\u041a\u0430\u043a \u0434\u0435\u043b\u0430?",
                "i need help": "\u041c\u043d\u0435 \u043d\u0443\u0436\u043d\u0430 \u043f\u043e\u043c\u043e\u0449\u044c.",
            },
            "zh": {
                "hello": "\u4f60\u597d\u3002",
                "thank you": "\u8c22\u8c22\u3002",
                "good morning": "\u65e9\u4e0a\u597d\u3002",
                "good night": "\u665a\u5b89\u3002",
                "how are you": "\u4f60\u597d\u5417\uff1f",
                "i need help": "\u6211\u9700\u8981\u5e2e\u52a9\u3002",
            },
            "ja": {
                "hello": "\u3053\u3093\u306b\u3061\u306f\u3002",
                "thank you": "\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3059\u3002",
                "good morning": "\u304a\u306f\u3088\u3046\u3054\u3056\u3044\u307e\u3059\u3002",
                "good night": "\u304a\u3084\u3059\u307f\u306a\u3055\u3044\u3002",
                "how are you": "\u304a\u5143\u6c17\u3067\u3059\u304b\uff1f",
                "i need help": "\u52a9\u3051\u304c\u5fc5\u8981\u3067\u3059\u3002",
            },
            "ko": {
                "hello": "\uc548\ub155\ud558\uc138\uc694.",
                "thank you": "\uac10\uc0ac\ud569\ub2c8\ub2e4.",
                "good morning": "\uc88b\uc740 \uc544\uce68\uc785\ub2c8\ub2e4.",
                "good night": "\uc548\ub155\ud788 \uc8fc\ubb34\uc138\uc694.",
                "how are you": "\uc5b4\ub5bb\uac8c \uc9c0\ub0b4\uc138\uc694?",
                "i need help": "\ub3c4\uc6c0\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
            },
            "ar": {
                "hello": "\u0645\u0631\u062d\u0628\u0627.",
                "thank you": "\u0634\u0643\u0631\u0627.",
                "good morning": "\u0635\u0628\u0627\u062d \u0627\u0644\u062e\u064a\u0631.",
                "good night": "\u062a\u0635\u0628\u062d \u0639\u0644\u0649 \u062e\u064a\u0631.",
                "how are you": "\u0643\u064a\u0641 \u062d\u0627\u0644\u0643\u061f",
                "i need help": "\u0623\u062d\u062a\u0627\u062c \u0625\u0644\u0649 \u0645\u0633\u0627\u0639\u062f\u0629.",
            },
            "hi": {
                "hello": "\u0928\u092e\u0938\u094d\u0924\u0947.",
                "thank you": "\u0927\u0928\u094d\u092f\u0935\u093e\u0926.",
                "good morning": "\u0936\u0941\u092d \u092a\u094d\u0930\u092d\u093e\u0924.",
                "good night": "\u0936\u0941\u092d \u0930\u093e\u0924\u094d\u0930\u093f.",
                "how are you": "\u0906\u092a \u0915\u0948\u0938\u0947 \u0939\u0948\u0902?",
                "i need help": "\u092e\u0941\u091d\u0947 \u092e\u0926\u0926 \u091a\u093e\u0939\u093f\u090f.",
            },
            "ht": {
                "hello": "bonjou",
                "thank you": "mèsi",
                "good morning": "bonjou",
                "good night": "bòn nuit",
                "how are you": "kijan ou ye",
                "i need help": "mwen bezwen èd",
            },
        }
        for target_language, phrases in common.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source_phrase): translated for source_phrase, translated in phrases.items()}
            )

    def _add_conversation_phrases(self) -> None:
        """High-frequency conversation lines for every supported target language."""
        conversation = {
            "es": {
                "yes": "Sí.", "no": "No.", "please": "Por favor.", "excuse me": "Disculpe.",
                "goodbye": "Adiós.", "good afternoon": "Buenas tardes.",
                "i don't understand": "No entiendo.", "thank you very much": "Muchas gracias.",
                "can you help me": "¿Puede ayudarme?", "where is the bathroom": "¿Dónde está el baño?",
            },
            "fr": {
                "yes": "Oui.", "no": "Non.", "please": "S'il vous plaît.", "excuse me": "Excusez-moi.",
                "goodbye": "Au revoir.", "good afternoon": "Bon après-midi.",
                "i don't understand": "Je ne comprends pas.", "thank you very much": "Merci beaucoup.",
                "can you help me": "Pouvez-vous m'aider ?", "where is the bathroom": "Où sont les toilettes ?",
            },
            "de": {
                "yes": "Ja.", "no": "Nein.", "please": "Bitte.", "excuse me": "Entschuldigung.",
                "goodbye": "Auf Wiedersehen.", "good afternoon": "Guten Tag.",
                "i don't understand": "Ich verstehe nicht.", "thank you very much": "Vielen Dank.",
                "can you help me": "Können Sie mir helfen?", "where is the bathroom": "Wo ist die Toilette?",
            },
            "it": {
                "yes": "Sì.", "no": "No.", "please": "Per favore.", "excuse me": "Mi scusi.",
                "goodbye": "Arrivederci.", "good afternoon": "Buon pomeriggio.",
                "i don't understand": "Non capisco.", "thank you very much": "Grazie mille.",
                "can you help me": "Può aiutarmi?", "where is the bathroom": "Dov'è il bagno?",
            },
            "pt": {
                "yes": "Sim.", "no": "Não.", "please": "Por favor.", "excuse me": "Com licença.",
                "goodbye": "Adeus.", "good afternoon": "Boa tarde.",
                "i don't understand": "Não entendo.", "thank you very much": "Muito obrigado.",
                "can you help me": "Pode me ajudar?", "where is the bathroom": "Onde fica o banheiro?",
            },
            "nl": {
                "yes": "Ja.", "no": "Nee.", "please": "Alstublieft.", "excuse me": "Pardon.",
                "goodbye": "Tot ziens.", "good afternoon": "Goedemiddag.",
                "i don't understand": "Ik begrijp het niet.", "thank you very much": "Hartelijk dank.",
                "can you help me": "Kunt u mij helpen?", "where is the bathroom": "Waar is het toilet?",
            },
            "ru": {
                "yes": "Да.", "no": "Нет.", "please": "Пожалуйста.", "excuse me": "Извините.",
                "goodbye": "До свидания.", "good afternoon": "Добрый день.",
                "i don't understand": "Я не понимаю.", "thank you very much": "Большое спасибо.",
                "can you help me": "Вы можете мне помочь?", "where is the bathroom": "Где туалет?",
            },
            "zh": {
                "yes": "是的。", "no": "不是。", "please": "请。", "excuse me": "对不起。",
                "goodbye": "再见。", "good afternoon": "下午好。",
                "i don't understand": "我不明白。", "thank you very much": "非常感谢。",
                "can you help me": "你能帮助我吗？", "where is the bathroom": "洗手间在哪里？",
            },
            "ja": {
                "yes": "はい。", "no": "いいえ。", "please": "お願いします。", "excuse me": "すみません。",
                "goodbye": "さようなら。", "good afternoon": "こんにちは。",
                "i don't understand": "わかりません。", "thank you very much": "どうもありがとうございます。",
                "can you help me": "手伝ってください。", "where is the bathroom": "トイレはどこですか？",
            },
            "ko": {
                "yes": "네.", "no": "아니요.", "please": "제발.", "excuse me": "실례합니다.",
                "goodbye": "안녕히 가세요.", "good afternoon": "안녕하세요.",
                "i don't understand": "이해하지 못했습니다.", "thank you very much": "정말 감사합니다.",
                "can you help me": "도와주실 수 있나요?", "where is the bathroom": "화장실이 어디예요?",
            },
            "ar": {
                "yes": "نعم.", "no": "لا.", "please": "من فضلك.", "excuse me": "عذراً.",
                "goodbye": "مع السلامة.", "good afternoon": "مساء الخير.",
                "i don't understand": "لا أفهم.", "thank you very much": "شكراً جزيلاً.",
                "can you help me": "هل يمكنك مساعدتي؟", "where is the bathroom": "أين الحمام؟",
            },
            "hi": {
                "yes": "हाँ।", "no": "नहीं।", "please": "कृपया।", "excuse me": "माफ़ कीजिए।",
                "goodbye": "अलविदा।", "good afternoon": "नमस्कार।",
                "i don't understand": "मैं समझा नहीं।", "thank you very much": "बहुत धन्यवाद।",
                "can you help me": "क्या आप मेरी मदद कर सकते हैं?", "where is the bathroom": "शौचालय कहाँ है?",
            },
            "ht": {
                "yes": "Wi.", "no": "Non.", "please": "Tanpri.", "excuse me": "Eskize mwen.",
                "goodbye": "Orevwa.", "good afternoon": "Bon aprè-midi.",
                "i don't understand": "Mwen pa konprann.", "thank you very much": "Mèsi anpil.",
                "can you help me": "Èske ou ka ede mwen?", "where is the bathroom": "Kote twalèt la?",
            },
        }
        for target_language, phrases in conversation.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_travel_phrases(self) -> None:
        """Travel and navigation lines needed instantly in every language."""
        travel = {
            "es": {
                "do you speak english": "¿Habla inglés?",
                "i dont speak english": "No hablo inglés.",
                "slow down please": "Más despacio, por favor.",
                "please repeat": "Repita, por favor.",
                "how much does it cost": "¿Cuánto cuesta?",
                "where is the pharmacy": "¿Dónde está la farmacia?",
                "i am lost": "Estoy perdido.",
                "my name is": "Me llamo",
                "nice to meet you": "Mucho gusto.",
                "what time is it": "¿Qué hora es?",
                "i am allergic": "Soy alérgico.",
                "water please": "Agua, por favor.",
                "food please": "Comida, por favor.",
            },
            "fr": {
                "do you speak english": "Parlez-vous anglais ?",
                "i dont speak english": "Je ne parle pas anglais.",
                "slow down please": "Plus lentement, s'il vous plaît.",
                "please repeat": "Répétez, s'il vous plaît.",
                "how much does it cost": "Combien ça coûte ?",
                "where is the pharmacy": "Où est la pharmacie ?",
                "i am lost": "Je suis perdu.",
                "my name is": "Je m'appelle",
                "nice to meet you": "Enchanté.",
                "what time is it": "Quelle heure est-il ?",
                "i am allergic": "Je suis allergique.",
                "water please": "De l'eau, s'il vous plaît.",
                "food please": "À manger, s'il vous plaît.",
            },
            "de": {
                "do you speak english": "Sprechen Sie Englisch?",
                "i dont speak english": "Ich spreche kein Englisch.",
                "slow down please": "Bitte langsamer.",
                "please repeat": "Bitte wiederholen.",
                "how much does it cost": "Wie viel kostet das?",
                "where is the pharmacy": "Wo ist die Apotheke?",
                "i am lost": "Ich habe mich verlaufen.",
                "my name is": "Ich heiße",
                "nice to meet you": "Freut mich.",
                "what time is it": "Wie spät ist es?",
                "i am allergic": "Ich bin allergisch.",
                "water please": "Wasser, bitte.",
                "food please": "Essen, bitte.",
            },
            "it": {
                "do you speak english": "Parla inglese?",
                "i dont speak english": "Non parlo inglese.",
                "slow down please": "Più lentamente, per favore.",
                "please repeat": "Ripeta, per favore.",
                "how much does it cost": "Quanto costa?",
                "where is the pharmacy": "Dov'è la farmacia?",
                "i am lost": "Mi sono perso.",
                "my name is": "Mi chiamo",
                "nice to meet you": "Piacere.",
                "what time is it": "Che ore sono?",
                "i am allergic": "Sono allergico.",
                "water please": "Acqua, per favore.",
                "food please": "Cibo, per favore.",
            },
            "pt": {
                "do you speak english": "Você fala inglês?",
                "i dont speak english": "Eu não falo inglês.",
                "slow down please": "Mais devagar, por favor.",
                "please repeat": "Repita, por favor.",
                "how much does it cost": "Quanto custa?",
                "where is the pharmacy": "Onde fica a farmácia?",
                "i am lost": "Estou perdido.",
                "my name is": "Meu nome é",
                "nice to meet you": "Prazer em conhecê-lo.",
                "what time is it": "Que horas são?",
                "i am allergic": "Sou alérgico.",
                "water please": "Água, por favor.",
                "food please": "Comida, por favor.",
            },
            "nl": {
                "do you speak english": "Spreekt u Engels?",
                "i dont speak english": "Ik spreek geen Engels.",
                "slow down please": "Langzamer, alstublieft.",
                "please repeat": "Herhaal alstublieft.",
                "how much does it cost": "Hoeveel kost het?",
                "where is the pharmacy": "Waar is de apotheek?",
                "i am lost": "Ik ben verdwaald.",
                "my name is": "Ik heet",
                "nice to meet you": "Aangenaam.",
                "what time is it": "Hoe laat is het?",
                "i am allergic": "Ik ben allergisch.",
                "water please": "Water, alstublieft.",
                "food please": "Eten, alstublieft.",
            },
            "ru": {
                "do you speak english": "Вы говорите по-английски?",
                "i dont speak english": "Я не говорю по-английски.",
                "slow down please": "Медленнее, пожалуйста.",
                "please repeat": "Повторите, пожалуйста.",
                "how much does it cost": "Сколько это стоит?",
                "where is the pharmacy": "Где аптека?",
                "i am lost": "Я заблудился.",
                "my name is": "Меня зовут",
                "nice to meet you": "Приятно познакомиться.",
                "what time is it": "Который час?",
                "i am allergic": "У меня аллергия.",
                "water please": "Воду, пожалуйста.",
                "food please": "Еду, пожалуйста.",
            },
            "zh": {
                "do you speak english": "你会说英语吗？",
                "i dont speak english": "我不会说英语。",
                "slow down please": "请慢一点。",
                "please repeat": "请重复一遍。",
                "how much does it cost": "这个多少钱？",
                "where is the pharmacy": "药店在哪里？",
                "i am lost": "我迷路了。",
                "my name is": "我叫",
                "nice to meet you": "很高兴认识你。",
                "what time is it": "现在几点？",
                "i am allergic": "我过敏。",
                "water please": "请给我水。",
                "food please": "请给我食物。",
            },
            "ja": {
                "do you speak english": "英語を話せますか？",
                "i dont speak english": "英語は話せません。",
                "slow down please": "もう少しゆっくり話してください。",
                "please repeat": "もう一度言ってください。",
                "how much does it cost": "いくらですか？",
                "where is the pharmacy": "薬局はどこですか？",
                "i am lost": "道に迷いました。",
                "my name is": "私の名前は",
                "nice to meet you": "はじめまして。",
                "what time is it": "今何時ですか？",
                "i am allergic": "アレルギーがあります。",
                "water please": "お水をください。",
                "food please": "食べ物をください。",
            },
            "ko": {
                "do you speak english": "영어 하실 수 있나요?",
                "i dont speak english": "영어를 못 합니다.",
                "slow down please": "천천히 말해 주세요.",
                "please repeat": "다시 말씀해 주세요.",
                "how much does it cost": "얼마예요?",
                "where is the pharmacy": "약국이 어디예요?",
                "i am lost": "길을 잃었어요.",
                "my name is": "제 이름은",
                "nice to meet you": "만나서 반갑습니다.",
                "what time is it": "지금 몇 시예요?",
                "i am allergic": "알레르기가 있어요.",
                "water please": "물 주세요.",
                "food please": "음식 주세요.",
            },
            "ar": {
                "do you speak english": "هل تتحدث الإنجليزية؟",
                "i dont speak english": "لا أتحدث الإنجليزية.",
                "slow down please": "أبطئ من فضلك.",
                "please repeat": "كرر من فضلك.",
                "how much does it cost": "كم يكلف؟",
                "where is the pharmacy": "أين الصيدلية؟",
                "i am lost": "أنا ضائع.",
                "my name is": "اسمي",
                "nice to meet you": "تشرفت بمعرفتك.",
                "what time is it": "كم الساعة؟",
                "i am allergic": "لدي حساسية.",
                "water please": "ماء من فضلك.",
                "food please": "طعام من فضلك.",
            },
            "hi": {
                "do you speak english": "क्या आप अंग्रेज़ी बोलते हैं?",
                "i dont speak english": "मैं अंग्रेज़ी नहीं बोलता।",
                "slow down please": "धीरे बोलिए, कृपया।",
                "please repeat": "कृपया दोहराएं।",
                "how much does it cost": "इसकी कीमत कितनी है?",
                "where is the pharmacy": "फार्मेसी कहाँ है?",
                "i am lost": "मैं खो गया हूँ।",
                "my name is": "मेरा नाम",
                "nice to meet you": "आपसे मिलकर खुशी हुई।",
                "what time is it": "क्या समय हुआ है?",
                "i am allergic": "मुझे एलर्जी है।",
                "water please": "पानी, कृपया।",
                "food please": "खाना, कृपया।",
            },
            "ht": {
                "do you speak english": "Èske ou pale angle?",
                "i dont speak english": "Mwen pa pale angle.",
                "slow down please": "Ralanti, tanpri.",
                "please repeat": "Repete, tanpri.",
                "how much does it cost": "Konbyen li koute?",
                "where is the pharmacy": "Kote famasi a?",
                "i am lost": "Mwen pèdi.",
                "my name is": "Non mwen se",
                "nice to meet you": "Li fè mwen plezi rankontre ou.",
                "what time is it": "Ki lè li ye?",
                "i am allergic": "Mwen gen alèji.",
                "water please": "Dlo, tanpri.",
                "food please": "Manje, tanpri.",
            },
        }
        for target_language, phrases in travel.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_travel = {
            "es": {
                "habla ingles": "Do you speak English?",
                "no hablo ingles": "I don't speak English.",
                "mas despacio por favor": "Slow down please.",
                "repita por favor": "Please repeat.",
                "cuanto cuesta": "How much does it cost?",
                "donde esta la farmacia": "Where is the pharmacy?",
                "estoy perdido": "I am lost.",
                "mucho gusto": "Nice to meet you.",
                "que hora es": "What time is it?",
                "agua por favor": "Water please.",
            },
            "fr": {
                "parlez vous anglais": "Do you speak English?",
                "je ne parle pas anglais": "I don't speak English.",
                "plus lentement s il vous plait": "Slow down please.",
                "repetez s il vous plait": "Please repeat.",
                "combien ca coute": "How much does it cost?",
                "ou est la pharmacie": "Where is the pharmacy?",
                "je suis perdu": "I am lost.",
                "enchant e": "Nice to meet you.",
                "quelle heure est il": "What time is it?",
            },
            "de": {
                "sprechen sie englisch": "Do you speak English?",
                "ich spreche kein englisch": "I don't speak English.",
                "bitte langsamer": "Slow down please.",
                "bitte wiederholen": "Please repeat.",
                "wie viel kostet das": "How much does it cost?",
                "wo ist die apotheke": "Where is the pharmacy?",
                "ich habe mich verlaufen": "I am lost.",
            },
            "ht": {
                "eske ou pale angle": "Do you speak English?",
                "mwen pa pale angle": "I don't speak English.",
                "ralanti tanpri": "Slow down please.",
                "repete tanpri": "Please repeat.",
                "konbyen li koute": "How much does it cost?",
                "kote famasi a": "Where is the pharmacy?",
                "mwen pedi": "I am lost.",
                "ki le li ye": "What time is it?",
                "dlo tanpri": "Water please.",
            },
            "ru": {
                "\u0432\u044b \u0433\u043e\u0432\u043e\u0440\u0438\u0442\u0435 \u043f\u043e \u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438": "Do you speak English?",
                "\u044f \u043d\u0435 \u0433\u043e\u0432\u043e\u0440\u044e \u043f\u043e \u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438": "I don't speak English.",
                "\u0433\u0434\u0435 \u0430\u043f\u0442\u0435\u043a\u0430": "Where is the pharmacy?",
            },
            "zh": {
                "\u4f60\u4f1a\u8bf4\u82f1\u8bed\u5417": "Do you speak English?",
                "\u6211\u4e0d\u4f1a\u8bf4\u82f1\u8bed": "I don't speak English.",
                "\u836f\u5e97\u5728\u54ea\u91cc": "Where is the pharmacy?",
                "\u6211\u8ff7\u8def\u4e86": "I am lost.",
            },
            "ja": {
                "\u82f1\u8a9e\u3092\u8a71\u305b\u307e\u3059\u304b": "Do you speak English?",
                "\u82f1\u8a9e\u306f\u8a71\u305b\u307e\u305b\u3093": "I don't speak English.",
                "\u9053\u306b\u8ff7\u3044\u307e\u3057\u305f": "I am lost.",
            },
            "ko": {
                "\uc601\uc5b4 \ud558\uc2e4 \uc218 \uc788\ub098\uc694": "Do you speak English?",
                "\uc601\uc5b4\ub97c \ubabb \ud569\ub2c8\ub2e4": "I don't speak English.",
                "\uae38\uc744 \uc783\uc5c8\uc5b4\uc694": "I am lost.",
            },
            "ar": {
                "\u0647\u0644 \u062a\u062a\u062d\u062f\u062b \u0627\u0644\u0625\u0646\u062c\u0644\u064a\u0632\u064a\u0629": "Do you speak English?",
                "\u0644\u0627 \u0623\u062a\u062d\u062f\u062b \u0627\u0644\u0625\u0646\u062c\u0644\u064a\u0632\u064a\u0629": "I don't speak English.",
                "\u0623\u064a\u0646 \u0627\u0644\u0635\u064a\u062f\u0644\u064a\u0629": "Where is the pharmacy?",
            },
            "hi": {
                "\u0915\u094d\u092f\u093e \u0906\u092a \u0905\u0902\u0917\u094d\u0930\u0947\u091c\u0940 \u092c\u094b\u0932\u0924\u0947 \u0939\u0948\u0902": "Do you speak English?",
                "\u092e\u0948\u0902 \u0905\u0902\u0917\u094d\u0930\u0947\u091c\u0940 \u0928\u0939\u0940\u0902 \u092c\u094b\u0932\u0924\u093e": "I don't speak English.",
                "\u092b\u093e\u0930\u094d\u092e\u0947\u0938\u0940 \u0915\u0939\u093e\u0902 \u0939\u0948": "Where is the pharmacy?",
            },
        }
        for source_language, phrases in native_travel.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_direction_phrases(self) -> None:
        """Navigation and transport lines for travelers."""
        direction = {
            "es": {
                "turn left": "Gire a la izquierda.",
                "turn right": "Gire a la derecha.",
                "go straight": "Siga recto.",
                "stop here": "Pare aquí.",
                "where is the bus stop": "¿Dónde está la parada de autobús?",
                "i need a taxi": "Necesito un taxi.",
                "how do i get there": "¿Cómo llego allí?",
                "is it far": "¿Está lejos?",
            },
            "fr": {
                "turn left": "Tournez à gauche.",
                "turn right": "Tournez à droite.",
                "go straight": "Allez tout droit.",
                "stop here": "Arrêtez-vous ici.",
                "where is the bus stop": "Où est l'arrêt de bus ?",
                "i need a taxi": "J'ai besoin d'un taxi.",
                "how do i get there": "Comment y aller ?",
                "is it far": "Est-ce loin ?",
            },
            "de": {
                "turn left": "Biegen Sie links ab.",
                "turn right": "Biegen Sie rechts ab.",
                "go straight": "Gehen Sie geradeaus.",
                "stop here": "Halten Sie hier.",
                "where is the bus stop": "Wo ist die Bushaltestelle?",
                "i need a taxi": "Ich brauche ein Taxi.",
                "how do i get there": "Wie komme ich dorthin?",
                "is it far": "Ist es weit?",
            },
            "it": {
                "turn left": "Giri a sinistra.",
                "turn right": "Giri a destra.",
                "go straight": "Vada dritto.",
                "stop here": "Si fermi qui.",
                "where is the bus stop": "Dov'è la fermata dell'autobus?",
                "i need a taxi": "Ho bisogno di un taxi.",
                "how do i get there": "Come ci arrivo?",
                "is it far": "È lontano?",
            },
            "pt": {
                "turn left": "Vire à esquerda.",
                "turn right": "Vire à direita.",
                "go straight": "Siga em frente.",
                "stop here": "Pare aqui.",
                "where is the bus stop": "Onde fica o ponto de ônibus?",
                "i need a taxi": "Preciso de um táxi.",
                "how do i get there": "Como chego lá?",
                "is it far": "É longe?",
            },
            "nl": {
                "turn left": "Ga linksaf.",
                "turn right": "Ga rechtsaf.",
                "go straight": "Ga rechtdoor.",
                "stop here": "Stop hier.",
                "where is the bus stop": "Waar is de bushalte?",
                "i need a taxi": "Ik heb een taxi nodig.",
                "how do i get there": "Hoe kom ik daar?",
                "is it far": "Is het ver?",
            },
            "ru": {
                "turn left": "Поверните налево.",
                "turn right": "Поверните направо.",
                "go straight": "Идите прямо.",
                "stop here": "Остановитесь здесь.",
                "where is the bus stop": "Где автобусная остановка?",
                "i need a taxi": "Мне нужно такси.",
                "how do i get there": "Как туда добраться?",
                "is it far": "Это далеко?",
            },
            "zh": {
                "turn left": "向左转。",
                "turn right": "向右转。",
                "go straight": "直走。",
                "stop here": "在这里停。",
                "where is the bus stop": "公交车站在哪里？",
                "i need a taxi": "我需要出租车。",
                "how do i get there": "我怎么去那里？",
                "is it far": "远吗？",
            },
            "ja": {
                "turn left": "左に曲がってください。",
                "turn right": "右に曲がってください。",
                "go straight": "まっすぐ行ってください。",
                "stop here": "ここで止まってください。",
                "where is the bus stop": "バス停はどこですか？",
                "i need a taxi": "タクシーが必要です。",
                "how do i get there": "どうやって行けばいいですか？",
                "is it far": "遠いですか？",
            },
            "ko": {
                "turn left": "왼쪽으로 도세요.",
                "turn right": "오른쪽으로 도세요.",
                "go straight": "직진하세요.",
                "stop here": "여기서 세워 주세요.",
                "where is the bus stop": "버스 정류장이 어디예요?",
                "i need a taxi": "택시가 필요해요.",
                "how do i get there": "거기에 어떻게 가요?",
                "is it far": "멀어요?",
            },
            "ar": {
                "turn left": "انعطف يساراً.",
                "turn right": "انعطف يميناً.",
                "go straight": "اسلك مباشرة.",
                "stop here": "توقف هنا.",
                "where is the bus stop": "أين موقف الحافلة؟",
                "i need a taxi": "أحتاج إلى سيارة أجرة.",
                "how do i get there": "كيف أصل إلى هناك؟",
                "is it far": "هل هو بعيد؟",
            },
            "hi": {
                "turn left": "बाएँ मुड़िए।",
                "turn right": "दाएँ मुड़िए।",
                "go straight": "सीधे जाइए।",
                "stop here": "यहाँ रुकिए।",
                "where is the bus stop": "बस स्टॉप कहाँ है?",
                "i need a taxi": "मुझे टैक्सी चाहिए।",
                "how do i get there": "मैं वहाँ कैसे पहुँचूँ?",
                "is it far": "क्या यह दूर है?",
            },
            "ht": {
                "turn left": "Vire a goch.",
                "turn right": "Vire a dwat.",
                "go straight": "Ale dwat.",
                "stop here": "Kanpe isit.",
                "where is the bus stop": "Kote arè bis la?",
                "i need a taxi": "Mwen bezwen yon taksi.",
                "how do i get there": "Kijan mwen ka rive la?",
                "is it far": "Èske li lwen?",
            },
        }
        for target_language, phrases in direction.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_direction = {
            "es": {
                "gire a la izquierda": "Turn left.",
                "gire a la derecha": "Turn right.",
                "siga recto": "Go straight.",
                "pare aqui": "Stop here.",
                "donde esta la parada de autobus": "Where is the bus stop?",
                "necesito un taxi": "I need a taxi.",
            },
            "fr": {
                "tournez a gauche": "Turn left.",
                "tournez a droite": "Turn right.",
                "allez tout droit": "Go straight.",
                "arretez vous ici": "Stop here.",
                "ou est l arret de bus": "Where is the bus stop?",
                "j ai besoin d un taxi": "I need a taxi.",
            },
            "de": {
                "biegen sie links ab": "Turn left.",
                "biegen sie rechts ab": "Turn right.",
                "gehen sie geradeaus": "Go straight.",
                "halten sie hier": "Stop here.",
                "wo ist die bushaltestelle": "Where is the bus stop?",
                "ich brauche ein taxi": "I need a taxi.",
            },
            "it": {
                "giri a sinistra": "Turn left.",
                "giri a destra": "Turn right.",
                "vada dritto": "Go straight.",
                "si fermi qui": "Stop here.",
                "ho bisogno di un taxi": "I need a taxi.",
            },
            "pt": {
                "vire a esquerda": "Turn left.",
                "vire a direita": "Turn right.",
                "siga em frente": "Go straight.",
                "pare aqui": "Stop here.",
                "preciso de um taxi": "I need a taxi.",
            },
            "ht": {
                "vire a goch": "Turn left.",
                "vire a dwat": "Turn right.",
                "ale dwat": "Go straight.",
                "kanpe isit": "Stop here.",
                "kote are bis la": "Where is the bus stop?",
                "mwen bezwen yon taksi": "I need a taxi.",
            },
            "zh": {
                "\u5411\u5de6\u8f6c": "Turn left.",
                "\u5411\u53f3\u8f6c": "Turn right.",
                "\u76f4\u8d70": "Go straight.",
                "\u516c\u4ea4\u8f66\u7ad9\u5728\u54ea\u91cc": "Where is the bus stop?",
                "\u6211\u9700\u8981\u51fa\u79df\u8f66": "I need a taxi.",
            },
            "ja": {
                "\u5de6\u306b\u66f2\u304c\u3063\u3066\u304f\u3060\u3055\u3044": "Turn left.",
                "\u53f3\u306b\u66f2\u304c\u3063\u3066\u304f\u3060\u3055\u3044": "Turn right.",
                "\u30bf\u30af\u30b7\u30fc\u304c\u5fc5\u8981\u3067\u3059": "I need a taxi.",
            },
            "ko": {
                "\uc67c\ucabd\uc73c\ub85c \ub3c4\uc138\uc694": "Turn left.",
                "\uc624\ub978\ucabd\uc73c\ub85c \ub3c4\uc138\uc694": "Turn right.",
                "\ud0dd\uc2dc\uac00 \ud544\uc694\ud574\uc694": "I need a taxi.",
            },
            "ar": {
                "\u0627\u0646\u0639\u0637\u0641 \u064a\u0633\u0627\u0631\u0627": "Turn left.",
                "\u0627\u0646\u0639\u0637\u0641 \u064a\u0645\u064a\u0646\u0627": "Turn right.",
                "\u0623\u062d\u062a\u0627\u062c \u0625\u0644\u0649 \u0633\u064a\u0627\u0631\u0629 \u0623\u062c\u0631\u0629": "I need a taxi.",
            },
            "hi": {
                "\u092c\u093e\u090f\u0901 \u092e\u0941\u0921\u093c\u093f\u090f": "Turn left.",
                "\u0926\u093e\u090f\u0901 \u092e\u0941\u0921\u093c\u093f\u090f": "Turn right.",
                "\u092e\u0941\u091d\u0947 \u091f\u0948\u0915\u094d\u0938\u0940 \u091a\u093e\u0939\u093f\u090f": "I need a taxi.",
            },
        }
        for source_language, phrases in native_direction.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_food_phrases(self) -> None:
        """Restaurant and dining lines for travelers."""
        food = {
            "es": {
                "i am hungry": "Tengo hambre.",
                "the check please": "La cuenta, por favor.",
                "i would like water": "Quisiera agua.",
                "i am vegetarian": "Soy vegetariano.",
                "i am allergic to nuts": "Soy alérgico a los frutos secos.",
                "what do you recommend": "¿Qué recomienda?",
                "is this gluten free": "¿Esto es sin gluten?",
                "no spicy please": "Sin picante, por favor.",
            },
            "fr": {
                "i am hungry": "J'ai faim.",
                "the check please": "L'addition, s'il vous plaît.",
                "i would like water": "Je voudrais de l'eau.",
                "i am vegetarian": "Je suis végétarien.",
                "i am allergic to nuts": "Je suis allergique aux noix.",
                "what do you recommend": "Que recommandez-vous ?",
                "is this gluten free": "Est-ce sans gluten ?",
                "no spicy please": "Sans épicé, s'il vous plaît.",
            },
            "de": {
                "i am hungry": "Ich habe Hunger.",
                "the check please": "Die Rechnung, bitte.",
                "i would like water": "Ich möchte Wasser.",
                "i am vegetarian": "Ich bin Vegetarier.",
                "i am allergic to nuts": "Ich bin allergisch gegen Nüsse.",
                "what do you recommend": "Was empfehlen Sie?",
                "is this gluten free": "Ist das glutenfrei?",
                "no spicy please": "Nicht scharf, bitte.",
            },
            "it": {
                "i am hungry": "Ho fame.",
                "the check please": "Il conto, per favore.",
                "i would like water": "Vorrei dell'acqua.",
                "i am vegetarian": "Sono vegetariano.",
                "i am allergic to nuts": "Sono allergico alla frutta secca.",
                "what do you recommend": "Cosa consiglia?",
                "is this gluten free": "È senza glutine?",
                "no spicy please": "Non piccante, per favore.",
            },
            "pt": {
                "i am hungry": "Estou com fome.",
                "the check please": "A conta, por favor.",
                "i would like water": "Eu gostaria de água.",
                "i am vegetarian": "Sou vegetariano.",
                "i am allergic to nuts": "Sou alérgico a nozes.",
                "what do you recommend": "O que você recomenda?",
                "is this gluten free": "Isso é sem glúten?",
                "no spicy please": "Sem pimenta, por favor.",
            },
            "nl": {
                "i am hungry": "Ik heb honger.",
                "the check please": "De rekening, alstublieft.",
                "i would like water": "Ik wil graag water.",
                "i am vegetarian": "Ik ben vegetariër.",
                "i am allergic to nuts": "Ik ben allergisch voor noten.",
                "what do you recommend": "Wat raadt u aan?",
                "is this gluten free": "Is dit glutenvrij?",
                "no spicy please": "Niet pittig, alstublieft.",
            },
            "ru": {
                "i am hungry": "Я голоден.",
                "the check please": "Счёт, пожалуйста.",
                "i would like water": "Я хотел бы воды.",
                "i am vegetarian": "Я вегетарианец.",
                "i am allergic to nuts": "У меня аллергия на орехи.",
                "what do you recommend": "Что вы рекомендуете?",
                "is this gluten free": "Это без глютена?",
                "no spicy please": "Не острое, пожалуйста.",
            },
            "zh": {
                "i am hungry": "我饿了。",
                "the check please": "请结账。",
                "i would like water": "我想要水。",
                "i am vegetarian": "我是素食者。",
                "i am allergic to nuts": "我对坚果过敏。",
                "what do you recommend": "您推荐什么？",
                "is this gluten free": "这是无麸质的吗？",
                "no spicy please": "请不要辣。",
            },
            "ja": {
                "i am hungry": "お腹がすきました。",
                "the check please": "お会計お願いします。",
                "i would like water": "お水をください。",
                "i am vegetarian": "私は菜食主義者です。",
                "i am allergic to nuts": "ナッツアレルギーがあります。",
                "what do you recommend": "おすすめは何ですか？",
                "is this gluten free": "これはグルテンフリーですか？",
                "no spicy please": "辛くしないでください。",
            },
            "ko": {
                "i am hungry": "배고파요.",
                "the check please": "계산서 주세요.",
                "i would like water": "물 주세요.",
                "i am vegetarian": "저는 채식주의자예요.",
                "i am allergic to nuts": "견과류 알레르기가 있어요.",
                "what do you recommend": "뭐를 추천하세요?",
                "is this gluten free": "글루텐 프리인가요?",
                "no spicy please": "맵지 않게 해 주세요.",
            },
            "ar": {
                "i am hungry": "أنا جائع.",
                "the check please": "الحساب من فضلك.",
                "i would like water": "أريد ماء.",
                "i am vegetarian": "أنا نباتي.",
                "i am allergic to nuts": "لدي حساسية من المكسرات.",
                "what do you recommend": "ماذا تنصح؟",
                "is this gluten free": "هل هذا خالٍ من الغلوتين؟",
                "no spicy please": "بدون توابل حارة من فضلك.",
            },
            "hi": {
                "i am hungry": "मुझे भूख लगी है।",
                "the check please": "बिल दीजिए, कृपया।",
                "i would like water": "मुझे पानी चाहिए।",
                "i am vegetarian": "मैं शाकाहारी हूँ।",
                "i am allergic to nuts": "मुझे मेवों से एलर्जी है।",
                "what do you recommend": "आप क्या सुझाव देते हैं?",
                "is this gluten free": "क्या यह ग्लूटेन मुक्त है?",
                "no spicy please": "मसालेदार नहीं, कृपया।",
            },
            "ht": {
                "i am hungry": "Mwen grangou.",
                "the check please": "Bòdè a, tanpri.",
                "i would like water": "Mwen ta renmen dlo.",
                "i am vegetarian": "Mwen se yon vejetaryen.",
                "i am allergic to nuts": "Mwen gen alèji ak nwa.",
                "what do you recommend": "Kisa ou rekòmande?",
                "is this gluten free": "Èske sa san gluten?",
                "no spicy please": "Pa fè l pike, tanpri.",
            },
        }
        for target_language, phrases in food.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_food = {
            "es": {
                "tengo hambre": "I am hungry.",
                "la cuenta por favor": "The check please.",
                "quisiera agua": "I would like water.",
                "soy vegetariano": "I am vegetarian.",
            },
            "fr": {
                "j ai faim": "I am hungry.",
                "l addition s il vous plait": "The check please.",
                "je voudrais de l eau": "I would like water.",
            },
            "de": {
                "ich habe hunger": "I am hungry.",
                "die rechnung bitte": "The check please.",
                "ich mochte wasser": "I would like water.",
            },
            "it": {
                "ho fame": "I am hungry.",
                "il conto per favore": "The check please.",
            },
            "pt": {
                "estou com fome": "I am hungry.",
                "a conta por favor": "The check please.",
            },
            "ht": {
                "mwen grangou": "I am hungry.",
                "bode a tanpri": "The check please.",
                "mwen ta renmen dlo": "I would like water.",
            },
            "zh": {
                "\u6211\u997f\u4e86": "I am hungry.",
                "\u8bf7\u7ed3\u8d26": "The check please.",
                "\u6211\u60f3\u8981\u6c34": "I would like water.",
            },
            "ja": {
                "\u304a\u4f1a\u8a08\u304a\u9858\u3044\u3057\u307e\u3059": "The check please.",
                "\u304a\u6c34\u3092\u304f\u3060\u3055\u3044": "I would like water.",
            },
            "ko": {
                "\ubc30\uace0\ud30c\uc694": "I am hungry.",
                "\uacc4\uc0b0\uc11c \uc8fc\uc138\uc694": "The check please.",
            },
        }
        for source_language, phrases in native_food.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_medical_phrases(self) -> None:
        """Common symptom lines for clinic and pharmacy visits."""
        medical = {
            "es": {
                "i feel sick": "Me siento mal.",
                "i have a fever": "Tengo fiebre.",
                "i have a headache": "Me duele la cabeza.",
                "i have chest pain": "Me duele el pecho.",
                "i am diabetic": "Soy diabético.",
                "call an ambulance": "Llame a una ambulancia.",
            },
            "fr": {
                "i feel sick": "Je me sens mal.",
                "i have a fever": "J'ai de la fièvre.",
                "i have a headache": "J'ai mal à la tête.",
                "i have chest pain": "J'ai mal à la poitrine.",
                "i am diabetic": "Je suis diabétique.",
                "call an ambulance": "Appelez une ambulance.",
            },
            "de": {
                "i feel sick": "Mir ist schlecht.",
                "i have a fever": "Ich habe Fieber.",
                "i have a headache": "Ich habe Kopfschmerzen.",
                "i have chest pain": "Ich habe Brustschmerzen.",
                "i am diabetic": "Ich bin Diabetiker.",
                "call an ambulance": "Rufen Sie einen Krankenwagen.",
            },
            "it": {
                "i feel sick": "Mi sento male.",
                "i have a fever": "Ho la febbre.",
                "i have a headache": "Ho mal di testa.",
                "i have chest pain": "Ho dolore al petto.",
                "i am diabetic": "Sono diabetico.",
                "call an ambulance": "Chiami un'ambulanza.",
            },
            "pt": {
                "i feel sick": "Estou me sentindo mal.",
                "i have a fever": "Estou com febre.",
                "i have a headache": "Estou com dor de cabeça.",
                "i have chest pain": "Estou com dor no peito.",
                "i am diabetic": "Sou diabético.",
                "call an ambulance": "Chame uma ambulância.",
            },
            "nl": {
                "i feel sick": "Ik voel me ziek.",
                "i have a fever": "Ik heb koorts.",
                "i have a headache": "Ik heb hoofdpijn.",
                "i have chest pain": "Ik heb pijn op de borst.",
                "i am diabetic": "Ik ben diabetisch.",
                "call an ambulance": "Bel een ambulance.",
            },
            "ru": {
                "i feel sick": "Мне плохо.",
                "i have a fever": "У меня жар.",
                "i have a headache": "У меня болит голова.",
                "i have chest pain": "У меня боль в груди.",
                "i am diabetic": "Я диабетик.",
                "call an ambulance": "Вызовите скорую.",
            },
            "zh": {
                "i feel sick": "我感觉不舒服。",
                "i have a fever": "我发烧了。",
                "i have a headache": "我头疼。",
                "i have chest pain": "我胸口疼。",
                "i am diabetic": "我是糖尿病患者。",
                "call an ambulance": "请叫救护车。",
            },
            "ja": {
                "i feel sick": "気分が悪いです。",
                "i have a fever": "熱があります。",
                "i have a headache": "頭が痛いです。",
                "i have chest pain": "胸が痛いです。",
                "i am diabetic": "糖尿病です。",
                "call an ambulance": "救急車を呼んでください。",
            },
            "ko": {
                "i feel sick": "몸이 안 좋아요.",
                "i have a fever": "열이 있어요.",
                "i have a headache": "머리가 아파요.",
                "i have chest pain": "가슴이 아파요.",
                "i am diabetic": "저는 당뇨병이 있어요.",
                "call an ambulance": "구급차를 불러 주세요.",
            },
            "ar": {
                "i feel sick": "أشعر بالمرض.",
                "i have a fever": "لدي حمى.",
                "i have a headache": "لدي صداع.",
                "i have chest pain": "لدي ألم في الصدر.",
                "i am diabetic": "أنا مصاب بالسكري.",
                "call an ambulance": "اتصل بسيارة إسعاف.",
            },
            "hi": {
                "i feel sick": "मैं बीमार महसूस कर रहा हूँ।",
                "i have a fever": "मुझे बुखार है।",
                "i have a headache": "मुझे सिरदर्द है।",
                "i have chest pain": "मुझे छाती में दर्द है।",
                "i am diabetic": "मुझे मधुमेह है।",
                "call an ambulance": "एम्बुलेंस बुलाइए।",
            },
            "ht": {
                "i feel sick": "Mwen pa santi m byen.",
                "i have a fever": "Mwen gen lafyèv.",
                "i have a headache": "Mwen gen maltèt.",
                "i have chest pain": "Mwen gen doulè nan pwatrin.",
                "i am diabetic": "Mwen gen dyabèt.",
                "call an ambulance": "Rele yon anbilans.",
            },
        }
        for target_language, phrases in medical.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_medical = {
            "es": {
                "me siento mal": "I feel sick.",
                "tengo fiebre": "I have a fever.",
                "me duele la cabeza": "I have a headache.",
                "llame a una ambulancia": "Call an ambulance.",
            },
            "fr": {
                "je me sens mal": "I feel sick.",
                "j ai de la fievre": "I have a fever.",
                "appelez une ambulance": "Call an ambulance.",
            },
            "de": {
                "mir ist schlecht": "I feel sick.",
                "ich habe fieber": "I have a fever.",
                "rufen sie einen krankenwagen": "Call an ambulance.",
            },
            "ht": {
                "mwen pa santi m byen": "I feel sick.",
                "mwen gen lafyev": "I have a fever.",
                "mwen gen maltet": "I have a headache.",
                "rele yon anbilans": "Call an ambulance.",
            },
            "zh": {
                "\u6211\u611f\u89c9\u4e0d\u8212\u670d": "I feel sick.",
                "\u6211\u53d1\u70e7\u4e86": "I have a fever.",
                "\u8bf7\u53eb\u6551\u62a4\u8f66": "Call an ambulance.",
            },
            "ja": {
                "\u6c17\u5206\u304c\u6076\u3044\u3067\u3059": "I feel sick.",
                "\u71b1\u304c\u3042\u308a\u307e\u3059": "I have a fever.",
                "\u6551\u6025\u8eca\u3092\u547c\u3093\u3067\u304f\u3060\u3055\u3044": "Call an ambulance.",
            },
            "ko": {
                "\ubab8\uc774 \uc548 \uc88b\uc544\uc694": "I feel sick.",
                "\uc5f4\uc774 \uc788\uc5b4\uc694": "I have a fever.",
                "\uad6c\uae09\ucc28\ub97c \ubd88\ub7ec \uc8fc\uc138\uc694": "Call an ambulance.",
            },
            "ar": {
                "\u0623\u0634\u0639\u0631 \u0628\u0627\u0644\u0645\u0631\u0636": "I feel sick.",
                "\u0644\u062f\u064a \u062d\u0645\u0649": "I have a fever.",
                "\u0627\u062a\u0635\u0644 \u0628\u0633\u064a\u0627\u0631\u0629 \u0625\u0633\u0639\u0627\u0641": "Call an ambulance.",
            },
            "hi": {
                "\u092e\u0948\u0902 \u092c\u0940\u092e\u093e\u0930 \u092e\u0939\u0938\u0942\u0938 \u0915\u0930 \u0930\u0939\u093e \u0939\u0942\u0901": "I feel sick.",
                "\u092e\u0941\u091d\u0947 \u092c\u0941\u0916\u093e\u0930 \u0939\u0948": "I have a fever.",
                "\u090f\u092e\u094d\u092c\u0941\u0932\u0947\u0902\u0938 \u092c\u0941\u0932\u093e\u0907\u090f": "Call an ambulance.",
            },
        }
        for source_language, phrases in native_medical.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_daily_phrases(self) -> None:
        """Time, hotel, shopping, and social phrases for everyday travel."""
        daily = {
            "es": {
                "today": "Hoy.", "tomorrow": "Mañana.", "yesterday": "Ayer.", "now": "Ahora.", "later": "Más tarde.",
                "i have a reservation": "Tengo una reserva.",
                "what is the wifi password": "¿Cuál es la contraseña del wifi?",
                "i need a room": "Necesito una habitación.",
                "check in please": "Registro, por favor.",
                "check out please": "Salida, por favor.",
                "how much is this": "¿Cuánto cuesta esto?",
                "do you accept cards": "¿Aceptan tarjetas?",
                "i am just looking": "Solo estoy mirando.",
                "can i try this on": "¿Puedo probármelo?",
                "too expensive": "Demasiado caro.",
                "see you later": "Hasta luego.",
                "congratulations": "Felicidades.",
                "happy birthday": "Feliz cumpleaños.",
                "good luck": "Buena suerte.",
            },
            "fr": {
                "today": "Aujourd'hui.", "tomorrow": "Demain.", "yesterday": "Hier.", "now": "Maintenant.", "later": "Plus tard.",
                "i have a reservation": "J'ai une réservation.",
                "what is the wifi password": "Quel est le mot de passe wifi ?",
                "i need a room": "J'ai besoin d'une chambre.",
                "check in please": "Enregistrement, s'il vous plaît.",
                "check out please": "Départ, s'il vous plaît.",
                "how much is this": "Combien ça coûte ?",
                "do you accept cards": "Acceptez-vous les cartes ?",
                "i am just looking": "Je regarde seulement.",
                "can i try this on": "Puis-je l'essayer ?",
                "too expensive": "Trop cher.",
                "see you later": "À plus tard.",
                "congratulations": "Félicitations.",
                "happy birthday": "Joyeux anniversaire.",
                "good luck": "Bonne chance.",
            },
            "de": {
                "today": "Heute.", "tomorrow": "Morgen.", "yesterday": "Gestern.", "now": "Jetzt.", "later": "Später.",
                "i have a reservation": "Ich habe eine Reservierung.",
                "what is the wifi password": "Wie lautet das WLAN-Passwort?",
                "i need a room": "Ich brauche ein Zimmer.",
                "check in please": "Einchecken, bitte.",
                "check out please": "Auschecken, bitte.",
                "how much is this": "Wie viel kostet das?",
                "do you accept cards": "Akzeptieren Sie Karten?",
                "i am just looking": "Ich schaue nur.",
                "can i try this on": "Kann ich das anprobieren?",
                "too expensive": "Zu teuer.",
                "see you later": "Bis später.",
                "congratulations": "Herzlichen Glückwunsch.",
                "happy birthday": "Alles Gute zum Geburtstag.",
                "good luck": "Viel Glück.",
            },
            "it": {
                "today": "Oggi.", "tomorrow": "Domani.", "yesterday": "Ieri.", "now": "Adesso.", "later": "Più tardi.",
                "i have a reservation": "Ho una prenotazione.",
                "what is the wifi password": "Qual è la password del wifi?",
                "i need a room": "Ho bisogno di una camera.",
                "check in please": "Check-in, per favore.",
                "check out please": "Check-out, per favore.",
                "how much is this": "Quanto costa questo?",
                "do you accept cards": "Accettate carte?",
                "i am just looking": "Sto solo guardando.",
                "can i try this on": "Posso provarlo?",
                "too expensive": "Troppo caro.",
                "see you later": "A dopo.",
                "congratulations": "Congratulazioni.",
                "happy birthday": "Buon compleanno.",
                "good luck": "Buona fortuna.",
            },
            "pt": {
                "today": "Hoje.", "tomorrow": "Amanhã.", "yesterday": "Ontem.", "now": "Agora.", "later": "Mais tarde.",
                "i have a reservation": "Tenho uma reserva.",
                "what is the wifi password": "Qual é a senha do wifi?",
                "i need a room": "Preciso de um quarto.",
                "check in please": "Check-in, por favor.",
                "check out please": "Check-out, por favor.",
                "how much is this": "Quanto custa isso?",
                "do you accept cards": "Aceitam cartões?",
                "i am just looking": "Estou só olhando.",
                "can i try this on": "Posso experimentar?",
                "too expensive": "Muito caro.",
                "see you later": "Até mais tarde.",
                "congratulations": "Parabéns.",
                "happy birthday": "Feliz aniversário.",
                "good luck": "Boa sorte.",
            },
            "nl": {
                "today": "Vandaag.", "tomorrow": "Morgen.", "yesterday": "Gisteren.", "now": "Nu.", "later": "Later.",
                "i have a reservation": "Ik heb een reservering.",
                "what is the wifi password": "Wat is het wifi-wachtwoord?",
                "i need a room": "Ik heb een kamer nodig.",
                "check in please": "Inchecken, alstublieft.",
                "check out please": "Uitchecken, alstublieft.",
                "how much is this": "Hoeveel kost dit?",
                "do you accept cards": "Accepteert u kaarten?",
                "i am just looking": "Ik kijk alleen.",
                "can i try this on": "Mag ik dit passen?",
                "too expensive": "Te duur.",
                "see you later": "Tot later.",
                "congratulations": "Gefeliciteerd.",
                "happy birthday": "Gefeliciteerd met je verjaardag.",
                "good luck": "Veel succes.",
            },
            "ru": {
                "today": "Сегодня.", "tomorrow": "Завтра.", "yesterday": "Вчера.", "now": "Сейчас.", "later": "Позже.",
                "i have a reservation": "У меня есть бронь.",
                "what is the wifi password": "Какой пароль от wifi?",
                "i need a room": "Мне нужна комната.",
                "check in please": "Регистрация, пожалуйста.",
                "check out please": "Выезд, пожалуйста.",
                "how much is this": "Сколько это стоит?",
                "do you accept cards": "Вы принимаете карты?",
                "i am just looking": "Я просто смотрю.",
                "can i try this on": "Можно примерить?",
                "too expensive": "Слишком дорого.",
                "see you later": "Увидимся позже.",
                "congratulations": "Поздравляю.",
                "happy birthday": "С днём рождения.",
                "good luck": "Удачи.",
            },
            "zh": {
                "today": "今天。", "tomorrow": "明天。", "yesterday": "昨天。", "now": "现在。", "later": "稍后。",
                "i have a reservation": "我有预订。",
                "what is the wifi password": "WiFi密码是什么？",
                "i need a room": "我需要一间房。",
                "check in please": "请办理入住。",
                "check out please": "请办理退房。",
                "how much is this": "这个多少钱？",
                "do you accept cards": "可以刷卡吗？",
                "i am just looking": "我只是看看。",
                "can i try this on": "我可以试穿吗？",
                "too expensive": "太贵了。",
                "see you later": "回头见。",
                "congratulations": "恭喜。",
                "happy birthday": "生日快乐。",
                "good luck": "祝你好运。",
            },
            "ja": {
                "today": "今日。", "tomorrow": "明日。", "yesterday": "昨日。", "now": "今。", "later": "後で。",
                "i have a reservation": "予約があります。",
                "what is the wifi password": "WiFiのパスワードは何ですか？",
                "i need a room": "部屋が必要です。",
                "check in please": "チェックインお願いします。",
                "check out please": "チェックアウトお願いします。",
                "how much is this": "これはいくらですか？",
                "do you accept cards": "カードは使えますか？",
                "i am just looking": "見ているだけです。",
                "can i try this on": "試着できますか？",
                "too expensive": "高すぎます。",
                "see you later": "また後で。",
                "congratulations": "おめでとうございます。",
                "happy birthday": "お誕生日おめでとうございます。",
                "good luck": "頑張ってください。",
            },
            "ko": {
                "today": "오늘.", "tomorrow": "내일.", "yesterday": "어제.", "now": "지금.", "later": "나중에.",
                "i have a reservation": "예약했어요.",
                "what is the wifi password": "와이파이 비밀번호가 뭐예요?",
                "i need a room": "방이 필요해요.",
                "check in please": "체크인 해 주세요.",
                "check out please": "체크아웃 해 주세요.",
                "how much is this": "이거 얼마예요?",
                "do you accept cards": "카드 되나요?",
                "i am just looking": "그냥 구경하는 거예요.",
                "can i try this on": "입어 봐도 돼요?",
                "too expensive": "너무 비싸요.",
                "see you later": "나중에 봐요.",
                "congratulations": "축하해요.",
                "happy birthday": "생일 축하해요.",
                "good luck": "행운을 빌어요.",
            },
            "ar": {
                "today": "اليوم.", "tomorrow": "غداً.", "yesterday": "أمس.", "now": "الآن.", "later": "لاحقاً.",
                "i have a reservation": "لدي حجز.",
                "what is the wifi password": "ما هي كلمة مرور الواي فاي؟",
                "i need a room": "أحتاج إلى غرفة.",
                "check in please": "تسجيل الدخول من فضلك.",
                "check out please": "تسجيل الخروج من فضلك.",
                "how much is this": "كم سعر هذا؟",
                "do you accept cards": "هل تقبلون البطاقات؟",
                "i am just looking": "أنا فقط أتفرج.",
                "can i try this on": "هل يمكنني تجربته؟",
                "too expensive": "غالي جداً.",
                "see you later": "أراك لاحقاً.",
                "congratulations": "تهانينا.",
                "happy birthday": "عيد ميلاد سعيد.",
                "good luck": "حظاً سعيداً.",
            },
            "hi": {
                "today": "आज।", "tomorrow": "कल।", "yesterday": "बीता कल।", "now": "अभी।", "later": "बाद में।",
                "i have a reservation": "मेरा आरक्षण है।",
                "what is the wifi password": "वाईफाई पासवर्ड क्या है?",
                "i need a room": "मुझे कमरा चाहिए।",
                "check in please": "चेक इन करें, कृपया।",
                "check out please": "चेक आउट करें, कृपया।",
                "how much is this": "यह कितने का है?",
                "do you accept cards": "क्या आप कार्ड स्वीकार करते हैं?",
                "i am just looking": "मैं बस देख रहा हूँ।",
                "can i try this on": "क्या मैं इसे पहन कर देख सकता हूँ?",
                "too expensive": "बहुत महँगा।",
                "see you later": "फिर मिलेंगे।",
                "congratulations": "बधाई हो।",
                "happy birthday": "जन्मदिन मुबारक।",
                "good luck": "शुभकामनाएँ।",
            },
            "ht": {
                "today": "Jodi a.", "tomorrow": "Demen.", "yesterday": "Yè.", "now": "Kounye a.", "later": "Pita.",
                "i have a reservation": "Mwen gen yon rezèvasyon.",
                "what is the wifi password": "Ki modpas wifi a?",
                "i need a room": "Mwen bezwen yon chanm.",
                "check in please": "Anrejistreman, tanpri.",
                "check out please": "Depa, tanpri.",
                "how much is this": "Konbyen sa koute?",
                "do you accept cards": "Èske ou aksepte kat?",
                "i am just looking": "Mwen sèlman ap gade.",
                "can i try this on": "Èske mwen ka eseye li?",
                "too expensive": "Sa twò chè.",
                "see you later": "Na wè pita.",
                "congratulations": "Felisitasyon.",
                "happy birthday": "Bòn fèt.",
                "good luck": "Bon chans.",
            },
        }
        for target_language, phrases in daily.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_daily = {
            "es": {
                "hoy": "Today.", "manana": "Tomorrow.", "ayer": "Yesterday.",
                "tengo una reserva": "I have a reservation.",
                "cuanto cuesta esto": "How much is this?",
                "hasta luego": "See you later.",
            },
            "fr": {
                "aujourd hui": "Today.", "demain": "Tomorrow.",
                "j ai une reservation": "I have a reservation.",
                "a plus tard": "See you later.",
            },
            "de": {
                "heute": "Today.", "morgen": "Tomorrow.",
                "ich habe eine reservierung": "I have a reservation.",
                "wie viel kostet das": "How much is this?",
            },
            "ht": {
                "jodi a": "Today.", "demen": "Tomorrow.", "kounye a": "Now.",
                "mwen gen yon rezèvasyon": "I have a reservation.",
                "konbyen sa koute": "How much is this?",
                "na we pita": "See you later.",
            },
            "zh": {
                "\u4eca\u5929": "Today.", "\u660e\u5929": "Tomorrow.",
                "\u8fd9\u4e2a\u591a\u5c11\u94b1": "How much is this?",
                "\u6211\u6709\u9884\u8ba2": "I have a reservation.",
            },
            "ja": {
                "\u4eca\u65e5": "Today.", "\u660e\u65e5": "Tomorrow.",
                "\u3053\u308c\u306f\u3044\u304f\u3089\u3067\u3059\u304b": "How much is this?",
            },
            "ko": {
                "\uc624\ub298": "Today.", "\ub0b4\uc77c": "Tomorrow.",
                "\uc774\uac70 \uc5bc\ub9c8\uc608\uc694": "How much is this?",
            },
        }
        for source_language, phrases in native_daily.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_number_phrases(self) -> None:
        """Digits and number words for prices, addresses, and counting."""
        numbers = {
            "es": {
                "0": "cero", "zero": "cero", "1": "uno", "one": "uno", "2": "dos", "two": "dos",
                "3": "tres", "three": "tres", "4": "cuatro", "four": "cuatro", "5": "cinco", "five": "cinco",
                "6": "seis", "six": "seis", "7": "siete", "seven": "siete", "8": "ocho", "eight": "ocho",
                "9": "nueve", "nine": "nueve", "10": "diez", "ten": "diez", "twenty": "veinte", "hundred": "cien",
            },
            "fr": {
                "0": "zéro", "zero": "zéro", "1": "un", "one": "un", "2": "deux", "two": "deux",
                "3": "trois", "three": "trois", "4": "quatre", "four": "quatre", "5": "cinq", "five": "cinq",
                "6": "six", "six": "six", "7": "sept", "seven": "sept", "8": "huit", "eight": "huit",
                "9": "neuf", "nine": "neuf", "10": "dix", "ten": "dix", "twenty": "vingt", "hundred": "cent",
            },
            "de": {
                "0": "null", "zero": "null", "1": "eins", "one": "eins", "2": "zwei", "two": "zwei",
                "3": "drei", "three": "drei", "4": "vier", "four": "vier", "5": "fünf", "five": "fünf",
                "6": "sechs", "six": "sechs", "7": "sieben", "seven": "sieben", "8": "acht", "eight": "acht",
                "9": "neun", "nine": "neun", "10": "zehn", "ten": "zehn", "twenty": "zwanzig", "hundred": "hundert",
            },
            "it": {
                "0": "zero", "zero": "zero", "1": "uno", "one": "uno", "2": "due", "two": "due",
                "3": "tre", "three": "tre", "4": "quattro", "four": "quattro", "5": "cinque", "five": "cinque",
                "6": "sei", "six": "sei", "7": "sette", "seven": "sette", "8": "otto", "eight": "otto",
                "9": "nove", "nine": "nove", "10": "dieci", "ten": "dieci", "twenty": "venti", "hundred": "cento",
            },
            "pt": {
                "0": "zero", "zero": "zero", "1": "um", "one": "um", "2": "dois", "two": "dois",
                "3": "três", "three": "três", "4": "quatro", "four": "quatro", "5": "cinco", "five": "cinco",
                "6": "seis", "six": "seis", "7": "sete", "seven": "sete", "8": "oito", "eight": "oito",
                "9": "nove", "nine": "nove", "10": "dez", "ten": "dez", "twenty": "vinte", "hundred": "cem",
            },
            "nl": {
                "0": "nul", "zero": "nul", "1": "een", "one": "een", "2": "twee", "two": "twee",
                "3": "drie", "three": "drie", "4": "vier", "four": "vier", "5": "vijf", "five": "vijf",
                "6": "zes", "six": "zes", "7": "zeven", "seven": "zeven", "8": "acht", "eight": "acht",
                "9": "negen", "nine": "negen", "10": "tien", "ten": "tien", "twenty": "twintig", "hundred": "honderd",
            },
            "ru": {
                "0": "ноль", "zero": "ноль", "1": "один", "one": "один", "2": "два", "two": "два",
                "3": "три", "three": "три", "4": "четыре", "four": "четыре", "5": "пять", "five": "пять",
                "6": "шесть", "six": "шесть", "7": "семь", "seven": "семь", "8": "восемь", "eight": "восемь",
                "9": "девять", "nine": "девять", "10": "десять", "ten": "десять", "twenty": "двадцать", "hundred": "сто",
            },
            "zh": {
                "0": "零", "zero": "零", "1": "一", "one": "一", "2": "二", "two": "二",
                "3": "三", "three": "三", "4": "四", "four": "四", "5": "五", "five": "五",
                "6": "六", "six": "六", "7": "七", "seven": "七", "8": "八", "eight": "八",
                "9": "九", "nine": "九", "10": "十", "ten": "十", "twenty": "二十", "hundred": "一百",
            },
            "ja": {
                "0": "ゼロ", "zero": "ゼロ", "1": "一", "one": "一", "2": "二", "two": "二",
                "3": "三", "three": "三", "4": "四", "four": "四", "5": "五", "five": "五",
                "6": "六", "six": "六", "7": "七", "seven": "七", "8": "八", "eight": "八",
                "9": "九", "nine": "九", "10": "十", "ten": "十", "twenty": "二十", "hundred": "百",
            },
            "ko": {
                "0": "영", "zero": "영", "1": "일", "one": "일", "2": "이", "two": "이",
                "3": "삼", "three": "삼", "4": "사", "four": "사", "5": "오", "five": "오",
                "6": "육", "six": "육", "7": "칠", "seven": "칠", "8": "팔", "eight": "팔",
                "9": "구", "nine": "구", "10": "십", "ten": "십", "twenty": "이십", "hundred": "백",
            },
            "ar": {
                "0": "صفر", "zero": "صفر", "1": "واحد", "one": "واحد", "2": "اثنان", "two": "اثنان",
                "3": "ثلاثة", "three": "ثلاثة", "4": "أربعة", "four": "أربعة", "5": "خمسة", "five": "خمسة",
                "6": "ستة", "six": "ستة", "7": "سبعة", "seven": "سبعة", "8": "ثمانية", "eight": "ثمانية",
                "9": "تسعة", "nine": "تسعة", "10": "عشرة", "ten": "عشرة", "twenty": "عشرون", "hundred": "مائة",
            },
            "hi": {
                "0": "शून्य", "zero": "शून्य", "1": "एक", "one": "एक", "2": "दो", "two": "दो",
                "3": "तीन", "three": "तीन", "4": "चार", "four": "चार", "5": "पांच", "five": "पांच",
                "6": "छह", "six": "छह", "7": "सात", "seven": "सात", "8": "आठ", "eight": "आठ",
                "9": "नौ", "nine": "नौ", "10": "दस", "ten": "दस", "twenty": "बीस", "hundred": "सौ",
            },
            "ht": {
                "0": "zewo", "zero": "zewo", "1": "youn", "one": "youn", "2": "de", "two": "de",
                "3": "twa", "three": "twa", "4": "kat", "four": "kat", "5": "senk", "five": "senk",
                "6": "sis", "six": "sis", "7": "sèt", "seven": "sèt", "8": "uit", "eight": "uit",
                "9": "nèf", "nine": "nèf", "10": "dis", "ten": "dis", "twenty": "ven", "hundred": "san",
            },
        }
        for target_language, phrases in numbers.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_numbers = {
            "es": {"uno": "One.", "dos": "Two.", "tres": "Three.", "cinco": "Five.", "diez": "Ten."},
            "fr": {"un": "One.", "deux": "Two.", "trois": "Three.", "cinq": "Five.", "dix": "Ten."},
            "de": {"eins": "One.", "zwei": "Two.", "drei": "Three.", "funf": "Five.", "zehn": "Ten."},
            "ht": {"youn": "One.", "de": "Two.", "twa": "Three.", "senk": "Five.", "dis": "Ten."},
            "zh": {"\u4e00": "One.", "\u4e8c": "Two.", "\u4e09": "Three.", "\u4e94": "Five.", "\u5341": "Ten."},
            "ja": {"\u4e00": "One.", "\u4e8c": "Two.", "\u4e09": "Three.", "\u4e94": "Five.", "\u5341": "Ten."},
            "ko": {"\uc77c": "One.", "\uc774": "Two.", "\uc0bc": "Three.", "\uc624": "Five.", "\uc2ed": "Ten."},
        }
        for source_language, phrases in native_numbers.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_essential_phrases(self) -> None:
        """High-frequency lines not covered by other phrase tables."""
        essential = {
            "es": {
                "where are you from": "¿De dónde es usted?",
                "i dont know": "No lo sé.",
                "i understand": "Entiendo.",
                "speak slowly": "Hable despacio.",
                "my phone number is": "Mi número de teléfono es",
                "i need medicine": "Necesito medicina.",
                "i lost my passport": "Perdí mi pasaporte.",
                "i lost my wallet": "Perdí mi cartera.",
                "call my family": "Llame a mi familia.",
            },
            "fr": {
                "where are you from": "D'où venez-vous ?",
                "i dont know": "Je ne sais pas.",
                "i understand": "Je comprends.",
                "speak slowly": "Parlez lentement.",
                "my phone number is": "Mon numéro de téléphone est",
                "i need medicine": "J'ai besoin de médicaments.",
                "i lost my passport": "J'ai perdu mon passeport.",
                "i lost my wallet": "J'ai perdu mon portefeuille.",
                "call my family": "Appelez ma famille.",
            },
            "de": {
                "where are you from": "Woher kommen Sie?",
                "i dont know": "Ich weiß es nicht.",
                "i understand": "Ich verstehe.",
                "speak slowly": "Sprechen Sie langsam.",
                "my phone number is": "Meine Telefonnummer ist",
                "i need medicine": "Ich brauche Medizin.",
                "i lost my passport": "Ich habe meinen Pass verloren.",
                "i lost my wallet": "Ich habe meine Brieftasche verloren.",
                "call my family": "Rufen Sie meine Familie an.",
            },
            "it": {
                "where are you from": "Di dove è?",
                "i dont know": "Non lo so.",
                "i understand": "Capisco.",
                "speak slowly": "Parli lentamente.",
                "my phone number is": "Il mio numero di telefono è",
                "i need medicine": "Ho bisogno di medicine.",
                "i lost my passport": "Ho perso il passaporto.",
                "i lost my wallet": "Ho perso il portafoglio.",
                "call my family": "Chiami la mia famiglia.",
            },
            "pt": {
                "where are you from": "De onde você é?",
                "i dont know": "Eu não sei.",
                "i understand": "Eu entendo.",
                "speak slowly": "Fale devagar.",
                "my phone number is": "Meu número de telefone é",
                "i need medicine": "Preciso de remédio.",
                "i lost my passport": "Perdi meu passaporte.",
                "i lost my wallet": "Perdi minha carteira.",
                "call my family": "Ligue para minha família.",
            },
            "nl": {
                "where are you from": "Waar komt u vandaan?",
                "i dont know": "Ik weet het niet.",
                "i understand": "Ik begrijp het.",
                "speak slowly": "Spreek langzaam.",
                "my phone number is": "Mijn telefoonnummer is",
                "i need medicine": "Ik heb medicijnen nodig.",
                "i lost my passport": "Ik ben mijn paspoort kwijt.",
                "i lost my wallet": "Ik ben mijn portemonnee kwijt.",
                "call my family": "Bel mijn familie.",
            },
            "ru": {
                "where are you from": "Откуда вы?",
                "i dont know": "Я не знаю.",
                "i understand": "Я понимаю.",
                "speak slowly": "Говорите медленно.",
                "my phone number is": "Мой номер телефона",
                "i need medicine": "Мне нужны лекарства.",
                "i lost my passport": "Я потерял паспорт.",
                "i lost my wallet": "Я потерял кошелёк.",
                "call my family": "Позвоните моей семье.",
            },
            "zh": {
                "where are you from": "您来自哪里？",
                "i dont know": "我不知道。",
                "i understand": "我明白。",
                "speak slowly": "请说慢一点。",
                "my phone number is": "我的电话号码是",
                "i need medicine": "我需要药。",
                "i lost my passport": "我丢了护照。",
                "i lost my wallet": "我丢了钱包。",
                "call my family": "请给我的家人打电话。",
            },
            "ja": {
                "where are you from": "どちらから来ましたか？",
                "i dont know": "わかりません。",
                "i understand": "わかりました。",
                "speak slowly": "ゆっくり話してください。",
                "my phone number is": "私の電話番号は",
                "i need medicine": "薬が必要です。",
                "i lost my passport": "パスポートをなくしました。",
                "i lost my wallet": "財布をなくしました。",
                "call my family": "家族に電話してください。",
            },
            "ko": {
                "where are you from": "어디에서 오셨어요?",
                "i dont know": "모르겠어요.",
                "i understand": "이해했어요.",
                "speak slowly": "천천히 말해 주세요.",
                "my phone number is": "제 전화번호는",
                "i need medicine": "약이 필요해요.",
                "i lost my passport": "여권을 잃어버렸어요.",
                "i lost my wallet": "지갑을 잃어버렸어요.",
                "call my family": "가족에게 전화해 주세요.",
            },
            "ar": {
                "where are you from": "من أين أنت؟",
                "i dont know": "لا أعرف.",
                "i understand": "أفهم.",
                "speak slowly": "تحدث ببطء.",
                "my phone number is": "رقم هاتفي هو",
                "i need medicine": "أحتاج إلى دواء.",
                "i lost my passport": "فقدت جواز سفري.",
                "i lost my wallet": "فقدت محفظتي.",
                "call my family": "اتصل بعائلتي.",
            },
            "hi": {
                "where are you from": "आप कहाँ से हैं?",
                "i dont know": "मुझे नहीं पता।",
                "i understand": "मैं समझ गया।",
                "speak slowly": "धीरे बोलिए।",
                "my phone number is": "मेरा फ़ोन नंबर है",
                "i need medicine": "मुझे दवा चाहिए।",
                "i lost my passport": "मेरा पासपोर्ट खो गया।",
                "i lost my wallet": "मेरा बटुआ खो गया।",
                "call my family": "मेरे परिवार को फ़ोन करिए।",
            },
            "ht": {
                "where are you from": "Ki kote ou soti?",
                "i dont know": "Mwen pa konnen.",
                "i understand": "Mwen konprann.",
                "speak slowly": "Pale dousman.",
                "my phone number is": "Nimewo telefòn mwen se",
                "i need medicine": "Mwen bezwen medikaman.",
                "i lost my passport": "Mwen pèdi paspò mwen.",
                "i lost my wallet": "Mwen pèdi bous mwen.",
                "call my family": "Rele fanmi mwen.",
            },
        }
        for target_language, phrases in essential.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_essential = {
            "es": {
                "no lo se": "I don't know.",
                "entiendo": "I understand.",
                "hable despacio": "Speak slowly.",
                "perdi mi pasaporte": "I lost my passport.",
                "necesito medicina": "I need medicine.",
            },
            "fr": {
                "je ne sais pas": "I don't know.",
                "je comprends": "I understand.",
                "parlez lentement": "Speak slowly.",
                "j ai perdu mon passeport": "I lost my passport.",
            },
            "de": {
                "ich weiss es nicht": "I don't know.",
                "ich verstehe": "I understand.",
                "sprechen sie langsam": "Speak slowly.",
                "ich habe meinen pass verloren": "I lost my passport.",
            },
            "ht": {
                "mwen pa konnen": "I don't know.",
                "mwen konprann": "I understand.",
                "pale dousman": "Speak slowly.",
                "mwen pedi paspò mwen": "I lost my passport.",
                "mwen bezwen medikaman": "I need medicine.",
            },
            "zh": {
                "\u6211\u4e0d\u77e5\u9053": "I don't know.",
                "\u6211\u660e\u767d": "I understand.",
                "\u6211\u4e22\u4e86\u62a4\u7167": "I lost my passport.",
            },
            "ja": {
                "\u308f\u304b\u308a\u307e\u305b\u3093": "I don't know.",
                "\u308f\u304b\u308a\u307e\u3057\u305f": "I understand.",
                "\u30d1\u30b9\u30dd\u30fc\u30c8\u3092\u306a\u304f\u3057\u307e\u3057\u305f": "I lost my passport.",
            },
            "ko": {
                "\ubab8\ub974\uaca0\uc5b4\uc694": "I don't know.",
                "\uc774\ud574\ud588\uc5b4\uc694": "I understand.",
                "\uc5ec\uaed8\uc744 \uc783\uc5b4\ubc84\ub838\uc5b4\uc694": "I lost my passport.",
            },
        }
        for source_language, phrases in native_essential.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_courtesy_safety_phrases(self) -> None:
        """Politeness, home access, and urgent safety lines."""
        courtesy = {
            "es": {
                "good evening": "Buenas noches.",
                "i am sorry": "Lo siento.",
                "you are welcome": "De nada.",
                "how much": "¿Cuánto?",
                "open the door": "Abra la puerta.",
                "close the window": "Cierre la ventana.",
                "it hurts here": "Me duele aquí.",
                "i cannot breathe": "No puedo respirar.",
                "my child is sick": "Mi hijo está enfermo.",
                "is it safe": "¿Es seguro?",
                "where is the embassy": "¿Dónde está la embajada?",
            },
            "fr": {
                "good evening": "Bonsoir.",
                "i am sorry": "Je suis désolé.",
                "you are welcome": "De rien.",
                "how much": "Combien ?",
                "open the door": "Ouvrez la porte.",
                "close the window": "Fermez la fenêtre.",
                "it hurts here": "J'ai mal ici.",
                "i cannot breathe": "Je ne peux pas respirer.",
                "my child is sick": "Mon enfant est malade.",
                "is it safe": "Est-ce sûr ?",
                "where is the embassy": "Où est l'ambassade ?",
            },
            "de": {
                "good evening": "Guten Abend.",
                "i am sorry": "Es tut mir leid.",
                "you are welcome": "Gern geschehen.",
                "how much": "Wie viel?",
                "open the door": "Öffnen Sie die Tür.",
                "close the window": "Schließen Sie das Fenster.",
                "it hurts here": "Hier tut es weh.",
                "i cannot breathe": "Ich kann nicht atmen.",
                "my child is sick": "Mein Kind ist krank.",
                "is it safe": "Ist es sicher?",
                "where is the embassy": "Wo ist die Botschaft?",
            },
            "it": {
                "good evening": "Buonasera.",
                "i am sorry": "Mi dispiace.",
                "you are welcome": "Prego.",
                "how much": "Quanto?",
                "open the door": "Apri la porta.",
                "close the window": "Chiudi la finestra.",
                "it hurts here": "Mi fa male qui.",
                "i cannot breathe": "Non riesco a respirare.",
                "my child is sick": "Mio figlio è malato.",
                "is it safe": "È sicuro?",
                "where is the embassy": "Dov'è l'ambasciata?",
            },
            "pt": {
                "good evening": "Boa noite.",
                "i am sorry": "Desculpe.",
                "you are welcome": "De nada.",
                "how much": "Quanto?",
                "open the door": "Abra a porta.",
                "close the window": "Feche a janela.",
                "it hurts here": "Dói aqui.",
                "i cannot breathe": "Não consigo respirar.",
                "my child is sick": "Meu filho está doente.",
                "is it safe": "É seguro?",
                "where is the embassy": "Onde fica a embaixada?",
            },
            "nl": {
                "good evening": "Goedenavond.",
                "i am sorry": "Het spijt me.",
                "you are welcome": "Graag gedaan.",
                "how much": "Hoeveel?",
                "open the door": "Open de deur.",
                "close the window": "Sluit het raam.",
                "it hurts here": "Het doet hier pijn.",
                "i cannot breathe": "Ik kan niet ademen.",
                "my child is sick": "Mijn kind is ziek.",
                "is it safe": "Is het veilig?",
                "where is the embassy": "Waar is de ambassade?",
            },
            "ru": {
                "good evening": "Добрый вечер.",
                "i am sorry": "Извините.",
                "you are welcome": "Пожалуйста.",
                "how much": "Сколько?",
                "open the door": "Откройте дверь.",
                "close the window": "Закройте окно.",
                "it hurts here": "У меня болит здесь.",
                "i cannot breathe": "Я не могу дышать.",
                "my child is sick": "Мой ребёнок болен.",
                "is it safe": "Это безопасно?",
                "where is the embassy": "Где посольство?",
            },
            "zh": {
                "good evening": "晚上好。",
                "i am sorry": "对不起。",
                "you are welcome": "不客气。",
                "how much": "多少钱？",
                "open the door": "请开门。",
                "close the window": "请关窗。",
                "it hurts here": "这里疼。",
                "i cannot breathe": "我无法呼吸。",
                "my child is sick": "我的孩子病了。",
                "is it safe": "安全吗？",
                "where is the embassy": "大使馆在哪里？",
            },
            "ja": {
                "good evening": "こんばんは。",
                "i am sorry": "すみません。",
                "you are welcome": "どういたしまして。",
                "how much": "いくらですか？",
                "open the door": "ドアを開けてください。",
                "close the window": "窓を閉めてください。",
                "it hurts here": "ここが痛いです。",
                "i cannot breathe": "息ができません。",
                "my child is sick": "子供が病気です。",
                "is it safe": "安全ですか？",
                "where is the embassy": "大使館はどこですか？",
            },
            "ko": {
                "good evening": "안녕하세요.",
                "i am sorry": "죄송합니다.",
                "you are welcome": "천만에요.",
                "how much": "얼마예요?",
                "open the door": "문을 열어 주세요.",
                "close the window": "창문을 닫아 주세요.",
                "it hurts here": "여기가 아파요.",
                "i cannot breathe": "숨을 쉴 수 없어요.",
                "my child is sick": "제 아이가 아파요.",
                "is it safe": "안전한가요?",
                "where is the embassy": "대사관이 어디예요?",
            },
            "ar": {
                "good evening": "مساء الخير.",
                "i am sorry": "أنا آسف.",
                "you are welcome": "عفواً.",
                "how much": "كم؟",
                "open the door": "افتح الباب.",
                "close the window": "أغلق النافذة.",
                "it hurts here": "يؤلمني هنا.",
                "i cannot breathe": "لا أستطيع التنفس.",
                "my child is sick": "طفلي مريض.",
                "is it safe": "هل هو آمن؟",
                "where is the embassy": "أين السفارة؟",
            },
            "hi": {
                "good evening": "शुभ संध्या।",
                "i am sorry": "मुझे खेद है।",
                "you are welcome": "आपका स्वागत है।",
                "how much": "कितना?",
                "open the door": "दरवाज़ा खोलिए।",
                "close the window": "खिड़की बंद कीजिए।",
                "it hurts here": "यहाँ दर्द हो रहा है।",
                "i cannot breathe": "मैं साँस नहीं ले पा रहा।",
                "my child is sick": "मेरा बच्चा बीमार है।",
                "is it safe": "क्या यह सुरक्षित है?",
                "where is the embassy": "दूतावास कहाँ है?",
            },
            "ht": {
                "good evening": "Bòn swa.",
                "i am sorry": "Mwen regrèt.",
                "you are welcome": "Pa gen pwoblèm.",
                "how much": "Konbyen?",
                "open the door": "Louvri pòt la.",
                "close the window": "Fèmen fenèt la.",
                "it hurts here": "Sa fè m mal isit.",
                "i cannot breathe": "Mwen pa ka respire.",
                "my child is sick": "Pitit mwen malad.",
                "is it safe": "Èske li an sekirite?",
                "where is the embassy": "Kote anbasad la?",
            },
        }
        for target_language, phrases in courtesy.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_courtesy = {
            "es": {
                "buenas noches": "Good evening.",
                "lo siento": "I am sorry.",
                "de nada": "You are welcome.",
                "me duele aqui": "It hurts here.",
                "no puedo respirar": "I cannot breathe.",
                "donde esta la embajada": "Where is the embassy?",
            },
            "fr": {
                "bonsoir": "Good evening.",
                "je suis desole": "I am sorry.",
                "de rien": "You are welcome.",
                "j ai mal ici": "It hurts here.",
                "ou est l ambassade": "Where is the embassy?",
            },
            "de": {
                "guten abend": "Good evening.",
                "es tut mir leid": "I am sorry.",
                "ich kann nicht atmen": "I cannot breathe.",
                "wo ist die botschaft": "Where is the embassy?",
            },
            "ht": {
                "bon swa": "Good evening.",
                "mwen regret": "I am sorry.",
                "sa fe m mal isit": "It hurts here.",
                "mwen pa ka respire": "I cannot breathe.",
                "kote anbasad la": "Where is the embassy?",
            },
            "zh": {
                "\u665a\u4e0a\u597d": "Good evening.",
                "\u5bf9\u4e0d\u8d77": "I am sorry.",
                "\u8fd9\u91cc\u75bc": "It hurts here.",
                "\u6211\u65e0\u6cd5\u547c\u5438": "I cannot breathe.",
                "\u5927\u4f7f\u9986\u5728\u54ea\u91cc": "Where is the embassy?",
            },
            "ja": {
                "\u3053\u3093\u3070\u3093\u306f": "Good evening.",
                "\u3059\u307f\u307e\u305b\u3093": "I am sorry.",
                "\u3053\u3053\u304c\u75db\u3044\u3067\u3059": "It hurts here.",
                "\u606f\u304c\u3067\u304d\u307e\u305b\u3093": "I cannot breathe.",
            },
            "ko": {
                "\uc8c4\uc1a1\ud569\ub2c8\ub2e4": "I am sorry.",
                "\uc5ec\uae30\uac00 \uc544\ud30c\uc694": "It hurts here.",
                "\uc228\uc744 \uc26c\uc744 \uc218 \uc5c6\uc5b4\uc694": "I cannot breathe.",
            },
            "ar": {
                "\u0645\u0633\u0627\u0621 \u0627\u0644\u062e\u064a\u0631": "Good evening.",
                "\u0644\u0627 \u0623\u0633\u062a\u0637\u064a\u0639 \u0627\u0644\u062a\u0646\u0641\u0633": "I cannot breathe.",
                "\u0623\u064a\u0646 \u0627\u0644\u0633\u0641\u0627\u0631\u0629": "Where is the embassy?",
            },
        }
        for source_language, phrases in native_courtesy.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_life_context_phrases(self) -> None:
        """Personal, family, weather, and money phrases for everyday conversations."""
        _life_keys = (
            "i am a student", "i am a teacher", "i work here", "what is your job",
            "i am tired", "i am cold", "i am hot",
            "my wife", "my husband", "my son", "my daughter", "my baby", "my parents",
            "it is raining", "it is cold today", "it is hot today", "nice weather",
            "do you have wifi", "can i use your phone", "i have no money", "i need cash", "where is the atm",
        )
        life = {
            "es": {
                "i am a student": "Soy estudiante.", "i am a teacher": "Soy profesor.", "i work here": "Trabajo aquí.",
                "what is your job": "¿Cuál es su trabajo?", "i am tired": "Estoy cansado.", "i am cold": "Tengo frío.", "i am hot": "Tengo calor.",
                "my wife": "Mi esposa.", "my husband": "Mi esposo.", "my son": "Mi hijo.", "my daughter": "Mi hija.",
                "my baby": "Mi bebé.", "my parents": "Mis padres.",
                "it is raining": "Está lloviendo.", "it is cold today": "Hace frío hoy.", "it is hot today": "Hace calor hoy.", "nice weather": "Buen tiempo.",
                "do you have wifi": "¿Tiene wifi?", "can i use your phone": "¿Puedo usar su teléfono?",
                "i have no money": "No tengo dinero.", "i need cash": "Necesito efectivo.", "where is the atm": "¿Dónde está el cajero?",
            },
            "fr": {
                "i am a student": "Je suis étudiant.", "i am a teacher": "Je suis professeur.", "i work here": "Je travaille ici.",
                "what is your job": "Quel est votre métier ?", "i am tired": "Je suis fatigué.", "i am cold": "J'ai froid.", "i am hot": "J'ai chaud.",
                "my wife": "Ma femme.", "my husband": "Mon mari.", "my son": "Mon fils.", "my daughter": "Ma fille.",
                "my baby": "Mon bébé.", "my parents": "Mes parents.",
                "it is raining": "Il pleut.", "it is cold today": "Il fait froid aujourd'hui.", "it is hot today": "Il fait chaud aujourd'hui.", "nice weather": "Beau temps.",
                "do you have wifi": "Avez-vous le wifi ?", "can i use your phone": "Puis-je utiliser votre téléphone ?",
                "i have no money": "Je n'ai pas d'argent.", "i need cash": "J'ai besoin d'espèces.", "where is the atm": "Où est le distributeur ?",
            },
            "de": {
                "i am a student": "Ich bin Student.", "i am a teacher": "Ich bin Lehrer.", "i work here": "Ich arbeite hier.",
                "what is your job": "Was ist Ihr Beruf?", "i am tired": "Ich bin müde.", "i am cold": "Mir ist kalt.", "i am hot": "Mir ist heiß.",
                "my wife": "Meine Frau.", "my husband": "Mein Mann.", "my son": "Mein Sohn.", "my daughter": "Meine Tochter.",
                "my baby": "Mein Baby.", "my parents": "Meine Eltern.",
                "it is raining": "Es regnet.", "it is cold today": "Es ist kalt heute.", "it is hot today": "Es ist heiß heute.", "nice weather": "Schönes Wetter.",
                "do you have wifi": "Haben Sie WLAN?", "can i use your phone": "Kann ich Ihr Telefon benutzen?",
                "i have no money": "Ich habe kein Geld.", "i need cash": "Ich brauche Bargeld.", "where is the atm": "Wo ist der Geldautomat?",
            },
            "it": {
                "i am a student": "Sono uno studente.", "i am a teacher": "Sono un insegnante.", "i work here": "Lavoro qui.",
                "what is your job": "Qual è il suo lavoro?", "i am tired": "Sono stanco.", "i am cold": "Ho freddo.", "i am hot": "Ho caldo.",
                "my wife": "Mia moglie.", "my husband": "Mio marito.", "my son": "Mio figlio.", "my daughter": "Mia figlia.",
                "my baby": "Il mio bambino.", "my parents": "I miei genitori.",
                "it is raining": "Sta piovendo.", "it is cold today": "Fa freddo oggi.", "it is hot today": "Fa caldo oggi.", "nice weather": "Bel tempo.",
                "do you have wifi": "Avete il wifi?", "can i use your phone": "Posso usare il suo telefono?",
                "i have no money": "Non ho soldi.", "i need cash": "Ho bisogno di contanti.", "where is the atm": "Dov'è il bancomat?",
            },
            "pt": {
                "i am a student": "Sou estudante.", "i am a teacher": "Sou professor.", "i work here": "Trabalho aqui.",
                "what is your job": "Qual é o seu trabalho?", "i am tired": "Estou cansado.", "i am cold": "Estou com frio.", "i am hot": "Estou com calor.",
                "my wife": "Minha esposa.", "my husband": "Meu marido.", "my son": "Meu filho.", "my daughter": "Minha filha.",
                "my baby": "Meu bebê.", "my parents": "Meus pais.",
                "it is raining": "Está chovendo.", "it is cold today": "Está frio hoje.", "it is hot today": "Está quente hoje.", "nice weather": "Tempo bom.",
                "do you have wifi": "Você tem wifi?", "can i use your phone": "Posso usar seu telefone?",
                "i have no money": "Não tenho dinheiro.", "i need cash": "Preciso de dinheiro.", "where is the atm": "Onde fica o caixa eletrônico?",
            },
            "nl": {
                "i am a student": "Ik ben student.", "i am a teacher": "Ik ben leraar.", "i work here": "Ik werk hier.",
                "what is your job": "Wat is uw beroep?", "i am tired": "Ik ben moe.", "i am cold": "Ik heb het koud.", "i am hot": "Ik heb het warm.",
                "my wife": "Mijn vrouw.", "my husband": "Mijn man.", "my son": "Mijn zoon.", "my daughter": "Mijn dochter.",
                "my baby": "Mijn baby.", "my parents": "Mijn ouders.",
                "it is raining": "Het regent.", "it is cold today": "Het is koud vandaag.", "it is hot today": "Het is warm vandaag.", "nice weather": "Mooi weer.",
                "do you have wifi": "Heeft u wifi?", "can i use your phone": "Mag ik uw telefoon gebruiken?",
                "i have no money": "Ik heb geen geld.", "i need cash": "Ik heb contant geld nodig.", "where is the atm": "Waar is de geldautomaat?",
            },
            "ru": {
                "i am a student": "Я студент.", "i am a teacher": "Я учитель.", "i work here": "Я работаю здесь.",
                "what is your job": "Кем вы работаете?", "i am tired": "Я устал.", "i am cold": "Мне холодно.", "i am hot": "Мне жарко.",
                "my wife": "Моя жена.", "my husband": "Мой муж.", "my son": "Мой сын.", "my daughter": "Моя дочь.",
                "my baby": "Мой ребёнок.", "my parents": "Мои родители.",
                "it is raining": "Идёт дождь.", "it is cold today": "Сегодня холодно.", "it is hot today": "Сегодня жарко.", "nice weather": "Хорошая погода.",
                "do you have wifi": "У вас есть wifi?", "can i use your phone": "Можно воспользоваться вашим телефоном?",
                "i have no money": "У меня нет денег.", "i need cash": "Мне нужны наличные.", "where is the atm": "Где банкомат?",
            },
            "zh": {
                "i am a student": "我是学生。", "i am a teacher": "我是老师。", "i work here": "我在这里工作。",
                "what is your job": "您做什么工作？", "i am tired": "我很累。", "i am cold": "我很冷。", "i am hot": "我很热。",
                "my wife": "我的妻子。", "my husband": "我的丈夫。", "my son": "我的儿子。", "my daughter": "我的女儿。",
                "my baby": "我的宝宝。", "my parents": "我的父母。",
                "it is raining": "下雨了。", "it is cold today": "今天很冷。", "it is hot today": "今天很热。", "nice weather": "天气很好。",
                "do you have wifi": "有wifi吗？", "can i use your phone": "我可以用您的电话吗？",
                "i have no money": "我没有钱。", "i need cash": "我需要现金。", "where is the atm": "自动取款机在哪里？",
            },
            "ja": {
                "i am a student": "私は学生です。", "i am a teacher": "私は教師です。", "i work here": "ここで働いています。",
                "what is your job": "お仕事は何ですか？", "i am tired": "疲れました。", "i am cold": "寒いです。", "i am hot": "暑いです。",
                "my wife": "私の妻。", "my husband": "私の夫。", "my son": "私の息子。", "my daughter": "私の娘。",
                "my baby": "私の赤ちゃん。", "my parents": "私の両親。",
                "it is raining": "雨が降っています。", "it is cold today": "今日は寒いです。", "it is hot today": "今日は暑いです。", "nice weather": "いい天気です。",
                "do you have wifi": "WiFiはありますか？", "can i use your phone": "電話を使ってもいいですか？",
                "i have no money": "お金がありません。", "i need cash": "現金が必要です。", "where is the atm": "ATMはどこですか？",
            },
            "ko": {
                "i am a student": "저는 학생이에요.", "i am a teacher": "저는 선생님이에요.", "i work here": "여기서 일해요.",
                "what is your job": "직업이 뭐예요?", "i am tired": "피곤해요.", "i am cold": "추워요.", "i am hot": "더워요.",
                "my wife": "제 아내.", "my husband": "제 남편.", "my son": "제 아들.", "my daughter": "제 딸.",
                "my baby": "제 아기.", "my parents": "제 부모님.",
                "it is raining": "비가 와요.", "it is cold today": "오늘 추워요.", "it is hot today": "오늘 더워요.", "nice weather": "날씨가 좋아요.",
                "do you have wifi": "와이파이 있어요?", "can i use your phone": "전화 써도 돼요?",
                "i have no money": "돈이 없어요.", "i need cash": "현금이 필요해요.", "where is the atm": "ATM이 어디예요?",
            },
            "ar": {
                "i am a student": "أنا طالب.", "i am a teacher": "أنا معلم.", "i work here": "أعمل هنا.",
                "what is your job": "ما عملك؟", "i am tired": "أنا متعب.", "i am cold": "أشعر بالبرد.", "i am hot": "أشعر بالحر.",
                "my wife": "زوجتي.", "my husband": "زوجي.", "my son": "ابني.", "my daughter": "ابنتي.",
                "my baby": "طفلي.", "my parents": "والداي.",
                "it is raining": "إنها تمطر.", "it is cold today": "الجو بارد اليوم.", "it is hot today": "الجو حار اليوم.", "nice weather": "طقس جميل.",
                "do you have wifi": "هل لديك واي فاي؟", "can i use your phone": "هل يمكنني استخدام هاتفك؟",
                "i have no money": "ليس لدي مال.", "i need cash": "أحتاج إلى نقود.", "where is the atm": "أين الصراف الآلي؟",
            },
            "hi": {
                "i am a student": "मैं विद्यार्थी हूँ।", "i am a teacher": "मैं शिक्षक हूँ।", "i work here": "मैं यहाँ काम करता हूँ।",
                "what is your job": "आपका काम क्या है?", "i am tired": "मैं थका हुआ हूँ।", "i am cold": "मुझे ठंड लग रही है।", "i am hot": "मुझे गर्मी लग रही है।",
                "my wife": "मेरी पत्नी।", "my husband": "मेरा पति।", "my son": "मेरा बेटा।", "my daughter": "मेरी बेटी।",
                "my baby": "मेरा बच्चा।", "my parents": "मेरे माता-पिता।",
                "it is raining": "बारिश हो रही है।", "it is cold today": "आज ठंड है।", "it is hot today": "आज गर्मी है।", "nice weather": "अच्छा मौसम।",
                "do you have wifi": "क्या वाईफाई है?", "can i use your phone": "क्या मैं आपका फ़ोन इस्तेमाल कर सकता हूँ?",
                "i have no money": "मेरे पास पैसे नहीं हैं।", "i need cash": "मुझे नकद चाहिए।", "where is the atm": "एटीएम कहाँ है?",
            },
            "ht": {
                "i am a student": "Mwen se yon elèv.", "i am a teacher": "Mwen se yon pwofesè.", "i work here": "Mwen travay isit.",
                "what is your job": "Ki travay ou?", "i am tired": "Mwen fatige.", "i am cold": "Mwen gen frèt.", "i am hot": "Mwen gen cho.",
                "my wife": "Madanm mwen.", "my husband": "Mari mwen.", "my son": "Pitit gason mwen.", "my daughter": "Pitit fi mwen.",
                "my baby": "Tibebe mwen.", "my parents": "Paran mwen.",
                "it is raining": "Li ap pile.", "it is cold today": "Li frèt jodi a.", "it is hot today": "Li cho jodi a.", "nice weather": "Bèl tan.",
                "do you have wifi": "Èske ou gen wifi?", "can i use your phone": "Èske mwen ka itilize telefòn ou?",
                "i have no money": "Mwen pa gen lajan.", "i need cash": "Mwen bezwen lajan kach.", "where is the atm": "Kote machin ATM la?",
            },
        }
        for target_language, phrases in life.items():
            assert set(phrases) == set(_life_keys)
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_life = {
            "es": {
                "soy estudiante": "I am a student.", "estoy cansado": "I am tired.", "mi esposa": "My wife.",
                "no tengo dinero": "I have no money.", "donde esta el cajero": "Where is the ATM?",
            },
            "fr": {
                "je suis etudiant": "I am a student.", "j ai froid": "I am cold.", "ma femme": "My wife.",
                "je n ai pas d argent": "I have no money.", "ou est le distributeur": "Where is the ATM?",
            },
            "de": {
                "ich bin student": "I am a student.", "ich bin mude": "I am tired.", "meine frau": "My wife.",
                "ich habe kein geld": "I have no money.",
            },
            "ht": {
                "mwen se yon elev": "I am a student.", "mwen fatige": "I am tired.", "madanm mwen": "My wife.",
                "mwen pa gen lajan": "I have no money.", "kote machin atm la": "Where is the ATM?",
            },
            "zh": {
                "\u6211\u662f\u5b66\u751f": "I am a student.", "\u6211\u5f88\u7d2f": "I am tired.", "\u6211\u6ca1\u6709\u94b1": "I have no money.",
                "\u81ea\u52a8\u53d6\u6b3e\u673a\u5728\u54ea\u91cc": "Where is the ATM?",
            },
            "ja": {
                "\u79c1\u306f\u5b66\u751f\u3067\u3059": "I am a student.", "\u75b2\u308c\u307e\u3057\u305f": "I am tired.",
                "\u304a\u91d1\u304c\u3042\u308a\u307e\u305b\u3093": "I have no money.",
            },
            "ko": {
                "\uc800\ub294 \ud559\uc0dd\uc774\uc5d0\uc694": "I am a student.", "\ud53c\uace4\ud574\uc694": "I am tired.",
                "\ub3c8\uc774 \uc5c6\uc5b4\uc694": "I have no money.",
            },
        }
        for source_language, phrases in native_life.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_emergency_phrases(self) -> None:
        """High-stakes lines travelers need instantly in every language."""
        emergency = {
            "es": {
                "help": "¡Ayuda!",
                "i need a doctor": "Necesito un médico.",
                "call the police": "Llame a la policía.",
                "where is the hospital": "¿Dónde está el hospital?",
            },
            "fr": {
                "help": "Au secours !",
                "i need a doctor": "J'ai besoin d'un médecin.",
                "call the police": "Appelez la police.",
                "where is the hospital": "Où est l'hôpital ?",
            },
            "de": {
                "help": "Hilfe!",
                "i need a doctor": "Ich brauche einen Arzt.",
                "call the police": "Rufen Sie die Polizei.",
                "where is the hospital": "Wo ist das Krankenhaus?",
            },
            "it": {
                "help": "Aiuto!",
                "i need a doctor": "Ho bisogno di un medico.",
                "call the police": "Chiami la polizia.",
                "where is the hospital": "Dov'è l'ospedale?",
            },
            "pt": {
                "help": "Socorro!",
                "i need a doctor": "Preciso de um médico.",
                "call the police": "Chame a polícia.",
                "where is the hospital": "Onde fica o hospital?",
            },
            "nl": {
                "help": "Help!",
                "i need a doctor": "Ik heb een dokter nodig.",
                "call the police": "Bel de politie.",
                "where is the hospital": "Waar is het ziekenhuis?",
            },
            "ru": {
                "help": "Помогите!",
                "i need a doctor": "Мне нужен врач.",
                "call the police": "Вызовите полицию.",
                "where is the hospital": "Где больница?",
            },
            "zh": {
                "help": "救命！",
                "i need a doctor": "我需要医生。",
                "call the police": "请叫警察。",
                "where is the hospital": "医院在哪里？",
            },
            "ja": {
                "help": "助けて！",
                "i need a doctor": "医者が必要です。",
                "call the police": "警察を呼んでください。",
                "where is the hospital": "病院はどこですか？",
            },
            "ko": {
                "help": "도와주세요!",
                "i need a doctor": "의사가 필요합니다.",
                "call the police": "경찰을 불러 주세요.",
                "where is the hospital": "병원이 어디예요?",
            },
            "ar": {
                "help": "النجدة!",
                "i need a doctor": "أحتاج إلى طبيب.",
                "call the police": "اتصل بالشرطة.",
                "where is the hospital": "أين المستشفى؟",
            },
            "hi": {
                "help": "मदद!",
                "i need a doctor": "मुझे डॉक्टर चाहिए।",
                "call the police": "पुलिस को बुलाइए।",
                "where is the hospital": "अस्पताल कहाँ है?",
            },
            "ht": {
                "help": "Èd!",
                "i need a doctor": "Mwen bezwen yon doktè.",
                "call the police": "Rele lapolis.",
                "where is the hospital": "Kote lopital la?",
            },
        }
        english_keys = ("help", "i need a doctor", "call the police", "where is the hospital")
        for target_language, phrases in emergency.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )
        native_emergency = {
            "es": {
                "ayuda": "Help!", "necesito un medico": "I need a doctor.",
                "llame a la policia": "Call the police.", "donde esta el hospital": "Where is the hospital?",
            },
            "fr": {
                "au secours": "Help!", "j ai besoin d un medecin": "I need a doctor.",
                "appelez la police": "Call the police.", "ou est l hopital": "Where is the hospital?",
            },
            "de": {
                "hilfe": "Help!", "ich brauche einen arzt": "I need a doctor.",
                "rufen sie die polizei": "Call the police.", "wo ist das krankenhaus": "Where is the hospital?",
            },
            "it": {
                "aiuto": "Help!", "ho bisogno di un medico": "I need a doctor.",
                "chiami la polizia": "Call the police.", "dov e l ospedale": "Where is the hospital?",
            },
            "pt": {
                "socorro": "Help!", "preciso de um medico": "I need a doctor.",
                "chame a policia": "Call the police.", "onde fica o hospital": "Where is the hospital?",
            },
            "nl": {
                "help": "Help!", "ik heb een dokter nodig": "I need a doctor.",
                "bel de politie": "Call the police.", "waar is het ziekenhuis": "Where is the hospital?",
            },
            "ht": {"ed": "Help!", "mwen bezwen yon dokte": "I need a doctor.", "rele lapolis": "Call the police.", "kote lopital la": "Where is the hospital?"},
            "ru": {"\u043f\u043e\u043c\u043e\u0433\u0438\u0442\u0435": "Help!", "\u043c\u043d\u0435 \u043d\u0443\u0436\u0435\u043d \u0432\u0440\u0430\u0447": "I need a doctor."},
            "zh": {"\u6551\u547d": "Help!", "\u6211\u9700\u8981\u533b\u751f": "I need a doctor."},
            "ja": {"\u52a9\u3051\u3066": "Help!", "\u533b\u8005\u304c\u5fc5\u8981\u3067\u3059": "I need a doctor."},
            "ko": {"\ub3c4\uc640\uc918\uc694": "Help!", "\uc758\uc0ac\uac00 \ud544\uc694\ud569\ub2c8\ub2e4": "I need a doctor."},
            "ar": {"\u0627\u0644\u0646\u062c\u062f\u0629": "Help!", "\u0623\u062d\u062a\u0627\u062c \u0625\u0644\u0649 \u0637\u0628\u064a\u0628": "I need a doctor."},
            "hi": {"\u092e\u0926\u0926": "Help!", "\u092e\u0941\u091d\u0947 \u0921\u0949\u0915\u094d\u091f\u0930 \u091a\u093e\u0939\u093f\u090f": "I need a doctor."},
        }
        for source_language, phrases in native_emergency.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_barrier_phrases(self) -> None:
        """High-traffic pairs for live two-language conversations (no English pivot)."""
        barrier = {
            ("ht", "es"): {
                "bonjou": "Hola.",
                "mesi": "Gracias.",
                "mesi anpil": "Muchas gracias.",
                "kijan ou ye": "¿Cómo estás?",
                "wi": "Sí.",
                "non": "No.",
                "tanpri": "Por favor.",
                "eskize mwen": "Disculpe.",
                "orevwa": "Adiós.",
                "mwen pa konprann": "No entiendo.",
                "mwen bezwen ed": "Necesito ayuda.",
                "kote twalet la": "¿Dónde está el baño?",
            },
            ("es", "ht"): {
                "hola": "Bonjou.",
                "gracias": "Mèsi.",
                "muchas gracias": "Mèsi anpil.",
                "como estas": "Kijan ou ye?",
                "si": "Wi.",
                "no": "Non.",
                "por favor": "Tanpri.",
                "disculpe": "Eskize mwen.",
                "adios": "Orevwa.",
                "no entiendo": "Mwen pa konprann.",
                "necesito ayuda": "Mwen bezwen èd.",
                "donde esta el bano": "Kote twalèt la?",
            },
            ("ht", "fr"): {
                "bonjou": "Bonjour.",
                "mesi": "Merci.",
                "mesi anpil": "Merci beaucoup.",
                "kijan ou ye": "Comment allez-vous ?",
                "wi": "Oui.",
                "non": "Non.",
                "tanpri": "S'il vous plaît.",
                "eskize mwen": "Excusez-moi.",
                "orevwa": "Au revoir.",
                "mwen pa konprann": "Je ne comprends pas.",
                "mwen bezwen ed": "J'ai besoin d'aide.",
            },
            ("fr", "ht"): {
                "bonjour": "Bonjou.",
                "merci": "Mèsi.",
                "merci beaucoup": "Mèsi anpil.",
                "comment allez vous": "Kijan ou ye?",
                "oui": "Wi.",
                "non": "Non.",
                "s il vous plait": "Tanpri.",
                "excusez moi": "Eskize mwen.",
                "au revoir": "Orevwa.",
                "je ne comprends pas": "Mwen pa konprann.",
                "j ai besoin d aide": "Mwen bezwen èd.",
            },
            ("es", "fr"): {
                "hola": "Bonjour.",
                "gracias": "Merci.",
                "como estas": "Comment allez-vous ?",
                "si": "Oui.",
                "no": "Non.",
                "por favor": "S'il vous plaît.",
                "adios": "Au revoir.",
            },
            ("fr", "es"): {
                "bonjour": "Hola.",
                "merci": "Gracias.",
                "comment allez vous": "¿Cómo estás?",
                "oui": "Sí.",
                "non": "No.",
                "au revoir": "Adiós.",
            },
            ("de", "fr"): {
                "hallo": "Bonjour.",
                "danke": "Merci.",
                "wie geht es ihnen": "Comment allez-vous ?",
                "ja": "Oui.",
                "nein": "Non.",
                "bitte": "S'il vous plaît.",
                "auf wiedersehen": "Au revoir.",
            },
            ("fr", "de"): {
                "bonjour": "Hallo.",
                "merci": "Danke.",
                "comment allez vous": "Wie geht es Ihnen?",
                "oui": "Ja.",
                "non": "Nein.",
                "au revoir": "Auf Wiedersehen.",
            },
            ("de", "es"): {
                "hallo": "Hola.",
                "danke": "Gracias.",
                "wie geht es ihnen": "¿Cómo estás?",
                "ja": "Sí.",
                "nein": "No.",
                "bitte": "Por favor.",
                "auf wiedersehen": "Adiós.",
            },
            ("es", "de"): {
                "hola": "Hallo.",
                "gracias": "Danke.",
                "como estas": "Wie geht es Ihnen?",
                "si": "Ja.",
                "no": "Nein.",
                "por favor": "Bitte.",
                "adios": "Auf Wiedersehen.",
            },
            ("it", "fr"): {
                "ciao": "Bonjour.",
                "grazie": "Merci.",
                "come sta": "Comment allez-vous ?",
                "si": "Oui.",
                "no": "Non.",
                "per favore": "S'il vous plaît.",
                "arrivederci": "Au revoir.",
            },
            ("fr", "it"): {
                "bonjour": "Ciao.",
                "merci": "Grazie.",
                "comment allez vous": "Come sta?",
                "oui": "Sì.",
                "non": "No.",
                "au revoir": "Arrivederci.",
            },
            ("it", "es"): {
                "ciao": "Hola.",
                "grazie": "Gracias.",
                "come sta": "¿Cómo estás?",
                "si": "Sí.",
                "no": "No.",
                "per favore": "Por favor.",
                "arrivederci": "Adiós.",
            },
            ("es", "it"): {
                "hola": "Ciao.",
                "gracias": "Grazie.",
                "como estas": "Come sta?",
                "si": "Sì.",
                "no": "No.",
                "por favor": "Per favore.",
                "adios": "Arrivederci.",
            },
            ("pt", "es"): {
                "ola": "Hola.",
                "obrigado": "Gracias.",
                "como voce esta": "¿Cómo estás?",
                "sim": "Sí.",
                "nao": "No.",
                "por favor": "Por favor.",
                "adeus": "Adiós.",
            },
            ("es", "pt"): {
                "hola": "Olá.",
                "gracias": "Obrigado.",
                "como estas": "Como você está?",
                "si": "Sim.",
                "no": "Não.",
                "por favor": "Por favor.",
                "adios": "Adeus.",
            },
            ("pt", "fr"): {
                "ola": "Bonjour.",
                "obrigado": "Merci.",
                "como voce esta": "Comment allez-vous ?",
                "sim": "Oui.",
                "nao": "Non.",
                "por favor": "S'il vous plaît.",
                "adeus": "Au revoir.",
            },
            ("fr", "pt"): {
                "bonjour": "Olá.",
                "merci": "Obrigado.",
                "comment allez vous": "Como você está?",
                "oui": "Sim.",
                "non": "Não.",
                "au revoir": "Adeus.",
            },
        }
        for pair, phrases in barrier.items():
            self._phrases.setdefault(pair, {}).update(
                {_normalize_text(source): translated for source, translated in phrases.items()}
            )

    def _add_common_to_english_phrases(self) -> None:
        common = {
            "es": {
                "hola": "hello",
                "gracias": "Thank you.",
                "como estas": "How are you?",
                "si": "Yes.",
                "no": "No.",
                "por favor": "Please.",
                "disculpe": "Excuse me.",
                "adios": "Goodbye.",
                "no entiendo": "I don't understand.",
                "muchas gracias": "Thank you very much.",
                "necesito ayuda": "I need help.",
                "donde esta el bano": "Where is the bathroom?",
                "buenos dias": "Good morning.",
                "buenas noches": "Good evening.",
                "ayuda": "Help!",
            },
            "fr": {
                "bonjour": "Hello.",
                "merci": "Thank you.",
                "comment allez vous": "How are you?",
                "oui": "Yes.",
                "non": "No.",
                "s il vous plait": "Please.",
                "excusez moi": "Excuse me.",
                "au revoir": "Goodbye.",
                "je ne comprends pas": "I don't understand.",
                "merci beaucoup": "Thank you very much.",
                "aide": "Help!",
                "j ai besoin d aide": "I need help.",
                "ou sont les toilettes": "Where is the bathroom?",
            },
            "de": {
                "hallo": "Hello.",
                "danke": "Thank you.",
                "wie geht es ihnen": "How are you?",
                "ja": "Yes.",
                "nein": "No.",
                "bitte": "Please.",
                "entschuldigung": "Excuse me.",
                "auf wiedersehen": "Goodbye.",
                "ich verstehe nicht": "I don't understand.",
                "vielen dank": "Thank you very much.",
                "ich brauche hilfe": "I need help.",
                "wo ist die toilette": "Where is the bathroom?",
            },
            "it": {
                "ciao": "Hello.",
                "grazie": "Thank you.",
                "come sta": "How are you?",
                "si": "Yes.",
                "no": "No.",
                "per favore": "Please.",
                "mi scusi": "Excuse me.",
                "arrivederci": "Goodbye.",
                "non capisco": "I don't understand.",
                "grazie mille": "Thank you very much.",
                "ho bisogno di aiuto": "I need help.",
                "dov e il bagno": "Where is the bathroom?",
            },
            "pt": {
                "ola": "Hello.",
                "obrigado": "Thank you.",
                "como voce esta": "How are you?",
                "sim": "Yes.",
                "nao": "No.",
                "por favor": "Please.",
                "com licenca": "Excuse me.",
                "adeus": "Goodbye.",
                "nao entendo": "I don't understand.",
                "muito obrigado": "Thank you very much.",
                "ajuda": "Help!",
                "preciso de ajuda": "I need help.",
                "onde fica o banheiro": "Where is the bathroom?",
            },
            "nl": {
                "hallo": "Hello.",
                "dank je": "Thank you.",
                "dank u": "Thank you.",
                "hoe gaat het met u": "How are you?",
                "ja": "Yes.",
                "nee": "No.",
                "alstublieft": "Please.",
                "pardon": "Excuse me.",
                "tot ziens": "Goodbye.",
                "ik begrijp het niet": "I don't understand.",
                "hartelijk dank": "Thank you very much.",
                "ik heb hulp nodig": "I need help.",
                "waar is het toilet": "Where is the bathroom?",
            },
            "ru": {
                "\u043f\u0440\u0438\u0432\u0435\u0442": "Hello.",
                "\u0441\u043f\u0430\u0441\u0438\u0431\u043e": "Thank you.",
                "\u043a\u0430\u043a \u0434\u0435\u043b\u0430": "How are you?",
                "\u0434\u0430": "Yes.",
                "\u043d\u0435\u0442": "No.",
                "\u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430": "Please.",
                "\u0438\u0437\u0432\u0438\u043d\u0438\u0442\u0435": "Excuse me.",
                "\u0434\u043e \u0441\u0432\u0438\u0434\u0430\u043d\u0438\u044f": "Goodbye.",
                "\u044f \u043d\u0435 \u043f\u043e\u043d\u0438\u043c\u0430\u044e": "I don't understand.",
                "\u0431\u043e\u043b\u044c\u0448\u043e\u0435 \u0441\u043f\u0430\u0441\u0438\u0431\u043e": "Thank you very much.",
                "\u043c\u043d\u0435 \u043d\u0443\u0436\u043d\u0430 \u043f\u043e\u043c\u043e\u0449\u044c": "I need help.",
                "\u0433\u0434\u0435 \u0442\u0443\u0430\u043b\u0435\u0442": "Where is the bathroom?",
            },
            "zh": {
                "\u4f60\u597d": "Hello.",
                "\u8c22\u8c22": "Thank you.",
                "\u4f60\u597d\u5417": "How are you?",
                "\u662f\u7684": "Yes.",
                "\u4e0d\u662f": "No.",
                "\u8bf7": "Please.",
                "\u5bf9\u4e0d\u8d77": "Excuse me.",
                "\u518d\u89c1": "Goodbye.",
                "\u6211\u4e0d\u660e\u767d": "I don't understand.",
                "\u975e\u5e38\u611f\u8c22": "Thank you very much.",
                "\u6211\u9700\u8981\u5e2e\u52a9": "I need help.",
                "\u6d17\u624b\u95f4\u5728\u54ea\u91cc": "Where is the bathroom?",
            },
            "ja": {
                "\u3053\u3093\u306b\u3061\u306f": "Hello.",
                "\u3042\u308a\u304c\u3068\u3046": "Thank you.",
                "\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3059": "Thank you.",
                "\u304a\u5143\u6c17\u3067\u3059\u304b": "How are you?",
                "\u306f\u3044": "Yes.",
                "\u3044\u3044\u3048": "No.",
                "\u304a\u9858\u3044\u3057\u307e\u3059": "Please.",
                "\u3059\u307f\u307e\u305b\u3093": "Excuse me.",
                "\u3055\u3088\u3046\u306a\u3089": "Goodbye.",
                "\u308f\u304b\u308a\u307e\u305b\u3093": "I don't understand.",
                "\u3069\u3046\u3082\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3059": "Thank you very much.",
                "\u52a9\u3051\u304c\u5fc5\u8981\u3067\u3059": "I need help.",
                "\u30c8\u30a4\u30ec\u306f\u3069\u3053\u3067\u3059\u304b": "Where is the bathroom?",
            },
            "ko": {
                "\uc548\ub155\ud558\uc138\uc694": "Hello.",
                "\uac10\uc0ac\ud569\ub2c8\ub2e4": "Thank you.",
                "\uc5b4\ub5bb\uac8c \uc9c0\ub0b4\uc138\uc694": "How are you?",
                "\ub124": "Yes.",
                "\uc544\ub2c8\uc694": "No.",
                "\uc81c\ubc1c": "Please.",
                "\uc2e4\ub840\ud569\ub2c8\ub2e4": "Excuse me.",
                "\uc548\ub155\ud788 \uac00\uc138\uc694": "Goodbye.",
                "\uc774\ud574\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4": "I don't understand.",
                "\uc815\ub9d0 \uac10\uc0ac\ud569\ub2c8\ub2e4": "Thank you very much.",
                "\ub3c4\uc6c0\uc774 \ud544\uc694\ud569\ub2c8\ub2e4": "I need help.",
                "\ud654\uc7a5\uc2e4\uc774 \uc5b4\ub514\uc608\uc694": "Where is the bathroom?",
            },
            "ar": {
                "\u0645\u0631\u062d\u0628\u0627": "Hello.",
                "\u0634\u0643\u0631\u0627": "Thank you.",
                "\u0643\u064a\u0641 \u062d\u0627\u0644\u0643": "How are you?",
                "\u0646\u0639\u0645": "Yes.",
                "\u0644\u0627": "No.",
                "\u0645\u0646 \u0641\u0636\u0644\u0643": "Please.",
                "\u0639\u0630\u0631\u0627": "Excuse me.",
                "\u0645\u0639 \u0627\u0644\u0633\u0644\u0627\u0645\u0629": "Goodbye.",
                "\u0644\u0627 \u0623\u0641\u0647\u0645": "I don't understand.",
                "\u0634\u0643\u0631\u0627 \u062c\u0632\u064a\u0644\u0627": "Thank you very much.",
                "\u0623\u062d\u062a\u0627\u062c \u0625\u0644\u0649 \u0645\u0633\u0627\u0639\u062f\u0629": "I need help.",
                "\u0623\u064a\u0646 \u0627\u0644\u062d\u0645\u0627\u0645": "Where is the bathroom?",
            },
            "hi": {
                "\u0928\u092e\u0938\u094d\u0924\u0947": "Hello.",
                "\u0927\u0928\u094d\u092f\u0935\u093e\u0926": "Thank you.",
                "\u0906\u092a \u0915\u0948\u0938\u0947 \u0939\u0948\u0902": "How are you?",
                "\u0939\u093e\u0902": "Yes.",
                "\u0928\u0939\u0940\u0902": "No.",
                "\u0915\u0943\u092a\u092f\u093e": "Please.",
                "\u092e\u093e\u092b \u0915\u0940\u091c\u093f\u090f": "Excuse me.",
                "\u0905\u0932\u0935\u093f\u0926\u093e": "Goodbye.",
                "\u092e\u0948\u0902 \u0938\u092e\u091d\u093e \u0928\u0939\u0940\u0902": "I don't understand.",
                "\u092c\u0939\u0941\u0924 \u0927\u0928\u094d\u092f\u0935\u093e\u0926": "Thank you very much.",
                "\u092e\u0941\u091d\u0947 \u092e\u0926\u0926 \u091a\u093e\u0939\u093f\u090f": "I need help.",
                "\u0936\u094c\u091a\u093e\u0932\u092f \u0915\u0939\u093e\u0902 \u0939\u0948": "Where is the bathroom?",
            },
            "ht": {
                "bonjou": "Hello.",
                "mesi": "Thank you.",
                "mesi anpil": "Thank you very much.",
                "kijan ou ye": "How are you?",
                "wi": "Yes.",
                "non": "No.",
                "tanpri": "Please.",
                "eskize mwen": "Excuse me.",
                "orevwa": "Goodbye.",
                "mwen pa konprann": "I don't understand.",
                "mwen bezwen ed": "I need help.",
                "mwen bezwen ede": "I need help.",
                "kote twalet la": "Where is the bathroom?",
            },
        }
        for source_language, phrases in common.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source_phrase): translated for source_phrase, translated in phrases.items()}
            )

    def _canonical_phrase_key(self, text: str) -> str:
        normalized = _normalize_text(text)
        compact = normalized.replace(" ", "")
        aliased = _PHRASE_ALIASES.get(compact, _PHRASE_ALIASES.get(normalized, normalized))
        return _normalize_text(aliased)

    def _lookup_phrase(self, text: str, source: str, target: str) -> str | None:
        normalized = self._canonical_phrase_key(text)
        direct = self._phrases.get((source, target), {}).get(normalized)
        if direct:
            return direct
        if source == target:
            return text
        if source != "en":
            english = self._phrases.get((source, "en"), {}).get(normalized)
            if english:
                if target == "en":
                    return english
                pivoted = self._phrases.get(("en", target), {}).get(_normalize_text(english))
                if pivoted:
                    return pivoted
        return None

    def lookup_phrase_prefix(self, text: str, source: str, target: str) -> str | None:
        """Best-effort partial phrase match for streaming partial translation."""
        normalized = self._canonical_phrase_key(text)
        if not normalized:
            return None
        table = self._phrases.get((source, target), {})
        best_key = ""
        best_value = None
        for key, value in table.items():
            if normalized.startswith(key) and len(key) > len(best_key):
                best_key = key
                best_value = value
        if best_value and len(best_key) >= max(4, len(normalized) // 2):
            return best_value
        if source != "en":
            english_table = self._phrases.get((source, "en"), {})
            for key, english in english_table.items():
                if normalized.startswith(key) and len(key) > len(best_key):
                    pivoted = self._phrases.get(("en", target), {}).get(_normalize_text(english))
                    if pivoted:
                        best_key = key
                        best_value = pivoted
        return best_value

    def translate_with_meta(
        self,
        text: str,
        source_language: str | None = None,
        target_language: str | None = None,
        *,
        quality: bool = False,
    ) -> dict[str, str | bool]:
        phrase = self._lookup_phrase(text, source_language or "en", target_language or "ht")
        if phrase:
            return {"text": phrase, "phrase_hit": True, "partial_hit": False}
        prefix = self.lookup_phrase_prefix(text, source_language or "en", target_language or "ht")
        if prefix:
            return {"text": prefix, "phrase_hit": True, "partial_hit": True}
        translated = self.translate(text, source_language, target_language, quality=quality)
        return {
            "text": translated,
            "phrase_hit": not translated.startswith("["),
            "partial_hit": False,
        }

    def translate(
        self,
        text: str,
        source_language: str | None = None,
        target_language: str | None = None,
        *,
        quality: bool = False,
    ) -> str:
        # `quality` is accepted for signature parity with the ML translators
        # (the pipeline passes it to whatever translator it holds); a phrase
        # table has no beam search, so it is intentionally ignored here.
        if not text.strip():
            return ""
        source = source_language or "en"
        target = target_language or "ht"
        phrase = self._lookup_phrase(text, source, target)
        if phrase:
            return phrase
        if source == target:
            return text
        return f"[{source}->{target}] {text}"
