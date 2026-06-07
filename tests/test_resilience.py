"""Resilience and error recovery tests."""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock


class TestCircuitBreaker:
    @pytest.fixture
    def cb(self):
        from backend.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        return CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=3, recovery_timeout=0.5, success_threshold=2, timeout=2.0))

    @pytest.mark.asyncio
    async def test_closed_allows_calls(self, cb):
        from backend.circuit_breaker import CircuitState
        assert cb.state == CircuitState.CLOSED
        result = await cb.call(AsyncMock(return_value="ok"))
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_opens_after_failures(self, cb):
        from backend.circuit_breaker import CircuitState, CircuitBreakerOpenError
        failing = AsyncMock(side_effect=RuntimeError("fail"))
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(failing)
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(failing)

    @pytest.mark.asyncio
    async def test_half_open_recovery(self, cb):
        from backend.circuit_breaker import CircuitState
        failing = AsyncMock(side_effect=RuntimeError("fail"))
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(failing)
        assert cb.state == CircuitState.OPEN
        await asyncio.sleep(0.6)
        succeeding = AsyncMock(return_value="recovered")
        await cb.call(succeeding)
        await cb.call(succeeding)
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self, cb):
        from backend.circuit_breaker import CircuitState
        failing = AsyncMock(side_effect=RuntimeError("fail"))
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(failing)
        await asyncio.sleep(0.6)
        with pytest.raises(RuntimeError):
            await cb.call(failing)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_force_open_close(self, cb):
        from backend.circuit_breaker import CircuitState
        await cb.force_open()
        assert cb.state == CircuitState.OPEN
        await cb.force_close()
        assert cb.state == CircuitState.CLOSED


class TestHybridTranslatorFallback:
    def test_lightweight_exact_match(self):
        from translation.hybrid_translator import HybridTranslator
        t = HybridTranslator()
        assert t.translate("hello", "en", "es") == "hola"
        assert t.get_metrics()["lightweight_hits"] >= 1

    def test_fallback_chain(self):
        from translation.hybrid_translator import HybridTranslator
        t = HybridTranslator()
        t._ollama_enabled = True
        t.ollama._available = False
        t.ollama._last_check = time.monotonic()
        result = t.translate("This is a test sentence", "en", "es")
        assert result
        m = t.get_metrics()
        assert m["ollama_misses"] >= 1

    def test_placeholder_detection(self):
        from translation.hybrid_translator import HybridTranslator
        assert HybridTranslator.is_placeholder_translation("[en->es] hello", "en", "es")
        assert not HybridTranslator.is_placeholder_translation("hola", "en", "es")

    def test_same_language_passthrough(self):
        from translation.hybrid_translator import HybridTranslator
        t = HybridTranslator()
        assert t.translate("hello", "en", "en") == "hello"

    def test_empty_input(self):
        from translation.hybrid_translator import HybridTranslator
        t = HybridTranslator()
        assert t.translate("", "en", "es") == ""
        assert t.translate("   ", "en", "es") == ""

    def test_metrics_tracking(self):
        from translation.hybrid_translator import HybridTranslator
        t = HybridTranslator()
        t.translate("hello", "en", "es")
        m = t.get_metrics()
        assert isinstance(m, dict)
        assert sum(m.values()) >= 1


class TestOllamaTranslator:
    def test_unavailable_when_no_server(self):
        from translation.hybrid_translator import OllamaTranslator
        t = OllamaTranslator()
        t.base_url = "http://localhost:99999"
        assert t.is_available() is False

    def test_cache_hit(self):
        from translation.hybrid_translator import OllamaTranslator
        t = OllamaTranslator()
        t._cache[("en", "es", "hello")] = "hola"
        assert t.translate("hello", "en", "es") == "hola"

    def test_same_language(self):
        from translation.hybrid_translator import OllamaTranslator
        t = OllamaTranslator()
        assert t.translate("hello", "en", "en") == "hello"


class TestLatencyEngine:
    def test_stage_recording(self):
        from backend.latency import LatencyEngine
        le = LatencyEngine()
        le.record_stage("stt", 150.0)
        le.record_stage("stt", 200.0)
        snap = le.snapshot()
        assert snap["stages"]["stt"]["count"] == 2

    def test_pipeline_run(self):
        from backend.latency import LatencyEngine
        le = LatencyEngine()
        le.begin_run("t1", speaker="A")
        le.record_stage("stt", 150.0)
        le.record_stage("translation", 80.0)
        le.record_stage("tts", 200.0)
        run = le.end_run()
        assert run.total_ms == pytest.approx(430.0, abs=1.0)

    def test_percentiles(self):
        from backend.latency import LatencyEngine
        le = LatencyEngine()
        for i in range(100):
            le.record_stage("stt", float(i))
        snap = le.snapshot()
        assert snap["stages"]["stt"]["p50_ms"] == pytest.approx(50.0, abs=2.0)

    def test_health_unknown(self):
        from backend.latency import LatencyEngine
        assert LatencyEngine().health_assessment()["status"] == "unknown"

    def test_health_excellent(self):
        from backend.latency import LatencyEngine
        le = LatencyEngine()
        for _ in range(10):
            le.begin_run("x")
            le.record_stage("stt", 200)
            le.record_stage("translation", 100)
            le.end_run()
        assert le.health_assessment()["status"] in ("excellent", "good")

    def test_legacy_compat(self):
        from backend.latency import LatencyEngine
        le = LatencyEngine()
        le.update(stt=0.15, translate=0.05, tts=0.2)
        assert le.total() > 0


class TestConversationBrainDuplex:
    def test_soft_overlap(self):
        from backend.conversation import ConversationBrain
        brain = ConversationBrain()
        d1 = brain.request_turn("A")
        assert d1.allowed
        d2 = brain.request_turn("B")
        assert d2.allowed
        assert d2.behavior == "overlap"

    def test_turn_shift(self):
        from time import monotonic

        from backend.conversation import ConversationBrain
        brain = ConversationBrain()
        brain.soft_overlap_seconds = 0.0
        brain.request_turn("A")
        brain.active_since = monotonic() - 0.5
        d2 = brain.request_turn("B")
        assert d2.allowed
        assert d2.behavior == "turn_shift"

    def test_playback_interruption(self):
        from backend.conversation import ConversationBrain
        brain = ConversationBrain()
        brain.interruption_grace_seconds = 0.0
        brain.begin_playback("A")
        d = brain.request_turn("B")
        assert d.allowed
        assert d.behavior == "interruption"

    def test_playback_hold(self):
        from backend.conversation import ConversationBrain
        brain = ConversationBrain()
        brain.interruption_grace_seconds = 10.0
        brain.begin_playback("A")
        d = brain.request_turn("B")
        assert not d.allowed
        assert d.behavior == "hold"

    def test_end_turn_clears(self):
        from backend.conversation import ConversationBrain
        brain = ConversationBrain()
        brain.request_turn("A")
        brain.begin_playback("A")
        brain.end_turn("A")
        assert brain.active_speaker is None
        assert brain.playback_owner is None

    def test_semantic_analysis(self):
        from backend.conversation import ConversationBrain
        brain = ConversationBrain()
        ctx = brain.analyze_semantics("A", "Can you help me please?")
        assert ctx["last_intent"] in ("question", "request")

    def test_multi_turn_history(self):
        from backend.conversation import ConversationBrain
        brain = ConversationBrain()
        brain.analyze_semantics("A", "Hello")
        brain.analyze_semantics("B", "Hi there")
        brain.analyze_semantics("A", "How are you?")
        snap = brain.semantic_snapshot()
        assert len(snap["recent_turns"]) == 3


class TestReconnectResilience:
    def test_remote_timeout(self):
        from translation.remote_translator import RemoteTranslator
        t = RemoteTranslator(timeout_seconds=0.001)
        with pytest.raises(RuntimeError):
            t.translate("hello world", "en", "es")

    def test_hybrid_recovers_from_remote_failure(self):
        from translation.hybrid_translator import HybridTranslator
        t = HybridTranslator()
        t._ollama_enabled = False
        t.remote.timeout_seconds = 0.001
        result = t.translate("hello", "en", "es")
        assert result == "hola"

    def test_all_tiers_fail(self):
        from translation.hybrid_translator import HybridTranslator
        t = HybridTranslator()
        t._ollama_enabled = False
        t._marian_enabled = False
        t.remote.timeout_seconds = 0.001
        result = t.translate("The quick brown fox", "en", "es")
        assert "[en->es]" in result

    @pytest.mark.asyncio
    async def test_circuit_breaker_registry(self):
        from backend.circuit_breaker import get_circuit_breaker, reset_all_circuit_breakers, CircuitState
        cb1 = get_circuit_breaker("test_svc_1")
        await cb1.force_open()
        assert cb1.state == CircuitState.OPEN
        await reset_all_circuit_breakers()
        assert cb1.state == CircuitState.CLOSED


class TestStress:
    def test_rapid_translations(self):
        from translation.hybrid_translator import HybridTranslator
        t = HybridTranslator()
        results = [t.translate("hello", "en", "es") for _ in range(100)]
        assert all(r == "hola" for r in results)

    def test_concurrent_metrics(self):
        from translation.hybrid_translator import HybridTranslator
        import threading
        t = HybridTranslator()
        errors = []
        def worker():
            try:
                for _ in range(50):
                    t.translate("hello", "en", "es")
                    t.get_metrics()
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for th in threads: th.start()
        for th in threads: th.join()
        assert len(errors) == 0
        assert t.get_metrics()["lightweight_hits"] >= 200
