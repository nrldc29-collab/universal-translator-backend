from translation.marian_translator import MarianTranslator


def test_marian_memory_error_falls_back_and_retires_pair(monkeypatch):
    translator = MarianTranslator()
    calls = []

    def fail_to_load(source, target):
        calls.append((source, target))
        raise MemoryError("not enough memory")

    monkeypatch.setattr(translator, "_load_model", fail_to_load)

    assert translator.translate("hello", "en", "fr") == "Bonjour."
    assert translator.translate("thank you", "en", "fr") == "Merci."
    assert calls == [("en", "fr")]
