"""
Advanced Pipeline Integration

This module integrates all advanced optimization modules into a unified pipeline:
- Adaptive VAD for environmental awareness
- Smart buffering for network conditions
- Audio enhancement for better recognition
- Latency optimization for performance
- Predictive caching for speed

Usage:
    from backend.advanced_pipeline import AdvancedPipeline
    pipeline = AdvancedPipeline()
    result = pipeline.process_audio(audio_chunk, config)
"""

import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass
import time

from backend.adaptive_vad import AdaptiveVAD, Environment
from backend.smart_buffer import SmartBuffer, Priority
from backend.audio_enhancer import AudioEnhancer
from backend.latency_optimizer import LatencyOptimizer, PipelineMetrics, QualityLevel
from backend.predictive_cache import PredictiveCache


@dataclass
class PipelineConfig:
    """Pipeline configuration."""
    enable_adaptive_vad: bool = True
    enable_smart_buffer: bool = True
    enable_audio_enhancement: bool = True
    enable_latency_optimization: bool = True
    enable_predictive_cache: bool = True
    target_latency_ms: float = 1000
    max_latency_ms: float = 2000


@dataclass
class PipelineResult:
    """Pipeline processing result."""
    success: bool
    transcription: Optional[str]
    translation: Optional[str]
    tts_audio: Optional[bytes]
    latency_breakdown: Dict[str, float]
    environment: Environment
    quality_level: QualityLevel
    cache_hit: bool
    processing_time_ms: float


class AdvancedPipeline:
    """Advanced translation pipeline with all optimizations."""
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        
        # Initialize modules
        self.adaptive_vad = AdaptiveVAD() if self.config.enable_adaptive_vad else None
        self.smart_buffer = SmartBuffer() if self.config.enable_smart_buffer else None
        self.audio_enhancer = AudioEnhancer() if self.config.enable_audio_enhancement else None
        self.latency_optimizer = LatencyOptimizer(
            target_latency_ms=self.config.target_latency_ms,
            max_latency_ms=self.config.max_latency_ms,
        ) if self.config.enable_latency_optimization else None
        self.predictive_cache = PredictiveCache() if self.config.enable_predictive_cache else None
        
        # Performance tracking
        self.metrics_history: List[Dict] = []
        
    def process_audio(
        self,
        audio: np.ndarray,
        source_lang: str,
        target_lang: str,
        context: Dict = None,
    ) -> PipelineResult:
        """Process audio through advanced pipeline."""
        start_time = time.time()
        
        # Stage 1: Audio Enhancement
        if self.audio_enhancer:
            audio = self.audio_enhancer.process(audio)
        
        # Stage 2: Adaptive VAD
        environment = Environment.QUIET
        if self.adaptive_vad:
            vad_result = self.adaptive_vad.detect(audio)
            environment = vad_result.environment
            
            if not vad_result.is_speech:
                return PipelineResult(
                    success=False,
                    transcription=None,
                    translation=None,
                    tts_audio=None,
                    latency_breakdown={},
                    environment=environment,
                    quality_level=QualityLevel.MEDIUM,
                    cache_hit=False,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )
        
        # Stage 3: Smart Buffering
        if self.smart_buffer:
            priority = Priority.HIGH if environment == Environment.QUIET else Priority.NORMAL
            self.smart_buffer.add_chunk(audio.tobytes(), priority)
        
        # Stage 4: STT (placeholder - would call actual STT)
        stt_start = time.time()
        transcription = "simulated transcription"  # Placeholder
        stt_latency = (time.time() - stt_start) * 1000
        
        # Stage 5: Predictive Cache Check
        cache_hit = False
        translation = None
        
        if self.predictive_cache:
            cached = self.predictive_cache.get_translation(
                transcription,
                source_lang,
                target_lang,
                context,
            )
            if cached:
                translation = cached
                cache_hit = True
        
        # Stage 6: Translation (if not cached)
        if not translation:
            trans_start = time.time()
            translation = "simulated translation"  # Placeholder
            trans_latency = (time.time() - trans_start) * 1000
            
            if self.predictive_cache:
                self.predictive_cache.set_translation(
                    transcription,
                    translation,
                    source_lang,
                    target_lang,
                    context,
                )
        else:
            trans_latency = 0  # Cache hit
        
        # Stage 7: TTS (placeholder)
        tts_start = time.time()
        tts_audio = b"simulated audio"  # Placeholder
        tts_latency = (time.time() - tts_start) * 1000
        
        # Stage 8: Latency Optimization
        quality_level = QualityLevel.MEDIUM
        if self.latency_optimizer:
            metrics = PipelineMetrics(
                stt_latency_ms=stt_latency,
                translation_latency_ms=trans_latency,
                tts_latency_ms=tts_latency,
                end_to_end_latency_ms=(time.time() - start_time) * 1000,
                cpu_usage_percent=50.0,  # Placeholder
                memory_usage_mb=500.0,  # Placeholder
                network_latency_ms=50.0,  # Placeholder
            )
            config = self.latency_optimizer.optimize(metrics)
            quality_level = config.quality_level
        
        processing_time = (time.time() - start_time) * 1000
        
        return PipelineResult(
            success=True,
            transcription=transcription,
            translation=translation,
            tts_audio=tts_audio,
            latency_breakdown={
                "stt_ms": stt_latency,
                "translation_ms": trans_latency,
                "tts_ms": tts_latency,
                "total_ms": processing_time,
            },
            environment=environment,
            quality_level=quality_level,
            cache_hit=cache_hit,
            processing_time_ms=processing_time,
        )
    
    def get_optimization_status(self) -> Dict:
        """Get current optimization status."""
        status = {
            "adaptive_vad": {
                "enabled": self.config.enable_adaptive_vad,
                "environment": self.adaptive_vad.environment.value if self.adaptive_vad else None,
                "threshold": self.adaptive_vad.current_threshold if self.adaptive_vad else None,
            },
            "smart_buffer": {
                "enabled": self.config.enable_smart_buffer,
                "statistics": self.smart_buffer.get_statistics() if self.smart_buffer else None,
            },
            "predictive_cache": {
                "enabled": self.config.enable_predictive_cache,
                "statistics": self.predictive_cache.get_statistics() if self.predictive_cache else None,
            },
            "latency_optimizer": {
                "enabled": self.config.enable_latency_optimization,
                "report": self.latency_optimizer.get_optimization_report() if self.latency_optimizer else None,
            },
        }
        
        return status
    
    def warm_cache(self, source_lang: str, target_lang: str, translator_func):
        """Warm cache with common phrases."""
        if self.predictive_cache:
            self.predictive_cache.warm_cache(source_lang, target_lang, translator_func)
    
    def update_network_quality(self, quality: float):
        """Update network quality for adaptive buffering."""
        if self.smart_buffer:
            self.smart_buffer.update_network_quality(quality)
