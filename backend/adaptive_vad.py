"""
Adaptive Voice Activity Detection

This module implements adaptive VAD that adjusts to environmental conditions:
- Dynamic threshold adjustment based on noise levels
- Environmental classification (quiet, office, restaurant, street)
- Automatic sensitivity tuning
- Noise floor estimation and tracking

Usage:
    from backend.adaptive_vad import AdaptiveVAD
    vad = AdaptiveVAD()
    is_speech = vad.detect(audio_chunk)
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics


class Environment(Enum):
    """Environment classification."""
    QUIET = "quiet"
    OFFICE = "office"
    RESTAURANT = "restaurant"
    STREET = "street"
    CROWDED = "crowded"


@dataclass
class VADResult:
    """VAD detection result."""
    is_speech: bool
    confidence: float
    noise_level: float
    environment: Environment
    threshold: float


class AdaptiveVAD:
    """Adaptive voice activity detector."""
    
    def __init__(
        self,
        initial_threshold: float = 0.055,
        adaptation_rate: float = 0.1,
        min_threshold: float = 0.03,
        max_threshold: float = 0.15,
        window_size: int = 10,
    ):
        self.base_threshold = initial_threshold
        self.current_threshold = initial_threshold
        self.adaptation_rate = adaptation_rate
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.window_size = window_size
        
        # Noise floor tracking
        self.noise_history = []
        self.speech_history = []
        
        # Environment detection
        self.environment = Environment.QUIET
        self.environment_confidence = 0.0
        
    def calculate_energy(self, audio: np.ndarray) -> float:
        """Calculate RMS energy of audio."""
        return np.sqrt(np.mean(audio ** 2))
    
    def estimate_noise_floor(self, audio: np.ndarray) -> float:
        """Estimate noise floor from audio."""
        energy = self.calculate_energy(audio)
        self.noise_history.append(energy)
        
        if len(self.noise_history) > self.window_size:
            self.noise_history.pop(0)
        
        return statistics.mean(self.noise_history)
    
    def classify_environment(self, noise_level: float) -> Environment:
        """Classify environment based on noise level."""
        if noise_level < 0.02:
            return Environment.QUIET
        elif noise_level < 0.05:
            return Environment.OFFICE
        elif noise_level < 0.15:
            return Environment.RESTAURANT
        elif noise_level < 0.25:
            return Environment.STREET
        else:
            return Environment.CROWDED
    
    def adapt_threshold(self, noise_level: float, is_speech: bool):
        """Adapt threshold based on noise level and speech detection."""
        # Classify environment
        new_environment = self.classify_environment(noise_level)
        
        # Update environment with smoothing
        if new_environment != self.environment:
            self.environment_confidence = 0.0
        else:
            self.environment_confidence = min(1.0, self.environment_confidence + 0.1)
        
        if self.environment_confidence > 0.7:
            self.environment = new_environment
        
        # Environment-specific thresholds
        target_thresholds = {
            Environment.QUIET: 0.04,
            Environment.OFFICE: 0.055,
            Environment.RESTAURANT: 0.08,
            Environment.STREET: 0.10,
            Environment.CROWDED: 0.12,
        }
        
        target_threshold = target_thresholds.get(self.environment, self.base_threshold)
        
        # Adapt towards target threshold
        self.current_threshold = (
            self.current_threshold * (1 - self.adaptation_rate) +
            target_threshold * self.adaptation_rate
        )
        
        # Clamp to limits
        self.current_threshold = max(self.min_threshold, min(self.max_threshold, self.current_threshold))
    
    def detect(self, audio: np.ndarray) -> VADResult:
        """Detect speech in audio chunk."""
        # Convert to numpy if needed
        if not isinstance(audio, np.ndarray):
            audio = np.array(audio)
        
        # Calculate energy
        energy = self.calculate_energy(audio)
        
        # Estimate noise floor
        noise_level = self.estimate_noise_floor(audio)
        
        # Detect speech
        is_speech = energy > self.current_threshold
        
        # Calculate confidence
        confidence = min(1.0, (energy - self.current_threshold) / (self.current_threshold * 2))
        if not is_speech:
            confidence = 1.0 - confidence
        
        # Adapt threshold
        self.adapt_threshold(noise_level, is_speech)
        
        return VADResult(
            is_speech=is_speech,
            confidence=confidence,
            noise_level=noise_level,
            environment=self.environment,
            threshold=self.current_threshold,
        )
    
    def reset(self):
        """Reset VAD state."""
        self.current_threshold = self.base_threshold
        self.noise_history = []
        self.speech_history = []
        self.environment = Environment.QUIET
        self.environment_confidence = 0.0
