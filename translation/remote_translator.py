import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RemoteTranslator:
    def __init__(self, timeout_seconds: float | None = None):
        self.timeout_seconds = timeout_seconds or float(os.getenv("REMOTE_TRANSLATION_TIMEOUT_SECONDS", "10"))

    def translate(self, text: str, source_language: str | None = None, target_language: str | None = None) -> str:
        if not text.strip():
            return ""
        source = source_language or "en"
        target = target_language or "es"
        if source == target:
            return text
        query = urlencode({
            "client": "gtx",
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": text,
        })
        request = Request(
            f"https://translate.googleapis.com/translate_a/single?{query}",
            headers={"User-Agent": "UniversalTranslator/1.0"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated = "".join(part[0] for part in payload[0] if part and part[0]).strip()
        if not translated:
            raise RuntimeError("Remote translation returned empty text")
        return translated
