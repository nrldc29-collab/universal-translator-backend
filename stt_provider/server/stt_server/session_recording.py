"""
Session recording system for STT service.

This module provides session recording functionality that allows the STT service
to record audio streams, transcripts, and metadata for debugging, auditing, and
analysis purposes. Features include:
- Audio stream recording to PCM files
- Transcript and metadata persistence
- Configurable retention policies
- Automatic cleanup of old recordings
- File size and duration limits
"""
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class SessionRecording:
    """
    Represents a recorded session with audio, transcript, and metadata.
    
    Attributes:
        session_id: Unique identifier for the session
        tenant_id: Tenant ID that owns the session
        started_at: Unix timestamp when recording started
        ended_at: Unix timestamp when recording ended (None if active)
        audio_file_path: Path to the recorded audio file
        transcript_file_path: Path to the transcript JSON file
        metadata_file_path: Path to the session metadata file
        duration_seconds: Total recording duration in seconds
        audio_bytes: Total audio data recorded in bytes
    """
    session_id: UUID
    tenant_id: UUID
    started_at: float
    ended_at: Optional[float] = None
    audio_file_path: Optional[str] = None
    transcript_file_path: Optional[str] = None
    metadata_file_path: Optional[str] = None
    duration_seconds: float = 0.0
    audio_bytes: int = 0


@dataclass
class SessionRecordingConfig:
    """
    Configuration for session recording behavior.
    
    Attributes:
        enabled: Whether session recording is enabled
        max_duration_seconds: Maximum recording duration in seconds
        max_file_size_mb: Maximum audio file size in megabytes
        storage_dir: Directory path for storing recordings
        retain_days: Number of days to retain recordings before cleanup
    """
    enabled: bool = False
    max_duration_seconds: int = 3600  # 1 hour
    max_file_size_mb: int = 100
    storage_dir: str = "recordings"
    retain_days: int = 30


class SessionRecorder:
    """
    Manage session recording and playback for the STT service.
    
    This class handles the lifecycle of session recordings including starting
    new recordings, appending audio data, ending recordings, and cleanup of
    old recordings based on retention policies.
    
    Attributes:
        config: Configuration for recording behavior
        _recordings: Dictionary of active recordings by session ID
    """
    
    def __init__(self, config: Optional[SessionRecordingConfig] = None):
        """
        Initialize the session recorder.
        
        Args:
            config: Optional recording configuration, uses defaults if not provided
        """
        self.config = config or SessionRecordingConfig()
        self._recordings: Dict[UUID, SessionRecording] = {}
        self._ensure_storage_dir()
        logger.info(f"SessionRecorder initialized: enabled={self.config.enabled}, storage_dir={self.config.storage_dir}")
    
    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists, creating it if necessary."""
        storage_path = Path(self.config.storage_dir)
        storage_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Storage directory ensured: {storage_path}")
    
    def start_recording(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> Optional[SessionRecording]:
        """
        Start recording a session.
        
        Creates a new recording entry with file paths for audio, transcript,
        and metadata. Recording is only started if the feature is enabled.
        
        Args:
            session_id: Unique identifier for the session
            tenant_id: Tenant ID that owns the session
            
        Returns:
            SessionRecording if recording started, None if disabled
        """
        if not self.config.enabled:
            logger.debug(f"Recording disabled, skipping session {session_id}")
            return None
        
        recording = SessionRecording(
            session_id=session_id,
            tenant_id=tenant_id,
            started_at=time.time(),
        )
        
        # Create file paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{tenant_id}_{session_id}_{timestamp}"
        
        recording.audio_file_path = os.path.join(
            self.config.storage_dir,
            f"{base_filename}.pcm",
        )
        recording.transcript_file_path = os.path.join(
            self.config.storage_dir,
            f"{base_filename}.json",
        )
        recording.metadata_file_path = os.path.join(
            self.config.storage_dir,
            f"{base_filename}.meta",
        )
        
        self._recordings[session_id] = recording
        logger.info(f"Started recording session {session_id} for tenant {tenant_id}")
        return recording
    
    def append_audio(
        self,
        session_id: UUID,
        audio_data: bytes,
    ) -> bool:
        """
        Append audio data to a recording.
        
        Appends the provided audio data to the recording's audio file.
        Enforces file size and duration limits before writing.
        
        Args:
            session_id: Unique identifier for the session
            audio_data: Audio data bytes to append
            
        Returns:
            True if appended successfully, False if recording not found,
            disabled, or limits exceeded
        """
        if not self.config.enabled:
            return False
        
        recording = self._recordings.get(session_id)
        
        if not recording or not recording.audio_file_path:
            logger.warning(f"Recording not found for session {session_id}")
            return False
        
        # Check file size limit
        if recording.audio_bytes > (self.config.max_file_size_mb * 1024 * 1024):
            logger.warning(f"File size limit exceeded for session {session_id}")
            return False
        
        # Check duration limit
        if time.time() - recording.started_at > self.config.max_duration_seconds:
            logger.warning(f"Duration limit exceeded for session {session_id}")
            return False
        
        try:
            with open(recording.audio_file_path, "ab") as f:
                f.write(audio_data)
                recording.audio_bytes += len(audio_data)
            logger.debug(f"Appended {len(audio_data)} bytes to session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to append audio to session {session_id}: {e}")
            return False
    
    def end_recording(
        self,
        session_id: UUID,
        transcript: Optional[str] = None,
    ) -> Optional[SessionRecording]:
        """
        End a recording session.
        
        Finalizes the recording by setting the end time, calculating duration,
        saving the transcript if provided, and writing metadata to disk.
        
        Args:
            session_id: Unique identifier for the session
            transcript: Optional transcript text to save
            
        Returns:
            SessionRecording if ended successfully, None if not found
        """
        recording = self._recordings.get(session_id)
        
        if not recording:
            logger.warning(f"Recording not found for session {session_id}")
            return None
        
        recording.ended_at = time.time()
        recording.duration_seconds = recording.ended_at - recording.started_at
        
        logger.info(f"Ending recording session {session_id}, duration: {recording.duration_seconds:.2f}s")
        
        # Save transcript if provided
        if transcript and recording.transcript_file_path:
            try:
                import json
                with open(recording.transcript_file_path, "w") as f:
                    json.dump({"transcript": transcript}, f)
                logger.debug(f"Saved transcript for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to save transcript for session {session_id}: {e}")
        
        # Save metadata
        if recording.metadata_file_path:
            try:
                import json
                metadata = {
                    "session_id": str(recording.session_id),
                    "tenant_id": str(recording.tenant_id),
                    "started_at": recording.started_at,
                    "ended_at": recording.ended_at,
                    "duration_seconds": recording.duration_seconds,
                    "audio_bytes": recording.audio_bytes,
                    "audio_file_path": recording.audio_file_path,
                    "transcript_file_path": recording.transcript_file_path,
                }
                with open(recording.metadata_file_path, "w") as f:
                    json.dump(metadata, f)
                logger.debug(f"Saved metadata for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to save metadata for session {session_id}: {e}")
        
        return recording
    
    def get_recording(self, session_id: UUID) -> Optional[SessionRecording]:
        """
        Get a recording by session ID.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            SessionRecording if found, None otherwise
        """
        return self._recordings.get(session_id)
    
    def cleanup_old_recordings(self) -> int:
        """
        Remove recordings older than the retention period.
        
        Deletes both the in-memory recording entries and the associated
        audio, transcript, and metadata files.
        
        Returns:
            Number of recordings removed
        """
        if not self.config.enabled:
            return 0
        
        cutoff_time = time.time() - (self.config.retain_days * 86400)
        removed = 0
        
        to_remove = [
            session_id
            for session_id, recording in self._recordings.items()
            if recording.started_at < cutoff_time
        ]
        
        logger.info(f"Cleaning up {len(to_remove)} recordings older than {self.config.retain_days} days")
        
        for session_id in to_remove:
            recording = self._recordings[session_id]
            
            # Remove files
            for file_path in [
                recording.audio_file_path,
                recording.transcript_file_path,
                recording.metadata_file_path,
            ]:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.debug(f"Removed file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove file {file_path}: {e}")
            
            del self._recordings[session_id]
            removed += 1
        
        logger.info(f"Cleanup complete: {removed} recordings removed")
        return removed
    
    def get_stats(self) -> dict:
        """
        Get recording statistics.
        
        Returns:
            Dictionary containing active recording count, total recordings,
            total audio bytes, and configuration details
        """
        active_recordings = sum(
            1 for r in self._recordings.values() if r.ended_at is None
        )
        total_recordings = len(self._recordings)
        total_audio_bytes = sum(r.audio_bytes for r in self._recordings.values())
        
        stats = {
            "enabled": self.config.enabled,
            "active_recordings": active_recordings,
            "total_recordings": total_recordings,
            "total_audio_bytes": total_audio_bytes,
            "storage_dir": self.config.storage_dir,
            "retain_days": self.config.retain_days,
        }
        logger.debug(f"Recording stats: {stats}")
        return stats


# Global session recorder instance
_global_recorder: Optional[SessionRecorder] = None


def get_session_recorder() -> SessionRecorder:
    """Get the global session recorder instance."""
    global _global_recorder
    
    if _global_recorder is None:
        import os
        config = SessionRecordingConfig(
            enabled=os.environ.get("SESSION_RECORDING_ENABLED", "false").lower() == "true",
            max_duration_seconds=int(os.environ.get("SESSION_RECORDING_MAX_DURATION_SECONDS", "3600")),
            max_file_size_mb=int(os.environ.get("SESSION_RECORDING_MAX_SIZE_MB", "100")),
            storage_dir=os.environ.get("SESSION_RECORDING_DIR", "recordings"),
            retain_days=int(os.environ.get("SESSION_RECORDING_RETAIN_DAYS", "30")),
        )
        _global_recorder = SessionRecorder(config)
    
    return _global_recorder
