from backend.speakers import SpeakerMemory, detect_language_heuristic


def test_detect_language_heuristic_handles_spanish_accents():
    assert detect_language_heuristic("Hola, como estas?") == "es"
    assert detect_language_heuristic("Hola, \u00bfcomo estas?") == "es"


def test_speaker_memory_returns_copy_of_history():
    memory = SpeakerMemory()
    memory.register("phone-1", "en")
    memory.add_message("phone-1", "hello")

    context = memory.get_context("phone-1")
    context["history"].append("mutated")

    assert memory.get_context("phone-1")["history"] == ["hello"]
