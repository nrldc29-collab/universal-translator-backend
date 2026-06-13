"""Tests for backend.model_readiness."""

from backend.model_readiness import check_piper_voices, espeak_available, evaluate_preload_result


def test_evaluate_preload_ready_when_all_components_ok(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "local")
    monkeypatch.setenv("TRANSLATION_BACKEND", "marian")
    monkeypatch.setattr(
        "backend.model_readiness.check_piper_voices",
        lambda: {"present": [{"lang": "en", "path": "models/tts/en_US-lessac-medium.onnx"}], "missing": []},
    )
    monkeypatch.setattr("backend.model_readiness.espeak_available", lambda: True)
    preload = {
        "stt": {"ok": True},
        "tts": {"ok": True},
        "translation": {"ok": True},
    }
    result = evaluate_preload_result(preload)
    assert result["ready"] is True
    assert result["blockers"] == []


def test_evaluate_preload_blocks_on_stt_failure(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "local")
    monkeypatch.setenv("TRANSLATION_BACKEND", "lightweight")
    result = evaluate_preload_result({"stt": {"ok": False}, "tts": {"ok": True}, "translation": {"ok": True}})
    assert result["ready"] is True
    assert "stt_preload_failed" in result["warnings"]
    assert "stt_preload_failed" not in result["blockers"]


def test_evaluate_preload_blocks_on_translation_failure(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "local")
    monkeypatch.setenv("TRANSLATION_BACKEND", "marian")
    result = evaluate_preload_result(
        {
            "stt": {"ok": True},
            "tts": {"ok": True},
            "translation": {"ok": False, "error": "RuntimeError"},
        }
    )
    assert result["ready"] is False
    assert "translation_preload_failed" in result["blockers"]


def test_check_piper_voices_structure():
    voices = check_piper_voices()
    assert "present" in voices
    assert "missing" in voices
    assert isinstance(voices["present"], list)
    assert isinstance(voices["missing"], list)


def test_espeak_available_is_bool():
    assert isinstance(espeak_available(), bool)


def test_evaluate_preload_warns_when_espeak_missing_but_neural_ready(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "local")
    monkeypatch.setenv("TRANSLATION_BACKEND", "marian")
    monkeypatch.setattr(
        "backend.model_readiness.check_piper_voices",
        lambda: {"present": [{"lang": "en", "path": "models/tts/en_US-lessac-medium.onnx"}], "missing": []},
    )
    monkeypatch.setattr("backend.model_readiness.espeak_available", lambda: False)
    monkeypatch.setattr("backend.model_readiness.is_neural_tts_ready", lambda: True)
    result = evaluate_preload_result({"stt": {"ok": True}, "tts": {"ok": True}, "translation": {"ok": True}})
    assert result["ready"] is True
    assert "espeak_missing_ht_tts_unavailable" not in result["blockers"]
    assert "espeak_missing_using_neural_ht_tts" in result["warnings"]


def test_evaluate_preload_blocks_when_espeak_and_neural_missing(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "local")
    monkeypatch.setenv("TRANSLATION_BACKEND", "marian")
    monkeypatch.setattr(
        "backend.model_readiness.check_piper_voices",
        lambda: {"present": [{"lang": "en", "path": "models/tts/en_US-lessac-medium.onnx"}], "missing": []},
    )
    monkeypatch.setattr("backend.model_readiness.espeak_available", lambda: False)
    monkeypatch.setattr("backend.model_readiness.is_neural_tts_ready", lambda: False)
    result = evaluate_preload_result({"stt": {"ok": True}, "tts": {"ok": True}, "translation": {"ok": True}})
    assert result["ready"] is False
    assert "espeak_missing_ht_tts_unavailable" in result["blockers"]


def test_evaluate_preload_ready_with_lazy_startup(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "local")
    monkeypatch.setenv("TRANSLATION_BACKEND", "hybrid")
    monkeypatch.setenv("PRELOAD_MODELS", "0")
    monkeypatch.setattr("backend.model_readiness.espeak_available", lambda: False)
    monkeypatch.setattr("backend.model_readiness.is_neural_tts_ready", lambda: True)
    result = evaluate_preload_result(None)
    assert result["ready"] is True
    assert "stt_preload_failed" not in result["blockers"]
    assert "stt_lazy_load_deferred" in result["warnings"]


def test_evaluate_preload_partial_piper_voices_not_blocker_when_neural_ready(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "local")
    monkeypatch.setenv("TRANSLATION_BACKEND", "marian")
    monkeypatch.setattr(
        "backend.model_readiness.check_piper_voices",
        lambda: {
            "present": [{"lang": "en", "path": "models/tts/en_US-lessac-medium.onnx"}],
            "missing": [{"lang": "nl", "path": "models/tts/nl_NL-ronnie-medium.onnx"}],
        },
    )
    monkeypatch.setattr("backend.model_readiness.espeak_available", lambda: False)
    monkeypatch.setattr("backend.model_readiness.is_neural_tts_ready", lambda: True)
    result = evaluate_preload_result({"stt": {"ok": True}, "tts": {"ok": True}, "translation": {"ok": True}})
    assert result["ready"] is True
    assert "tts_no_piper_voices_or_espeak" not in result["blockers"]
    assert "tts_using_neural_fallback_for_missing_piper_voices" in result["warnings"]

    monkeypatch.setenv("STT_PROVIDER", "streaming")
    monkeypatch.setenv("TRANSLATION_BACKEND", "lightweight")
    monkeypatch.setenv("PRELOAD_MODELS", "1")
    result = evaluate_preload_result({"stt": {"ok": False}, "tts": {"ok": True}, "translation": {"ok": True}})
    assert result["ready"] is False
    assert "stt_streaming_provider_unreachable" in result["blockers"]
