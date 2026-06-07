import logging
from threading import Lock

from backend.config import get_nllb_model, get_translation_device, get_translation_num_beams

logger = logging.getLogger(__name__)


class MarianTranslator:
    def __init__(self, default_source_language: str = "en", default_target_language: str = "ht"):
        self.default_source_language = default_source_language
        self.default_target_language = default_target_language
        self._models = {}
        self._model_lock = Lock()
        self._cache = {}
        self._cache_lock = Lock()
        self.nllb_model = get_nllb_model()

    def _nllb_language(self, language: str) -> str:
        codes = {
            "en": "eng_Latn",
            "es": "spa_Latn",
            "ht": "hat_Latn",   # Haitian Creole — NLLB-200 supports this
            "fr": "fra_Latn",
            "de": "deu_Latn",
            "it": "ita_Latn",
            "pt": "por_Latn",
            "nl": "nld_Latn",
            "ru": "rus_Cyrl",
            "zh": "zho_Hans",
            "ja": "jpn_Jpan",
            "ko": "kor_Hang",
            "ar": "arb_Arab",
            "hi": "hin_Deva",
        }
        return codes.get(language, "eng_Latn")

    def _model_name(self, source_language: str, target_language: str) -> str:
        return f"Helsinki-NLP/opus-mt-{source_language}-{target_language}"

    def _load_model(self, source_language: str, target_language: str):
        key = (source_language, target_language)
        with self._model_lock:
            if key in self._models:
                return self._models[key]

            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            except ImportError as exc:
                raise RuntimeError("transformers is not installed. Install requirements to enable translation.") from exc

            try:
                model_name = self._model_name(source_language, target_language)
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForSeq2SeqLM.from_pretrained(model_name, use_safetensors=False)
                uses_nllb = False
            except (OSError, ValueError, RuntimeError) as exc:
                logger.info(
                    "No direct MarianMT model for %s->%s (%s); falling back to NLLB %s",
                    source_language, target_language, type(exc).__name__, self.nllb_model,
                )
                tokenizer = AutoTokenizer.from_pretrained(self.nllb_model)
                model = AutoModelForSeq2SeqLM.from_pretrained(self.nllb_model)
                uses_nllb = True

            device = "cpu"
            requested_device = get_translation_device()
            if requested_device == "cuda":
                try:
                    import torch

                    if torch.cuda.is_available():
                        model = model.to("cuda")
                        device = "cuda"
                except (RuntimeError, OSError):
                    device = "cpu"
            model.eval()
            translator = {
                "tokenizer": tokenizer,
                "model": model,
                "device": device,
                "source_language": source_language,
                "target_language": target_language,
                "uses_nllb": uses_nllb,
            }
            self._models[key] = translator
            return translator

    def _generate_translation(self, text: str, translator: dict, *, quality: bool = False) -> str:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("torch is required for local translation.") from exc

        tokenizer = translator["tokenizer"]
        model = translator["model"]
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        if translator.get("device") == "cuda":
            inputs = {key: value.to("cuda") for key, value in inputs.items()}
        # Greedy decoding (num_beams=1) stops at the EOS token, so this ceiling
        # only bounds pathological inputs — short sentences finish well before it.
        # Keeping it generous prevents long sentences from being truncated mid-thought.
        max_new_tokens = min(256, max(24, len(text.split()) * 3 + 16))
        num_beams = get_translation_num_beams(quality=quality)
        generate_kwargs = {"max_new_tokens": max_new_tokens, "num_beams": num_beams, "do_sample": False}

        if translator["uses_nllb"]:
            source_code = self._nllb_language(translator["source_language"])
            target_code = self._nllb_language(translator["target_language"])
            tokenizer.src_lang = source_code
            forced_bos_token_id = tokenizer.convert_tokens_to_ids(target_code)
            if isinstance(forced_bos_token_id, int) and forced_bos_token_id >= 0:
                generate_kwargs["forced_bos_token_id"] = forced_bos_token_id

        with torch.inference_mode():
            output_tokens = model.generate(**inputs, **generate_kwargs)
        return tokenizer.batch_decode(output_tokens, skip_special_tokens=True)[0]

    def translate(
        self,
        text: str,
        source_language: str | None = None,
        target_language: str | None = None,
        *,
        quality: bool = False,
    ) -> str:
        if not text.strip():
            return ""

        source = source_language or self.default_source_language
        target = target_language or self.default_target_language
        cache_key = (source, target, "quality" if quality else "fast", " ".join(text.lower().split()))
        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        translator = self._load_model(source, target)
        translated = self._generate_translation(text, translator, quality=quality)
        with self._cache_lock:
            self._cache[cache_key] = translated
            if len(self._cache) > 500:
                self._cache.pop(next(iter(self._cache)))
        return translated
