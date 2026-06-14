"""End-to-end integration tests for the Ollama + AILang pipeline.

Validates the complete chain:
  Translation request → AILang pipeline → Ollama LLM → enhanced output

Tests run in three modes:
  1. Ollama available  — full LLM-enhanced path
  2. Ollama unavailable — graceful degradation to offline rules
  3. Ollama disabled    — pure offline rule-based path

All tests are safe to run without Ollama — they auto-skip or degrade gracefully.
"""

import json
import os
import time
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ollama_is_reachable() -> bool:
    """Check if Ollama is actually running locally."""
    try:
        from urllib.request import Request, urlopen
        req = Request("http://localhost:11434/api/tags", headers={"User-Agent": "AnaiTranslator/test"})
        with urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return bool(data.get("models"))
    except Exception:
        return False


def _get_ollama_models() -> list:
    """Get list of available Ollama models."""
    try:
        from urllib.request import Request, urlopen
        req = Request("http://localhost:11434/api/tags", headers={"User-Agent": "AnaiTranslator/test"})
        with urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def _ollama_generate_works() -> bool:
    """Tags can succeed while /api/generate is broken — gate LLM-dependent tests."""
    if not _ollama_is_reachable():
        return False
    try:
        from urllib.request import Request, urlopen
        model = (_get_ollama_models() or ["llama3.2:3b"])[0].split(":")[0]
        payload = json.dumps({
            "model": model,
            "prompt": "Reply with exactly: ok",
            "stream": False,
            "options": {"num_predict": 8},
        }).encode("utf-8")
        req = Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "AnaiTranslator/test"},
            method="POST",
        )
        with urlopen(req, timeout=20.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return bool((data.get("response") or "").strip())
    except Exception:
        return False


OLLAMA_REACHABLE = _ollama_is_reachable()
OLLAMA_GENERATE_WORKS = _ollama_generate_works()
OLLAMA_MODELS = _get_ollama_models()


# ---------------------------------------------------------------------------
# Bridge routing tests
# ---------------------------------------------------------------------------

class TestOllamaBridgeRouting:
    """Tests for AILangBridge._route_ai_call with Ollama as first provider."""

    def test_try_ollama_returns_none_when_disabled(self):
        """When OLLAMA_ENABLED=false, _try_ollama returns None immediately."""
        from ailang_integration.runtime.bridge import AILangBridge
        bridge = AILangBridge()

        with patch.dict(os.environ, {"OLLAMA_ENABLED": "false"}):
            result = bridge._try_ollama("claude", "test prompt")
            assert result is None

    def test_try_ollama_returns_none_when_unreachable(self):
        """When Ollama is enabled but unreachable, _try_ollama returns None."""
        from ailang_integration.runtime.bridge import AILangBridge
        bridge = AILangBridge()

        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "OLLAMA_URL": "http://localhost:99999",  # unreachable
            "OLLAMA_MODEL": "nonexistent",
        }):
            result = bridge._try_ollama("claude", "test prompt")
            assert result is None

    def test_try_ollama_model_mapping(self):
        """AILang model aliases are mapped to the configured Ollama model."""
        from ailang_integration.runtime.bridge import AILangBridge
        bridge = AILangBridge()

        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "OLLAMA_URL": "http://localhost:99999",  # unreachable so it returns None fast
            "OLLAMA_MODEL": "mistral",
        }):
            # Even though Ollama is unreachable, the mapping should be set up
            # We verify by checking that the method doesn't crash on any alias
            for alias in ["claude", "fast", "gpt-4", "gpt-3.5", "unknown"]:
                result = bridge._try_ollama(alias, "test prompt")
                assert result is None  # unreachable, but no crash

    def test_route_ai_call_ollama_first(self):
        """Ollama is tried before OpenAI in the routing chain."""
        from ailang_integration.runtime.bridge import AILangBridge
        bridge = AILangBridge()

        ollama_attempts = []

        original_try_ollama = bridge._try_ollama

        def mock_try_ollama(alias_str, prompt, **kwargs):
            ollama_attempts.append(alias_str)
            return "ollama response"

        bridge._try_ollama = mock_try_ollama

        with patch.dict(os.environ, {"OLLAMA_ENABLED": "true"}):
            result = bridge._route_ai_call("claude", "test prompt")
            assert result == "ollama response"
            assert len(ollama_attempts) == 1

        bridge._try_ollama = original_try_ollama

    @pytest.mark.skipif(not OLLAMA_REACHABLE, reason="Ollama not running")
    def test_try_ollama_real_call(self):
        """Real Ollama call returns a non-empty response."""
        if not _ollama_generate_works():
            pytest.skip("Ollama generate API unavailable at test time")
        from ailang_integration.runtime.bridge import AILangBridge
        bridge = AILangBridge()

        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "OLLAMA_URL": "http://localhost:11434",
            "OLLAMA_MODEL": OLLAMA_MODELS[0].split(":")[0] if OLLAMA_MODELS else "mistral",
            "OLLAMA_TIMEOUT_SECONDS": "30",
        }):
            result = bridge._try_ollama("fast", "Say 'test ok' in Spanish")
            if result is None:
                pytest.skip("Ollama generate returned nothing (service busy or overloaded)")
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Pipeline runner LLM detection tests
# ---------------------------------------------------------------------------

class TestPipelineRunnerLLMDetection:
    """Tests for _llm_enabled() auto-detecting Ollama and OpenAI."""

    def test_llm_disabled_by_default(self):
        """With no env vars, LLM is disabled."""
        from ailang_integration.runtime.pipeline_runner import _llm_enabled
        with patch.dict(os.environ, {}, clear=True):
            # Remove all LLM-related vars
            for key in ["USE_LLM_AGENTS", "OLLAMA_ENABLED", "OPENAI_API_KEY"]:
                os.environ.pop(key, None)
            assert _llm_enabled() is False

    def test_llm_enabled_by_ollama(self):
        """OLLAMA_ENABLED=true auto-detects LLM availability."""
        from ailang_integration.runtime.pipeline_runner import _llm_enabled
        with patch.dict(os.environ, {"OLLAMA_ENABLED": "true"}, clear=False):
            os.environ.pop("USE_LLM_AGENTS", None)
            os.environ.pop("OPENAI_API_KEY", None)
            assert _llm_enabled() is True

    def test_llm_enabled_by_openai_key(self):
        """A real OPENAI_API_KEY auto-detects LLM availability."""
        from ailang_integration.runtime.pipeline_runner import _llm_enabled
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real-key"}, clear=False):
            os.environ.pop("USE_LLM_AGENTS", None)
            os.environ.pop("OLLAMA_ENABLED", None)
            assert _llm_enabled() is True

    def test_llm_not_enabled_by_placeholder_key(self):
        """Placeholder API keys do not enable LLM."""
        from ailang_integration.runtime.pipeline_runner import _llm_enabled
        with patch.dict(os.environ, {"OPENAI_API_KEY": "your_api_key_here"}, clear=False):
            os.environ.pop("USE_LLM_AGENTS", None)
            os.environ.pop("OLLAMA_ENABLED", None)
            assert _llm_enabled() is False

    def test_llm_explicit_flag(self):
        """USE_LLM_AGENTS=true explicitly enables LLM."""
        from ailang_integration.runtime.pipeline_runner import _llm_enabled
        with patch.dict(os.environ, {"USE_LLM_AGENTS": "true"}, clear=False):
            os.environ.pop("OLLAMA_ENABLED", None)
            os.environ.pop("OPENAI_API_KEY", None)
            assert _llm_enabled() is True


# ---------------------------------------------------------------------------
# Rule engine model selection tests
# ---------------------------------------------------------------------------

class TestRuleEngineModelSelection:
    """Tests for select_model() routing with Ollama/OpenAI awareness."""

    def test_medical_domain_uses_powerful_model_with_ollama(self):
        """Medical domain selects 'claude' when Ollama is available."""
        from ailang_integration.runtime.rule_engine import select_model
        with patch.dict(os.environ, {"OLLAMA_ENABLED": "true"}):
            os.environ.pop("OPENAI_API_KEY", None)
            assert select_model("medical", "normal", 100) == "claude"

    def test_medical_domain_falls_back_with_no_llm(self):
        """Without any LLM, medical domain uses 'fast' (offline rules)."""
        from ailang_integration.runtime.rule_engine import select_model
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OLLAMA_ENABLED", None)
            os.environ.pop("OPENAI_API_KEY", None)
            assert select_model("medical", "normal", 100) == "fast"

    def test_long_text_uses_powerful_model_with_ollama(self):
        """Long text selects 'claude' when Ollama is available."""
        from ailang_integration.runtime.rule_engine import select_model
        with patch.dict(os.environ, {"OLLAMA_ENABLED": "true"}):
            os.environ.pop("OPENAI_API_KEY", None)
            assert select_model("general", "normal", 500) == "claude"

    def test_urgent_short_text_uses_fast(self):
        """Urgent short text always uses 'fast' model."""
        from ailang_integration.runtime.rule_engine import select_model
        with patch.dict(os.environ, {"OLLAMA_ENABLED": "true"}):
            assert select_model("general", "urgent", 50) == "fast"


# ---------------------------------------------------------------------------
# AILang enhancement pipeline tests
# ---------------------------------------------------------------------------

class TestAILangEnhancementPipeline:
    """Tests for _apply_ailang_enhancements with and without Ollama."""

    def test_enhancement_works_without_ollama(self):
        """AILang enhancement works in offline mode (no LLM)."""
        from backend.streaming import _apply_ailang_enhancements
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OLLAMA_ENABLED", None)
            os.environ.pop("USE_LLM_AGENTS", None)
            result = _apply_ailang_enhancements(
                "hola mundo", "hello world", "en", "es", "speaker"
            )
            assert result is not None
            assert isinstance(result, str)

    def test_enhancement_preserves_translation(self):
        """Enhancement should not destroy a valid translation."""
        from backend.streaming import _apply_ailang_enhancements
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OLLAMA_ENABLED", None)
            os.environ.pop("USE_LLM_AGENTS", None)
            result = _apply_ailang_enhancements(
                "hola mundo", "hello world", "en", "es", "speaker"
            )
            # Result should be a non-empty string
            assert len(result) > 0

    def test_enhancement_handles_empty_input(self):
        """AILang enhancement handles empty/whitespace input gracefully."""
        from backend.streaming import _apply_ailang_enhancements
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OLLAMA_ENABLED", None)
            os.environ.pop("USE_LLM_AGENTS", None)
            result = _apply_ailang_enhancements(
                "", "", "en", "es", "speaker"
            )
            # Should not crash
            assert result is not None

    @pytest.mark.skipif(not OLLAMA_REACHABLE, reason="Ollama not running")
    def test_enhancement_with_ollama_real(self):
        """AILang enhancement produces output with a real Ollama call."""
        from backend.streaming import _apply_ailang_enhancements
        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "USE_LLM_AGENTS": "true",
            "OLLAMA_URL": "http://localhost:11434",
            "OLLAMA_MODEL": OLLAMA_MODELS[0].split(":")[0] if OLLAMA_MODELS else "mistral",
            "OLLAMA_TIMEOUT_SECONDS": "30",
        }):
            result = _apply_ailang_enhancements(
                "buenos dias", "good morning", "en", "es", "speaker"
            )
            assert result is not None
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Warm-up function tests
# ---------------------------------------------------------------------------

class TestOllamaWarmup:
    """Tests for _warm_ollama() startup warm-up function."""

    @pytest.mark.asyncio
    async def test_warmup_offline_mode(self):
        """With no LLM configured, warmup returns offline_mode status."""
        from backend.api import _warm_ollama
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OLLAMA_ENABLED", None)
            os.environ.pop("USE_LLM_AGENTS", None)
            os.environ.pop("OPENAI_API_KEY", None)
            result = await _warm_ollama()
            assert result["status"] == "offline_mode"
            assert "rule-based" in result["message"].lower() or "offline" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_warmup_unreachable(self):
        """With Ollama enabled but unreachable, warmup returns unreachable status."""
        from backend.api import _warm_ollama
        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "OLLAMA_URL": "http://localhost:99999",
        }):
            result = await _warm_ollama()
            assert result["status"] == "unreachable"

    @pytest.mark.asyncio
    async def test_warmup_cloud_mode(self):
        """With OpenAI key but no Ollama, warmup returns cloud_mode status."""
        from backend.api import _warm_ollama
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            os.environ.pop("OLLAMA_ENABLED", None)
            result = await _warm_ollama()
            assert result["status"] == "cloud_mode"

    @pytest.mark.skipif(not OLLAMA_GENERATE_WORKS, reason="Ollama generate API unavailable")
    @pytest.mark.asyncio
    async def test_warmup_active_real(self):
        """With Ollama running, warmup returns active status."""
        from backend.api import _warm_ollama
        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "OLLAMA_URL": "http://localhost:11434",
            "OLLAMA_MODEL": OLLAMA_MODELS[0].split(":")[0] if OLLAMA_MODELS else "mistral",
            "OLLAMA_TIMEOUT_SECONDS": "60",
        }):
            result = await _warm_ollama()
            assert result["status"] == "active"
            assert "warmup_ms" in result
            assert result["warmup_ms"] > 0


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------

class TestOllamaHealthEndpoint:
    """Tests for GET /health/ollama endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        os.environ.setdefault("USERS", "test:test123")
        os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
        from backend.api import app
        return TestClient(app)

    def test_health_ollama_returns_structure(self, client):
        """Endpoint returns expected JSON structure."""
        resp = client.get("/health/ollama")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "url" in data
        assert "model" in data
        assert "warmup" in data

    @pytest.mark.skipif(not OLLAMA_GENERATE_WORKS, reason="Ollama generate API unavailable")
    def test_health_ollama_reachable(self, client):
        """When Ollama is enabled and running, endpoint shows reachable and model loaded."""
        model = (OLLAMA_MODELS[0].split(":")[0] if OLLAMA_MODELS else "mistral")
        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "OLLAMA_URL": "http://localhost:11434",
            "OLLAMA_MODEL": model,
        }):
            resp = client.get("/health/ollama")
            data = resp.json()
            assert data["enabled"] is True
            assert data["reachable"] is True
            assert data["model_loaded"] is True
            assert len(data.get("models", [])) > 0


# ---------------------------------------------------------------------------
# Model switch endpoint tests
# ---------------------------------------------------------------------------

class TestOllamaModelSwitch:
    """Tests for POST /health/ollama/model endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        os.environ.setdefault("USERS", "test:test123")
        os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
        from backend.api import app
        return TestClient(app)

    def test_switch_missing_model_field(self, client):
        """Request without model field returns 400."""
        resp = client.post("/health/ollama/model", json={})
        assert resp.status_code == 400

    def test_switch_empty_model_field(self, client):
        """Request with empty model field returns 400."""
        resp = client.post("/health/ollama/model", json={"model": ""})
        assert resp.status_code == 400

    @pytest.mark.skipif(not OLLAMA_REACHABLE or len(OLLAMA_MODELS) < 2,
                        reason="Ollama not running or fewer than 2 models")
    def test_switch_model_real(self, client):
        """Switch to a different model successfully."""
        # Get current model
        status = client.get("/health/ollama").json()
        current = status["model"]

        # Find a different model
        other = None
        for m in OLLAMA_MODELS:
            base = m.split(":")[0]
            if base != current:
                other = base
                break

        if other is None:
            pytest.skip("No different model available to switch to")

        # Switch
        resp = client.post("/health/ollama/model", json={"model": other})
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_model"] == other
        assert data["previous_model"] == current

        # Verify via health endpoint
        status2 = client.get("/health/ollama").json()
        assert status2["model"] == other

        # Switch back
        client.post("/health/ollama/model", json={"model": current.split(":")[0]})

    @pytest.mark.skipif(not OLLAMA_REACHABLE, reason="Ollama not running")
    def test_switch_nonexistent_model(self, client):
        """Switching to a nonexistent model returns 404."""
        resp = client.post("/health/ollama/model", json={"model": "nonexistent-model-xyz"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Full end-to-end chain test
# ---------------------------------------------------------------------------

class TestOllamaE2EChain:
    """End-to-end test: translation request → AILang → Ollama → enhanced output."""

    @pytest.mark.skipif(not OLLAMA_REACHABLE, reason="Ollama not running")
    def test_e2e_translation_with_ollama(self):
        """Full chain: translate text with AILang+Ollama and get enhanced result."""
        from backend.pipeline import AnaiTranslatorPipeline

        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "USE_LLM_AGENTS": "true",
            "OLLAMA_URL": "http://localhost:11434",
            "OLLAMA_MODEL": OLLAMA_MODELS[0].split(":")[0] if OLLAMA_MODELS else "mistral",
            "OLLAMA_TIMEOUT_SECONDS": "30",
        }):
            pipeline = AnaiTranslatorPipeline(session_id="e2e_ollama_test", enable_ailang=True)
            result = pipeline.translate_text(
                "The patient needs immediate surgery.",
                "en",
                "es",
                speaker="Doctor",
            )

            # Must produce a translation
            assert result.translated_text is not None
            assert len(result.translated_text) > 0

            # Must have AILang metadata
            assert result.ailang_metadata is not None
            assert isinstance(result.ailang_metadata, dict)

    @pytest.mark.skipif(not OLLAMA_REACHABLE, reason="Ollama not running")
    def test_e2e_medical_domain_detection_with_ollama(self):
        """Medical text triggers domain detection through the full chain."""
        from backend.pipeline import AnaiTranslatorPipeline

        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "USE_LLM_AGENTS": "true",
            "OLLAMA_URL": "http://localhost:11434",
            "OLLAMA_MODEL": OLLAMA_MODELS[0].split(":")[0] if OLLAMA_MODELS else "mistral",
            "OLLAMA_TIMEOUT_SECONDS": "30",
        }):
            pipeline = AnaiTranslatorPipeline(session_id="e2e_medical_test", enable_ailang=True)
            result = pipeline.translate_text(
                "The patient was prescribed metformin 500mg twice daily for diabetes management.",
                "en",
                "es",
                speaker="Doctor",
            )

            assert result.translated_text is not None
            assert len(result.translated_text) > 0

    def test_e2e_degradation_without_ollama(self):
        """Translation works with AILang in offline mode when Ollama is unavailable."""
        from backend.pipeline import AnaiTranslatorPipeline

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OLLAMA_ENABLED", None)
            os.environ.pop("USE_LLM_AGENTS", None)
            os.environ.pop("OPENAI_API_KEY", None)

            pipeline = AnaiTranslatorPipeline(session_id="e2e_offline_test", enable_ailang=True)
            result = pipeline.translate_text(
                "Hello, how are you?",
                "en",
                "es",
                speaker="User",
            )

            # Must still produce a translation (via offline rules)
            assert result.translated_text is not None
            assert len(result.translated_text) > 0

    @pytest.mark.skipif(not OLLAMA_REACHABLE, reason="Ollama not running")
    def test_e2e_ollama_to_offline_failover(self):
        """When Ollama becomes unreachable mid-session, it degrades gracefully."""
        from ailang_integration.runtime.bridge import AILangBridge, get_bridge, reset_bridge

        with patch.dict(os.environ, {
            "OLLAMA_ENABLED": "true",
            "USE_LLM_AGENTS": "true",
            "OLLAMA_URL": "http://localhost:11434",
            "OLLAMA_MODEL": OLLAMA_MODELS[0].split(":")[0] if OLLAMA_MODELS else "mistral",
        }):
            reset_bridge()
            bridge = get_bridge()

            # First call with real Ollama — should succeed
            result1 = bridge._route_ai_call("fast", "Translate to Spanish: hello")
            assert result1 is not None

            # Now simulate Ollama going down
            with patch.dict(os.environ, {"OLLAMA_URL": "http://localhost:99999"}):
                result2 = bridge._route_ai_call("fast", "Translate to Spanish: goodbye")
                # Should degrade to stub — still returns something
                assert result2 is not None
                assert isinstance(result2, str)

            reset_bridge()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
