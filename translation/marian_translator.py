class MarianTranslator:
    def __init__(self, default_source_language: str = "en", default_target_language: str = "es"):
        self.default_source_language = default_source_language
        self.default_target_language = default_target_language
        self._pipelines = {}
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

    def _load_pipeline(self, source_language: str, target_language: str):
        key = (source_language, target_language)
        if key in self._pipelines:
            return self._pipelines[key]

        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError("transformers is not installed. Install requirements to enable translation.") from exc

        try:
            translator = pipeline("translation", model=self._model_name(source_language, target_language))
        except Exception:
            translator = pipeline(
                "translation",
                model=self.nllb_model,
                src_lang=self._nllb_language(source_language),
                tgt_lang=self._nllb_language(target_language),
            )
        self._pipelines[key] = translator
        return translator

    def translate(self, text: str, source_language: str | None = None, target_language: str | None = None) -> str:
        if not text.strip():
            return ""

        source = source_language or self.default_source_language
        target = target_language or self.default_target_language
        cache_key = (source, target, " ".join(text.lower().split()))
        if cache_key in self._cache:
            return self._cache[cache_key]
        translator = self._load_pipeline(source, target)
        result = translator(text)
        translated = result[0]["translation_text"]
        self._cache[cache_key] = translated
        if len(self._cache) > 500:
            self._cache.pop(next(iter(self._cache)))
        return translated
