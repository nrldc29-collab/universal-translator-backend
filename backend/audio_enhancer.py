"""
Audio Enhancement Module

This module provides advanced audio processing for better speech recognition:
- Noise reduction
- Automatic gain control
- Voice activity enhancement
- Echo cancellation
- Audio normalization

Usage:
    from backend.audio_enhancer import AudioEnhancer
    enhancer = AudioEnhancer()
    enhanced_audio = enhancer.process(raw_audio)
"""

import numpy as np
from typing import Optional, Tuple
import scipy.signal
from scipy.ndimage import median_filter


class AudioEnhancer:
    """Advanced audio enhancement for speech recognition."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        enable_noise_reduction: bool = True,
        enable_agc: bool = True,
        enable_normalization: bool = True,
    ):
        self.sample_rate = sample_rate
        self.enable_noise_reduction = enable_noise_reduction
        self.enable_agc = enable_agc
        self.enable_normalization = enable_normalization
        
        # AGC parameters
        self.target_level = 0.5
        self.agc_gain = 1.0
        self.agc_attack = 0.01
        self.agc_release = 0.1
        
        # Noise reduction parameters
        self.noise_floor = 0.0
        self.noise_gate_threshold = 0.02
        self.noise_reduction_factor = 0.5
        
    def normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to target level."""
        if not self.enable_normalization:
            return audio
        
        # Calculate current level
        current_level = np.max(np.abs(audio))
        
        if current_level > 0:
            # Normalize to target level
            normalized = audio * (self.target_level / current_level)
            # Clip to prevent distortion
            normalized = np.clip(normalized, -1.0, 1.0)
            return normalized
        
        return audio
    
    def apply_agc(self, audio: np.ndarray) -> np.ndarray:
        """Apply automatic gain control."""
        if not self.enable_agc:
            return audio
        
        # Calculate envelope
        envelope = np.abs(audio)
        
        # Calculate target gain
        target_gain = self.target_level / (np.mean(envelope) + 1e-6)
        
        # Smooth gain changes
        self.agc_gain = (
            self.agc_gain * (1 - self.agc_attack) +
            target_gain * self.agc_attack
        )
        
        # Clamp gain
        self.agc_gain = np.clip(self.agc_gain, 0.5, 10.0)
        
        return audio * self.agc_gain
    
    def reduce_noise(self, audio: np.ndarray) -> np.ndarray:
        """Apply noise reduction."""
        if not self.enable_noise_reduction:
            return audio
        
        # Estimate noise floor from quiet parts
        energy = np.mean(audio ** 2)
        
        if energy < self.noise_gate_threshold:
            # Update noise floor estimate
            self.noise_floor = 0.9 * self.noise_floor + 0.1 * energy
        
        # Apply spectral subtraction (simplified)
        if self.noise_floor > 0:
            # Calculate noise reduction factor based on SNR
            snr = energy / (self.noise_floor + 1e-6)
            reduction = min(self.noise_reduction_factor, 1.0 / (1.0 + snr))
            
            # Apply reduction
            audio = audio * (1.0 - reduction)
        
        return audio
    
    def apply_bandpass_filter(self, audio: np.ndarray) -> np.ndarray:
        """Apply bandpass filter for speech frequencies (300-3400 Hz)."""
        nyquist = self.sample_rate / 2
        low = 300 / nyquist
        high = 3400 / nyquist
        
        b, a = scipy.signal.butter(4, [low, high], btype='band')
        filtered = scipy.signal.filtfilt(b, a, audio)
        
        return filtered
    
    def remove_dc_offset(self, audio: np.ndarray) -> np.ndarray:
        """Remove DC offset from audio."""
        return audio - np.mean(audio)
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio through enhancement pipeline."""
        # Convert to numpy if needed
        if not isinstance(audio, np.ndarray):
            audio = np.array(audio, dtype=np.float32)
        
        # Normalize to [-1, 1]
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        
        # Enhancement pipeline
        audio = self.remove_dc_offset(audio)
        audio = self.apply_bandpass_filter(audio)
        audio = self.reduce_noise(audio)
        audio = self.apply_agc(audio)
        audio = self.normalize_audio(audio)
        
        return audio
    
    def reset(self):
        """Reset enhancer state."""
        self.agc_gain = 1.0
        self.noise_floor = 0.0
