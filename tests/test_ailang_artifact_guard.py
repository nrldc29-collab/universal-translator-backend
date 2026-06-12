"""Regression tests for AILang output sanitising."""


def test_apply_ailang_enhancements_rejects_internal_prompt(monkeypatch):
    from backend import streaming

    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    monkeypatch.setattr(streaming, "_AILANG_AVAILABLE", True)
    monkeypatch.setattr(
        streaming,
        "_ailang_enhance_v2",
        lambda **kwargs: {
            "translated_text": "[AI:fast] Ensure this French uses vous (formal). Keep meaning: [en->None] Hello..."
        },
    )

    result = streaming._apply_ailang_enhancements(
        translated_text="Bonjour.",
        source_text="Hello",
        source_lang="en",
        target_lang="fr",
        speaker="speaker",
    )

    assert result == "Bonjour."


def test_apply_ailang_enhancements_skips_offline_ailang(monkeypatch):
    from backend import streaming

    def fail_if_called(**kwargs):
        raise AssertionError("offline AILang enhancement should not run")

    monkeypatch.delenv("OLLAMA_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(streaming, "_AILANG_AVAILABLE", True)
    monkeypatch.setattr(streaming, "_ailang_enhance_v2", fail_if_called)

    result = streaming._apply_ailang_enhancements(
        translated_text="Bonjour.",
        source_text="Hello",
        source_lang="en",
        target_lang="fr",
        speaker="speaker",
    )

    assert result == "Bonjour."


def test_apply_ailang_enhancements_ignores_placeholder_api_key(monkeypatch):
    from backend import streaming

    def fail_if_called(**kwargs):
        raise AssertionError("placeholder API key must not enable AILang enhancement")

    monkeypatch.delenv("AILANG_ENHANCEMENTS_ENABLED", raising=False)
    monkeypatch.delenv("OLLAMA_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "your_api_key_here")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(streaming, "_AILANG_AVAILABLE", True)
    monkeypatch.setattr(streaming, "_ailang_enhance_v2", fail_if_called)

    result = streaming._apply_ailang_enhancements(
        translated_text="Bonjour.",
        source_text="Hello",
        source_lang="en",
        target_lang="fr",
        speaker="speaker",
    )

    assert result == "Bonjour."


def test_llm_agent_off_switch_overrides_available_api_key(monkeypatch):
    from backend import streaming

    monkeypatch.delenv("AILANG_ENHANCEMENTS_ENABLED", raising=False)
    monkeypatch.setenv("USE_LLM_AGENTS", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "configured-real-key")
    monkeypatch.setenv("OLLAMA_ENABLED", "true")

    assert streaming._ailang_enhancement_provider_enabled() is False
