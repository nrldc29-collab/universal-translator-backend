import json
import os
import logging
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


logger = logging.getLogger(__name__)

# Google Translate API language codes (ISO-ish) for all supported app languages.
REMOTE_LANGUAGE_CODES = {
    "en": "en",
    "es": "es",
    "ht": "ht",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "nl": "nl",
    "ru": "ru",
    "zh": "zh-CN",
    "ja": "ja",
    "ko": "ko",
    "ar": "ar",
    "hi": "hi",
}


def _remote_language(code: str | None) -> str:
    normalized = (code or "en").strip().lower().split("-")[0].split("_")[0] or "en"
    return REMOTE_LANGUAGE_CODES.get(normalized, normalized)


class RemoteTranslator:
    def __init__(self, timeout_seconds: float | None = None):
        self.timeout_seconds = timeout_seconds or float(os.getenv("REMOTE_TRANSLATION_TIMEOUT_SECONDS", "10"))
        self._cache: dict[tuple[str, str, str], str] = {}
        self._cache_lock = Lock()

    def translate(self, text: str, source_language: str | None = None, target_language: str | None = None) -> str:
        if not text.strip():
            return ""
        source = _remote_language(source_language or "en")
        target = _remote_language(target_language or "ht")
        if source == target:
            return text
        cache_key = (source, target, " ".join(text.lower().split()))
        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        query = urlencode({
            "client": "gtx",
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": text,
        })
        request = Request(
            f"https://translate.googleapis.com/translate_a/single?{query}",
            headers={"User-Agent": "AnaiTranslator/1.0"},
        )
        last_error: Exception | None = None
        for attempt in range(2):
            timeout = self.timeout_seconds if attempt == 0 else self.timeout_seconds * 1.5
            try:
                with urlopen(request, timeout=timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                translated = "".join(part[0] for part in payload[0] if part and part[0]).strip()
                if not translated:
                    raise RuntimeError("Remote translation returned empty text")
                with self._cache_lock:
                    self._cache[cache_key] = translated
                    if len(self._cache) > 500:
                        self._cache.pop(next(iter(self._cache)))
                return translated
            except (URLError, HTTPError, TimeoutError, OSError) as exc:
                last_error = exc
                logger.warning("remote_translation_failed attempt=%s error=%s", attempt + 1, exc)
                if attempt == 0:
                    continue
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                last_error = exc
                logger.warning("remote_translation_response_parse_failed attempt=%s error=%s", attempt + 1, exc)
                if attempt == 0:
                    continue
        raise RuntimeError(f"Remote translation failed: {last_error}") from last_error
