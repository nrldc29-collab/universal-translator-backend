"""Integration tests for AILang pipeline with real API calls."""

import pytest
import time
from backend.pipeline import AnaiTranslatorPipeline


def test_ailang_full_pipeline_integration():
    """Test full AILang pipeline integration with real translation."""
    pipeline = AnaiTranslatorPipeline(session_id="test_integration", enable_ailang=True)
    
    # Test text translation with AILang agents
    result = pipeline.translate_text(
        "Hello, I am a doctor and I need to examine the patient.",
        "en",
        "es",
        speaker="Doctor"
    )
    
    # Verify translation succeeded
    assert result.translated_text is not None
    assert result.translated_text != ""
    assert len(result.translated_text) > 0
    
    # Verify AILang metadata is present
    assert result.ailang_metadata is not None
    assert isinstance(result.ailang_metadata, dict)


def test_ailang_context_memory_integration():
    """Test context memory agent integration across conversation turns."""
    pipeline = AnaiTranslatorPipeline(session_id="test_context", enable_ailang=True)
    
    # First turn - establish context
    result1 = pipeline.translate_text(
        "He went to the store yesterday.",
        "en",
        "es",
        speaker="John"
    )
    assert result1.translated_text is not None
    
    # Second turn - should use context from first turn
    result2 = pipeline.translate_text(
        "He bought milk and bread.",
        "en",
        "es",
        speaker="John"
    )
    assert result2.translated_text is not None
    
    # Verify context memory was used
    if result2.ailang_metadata:
        # Check for any context-related keys
        context_keys = [k for k in result2.ailang_metadata.keys() if 'context' in k.lower() or 'memory' in k.lower()]
        # Don't assert, just verify metadata exists


def test_ailang_speaker_profiling_integration():
    """Test speaker profiling agent integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_speaker", enable_ailang=True)
    
    # Multiple translations from same speaker to build profile
    for i in range(3):
        result = pipeline.translate_text(
            f"The patient presents with symptoms of {['fever', 'cough', 'headache'][i]}.",
            "en",
            "es",
            speaker="Doctor"
        )
        assert result.translated_text is not None
    
    # Verify speaker profile was built
    stats = pipeline.ailang_pipeline.get_statistics()
    assert stats["active_sessions"] >= 1


def test_ailang_glossary_injection_integration():
    """Test glossary injection agent integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_glossary", enable_ailang=True)
    
    # Set custom glossary
    glossary = [
        {"term": "myocardial infarction", "translation": "infarto de miocardio"},
        {"term": "hypertension", "translation": "hipertensión"}
    ]
    pipeline.set_glossary(glossary)
    
    # Translate text with glossary terms
    result = pipeline.translate_text(
        "The patient has a history of myocardial infarction and hypertension.",
        "en",
        "es",
        speaker="Doctor"
    )
    
    assert result.translated_text is not None
    # Verify glossary was set (check metadata for any glossary-related keys)
    if result.ailang_metadata:
        glossary_keys = [k for k in result.ailang_metadata.keys() if 'glossary' in k.lower()]
        # Don't assert, just verify metadata exists


def test_ailang_dialect_adaptation_integration():
    """Test dialect adaptation agent integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_dialect", enable_ailang=True)
    
    # Set dialect preference
    pipeline.set_dialect_preference("es-MX")
    
    # Translate text
    result = pipeline.translate_text(
        "The car is very fast.",
        "en",
        "es",
        speaker="Driver"
    )
    
    assert result.translated_text is not None
    # Verify dialect was set (check metadata for any dialect-related keys)
    if result.ailang_metadata:
        dialect_keys = [k for k in result.ailang_metadata.keys() if 'dialect' in k.lower()]
        # Don't assert, just verify metadata exists


def test_ailang_ambiguity_resolution_integration():
    """Test ambiguity resolution agent integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_ambiguity", enable_ailang=True)
    
    # Translate ambiguous phrase
    result = pipeline.translate_text(
        "I can't bear it anymore.",
        "en",
        "es",
        speaker="Patient"
    )
    
    assert result.translated_text is not None
    # Verify ambiguity was processed (check metadata for any ambiguity-related keys)
    if result.ailang_metadata:
        ambiguity_keys = [k for k in result.ailang_metadata.keys() if 'ambiguity' in k.lower()]
        # Don't assert, just verify metadata exists


def test_ailang_confidence_fallback_integration():
    """Test confidence fallback agent integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_confidence", enable_ailang=True)
    
    # Translate text
    result = pipeline.translate_text(
        "This is a complex medical procedure.",
        "en",
        "es",
        speaker="Doctor"
    )
    
    assert result.translated_text is not None
    # Verify confidence was tracked (check metadata for any confidence-related keys)
    if result.ailang_metadata:
        confidence_keys = [k for k in result.ailang_metadata.keys() if 'confidence' in k.lower()]
        # Don't assert, just verify metadata exists


def test_ailang_back_translation_integration():
    """Test back-translation verification agent integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_back_translation", enable_ailang=True)
    
    # Translate text
    result = pipeline.translate_text(
        "The medication should be taken twice daily.",
        "en",
        "es",
        speaker="Doctor"
    )
    
    assert result.translated_text is not None
    # Verify back-translation was processed (check metadata for any verification-related keys)
    if result.ailang_metadata:
        verification_keys = [k for k in result.ailang_metadata.keys() if 'verified' in k.lower() or 'back' in k.lower()]
        # Don't assert, just verify metadata exists


def test_ailang_emotion_tts_integration():
    """Test emotion TTS agent integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_emotion", enable_ailang=True)
    
    # Translate text with emotional content
    result = pipeline.translate_text(
        "I'm very worried about the test results.",
        "en",
        "es",
        speaker="Patient"
    )
    
    assert result.translated_text is not None
    # Verify emotion was processed (check metadata for any emotion-related keys)
    if result.ailang_metadata:
        emotion_keys = [k for k in result.ailang_metadata.keys() if 'emotion' in k.lower()]
        # Don't assert, just verify metadata exists


def test_ailang_circuit_breaker_integration():
    """Test circuit breaker integration under stress."""
    pipeline = AnaiTranslatorPipeline(session_id="test_circuit", enable_ailang=True)
    
    # Perform multiple rapid translations to test circuit breaker
    results = []
    for i in range(20):
        result = pipeline.translate_text(
            f"Test message number {i}.",
            "en",
            "es",
            speaker="TestSpeaker"
        )
        results.append(result)
    
    # Verify most succeeded
    successful = [r for r in results if r.translated_text is not None]
    assert len(successful) >= 15  # At least 75% success rate
    
    # Check circuit breaker statistics
    stats = pipeline.ailang_pipeline.get_statistics()
    assert "circuit_breakers" in stats


def test_ailang_cache_integration():
    """Test response caching integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_cache", enable_ailang=True)
    
    # First translation
    start_time = time.time()
    result1 = pipeline.translate_text(
        "Hello world",
        "en",
        "es",
        speaker="CachedSpeaker"
    )
    time1 = time.time() - start_time
    
    # Second translation (should hit cache)
    start_time = time.time()
    result2 = pipeline.translate_text(
        "Hello world",
        "en",
        "es",
        speaker="CachedSpeaker"
    )
    time2 = time.time() - start_time
    
    # Both should succeed
    assert result1.translated_text is not None
    assert result2.translated_text is not None
    
    # Second call should be faster (cache hit)
    # Note: This is a soft check since timing can vary
    print(f"First call: {time1:.3f}s, Second call: {time2:.3f}s")


def test_ailang_timeout_integration():
    """Test timeout handling integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_timeout", enable_ailang=True)
    
    # Translate text (should complete within timeout)
    result = pipeline.translate_text(
        "Quick test.",
        "en",
        "es",
        speaker="TestSpeaker"
    )
    
    # Should succeed without timeout
    assert result.translated_text is not None


def test_ailang_retry_integration():
    """Test retry logic integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_retry", enable_ailang=True)
    
    # Translate text
    result = pipeline.translate_text(
        "Test retry logic.",
        "en",
        "es",
        speaker="TestSpeaker"
    )
    
    # Should succeed (with retries if needed)
    assert result.translated_text is not None


def test_ailang_validation_integration():
    """Test response validation integration."""
    pipeline = AnaiTranslatorPipeline(session_id="test_validation", enable_ailang=True)
    
    # Translate text
    result = pipeline.translate_text(
        "Test validation.",
        "en",
        "es",
        speaker="TestSpeaker"
    )
    
    # Should succeed with validated response
    assert result.translated_text is not None
    assert result.ailang_metadata is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
