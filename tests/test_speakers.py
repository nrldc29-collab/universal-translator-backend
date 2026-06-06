from backend.speakers import SpeakerMemory, detect_language_heuristic, resolve_barrier_route


def test_detect_language_heuristic_handles_spanish_accents():
    assert detect_language_heuristic("Hola, como estas?") == "es"
    assert detect_language_heuristic("Hola, \u00bfcomo estas?") == "es"


def test_detect_language_heuristic_handles_supported_voice_scripts():
    assert detect_language_heuristic("Привет") == "ru"
    assert detect_language_heuristic("你好") == "zh"
    assert detect_language_heuristic("こんにちは") == "ja"
    assert detect_language_heuristic("안녕하세요") == "ko"
    assert detect_language_heuristic("مرحبا") == "ar"
    assert detect_language_heuristic("नमस्ते") == "hi"


def test_barrier_route_flips_to_other_person_when_target_language_speaks():
    route = resolve_barrier_route("Bonjour", "en", "fr", enabled=True)

    assert route["speaker"] == "person-2"
    assert route["speaker_label"] == "Person 2"
    assert route["source_language"] == "fr"
    assert route["target_language"] == "en"
    assert route["detected_language"] == "fr"
    assert route["route_confidence"] >= 0.8
    assert route["needs_confirmation"] is False


def test_barrier_route_keeps_primary_direction_when_source_language_speaks():
    route = resolve_barrier_route("Hello", "en", "fr", enabled=True)

    assert route["speaker"] == "person-1"
    assert route["speaker_label"] == "Person 1"
    assert route["source_language"] == "en"
    assert route["target_language"] == "fr"
    assert route["route_confidence"] >= 0.8


def test_barrier_route_flags_out_of_pair_language_for_meaning_check():
    route = resolve_barrier_route("Привет", "en", "fr", enabled=True)

    assert route["source_language"] == "en"
    assert route["target_language"] == "fr"
    assert route["detected_language"] == "ru"
    assert route["needs_confirmation"] is True


def test_speaker_memory_returns_copy_of_history():
    memory = SpeakerMemory()
    memory.register("phone-1", "en")
    memory.add_message("phone-1", "hello")

    context = memory.get_context("phone-1")
    context["history"].append("mutated")

    assert memory.get_context("phone-1")["history"] == ["hello"]
