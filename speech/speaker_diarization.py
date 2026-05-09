"""
Speaker diarization module for identifying and separating multiple speakers.
Essential for group conversations and multi-speaker environments.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import base64


@dataclass
class SpeakerSegment:
    """Represents a segment of audio spoken by a specific speaker."""
    speaker_id: str
    start_time: float
    end_time: float
    confidence: float
    audio_data: Optional[bytes] = None
    text: Optional[str] = None


class SpeakerDiarizer:
    """
    Speaker diarization for multi-speaker scenarios.
    Identifies who is speaking when in an audio stream.
    """
    
    def __init__(
        self,
        method: str = "pyannote",  # or "simple_vad_based", "embedding_cluster"
        num_speakers: Optional[int] = None,
        min_speaker_duration: float = 0.5,  # seconds
    ):
        self.method = method
        self.num_speakers = num_speakers
        self.min_speaker_duration = min_speaker_duration
        self._model = None
        self._speaker_profiles = {}  # speaker_id -> embedding
        self._next_speaker_id = 1
        
    def preload(self) -> bool:
        """Preload diarization model."""
        try:
            if self.method == "pyannote":
                return self._preload_pyannote()
            elif self.method == "embedding_cluster":
                return self._preload_embedding_model()
            else:
                # simple_vad_based needs no preload
                return True
        except Exception as e:
            print(f"Failed to preload diarization: {e}")
            return False
    
    def _preload_pyannote(self):
        try:
            import pyannote.audio
            # Pyannote requires authentication - check for token
            # For now, fall back to embedding method
            print("Pyannote: falling back to embedding-based method")
            self.method = "embedding_cluster"
            return self._preload_embedding_model()
        except ImportError:
            print("Pyannote not installed. Install: pip install pyannote.audio")
            self.method = "simple_vad_based"
            return True
    
    def _preload_embedding_model(self):
        try:
            # Use speechbrain or similar for speaker embeddings
            # Placeholder for actual implementation
            print("Embedding-based diarization: ready (placeholder)")
            return True
        except Exception as e:
            print(f"Embedding model failed: {e}")
            self.method = "simple_vad_based"
            return True
    
    def diarize(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> List[SpeakerSegment]:
        """
        Perform speaker diarization on audio data.
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            sample_rate: Audio sample rate
            
        Returns:
            List of SpeakerSegment objects
        """
        if self.method == "pyannote":
            return self._diarize_pyannote(audio_data, sample_rate)
        elif self.method == "embedding_cluster":
            return self._diarize_embedding(audio_data, sample_rate)
        else:
            return self._diarize_simple(audio_data, sample_rate)
    
    def _diarize_simple(
        self,
        audio_data: bytes,
        sample_rate: int,
    ) -> List[SpeakerSegment]:
        """
        Simple VAD-based diarization.
        Assumes single speaker per audio segment.
        """
        # For simple mode, treat entire audio as one speaker
        duration = len(audio_data) / (sample_rate * 2)  # 2 bytes per sample for 16-bit
        
        return [SpeakerSegment(
            speaker_id="speaker_1",
            start_time=0.0,
            end_time=duration,
            confidence=1.0,
            audio_data=audio_data,
        )]
    
    def _diarize_embedding(
        self,
        audio_data: bytes,
        sample_rate: int,
    ) -> List[SpeakerSegment]:
        """
        Embedding-based diarization using speaker embeddings.
        Clusters embeddings to identify unique speakers.
        """
        try:
            import numpy as np
            from sklearn.cluster import AgglomerativeClustering
            
            # Convert audio to numpy array
            samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
            
            # Split into segments (e.g., 2-second windows)
            segment_duration = 2.0
            segment_samples = int(segment_duration * sample_rate)
            segments = []
            
            for i in range(0, len(samples), segment_samples):
                segment = samples[i:i + segment_samples]
                if len(segment) < sample_rate * 0.5:  # Skip very short segments
                    continue
                segments.append(segment)
            
            if not segments:
                return self._diarize_simple(audio_data, sample_rate)
            
            # Extract embeddings (placeholder - use actual speaker embedding model)
            embeddings = []
            for segment in segments:
                # Placeholder: use actual speaker embedding extraction
                # e.g., from speechbrain or pyannote
                embedding = np.mean(segment) * np.ones(128)  # Dummy 128-dim embedding
                embeddings.append(embedding)
            
            embeddings = np.array(embeddings)
            
            # Cluster embeddings
            num_clusters = min(self.num_speakers or 2, len(embeddings))
            clustering = AgglomerativeClustering(n_clusters=num_clusters)
            labels = clustering.fit_predict(embeddings)
            
            # Convert to SpeakerSegments
            speaker_segments = []
            for i, (segment, label) in enumerate(zip(segments, labels)):
                speaker_id = f"speaker_{label + 1}"
                start_time = i * segment_duration
                end_time = start_time + segment_duration
                
                speaker_segments.append(SpeakerSegment(
                    speaker_id=speaker_id,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=0.8,
                    audio_data=(segment * 32767).astype(np.int16).tobytes(),
                ))
            
            return speaker_segments
            
        except ImportError:
            print("sklearn not available, falling back to simple diarization")
            return self._diarize_simple(audio_data, sample_rate)
        except Exception as e:
            print(f"Embedding diarization error: {e}")
            return self._diarize_simple(audio_data, sample_rate)
    
    def _diarize_pyannote(
        self,
        audio_data: bytes,
        sample_rate: int,
    ) -> List[SpeakerSegment]:
        """Pyannote-based diarization (placeholder)."""
        # TODO: Implement actual pyannote diarization
        return self._diarize_simple(audio_data, sample_rate)
    
    def identify_speaker(
        self,
        audio_segment: bytes,
        sample_rate: int = 16000,
    ) -> Tuple[str, float]:
        """
        Identify the speaker of a given audio segment.
        Returns (speaker_id, confidence).
        """
        # Placeholder: compare against stored speaker profiles
        if not self._speaker_profiles:
            speaker_id = f"speaker_{self._next_speaker_id}"
            self._next_speaker_id += 1
            self._speaker_profiles[speaker_id] = self._extract_embedding(audio_segment)
            return speaker_id, 1.0
        
        # Compare with existing profiles
        # Placeholder implementation
        return "speaker_1", 0.8
    
    def _extract_embedding(self, audio_data: bytes) -> np.ndarray:
        """Extract speaker embedding from audio."""
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
        return np.mean(samples) * np.ones(128)  # Placeholder
    
    def diarize_file(self, audio_path: str) -> List[SpeakerSegment]:
        """Diarize an audio file."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        audio_data = path.read_bytes()
        return self.diarize(audio_data)


class GroupConversationTracker:
    """
    Tracks speakers in a group conversation.
    Maintains speaker identities across multiple audio segments.
    """
    
    def __init__(self):
        self.speakers = {}  # speaker_id -> {"name": str, "color": str, "total_speaking_time": float}
        self.conversation_history = []
        self._speaker_colors = [
            "#2563eb", "#16a34a", "#dc2626", "#ca8a04",
            "#7c3aed", "#0891b2", "#ea580c", "#4f46e5",
        ]
        self._color_index = 0
    
    def register_speaker(self, speaker_id: str, name: Optional[str] = None) -> Dict:
        """Register a speaker in the group conversation."""
        if speaker_id not in self.speakers:
            self.speakers[speaker_id] = {
                "id": speaker_id,
                "name": name or f"Person {len(self.speakers) + 1}",
                "color": self._speaker_colors[self._color_index % len(self._speaker_colors)],
                "total_speaking_time": 0.0,
            }
            self._color_index += 1
        return self.speakers[speaker_id]
    
    def add_segment(self, segment: SpeakerSegment):
        """Add a speaker segment to the conversation history."""
        speaker_info = self.register_speaker(segment.speaker_id)
        speaker_info["total_speaking_time"] += (segment.end_time - segment.start_time)
        
        self.conversation_history.append({
            "speaker": segment.speaker_id,
            "speaker_name": speaker_info["name"],
            "speaker_color": speaker_info["color"],
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "text": segment.text,
            "confidence": segment.confidence,
        })
    
    def get_speaker_info(self, speaker_id: str) -> Optional[Dict]:
        """Get information about a specific speaker."""
        return self.speakers.get(speaker_id)
    
    def get_all_speakers(self) -> List[Dict]:
        """Get all registered speakers."""
        return list(self.speakers.values())
    
    def get_conversation_summary(self) -> Dict:
        """Get a summary of the group conversation."""
        total_duration = sum(
            s["total_speaking_time"] for s in self.speakers.values()
        )
        return {
            "num_speakers": len(self.speakers),
            "total_duration": total_duration,
            "speakers": self.get_all_speakers(),
            "num_segments": len(self.conversation_history),
        }


def apply_diarization_to_stream(
    audio_bytes: bytes,
    diarizer: SpeakerDiarizer,
    sample_rate: int = 16000,
) -> List[Dict]:
    """
    Convenience function to apply diarization to an audio stream.
    
    Returns list of dicts with speaker info and audio segments.
    """
    segments = diarizer.diarize(audio_bytes, sample_rate)
    
    results = []
    for seg in segments:
        results.append({
            "speaker_id": seg.speaker_id,
            "start": seg.start_time,
            "end": seg.end_time,
            "confidence": seg.confidence,
            "audio_base64": base64.b64encode(seg.audio_data).decode("ascii") if seg.audio_data else None,
        })
    
    return results