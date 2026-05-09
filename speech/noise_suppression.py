"""
Noise suppression module for improving speech recognition in chaotic environments.
Uses spectral gating and deep learning-based approaches for real-world noise reduction.
"""

import numpy as np
import io
import wave
from pathlib import Path
from typing import Optional, Tuple


class NoiseSuppressor:
    """
    Noise suppression for audio streams.
    Implements spectral gating and optional deep noise suppression.
    """
    
    def __init__(
        self,
        method: str = "spectral_gating",  # or "deep_noise_suppression"
        sample_rate: int = 16000,
        frame_size: int = 1024,
        hop_length: int = 512,
    ):
        self.method = method
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.hop_length = hop_length
        self._noise_profile = None
        self._deep_model = None
        
    def preload(self) -> bool:
        """Preload noise suppression model if using deep learning method."""
        if self.method == "deep_noise_suppression":
            try:
                # Try to import deep noise suppression library
                # This could be RNNoise, DeepFilterNet, etc.
                # For now, we'll use spectral gating as fallback
                print("Deep noise suppression: using spectral gating fallback")
                self.method = "spectral_gating"
                return True
            except ImportError:
                print("Deep noise suppression not available, using spectral gating")
                self.method = "spectral_gating"
                return True
        return True
    
    def profile_noise(self, audio_data: bytes, duration_ms: int = 500) -> None:
        """
        Profile noise from initial audio segment (first 500ms typically).
        This helps the spectral gating algorithm know what is "noise".
        """
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
        
        # Take first duration_ms of audio as noise profile
        noise_samples = int(self.sample_rate * duration_ms / 1000)
        if len(samples) > noise_samples:
            self._noise_profile = np.mean(np.abs(samples[:noise_samples]))
        else:
            self._noise_profile = np.mean(np.abs(samples))
    
    def suppress(self, audio_data: bytes) -> bytes:
        """
        Apply noise suppression to audio data.
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            
        Returns:
            Noise-suppressed audio bytes
        """
        if self.method == "spectral_gating":
            return self._spectral_gating(audio_data)
        elif self.method == "deep_noise_suppression":
            return self._deep_suppression(audio_data)
        else:
            return audio_data
    
    def _spectral_gating(self, audio_data: bytes) -> bytes:
        """
        Simple spectral gating for noise reduction.
        Uses a basic noise gate based on noise profile.
        """
        try:
            import numpy as np
            from scipy import signal
            from scipy.fft import rfft, irfft
            
            # Convert bytes to numpy array
            samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
            
            # If no noise profile, create one from quietest parts
            if self._noise_profile is None:
                # Use bottom 10th percentile as noise floor
                sorted_amp = np.sort(np.abs(samples))
                noise_floor_idx = int(len(sorted_amp) * 0.1)
                self._noise_profile = sorted_amp[:noise_floor_idx].mean() if noise_floor_idx > 0 else 0.01
            
            # Apply noise gate
            noise_gate_threshold = self._noise_profile * 3.0  # 3x noise floor
            
            # Simple noise gating
            gated_samples = np.where(
                np.abs(samples) < noise_gate_threshold,
                samples * 0.1,  # Attenuate by 90%
                samples  # Keep original
            )
            
            # Convert back to int16
            output_samples = (gated_samples * 32767).astype(np.int16)
            return output_samples.tobytes()
            
        except ImportError:
            # Fallback: return original if scipy not available
            return audio_data
        except Exception as e:
            print(f"Noise suppression error: {e}")
            return audio_data
    
    def _deep_suppression(self, audio_data: bytes) -> bytes:
        """
        Deep learning-based noise suppression.
        Placeholder for integration with models like RNNoise, DeepFilterNet, etc.
        """
        # TODO: Implement actual deep noise suppression
        # For now, fall back to spectral gating
        return self._spectral_gating(audio_data)
    
    def suppress_wav_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Apply noise suppression to a WAV file.
        
        Args:
            input_path: Path to input WAV file
            output_path: Path to output WAV file (default: input_path with _denoised suffix)
            
        Returns:
            Path to the output file
        """
        if output_path is None:
            p = Path(input_path)
            output_path = str(p.parent / f"{p.stem}_denoised{p.suffix}")
        
        # Read WAV file
        with wave.open(input_path, 'rb') as wav_in:
            params = wav_in.getparams()
            frames = wav_in.readframes(params.nframes)
        
        # Apply suppression
        suppressed = self.suppress(frames)
        
        # Write output WAV
        with wave.open(output_path, 'wb') as wav_out:
            wav_out.setparams(params)
            wav_out.writeframes(suppressed)
        
        return output_path


class AdaptiveNoiseSuppressor(NoiseSuppressor):
    """
    Adaptive noise suppressor that adjusts to changing noise conditions.
    Useful for mobile environments where noise characteristics change.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._noise_history = []
        self._adaptation_rate = 0.1
        
    def adapt(self, audio_chunk: bytes) -> None:
        """
        Adapt noise profile based on incoming audio.
        Uses exponential moving average to track noise floor changes.
        """
        samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32767.0
        current_noise = np.mean(np.abs(samples))
        
        if self._noise_profile is None:
            self._noise_profile = current_noise
        else:
            # Exponential moving average
            self._noise_profile = (
                self._adaptation_rate * current_noise +
                (1 - self._adaptation_rate) * self._noise_profile
            )
        
        self._noise_history.append(self._noise_profile)
        if len(self._noise_history) > 100:
            self._noise_history.pop(0)
    
    def suppress(self, audio_data: bytes) -> bytes:
        # Adapt to current noise conditions
        self.adapt(audio_data)
        return super().suppress(audio_data)


def apply_noise_suppression(
    audio_bytes: bytes,
    sample_rate: int = 16000,
    method: str = "spectral_gating",
) -> bytes:
    """
    Convenience function to apply noise suppression.
    
    Args:
        audio_bytes: Raw audio bytes
        sample_rate: Audio sample rate
        method: Suppression method
        
    Returns:
        Noise-suppressed audio bytes
    """
    suppressor = NoiseSuppressor(method=method, sample_rate=sample_rate)
    suppressor.preload()
    return suppressor.suppress(audio_bytes)