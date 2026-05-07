class LightweightTranslator:
    def __init__(self):
        self._phrases = {
            ("en", "es"): {
                "hello": "hola",
                "hello world": "hola mundo",
                "good morning": "buenos días",
                "good night": "buenas noches",
                "thank you": "gracias",
                "how are you": "cómo estás",
                "i need help": "necesito ayuda",
                "where is the bathroom": "dónde está el baño",
            },
            ("es", "en"): {
                "hola": "hello",
                "hola mundo": "hello world",
                "buenos días": "good morning",
                "buenas noches": "good night",
                "gracias": "thank you",
                "cómo estás": "how are you",
                "necesito ayuda": "i need help",
                "dónde está el baño": "where is the bathroom",
            },
        }

    def translate(self, text: str, source_language: str | None = None, target_language: str | None = None) -> str:
        if not text.strip():
            return ""
        source = source_language or "en"
        target = target_language or "es"
        normalized = " ".join(text.lower().strip().split())
        phrase = self._phrases.get((source, target), {}).get(normalized)
        if phrase:
            return phrase
        if source == target:
            return text
        return f"[{source}->{target}] {text}"
