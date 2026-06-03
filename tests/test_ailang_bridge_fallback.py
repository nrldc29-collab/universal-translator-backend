"""Regression tests for the AILang bridge offline fallback.

Previously, when no live model was reachable, the bridge echoed its own prompt
back as the "model output" (e.g. "[AI:fast] Ensure this French uses vous
(formal). Keep meaning: ... Hello..."). That leaked prompt text surfaced in the
UI as the translation. The bridge must instead raise for generative prompts so
the pipeline falls back to the real base translation.
"""
import pytest

from ailang_integration.runtime.bridge import (
    AILangBridge,
    AILangModelUnavailable,
    _offline_fallback,
)


def test_offline_fallback_returns_stubs_for_structured_prompts():
    assert "domain" in _offline_fallback("fast", "analyze domain and formality for this text")
    assert "people" in _offline_fallback(
        "fast", "Extract named entities and pronouns from this text"
    )
    assert "similarity_score" in _offline_fallback("fast", "compare these translations for similarity")
    assert _offline_fallback("fast", "Identify genuinely ambiguous words in this en text") == "[]"


def test_offline_fallback_raises_for_generative_prompts():
    with pytest.raises(AILangModelUnavailable):
        _offline_fallback(
            "fast",
            "Ensure this French uses vous (formal). Keep meaning: [en->None] Hello",
        )
    with pytest.raises(AILangModelUnavailable):
        _offline_fallback(
            "fast",
            "Given history, resolve any ambiguous pronouns in: Hello",
        )


def _make_bare_bridge():
    bridge = object.__new__(AILangBridge)
    bridge._ai_providers = {}
    bridge._call_count = 0
    bridge._call_errors = 0
    bridge._call_latency_ms = []
    bridge._max_latency_samples = 100
    return bridge


def test_route_ai_call_never_leaks_prompt_when_offline(monkeypatch):
    import backend.cip_client as cip_client

    # No OpenAI key and CIP returns nothing -> fully offline.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cip_client, "call_cip_brain", lambda *a, **k: {})

    bridge = _make_bare_bridge()

    # A generative translation prompt must raise (so the caller keeps the base
    # translation) rather than echoing the prompt as a fake translation.
    with pytest.raises(AILangModelUnavailable):
        bridge._route_ai_call(
            "fast",
            "Ensure this French uses vous (formal). Keep meaning: [en->None] Hello",
        )

    # Structured analysis prompts still get a usable JSON stub.
    out = bridge._route_ai_call("fast", "analyze domain and formality for this text")
    assert out.lstrip().startswith("{")
    assert "domain" in out
    assert not out.startswith("[AI:")
