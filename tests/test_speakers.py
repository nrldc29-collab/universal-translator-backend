from backend.speakers import SpeakerMemory, detect_language_heuristic


def test_detect_language_heuristic_handles_spanish_accents():
    assert detect_language_heuristic("Hola, como estas?") == "es"
    assert detect_language_heuristic("Hola, \u00bfcomo estas?") == "es"


def test_detect_language_heuristic_handles_haitian_creole():
    assert detect_language_heuristic("Mwen bezwen èd") == "ht"
    assert detect_language_heuristic("Bonjou, kijan ou ye?") == "ht"


def test_detect_language_in_pair_en_ht():
    from backend.speakers import detect_language_in_pair

    assert detect_language_in_pair("Mwen bezwen èd", "en", "ht") == "ht"
    assert detect_language_in_pair("I need help", "en", "ht") == "en"


def test_resolve_whisper_language_auto_for_ht_pair():
    from backend.speakers import resolve_whisper_language

    assert resolve_whisper_language("en", "ht") is None
    assert resolve_whisper_language("en", "es") == "en"


def test_opposite_language_in_pair_en_ht():
    from backend.speakers import opposite_language_in_pair

    assert opposite_language_in_pair("ht", "en", "ht") == "en"
    assert opposite_language_in_pair("en", "en", "ht") == "ht"


def test_speaker_memory_returns_copy_of_history():
    memory = SpeakerMemory()
    memory.register("phone-1", "en")
    memory.add_message("phone-1", "hello")

    context = memory.get_context("phone-1")
    context["history"].append("mutated")

    assert memory.get_context("phone-1")["history"] == ["hello"]
