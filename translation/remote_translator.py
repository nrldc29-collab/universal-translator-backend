import json
import os
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


logger = logging.getLogger(__name__)


class RemoteTranslator:
    def __init__(self, timeout_seconds: float | None = None):
        self.timeout_seconds = timeout_seconds or float(os.getenv("REMOTE_TRANSLATION_TIMEOUT_SECONDS", "10"))

    def translate(self, text: str, source_language: str | None = None, target_language: str | None = None) -> str:
        if not text.strip():
            return ""
        source = source_language or "en"
        target = target_language or "ht"
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
            headers={"User-Agent": "AnaiTranslator/1.0"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            translated = "".join(part[0] for part in payload[0] if part and part[0]).strip()
            if not translated:
                raise RuntimeError("Remote translation returned empty text")
            return translated
        except (URLError, HTTPError, TimeoutError) as exc:
            logger.warning("remote_translation_failed error=%s", exc)
            raise RuntimeError(f"Remote translation failed: {exc}") from exc
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            logger.warning("remote_translation_response_parse_failed error=%s", exc)
            raise RuntimeError(f"Remote translation response parse failed: {exc}") from exc
