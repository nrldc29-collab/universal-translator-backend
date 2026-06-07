"""
Smart Audio Buffer Management

This module implements intelligent buffer management for audio streaming:
- Dynamic buffer sizing based on network conditions
- Priority-based chunk handling
- Adaptive quality adjustment
- Memory pressure awareness
- Latency-aware buffering

Usage:
    from backend.smart_buffer import SmartBuffer
    buffer = SmartBuffer(max_size_mb=12)
    buffer.add_chunk(chunk, priority=1)
    chunk = buffer.get_next_chunk()
"""

import heapq
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum
import time


class Priority(Enum):
    """Chunk priority levels."""
    CRITICAL = 1  # Final transcription, important for context
    HIGH = 2      # Partial transcription, real-time feedback
    NORMAL = 3    # Regular audio chunks
    LOW = 4       # Background audio, filler


@dataclass
class BufferChunk:
    """Audio chunk with metadata."""
    data: bytes
    priority: Priority
    timestamp: float
    sequence: int
    size_bytes: int = field(init=False)
    
    def __post_init__(self):
        self.size_bytes = len(self.data)
    
    def __lt__(self, other):
        # Higher priority (lower number) comes first
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        # Within same priority, older chunks first
        return self.timestamp < other.timestamp


class SmartBuffer:
    """Smart audio buffer with priority management."""
    
    def __init__(
        self,
        max_size_mb: float = 12,
        max_chunks: int = 1000,
        enable_adaptive_sizing: bool = True,
        latency_target_ms: float = 500,
    ):
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.max_chunks = max_chunks
        self.enable_adaptive_sizing = enable_adaptive_sizing
        self.latency_target_ms = latency_target_ms
        
        self.chunks: List[BufferChunk] = []
        self.current_size_bytes = 0
        self.sequence_counter = 0
        
        # Statistics
        self.total_added = 0
        self.total_dropped = 0
        self.total_retrieved = 0
        
        # Adaptive sizing
        self.current_max_size = self.max_size_bytes
        self.network_quality = 1.0  # 0.0 to 1.0
        
    def add_chunk(self, data: bytes, priority: Priority = Priority.NORMAL) -> bool:
        """Add chunk to buffer with priority."""
        if not data:
            return False
        chunk = BufferChunk(
            data=data,
            priority=priority,
            timestamp=time.time(),
            sequence=self.sequence_counter,
        )
        self.sequence_counter += 1
        
        # Check if buffer is full
        if self._is_full(chunk.size_bytes):
            # Try to make space by dropping low-priority chunks
            if not self._make_space(chunk.size_bytes):
                self.total_dropped += 1
                return False
        
        # Add chunk
        heapq.heappush(self.chunks, chunk)
        self.current_size_bytes += chunk.size_bytes
        self.total_added += 1
        
        return True
    
    def get_next_chunk(self) -> Optional[bytes]:
        """Get next highest-priority chunk."""
        if not self.chunks:
            return None
        
        chunk = heapq.heappop(self.chunks)
        self.current_size_bytes -= chunk.size_bytes
        self.total_retrieved += 1
        
        return chunk.data
    
    def peek_next(self) -> Optional[bytes]:
        """Peek at next chunk without removing."""
        if not self.chunks:
            return None
        return self.chunks[0].data
    
    def _is_full(self, additional_bytes: int) -> bool:
        """Check if buffer is full."""
        return (
            len(self.chunks) >= self.max_chunks or
            self.current_size_bytes + additional_bytes > self.current_max_size
        )
    
    def _make_space(self, required_bytes: int) -> bool:
        """Make space by dropping low-priority chunks."""
        freed_bytes = 0
        chunks_to_drop = []
        
        # Find low-priority chunks to drop
        for chunk in self.chunks:
            if chunk.priority == Priority.LOW:
                chunks_to_drop.append(chunk)
                freed_bytes += chunk.size_bytes
                if freed_bytes >= required_bytes:
                    break
        
        # If still need space, try NORMAL priority
        if freed_bytes < required_bytes:
            for chunk in self.chunks:
                if chunk.priority == Priority.NORMAL and chunk not in chunks_to_drop:
                    chunks_to_drop.append(chunk)
                    freed_bytes += chunk.size_bytes
                    if freed_bytes >= required_bytes:
                        break
        
        # Remove dropped chunks
        if freed_bytes >= required_bytes:
            for chunk in chunks_to_drop:
                self.chunks.remove(chunk)
                self.current_size_bytes -= chunk.size_bytes
                self.total_dropped += 1
            heapq.heapify(self.chunks)
            return True
        
        return False
    
    def update_network_quality(self, quality: float):
        """Update network quality (0.0 to 1.0)."""
        self.network_quality = max(0.0, min(1.0, quality))
        
        if self.enable_adaptive_sizing:
            # Reduce buffer size on poor network to reduce latency
            self.current_max_size = int(self.max_size_bytes * (0.5 + 0.5 * self.network_quality))
    
    def get_statistics(self) -> dict:
        """Get buffer statistics."""
        return {
            "total_added": self.total_added,
            "total_dropped": self.total_dropped,
            "total_retrieved": self.total_retrieved,
            "current_size_bytes": self.current_size_bytes,
            "current_size_mb": self.current_size_bytes / 1024 / 1024,
            "chunk_count": len(self.chunks),
            "drop_rate": self.total_dropped / max(1, self.total_added),
            "network_quality": self.network_quality,
            "adaptive_max_size_mb": self.current_max_size / 1024 / 1024,
        }
    
    def clear(self):
        """Clear buffer."""
        self.chunks = []
        self.current_size_bytes = 0
        self.sequence_counter = 0
    
    def get_priority_distribution(self) -> dict:
        """Get distribution of chunks by priority."""
        distribution = {p: 0 for p in Priority}
        for chunk in self.chunks:
            distribution[chunk.priority] += 1
        return {p.name: count for p, count in distribution.items()}
