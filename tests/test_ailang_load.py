"""Load test for AILang pipeline to verify stability under stress."""

import pytest
import time
import threading
from backend.pipeline import AnaiTranslatorPipeline


def test_ailang_pipeline_single_translation():
    """Test single translation with AILang pipeline."""
    pipeline = AnaiTranslatorPipeline(session_id="test_load", enable_ailang=True)
    result = pipeline.translate_text("Hello, how are you today?", "en", "es", speaker="Doctor")
    
    assert result.translated_text is not None
    assert result.translated_text != ""
    assert result.ailang_metadata is not None
    assert "analysis" in result.ailang_metadata


def test_ailang_pipeline_concurrent_translations():
    """Test concurrent translations to verify thread safety."""
    pipeline = AnaiTranslatorPipeline(session_id="test_concurrent", enable_ailang=True)
    results = []
    errors = []
    
    def translate_worker(worker_id):
        try:
            result = pipeline.translate_text(f"Hello from worker {worker_id}", "en", "es", speaker=f"Speaker{worker_id}")
            results.append((worker_id, result))
        except Exception as e:
            errors.append((worker_id, e))
    
    # Run 10 concurrent translations
    threads = []
    for i in range(10):
        thread = threading.Thread(target=translate_worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    # Verify all translations succeeded
    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(results) == 10, f"Expected 10 results, got {len(results)}"
    
    # Verify all results have valid translations
    for worker_id, result in results:
        assert result.translated_text is not None
        assert result.translated_text != ""
        assert result.ailang_metadata is not None


def test_ailang_pipeline_circuit_breaker():
    """Test circuit breaker opens after repeated failures."""
    pipeline = AnaiTranslatorPipeline(session_id="test_circuit", enable_ailang=True)
    
    # Get circuit breaker for an agent
    circuit_breaker = pipeline.ailang_pipeline._circuit_breakers.get("TranslationBrain")
    assert circuit_breaker is not None
    
    # Record multiple failures to trigger circuit breaker
    for _ in range(10):
        circuit_breaker.record_failure()
    
    # Verify circuit breaker is open
    assert circuit_breaker.state.value == "open"
    
    # Verify requests are blocked
    assert not circuit_breaker.allow_request()
    
    # Test recovery after timeout
    circuit_breaker.last_failure_time = time.time() - 70  # Set to past
    assert circuit_breaker.allow_request()  # Should allow after timeout


def test_ailang_pipeline_cache():
    """Test response caching for expensive operations."""
    pipeline = AnaiTranslatorPipeline(session_id="test_cache", enable_ailang=True)
    
    # First call should populate cache
    result1 = pipeline.translate_text("Hello world", "en", "es", speaker="CachedSpeaker")
    
    # Second call with same speaker should hit cache
    result2 = pipeline.translate_text("Hello world", "en", "es", speaker="CachedSpeaker")
    
    # Both should succeed
    assert result1.translated_text is not None
    assert result2.translated_text is not None


def test_ailang_pipeline_agent_enable_disable():
    """Test agent enable/disable functionality."""
    pipeline = AnaiTranslatorPipeline(session_id="test_enable", enable_ailang=True)
    
    # Disable an agent
    pipeline.ailang_pipeline.set_agent_enabled("SpeakerProfilerAgent", False)
    assert not pipeline.ailang_pipeline.is_agent_enabled("SpeakerProfilerAgent")
    
    # Translation should still work without the disabled agent
    result = pipeline.translate_text("Hello", "en", "es", speaker="TestSpeaker")
    assert result.translated_text is not None
    
    # Re-enable the agent
    pipeline.ailang_pipeline.set_agent_enabled("SpeakerProfilerAgent", True)
    assert pipeline.ailang_pipeline.is_agent_enabled("SpeakerProfilerAgent")


def test_ailang_pipeline_statistics():
    """Test statistics collection."""
    pipeline = AnaiTranslatorPipeline(session_id="test_stats", enable_ailang=True)
    
    # Perform some translations
    for i in range(5):
        pipeline.translate_text(f"Test {i}", "en", "es", speaker="StatsSpeaker")
    
    # Get statistics
    stats = pipeline.ailang_pipeline.get_statistics()
    
    # Verify statistics structure
    assert "enabled" in stats
    assert "active_sessions" in stats
    assert "circuit_breakers" in stats
    assert isinstance(stats["circuit_breakers"], dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
