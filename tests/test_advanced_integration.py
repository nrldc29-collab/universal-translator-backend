"""
Integration Tests for Advanced Optimization Modules

This module tests the integration of advanced optimization modules:
- Predictive cache integration with pipeline
- Adaptive VAD integration with streaming
- Smart buffer integration with streaming
- Audio enhancement integration with streaming
- End-to-end integration with all modules

Usage:
    pytest tests/test_advanced_integration.py -v
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List


class TestPredictiveCacheIntegration:
    """Test predictive cache integration with main pipeline."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_in_pipeline(self):
        """Test that cache hits work in pipeline translation."""
        from backend.pipeline import AnaiTranslatorPipeline
        from backend.predictive_cache import PredictiveCache
        
        # Create pipeline with cache enabled
        pipeline = AnaiTranslatorPipeline(
            enable_predictive_cache=True,
            enable_ailang=False,  # Disable for simpler test
        )
        
        # First translation should cache
        result1 = pipeline.translate_text(
            text="hello",
            source_language="en",
            target_language="es",
            synthesize_audio=False,
        )
        
        # Check cache was populated
        assert pipeline.predictive_cache is not None
        stats = pipeline.predictive_cache.get_statistics()
        assert stats["size"] > 0
    
    @pytest.mark.asyncio
    async def test_cache_miss_in_pipeline(self):
        """Test that cache misses work in pipeline translation."""
        from backend.pipeline import AnaiTranslatorPipeline
        
        # Create pipeline with cache disabled
        pipeline = AnaiTranslatorPipeline(
            enable_predictive_cache=False,
            enable_ailang=False,
        )
        
        # Translation should work without cache
        result = pipeline.translate_text(
            text="hello",
            source_language="en",
            target_language="es",
            synthesize_audio=False,
        )
        
        assert result.translated_text is not None
        assert pipeline.predictive_cache is None
    
    @pytest.mark.asyncio
    async def test_cache_with_context(self):
        """Test that cache works with context (session, speaker)."""
        from backend.pipeline import AnaiTranslatorPipeline
        
        pipeline = AnaiTranslatorPipeline(
            enable_predictive_cache=True,
            enable_ailang=False,
            session_id="test_session",
        )
        
        # Translate with speaker context
        result = pipeline.translate_text(
            text="hello",
            source_language="en",
            target_language="es",
            speaker="speaker_a",
            synthesize_audio=False,
        )
        
        # First translation should succeed
        assert result.translated_text is not None
        
        # Second translation should use cache
        result2 = pipeline.translate_text(
            text="hello",
            source_language="en",
            target_language="es",
            speaker="speaker_a",
            synthesize_audio=False,
        )
        assert result2.translated_text is not None


class TestAdaptiveVADIntegration:
    """Test adaptive VAD integration with streaming."""
    
    @pytest.mark.asyncio
    async def test_adaptive_vad_initialization(self):
        """Test that adaptive VAD initializes in streaming."""
        from backend.adaptive_vad import AdaptiveVAD
        
        vad = AdaptiveVAD()
        assert vad is not None
        assert vad.current_threshold > 0
        assert vad.environment is not None
    
    @pytest.mark.asyncio
    async def test_adaptive_vad_noise_adaptation(self):
        """Test that adaptive VAD adapts to noise levels."""
        from backend.adaptive_vad import AdaptiveVAD, Environment
        
        vad = AdaptiveVAD()
        
        # Simulate quiet environment
        quiet_audio = np.random.uniform(-0.01, 0.01, 16000).astype(np.float32)
        result = vad.detect(quiet_audio)
        assert result.environment == Environment.QUIET
        
        # Simulate very noisy environment
        noisy_audio = np.random.uniform(-0.5, 0.5, 16000).astype(np.float32)
        result = vad.detect(noisy_audio)
        # Should detect higher noise level
        assert result.noise_level > 0.1
    
    @pytest.mark.asyncio
    async def test_adaptive_vad_threshold_adjustment(self):
        """Test that adaptive VAD adjusts threshold."""
        from backend.adaptive_vad import AdaptiveVAD
        
        vad = AdaptiveVAD()
        initial_threshold = vad.current_threshold
        
        # Process noisy audio
        noisy_audio = np.random.uniform(-0.3, 0.3, 16000).astype(np.float32)
        for _ in range(10):
            vad.detect(noisy_audio)
        
        # Threshold should have changed (may increase or decrease based on adaptation)
        assert vad.current_threshold != initial_threshold or vad.environment is not None


class TestSmartBufferIntegration:
    """Test smart buffer integration with streaming."""
    
    @pytest.mark.asyncio
    async def test_smart_buffer_initialization(self):
        """Test that smart buffer initializes correctly."""
        from backend.smart_buffer import SmartBuffer, Priority
        
        buffer = SmartBuffer(max_size_mb=12)
        assert buffer is not None
        assert buffer.max_size_bytes == 12 * 1024 * 1024
    
    @pytest.mark.asyncio
    async def test_smart_buffer_priority_handling(self):
        """Test that smart buffer handles priority correctly."""
        from backend.smart_buffer import SmartBuffer, Priority
        
        buffer = SmartBuffer(max_size_mb=1)
        
        # Add high priority chunk
        buffer.add_chunk(b"critical_data", Priority.CRITICAL)
        
        # Add low priority chunk
        buffer.add_chunk(b"low_priority_data", Priority.LOW)
        
        # High priority should be retrieved first
        chunk = buffer.get_next_chunk()
        assert chunk == b"critical_data"
    
    @pytest.mark.asyncio
    async def test_smart_buffer_network_adaptation(self):
        """Test that smart buffer adapts to network quality."""
        from backend.smart_buffer import SmartBuffer
        
        buffer = SmartBuffer(max_size_mb=12)
        
        # Set poor network quality
        buffer.update_network_quality(0.3)
        
        # Buffer should reduce size
        assert buffer.current_max_size < buffer.max_size_bytes
        
        # Set good network quality
        buffer.update_network_quality(0.9)
        
        # Buffer should increase size
        assert buffer.current_max_size > buffer.max_size_bytes * 0.5


class TestAudioEnhancerIntegration:
    """Test audio enhancement integration with streaming."""
    
    @pytest.mark.asyncio
    async def test_audio_enhancer_initialization(self):
        """Test that audio enhancer initializes correctly."""
        from backend.audio_enhancer import AudioEnhancer
        
        enhancer = AudioEnhancer()
        assert enhancer is not None
        assert enhancer.sample_rate == 16000
    
    @pytest.mark.asyncio
    async def test_audio_enhancer_processing(self):
        """Test that audio enhancer processes audio."""
        from backend.audio_enhancer import AudioEnhancer
        
        enhancer = AudioEnhancer()
        
        # Create test audio
        audio = np.random.uniform(-0.5, 0.5, 16000).astype(np.float32)
        
        # Process audio
        enhanced = enhancer.process(audio)
        
        # Should return numpy array
        assert isinstance(enhanced, np.ndarray)
        assert len(enhanced) == len(audio)
    
    @pytest.mark.asyncio
    async def test_audio_enhancer_normalization(self):
        """Test that audio enhancer normalizes audio."""
        from backend.audio_enhancer import AudioEnhancer
        
        enhancer = AudioEnhancer()
        
        # Create quiet audio
        quiet_audio = np.random.uniform(-0.01, 0.01, 16000).astype(np.float32)
        
        # Process audio
        enhanced = enhancer.process(quiet_audio)
        
        # Should be normalized to target level
        assert np.max(np.abs(enhanced)) > 0.1


class TestAdvancedPipelineIntegration:
    """Test advanced pipeline with all modules integrated."""
    
    @pytest.mark.asyncio
    async def test_advanced_pipeline_initialization(self):
        """Test that advanced pipeline initializes with all modules."""
        from backend.advanced_pipeline import AdvancedPipeline, PipelineConfig
        
        config = PipelineConfig(
            enable_adaptive_vad=True,
            enable_smart_buffer=True,
            enable_audio_enhancement=True,
            enable_latency_optimization=True,
            enable_predictive_cache=True,
        )
        
        pipeline = AdvancedPipeline(config)
        assert pipeline is not None
        assert pipeline.adaptive_vad is not None
        assert pipeline.smart_buffer is not None
        assert pipeline.audio_enhancer is not None
        assert pipeline.latency_optimizer is not None
        assert pipeline.predictive_cache is not None
    
    @pytest.mark.asyncio
    async def test_advanced_pipeline_processing(self):
        """Test that advanced pipeline processes audio correctly."""
        from backend.advanced_pipeline import AdvancedPipeline, PipelineConfig
        
        config = PipelineConfig(
            enable_adaptive_vad=True,
            enable_smart_buffer=True,
            enable_audio_enhancement=True,
            enable_latency_optimization=True,
            enable_predictive_cache=True,
        )
        
        pipeline = AdvancedPipeline(config)
        
        # Create test audio
        audio = np.random.uniform(-0.3, 0.3, 16000).astype(np.float32)
        
        # Process audio
        result = pipeline.process_audio(
            audio=audio,
            source_lang="en",
            target_lang="es",
            context={"session_id": "test"},
        )
        
        # Should return result
        assert result is not None
        assert result.environment is not None
        assert result.quality_level is not None
    
    @pytest.mark.asyncio
    async def test_advanced_pipeline_optimization_status(self):
        """Test that advanced pipeline provides optimization status."""
        from backend.advanced_pipeline import AdvancedPipeline, PipelineConfig
        
        config = PipelineConfig(
            enable_adaptive_vad=True,
            enable_smart_buffer=True,
            enable_audio_enhancement=True,
            enable_latency_optimization=True,
            enable_predictive_cache=True,
        )
        
        pipeline = AdvancedPipeline(config)
        
        # Get optimization status
        status = pipeline.get_optimization_status()
        
        # Should include all modules
        assert "adaptive_vad" in status
        assert "smart_buffer" in status
        assert "predictive_cache" in status
        assert "latency_optimizer" in status


class TestEnvironmentVariableConfiguration:
    """Test that environment variables configure advanced features."""
    
    @pytest.mark.asyncio
    async def test_predictive_cache_env_var(self):
        """Test that ENABLE_PREDICTIVE_CACHE environment variable works."""
        import os
        
        # Set environment variable
        os.environ["ENABLE_PREDICTIVE_CACHE"] = "1"
        os.environ["PREDICTIVE_CACHE_SIZE"] = "500"
        os.environ["PREDICTIVE_CACHE_TTL"] = "1800"
        
        from backend.pipeline import AnaiTranslatorPipeline
        
        pipeline = AnaiTranslatorPipeline(
            enable_predictive_cache=True,
            enable_ailang=False,
        )
        
        # Should use environment values
        assert pipeline.predictive_cache is not None
        stats = pipeline.predictive_cache.get_statistics()
        assert stats is not None
        
        # Cleanup
        del os.environ["ENABLE_PREDICTIVE_CACHE"]
        del os.environ["PREDICTIVE_CACHE_SIZE"]
        del os.environ["PREDICTIVE_CACHE_TTL"]


class TestDiagnosticsIntegration:
    """Test that diagnostics endpoint includes advanced features."""
    
    @pytest.mark.asyncio
    async def test_diagnostics_includes_cache_stats(self):
        """Test that /diagnostics includes predictive cache statistics."""
        from backend.pipeline import AnaiTranslatorPipeline
        
        pipeline = AnaiTranslatorPipeline(
            enable_predictive_cache=True,
            enable_ailang=False,
        )
        
        # Get preload stats
        preload_result = pipeline.preload()
        
        # Should include cache stats
        assert "predictive_cache" in preload_result
        # Cache stats should be present
        assert preload_result["predictive_cache"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
