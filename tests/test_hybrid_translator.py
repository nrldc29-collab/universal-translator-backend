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


def test_hybrid_falls_back_to_remote_for_placeholder():
    translator = HybridTranslator()
    fake_remote = FakeRemoteTranslator()
    fake_marian = FakeMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you today", "en", "es")

    assert result == "hola, \u00bfc\u00f3mo est\u00e1s hoy?"
    assert fake_remote.calls == [("hello how are you today", "en", "es")]
    assert fake_marian.calls == []


def test_hybrid_keeps_placeholder_when_remote_is_down():
    translator = HybridTranslator()
    fake_remote = FakeFailingRemoteTranslator()
    fake_marian = FakeMarianTranslator()
    translator.remote = fake_remote
    translator.marian = fake_marian

    result = translator.translate("hello how are you today", "en", "es")

    assert result == "[en->es] hello how are you today"
    assert fake_remote.calls == [("hello how are you today", "en", "es")]
    assert fake_marian.calls == []


def test_placeholder_detection():
    assert HybridTranslator.is_placeholder_translation("[en->es] hello", "en", "es")
    assert not HybridTranslator.is_placeholder_translation("hola", "en", "es")
