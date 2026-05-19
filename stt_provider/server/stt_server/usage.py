"""
Usage tracking and persistence module.

This module provides functionality for tracking STT service usage metrics
including sessions, transcripts, audio statistics, and estimated audio seconds.
It supports in-memory tracking with periodic persistence to disk and database
integration for durable usage counter updates.
"""
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import UUID

from stt_server.config import settings

logger = logging.getLogger(__name__)

USAGE_PATH = Path("logs/usage-snapshot.json")


@dataclass
class UsageCounter:
    """
    Usage counter for tracking STT service metrics.
    
    Tracks various usage metrics including session counts, transcript counts,
    audio statistics, and estimated audio duration for a specific API key label.
    
    Attributes:
        sessions_started: Total number of sessions started
        sessions_closed: Total number of sessions closed
        partial_transcripts: Total partial transcript events
        final_transcripts: Total final transcript events
        errors: Total error events
        audio_frames_received: Total binary audio frames received
        audio_bytes_received: Total binary audio bytes received
        estimated_audio_seconds: Estimated total audio duration in seconds
    """
    sessions_started: int = 0
    sessions_closed: int = 0
    partial_transcripts: int = 0
    final_transcripts: int = 0
    errors: int = 0
    audio_frames_received: int = 0
    audio_bytes_received: int = 0
    estimated_audio_seconds: float = 0.0

    def add_audio_bytes(self, byte_count: int) -> None:
        """
        Add audio bytes and estimate audio duration.
        
        Calculates the estimated audio duration based on the byte count
        using the configured sample rate and channels.
        
        Args:
            byte_count: Number of audio bytes received
        """
        bytes_per_second = settings.sample_rate * settings.channels * 2

        if bytes_per_second > 0:
            self.estimated_audio_seconds += byte_count / bytes_per_second

    def as_dict(self) -> dict:
        """
        Convert the usage counter to a dictionary.
        
        Returns:
            Dictionary representation of the usage counter
        """
        return {
            "sessions_started": self.sessions_started,
            "sessions_closed": self.sessions_closed,
            "partial_transcripts": self.partial_transcripts,
            "final_transcripts": self.final_transcripts,
            "errors": self.errors,
            "audio_frames_received": self.audio_frames_received,
            "audio_bytes_received": self.audio_bytes_received,
            "estimated_audio_seconds": round(self.estimated_audio_seconds, 3),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UsageCounter":
        """
        Create a UsageCounter from a dictionary.
        
        Args:
            data: Dictionary containing usage counter data
            
        Returns:
            UsageCounter instance
        """
        return cls(
            sessions_started=int(data.get("sessions_started", 0)),
            sessions_closed=int(data.get("sessions_closed", 0)),
            partial_transcripts=int(data.get("partial_transcripts", 0)),
            final_transcripts=int(data.get("final_transcripts", 0)),
            errors=int(data.get("errors", 0)),
            audio_frames_received=int(data.get("audio_frames_received", 0)),
            audio_bytes_received=int(data.get("audio_bytes_received", 0)),
            estimated_audio_seconds=float(data.get("estimated_audio_seconds", 0.0)),
        )


@dataclass
class UsageStore:
    """
    In-memory store for usage counters by API key label.
    
    Manages usage counters for different API key labels, providing methods
    for getting counters, persisting to disk, and loading from disk.
    
    Attributes:
        by_key_label: Dictionary mapping key labels to UsageCounter instances
    """
    by_key_label: dict[str, UsageCounter] = field(default_factory=dict)

    def get(self, key_label: str) -> UsageCounter:
        """
        Get or create a usage counter for a key label.
        
        Returns the existing counter for the label, or creates a new one
        if it doesn't exist.
        
        Args:
            key_label: API key label to get the counter for
            
        Returns:
            UsageCounter instance for the key label
        """
        label = key_label or "unknown"

        if label not in self.by_key_label:
            self.by_key_label[label] = UsageCounter()

        return self.by_key_label[label]

    def as_dict(self) -> dict:
        """
        Convert the usage store to a dictionary.
        
        Returns:
            Dictionary mapping key labels to counter dictionaries
        """
        return {
            label: counter.as_dict()
            for label, counter in sorted(self.by_key_label.items())
        }

    def reset(self) -> None:
        """
        Reset all usage counters.
        
        Clears all counters and saves the empty state to disk.
        """
        logger.info("Resetting usage store")
        self.by_key_label = {}
        self.save()

    def save(self) -> None:
        """
        Persist the usage store to disk.
        
        Writes the current usage store state to a JSON file using atomic
        write with temporary file and rename to prevent corruption.
        """
        USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "by_key_label": self.as_dict(),
        }

        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(USAGE_PATH.parent),
            prefix="usage-snapshot.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)

        os.replace(tmp_path, USAGE_PATH)
        logger.debug(f"Usage store saved to {USAGE_PATH}")

    def load(self) -> None:
        """
        Load the usage store from disk.
        
        Reads the usage store state from the JSON file and populates
        the in-memory store. Silently skips if the file doesn't exist.
        """
        if not USAGE_PATH.exists():
            logger.debug(f"Usage snapshot file not found at {USAGE_PATH}")
            return

        data = json.loads(USAGE_PATH.read_text())
        raw_by_key_label = data.get("by_key_label", {})

        self.by_key_label = {
            label: UsageCounter.from_dict(counter)
            for label, counter in raw_by_key_label.items()
        }
        logger.info(f"Usage store loaded from {USAGE_PATH} with {len(self.by_key_label)} key labels")


# Global usage store instance
usage_store = UsageStore()


async def increment_usage_counters(
    db,
    *,
    tenant_id: UUID,
    audio_seconds: int,
    stream_count: int = 0,
    transcription_count: int = 0,
) -> None:
    """
    Increment usage counters in the database for a tenant.
    
    Updates the durable usage counters in the database for the specified tenant,
    incrementing audio seconds, stream count, and transcription count.
    Uses upsert logic to handle both new and existing records.
    
    Args:
        db: Database connection
        tenant_id: UUID of the tenant
        audio_seconds: Audio seconds to add
        stream_count: Stream count to add (default: 0)
        transcription_count: Transcription count to add (default: 0)
    """
    await db.execute(
        """
        INSERT INTO usage_counters (
            tenant_id,
            usage_date,
            audio_seconds,
            stream_count,
            transcription_count
        )
        VALUES ($1, CURRENT_DATE, $2, $3, $4)
        ON CONFLICT (tenant_id, usage_date)
        DO UPDATE SET
            audio_seconds = usage_counters.audio_seconds + EXCLUDED.audio_seconds,
            stream_count = usage_counters.stream_count + EXCLUDED.stream_count,
            transcription_count = usage_counters.transcription_count + EXCLUDED.transcription_count
        """,
        tenant_id,
        audio_seconds,
        stream_count,
        transcription_count,
    )
    logger.debug(f"Incremented usage counters for tenant {tenant_id}: audio_seconds={audio_seconds}, stream_count={stream_count}, transcription_count={transcription_count}")

# Call it when a WebSocket session closes:
#
# from stt_server.usage import increment_usage_counters
#
# await increment_usage_counters(
#     db,
#     tenant_id=tenant.id,
#     audio_seconds=int(audio_seconds),
#     stream_count=1,
# )
#
# Call it when a REST transcription completes:
#
# await increment_usage_counters(
#     db,
#     tenant_id=tenant.id,
#     audio_seconds=int(audio_seconds),
#     transcription_count=1,
# )
#
# This completes the durable usage-counter write path required after externalizing state to Postgres, replacing file-based usage snapshots with transactional tenant usage records
