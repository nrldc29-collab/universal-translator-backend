from translation.hybrid_translator import HybridTranslator


class FakeMarianTranslator:
    def __init__(self):
        self.calls = []

    def translate(self, text, source_language=None, target_language=None):
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
    fake_remote = FakeRemoteTranslator()
    fake_marian = FakeMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you today", "en", "es")

    assert result == "hola, \u00bfc\u00f3mo est\u00e1s hoy?"
    assert fake_marian.calls == [("hello how are you today", "en", "es")]
    assert fake_remote.calls == []


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
    def translate(self, text, source_language=None, target_language=None):
        self.calls.append((text, source_language, target_language))
        raise RuntimeError("marian unavailable")


def test_hybrid_keeps_placeholder_when_local_paths_fail():
    translator = HybridTranslator()
    fake_remote = FakeFailingRemoteTranslator()
    fake_marian = FailingMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you today", "en", "es")

    assert result == "[en->es] hello how are you today"
    assert fake_marian.calls == [("hello how are you today", "en", "es")]
    assert fake_remote.calls == []


def test_placeholder_detection():
    assert HybridTranslator.is_placeholder_translation("[en->es] hello", "en", "es")
    assert not HybridTranslator.is_placeholder_translation("hola", "en", "es")
