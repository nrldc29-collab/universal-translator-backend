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
        }

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
