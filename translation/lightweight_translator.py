import string
import unicodedata


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
                "thank you": "mèsi",
                "i need help": "mwen bezwen èd",
                "good morning": "bonjou",
                "how are you": "kijan ou ye",
            },
            ("ht", "en"): {
                "bonjou": "hello",
                "mesi": "thank you",
                "mwen bezwen ed": "i need help",
                "kijan ou ye": "how are you",
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
        self._add_common_to_english_phrases()

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
                "hello": "Bonjou.",
                "thank you": "M\u00e8si.",
                "good morning": "Bonjou.",
                "good night": "B\u00f2n nuit.",
                "how are you": "Kijan ou ye?",
                "i need help": "Mwen bezwen \u00e8d.",
            },
        }
        for target_language, phrases in common.items():
            self._phrases.setdefault(("en", target_language), {}).update(
                {_normalize_text(source_phrase): translated for source_phrase, translated in phrases.items()}
            )

    def _add_common_to_english_phrases(self) -> None:
        common = {
            "fr": {
                "bonjour": "Hello.",
                "merci": "Thank you.",
                "comment allez vous": "How are you?",
            },
            "de": {
                "hallo": "Hello.",
                "danke": "Thank you.",
                "wie geht es ihnen": "How are you?",
            },
            "it": {
                "ciao": "Hello.",
                "grazie": "Thank you.",
                "come sta": "How are you?",
            },
            "pt": {
                "ola": "Hello.",
                "obrigado": "Thank you.",
                "como voce esta": "How are you?",
            },
            "nl": {
                "hallo": "Hello.",
                "dank u": "Thank you.",
                "hoe gaat het met u": "How are you?",
            },
            "ru": {
                "\u043f\u0440\u0438\u0432\u0435\u0442": "Hello.",
                "\u0441\u043f\u0430\u0441\u0438\u0431\u043e": "Thank you.",
                "\u043a\u0430\u043a \u0434\u0435\u043b\u0430": "How are you?",
            },
            "zh": {
                "\u4f60\u597d": "Hello.",
                "\u8c22\u8c22": "Thank you.",
                "\u4f60\u597d\u5417": "How are you?",
            },
            "ja": {
                "\u3053\u3093\u306b\u3061\u306f": "Hello.",
                "\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3059": "Thank you.",
                "\u304a\u5143\u6c17\u3067\u3059\u304b": "How are you?",
            },
            "ko": {
                "\uc548\ub155\ud558\uc138\uc694": "Hello.",
                "\uac10\uc0ac\ud569\ub2c8\ub2e4": "Thank you.",
                "\uc5b4\ub5bb\uac8c \uc9c0\ub0b4\uc138\uc694": "How are you?",
            },
            "ar": {
                "\u0645\u0631\u062d\u0628\u0627": "Hello.",
                "\u0634\u0643\u0631\u0627": "Thank you.",
                "\u0643\u064a\u0641 \u062d\u0627\u0644\u0643": "How are you?",
            },
            "hi": {
                "\u0928\u092e\u0938\u094d\u0924\u0947": "Hello.",
                "\u0927\u0928\u094d\u092f\u0935\u093e\u0926": "Thank you.",
                "\u0906\u092a \u0915\u0948\u0938\u0947 \u0939\u0948\u0902": "How are you?",
            },
            "ht": {
                "bonjou": "Hello.",
                "mesi": "Thank you.",
                "kijan ou ye": "How are you?",
            },
        }
        for source_language, phrases in common.items():
            self._phrases.setdefault((source_language, "en"), {}).update(
                {_normalize_text(source_phrase): translated for source_phrase, translated in phrases.items()}
            )

    def translate(self, text: str, source_language: str | None = None, target_language: str | None = None) -> str:
        if not text.strip():
            return ""
        source = source_language or "en"
        target = target_language or "ht"
        phrase = self._phrases.get((source, target), {}).get(_normalize_text(text))
        if phrase:
            return phrase
        if source == target:
            return text
        return f"[{source}->{target}] {text}"
