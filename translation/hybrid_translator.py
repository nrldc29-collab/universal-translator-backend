"""Three-tier hybrid translator: Ollama -> NLLB/Marian -> Remote API.

Routing logic:
  1. If Ollama is available and enabled, use it first (best quality, local).
  2. If Ollama fails or is unavailable, fall back to NLLB/Marian (local ML models).
  3. If local models fail, fall back to remote Google Translate API.
  4. If everything fails, return the lightweight phrase-table result.
"""

import json
import logging
import os
import time
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .lightweight_translator import LightweightTranslator
from .marian_translator import MarianTranslator
from .remote_translator import RemoteTranslator

logger = logging.getLogger(__name__)


class OllamaTranslator:
    """Translator that uses a local Ollama LLM for high-quality translation."""

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "8"))
        self._available = None
        self._last_check = 0.0
        self._check_interval = 30.0
        self._lock = Lock()
        self._cache = {}
        self._cache_lock = Lock()

    def is_available(self):
        now = time.monotonic()
        if self._available is not None and (now - self._last_check) < self._check_interval:
            return self._available
        with self._lock:
            if self._available is not None and (time.monotonic() - self._last_check) < self._check_interval:
                return self._available
            try:
                req = Request(
                    f"{self.base_url}/api/tags",
                    headers={"User-Agent": "AnaiTranslator/1.0"},
                )
                with urlopen(req, timeout=2.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "") for m in data.get("models", [])]
                    model_base = self.model.split(":")[0]
                    self._available = any(model_base in m for m in models)
            except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError):
                self._available = False
            self._last_check = time.monotonic()
            return self._available

    def translate(self, text, source_language=None, target_language=None):
        if not text.strip():
            return ""
        source = source_language or "en"
        target = target_language or "es"
        if source == target:
            return text

        cache_key = (source, target, " ".join(text.lower().split()))
        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        lang_names = {
            "en": "English", "es": "Spanish", "fr": "French", "de": "German",
            "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
            "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
            "hi": "Hindi", "ht": "Haitian Creole",
        }
        source_name = lang_names.get(source, source)
        target_name = lang_names.get(target, target)

        prompt = (
            f"Translate the following text from {source_name} to {target_name}. "
            f"Return ONLY the translated text, nothing else.\n\n{text}"
        )

        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 256},
        }).encode("utf-8")

        req = Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "AnaiTranslator/1.0"},
            method="POST",
        )

        try:
            started = time.monotonic()
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.monotonic() - started

            translated = data.get("response", "").strip()
            for prefix in ("Translation:", "Translated:", "Here is the translation:", f"{target_name}:"):
                if translated.lower().startswith(prefix.lower()):
                    translated = translated[len(prefix):].strip()
            if len(translated) > 2 and translated[0] in ('"', "'") and translated[-1] in ('"', "'"):
                translated = translated[1:-1].strip()

            if not translated:
                raise RuntimeError("Ollama returned empty translation")

            logger.info("ollama_translation ok model=%s elapsed=%.2fs", self.model, elapsed)
            with self._cache_lock:
                self._cache[cache_key] = translated
                if len(self._cache) > 500:
                    self._cache.pop(next(iter(self._cache)))
            return translated

        except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("ollama_translation_failed error=%s", exc)
            raise RuntimeError(f"Ollama translation failed: {exc}") from exc


class HybridTranslator:
    """Three-tier translation: Ollama -> Marian/NLLB -> Remote -> Lightweight."""

    def __init__(self):
        self.lightweight = LightweightTranslator()
        self.remote = RemoteTranslator()
        self.marian = MarianTranslator()
        self.ollama = OllamaTranslator()
        self._ollama_enabled = os.getenv("OLLAMA_ENABLED", "1" if os.getenv("OLLAMA_URL") else "0") == "1"
        self._marian_enabled = os.getenv("HYBRID_ENABLE_MARIAN_FALLBACK", "1") == "1"
        self._forced_tier = os.getenv("TRANSLATION_TIER", "auto").lower()
        self._metrics = {
            "ollama_hits": 0, "ollama_misses": 0,
            "marian_hits": 0, "marian_misses": 0,
            "remote_hits": 0, "remote_misses": 0,
            "lightweight_hits": 0,
        }
        self._lock = Lock()

    @staticmethod
    def is_placeholder_translation(text, source_language=None, target_language=None):
        if not text:
            return False
        source = source_language or "en"
        target = target_language or "es"
        return text.startswith(f"[{source}->{target}]")

    def get_metrics(self):
        with self._lock:
            return dict(self._metrics)

    def _record(self, tier, hit):
        with self._lock:
            key = f"{tier}_{'hits' if hit else 'misses'}"
            if key in self._metrics:
                self._metrics[key] += 1

    def translate(self, text, source_language=None, target_language=None):
        if not text.strip():
            return ""
        source = source_language or "en"
        target = target_language or "es"
        if source == target:
            return text

        lightweight_result = self.lightweight.translate(text, source, target)
        if not self.is_placeholder_translation(lightweight_result, source, target):
            self._record("lightweight", True)
            return lightweight_result

        if self._forced_tier == "ollama":
            return self._try_ollama(text, source, target) or lightweight_result
        if self._forced_tier == "local":
            return self._try_marian(text, source, target) or lightweight_result
        if self._forced_tier == "remote":
            return self._try_remote(text, source, target) or lightweight_result

        if self._ollama_enabled:
            ollama_result = self._try_ollama(text, source, target)
            if ollama_result:
                return ollama_result

        if self._marian_enabled:
            marian_result = self._try_marian(text, source, target, quality=quality)
            if marian_result:
                return marian_result

        remote_result = self._try_remote(text, source, target)
        if remote_result:
            return remote_result

        return lightweight_result

    def _try_ollama(self, text, source, target):
        try:
            if not self.ollama.is_available():
                self._record("ollama", False)
                return None
            result = self.ollama.translate(text, source, target)
            self._record("ollama", True)
            return result
        except (RuntimeError, ConnectionError, TimeoutError, ValueError):
            self._record("ollama", False)
            return None

    def _try_marian(self, text, source, target, *, quality=False):
        try:
            result = self.marian.translate(text, source, target, quality=quality)
            if result and not self.is_placeholder_translation(result, source, target):
                self._record("marian", True)
                return result
            self._record("marian", False)
            return None
        except (RuntimeError, ImportError, OSError):
            self._record("marian", False)
            return None

    def _try_remote(self, text, source, target):
        try:
            result = self.remote.translate(text, source, target)
            if result and not self.is_placeholder_translation(result, source, target):
                self._record("remote", True)
                return result
            self._record("remote", False)
            return None
        except (RuntimeError, ConnectionError, TimeoutError, ValueError):
            self._record("remote", False)
            return None
