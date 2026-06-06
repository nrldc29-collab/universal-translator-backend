import os

from .lightweight_translator import LightweightTranslator
from .marian_translator import MarianTranslator
from .remote_translator import RemoteTranslator


def _marian_fallback_enabled() -> bool:
    return os.getenv("HYBRID_ENABLE_MARIAN_FALLBACK", "1") != "0"


def _remote_fallback_enabled() -> bool:
    return os.getenv("HYBRID_ENABLE_REMOTE", "0") == "1"


class HybridTranslator:
    def __init__(self):
        self.lightweight = LightweightTranslator()
        self.remote = RemoteTranslator()
        self.marian = MarianTranslator()

    @staticmethod
    def is_placeholder_translation(text: str, source_language: str | None = None, target_language: str | None = None) -> bool:
        if not text:
            return False
        source = source_language or "en"
        target = target_language or "ht"
        return text.startswith(f"[{source}->{target}]")

    def translate(self, text: str, source_language: str | None = None, target_language: str | None = None) -> str:
        lightweight_result = self.lightweight.translate(text, source_language, target_language)
        if not self.is_placeholder_translation(lightweight_result, source_language, target_language):
            return lightweight_result
        if _marian_fallback_enabled():
            try:
                return self.marian.translate(text, source_language, target_language)
            except (RuntimeError, OSError, ValueError):
                pass
        if _remote_fallback_enabled():
            try:
                return self.remote.translate(text, source_language, target_language)
            except (ConnectionError, TimeoutError, RuntimeError, ValueError):
                pass
        return lightweight_result
