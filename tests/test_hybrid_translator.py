from translation.hybrid_translator import HybridTranslator


class FakeMarianTranslator:
    def __init__(self):
        self.calls = []

    def translate(self, text, source_language=None, target_language=None, *, quality=False):
        self.calls.append((text, source_language, target_language))
        return "hola, \u00bfc\u00f3mo est\u00e1s hoy?"


class FakeRemoteTranslator:
    def __init__(self):
        self.calls = []

    def translate(self, text, source_language=None, target_language=None):
        self.calls.append((text, source_language, target_language))
        return "hola, \u00bfc\u00f3mo est\u00e1s hoy?"


class FakeFailingRemoteTranslator(FakeRemoteTranslator):
    def translate(self, text, source_language=None, target_language=None):
        self.calls.append((text, source_language, target_language))
        raise RuntimeError("remote unavailable")


def test_hybrid_keeps_exact_lightweight_phrase_when_hints_present():
    translator = HybridTranslator()
    fake_marian = FakeMarianTranslator()
    translator.marian = fake_marian
    translator.remote = FakeFailingRemoteTranslator()
    translator._ollama_enabled = False

    result = translator.translate("hello", "en", "es", hints=["preserve informal tone"])

    assert result == "hola"
    assert fake_marian.calls == []


def test_hybrid_uses_lightweight_phrase_without_marian():
    translator = HybridTranslator()
    fake_remote = FakeRemoteTranslator()
    fake_marian = FakeMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you", "en", "es")

    assert result == "Hola, \u00bfc\u00f3mo est\u00e1s?"
    assert fake_remote.calls == []
    assert fake_marian.calls == []


def test_hybrid_falls_back_to_marian_for_placeholder():
    translator = HybridTranslator()
    fake_remote = FakeFailingRemoteTranslator()
    fake_marian = FakeMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you today", "en", "es")

    assert result == "hola, \u00bfc\u00f3mo est\u00e1s hoy?"
    assert fake_marian.calls == [("hello how are you today", "en", "es")]
    assert fake_remote.calls == [("hello how are you today", "en", "es")]


def test_hybrid_prefers_remote_before_marian_for_fast_path(monkeypatch):
    monkeypatch.setenv("HYBRID_ENABLE_REMOTE", "1")
    translator = HybridTranslator()
    fake_remote = FakeRemoteTranslator()
    fake_marian = FakeMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you today", "en", "es", quality=False)

    assert result == "hola, \u00bfc\u00f3mo est\u00e1s hoy?"
    assert fake_remote.calls == [("hello how are you today", "en", "es")]
    assert fake_marian.calls == []


def test_hybrid_prefers_remote_for_normal_text_even_with_hints(monkeypatch):
    monkeypatch.setenv("HYBRID_ENABLE_REMOTE", "1")
    translator = HybridTranslator()
    fake_remote = FakeRemoteTranslator()
    fake_marian = FakeMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian
    translator._ollama_enabled = False

    result = translator.translate(
        "hello how are you today",
        "en",
        "es",
        hints=["Preserve natural question form in the target language."],
    )

    assert result == "hola, ¿cómo estás hoy?"
    assert fake_remote.calls == [("hello how are you today", "en", "es")]
    assert fake_marian.calls == []


def test_hybrid_uses_remote_only_when_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("HYBRID_ENABLE_REMOTE", "1")
    monkeypatch.setenv("HYBRID_ENABLE_MARIAN_FALLBACK", "0")
    translator = HybridTranslator()
    fake_remote = FakeRemoteTranslator()
    fake_marian = FakeMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you today", "en", "es")

    assert result == "hola, \u00bfc\u00f3mo est\u00e1s hoy?"
    assert fake_remote.calls == [("hello how are you today", "en", "es")]
    assert fake_marian.calls == []


class FailingMarianTranslator(FakeMarianTranslator):
    def translate(self, text, source_language=None, target_language=None, *, quality=False):
        self.calls.append((text, source_language, target_language))
        raise RuntimeError("marian unavailable")


class MemoryFailingMarianTranslator(FakeMarianTranslator):
    def translate(self, text, source_language=None, target_language=None, *, quality=False):
        self.calls.append((text, source_language, target_language))
        raise MemoryError("model is too large")


def test_hybrid_keeps_placeholder_when_local_paths_fail():
    translator = HybridTranslator()
    fake_remote = FakeFailingRemoteTranslator()
    fake_marian = FailingMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you today", "en", "es")

    assert result == "[en->es] hello how are you today"
    assert fake_marian.calls == [("hello how are you today", "en", "es")]
    assert fake_remote.calls == [("hello how are you today", "en", "es")]


def test_hybrid_survives_marian_memory_error():
    translator = HybridTranslator()
    translator._remote_enabled = False
    translator.marian = MemoryFailingMarianTranslator()

    result = translator.translate("an unknown sentence", "ht", "zh")

    assert result == "[ht->zh] an unknown sentence"
    assert translator.get_metrics()["marian_misses"] == 1


def test_translate_accepts_quality_flag_without_error(monkeypatch):
    translator = HybridTranslator()
    calls = []

    def fake_marian(text, source, target, *, quality=False):
        calls.append(quality)
        return "translated phrase"

    monkeypatch.setattr(translator, "_try_ollama", lambda *args, **kwargs: None)
    monkeypatch.setattr(translator, "_try_marian", fake_marian)
    monkeypatch.setattr(translator, "_try_remote", lambda *args, **kwargs: None)
    monkeypatch.setenv("OLLAMA_ENABLED", "0")

    result = translator.translate("quantum computing", "en", "fr", quality=True)
    assert result == "translated phrase"
    assert calls == [True]


def test_placeholder_detection():
    assert HybridTranslator.is_placeholder_translation("[en->es] hello", "en", "es")
    assert not HybridTranslator.is_placeholder_translation("hola", "en", "es")
