class MarianTranslator:
    def __init__(self, default_source_language: str = "en", default_target_language: str = "es"):
        self.default_source_language = default_source_language
        self.default_target_language = default_target_language
        self._models = {}
        self._cache = {}
        self.nllb_model = "facebook/nllb-200-distilled-600M"

    def _nllb_language(self, language: str) -> str:
        codes = {
            "en": "eng_Latn",
            "es": "spa_Latn",
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
        if key in self._models:
            return self._models[key]

        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("transformers is not installed. Install requirements to enable translation.") from exc

        try:
            model_name = self._model_name(source_language, target_language)
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            uses_nllb = False
        except Exception:
            tokenizer = AutoTokenizer.from_pretrained(self.nllb_model)
            model = AutoModelForSeq2SeqLM.from_pretrained(self.nllb_model)
            uses_nllb = True

        model.eval()
        translator = {
            "tokenizer": tokenizer,
            "model": model,
            "source_language": source_language,
            "target_language": target_language,
            "uses_nllb": uses_nllb,
        }
        self._models[key] = translator
        return translator

    def _generate_translation(self, text: str, translator: dict) -> str:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("torch is required for local translation.") from exc

        tokenizer = translator["tokenizer"]
        model = translator["model"]
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        generate_kwargs = {"max_new_tokens": 256}

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

    def translate(self, text: str, source_language: str | None = None, target_language: str | None = None) -> str:
        if not text.strip():
            return ""

        source = source_language or self.default_source_language
        target = target_language or self.default_target_language
        cache_key = (source, target, " ".join(text.lower().split()))
        if cache_key in self._cache:
            return self._cache[cache_key]
        translator = self._load_model(source, target)
        translated = self._generate_translation(text, translator)
        self._cache[cache_key] = translated
        if len(self._cache) > 500:
            self._cache.pop(next(iter(self._cache)))
        return translated
