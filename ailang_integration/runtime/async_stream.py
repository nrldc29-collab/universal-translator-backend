"""Async/Streaming Support — Real-time pipeline execution.

Enables streaming translation where each pipeline step runs
as audio comes in, not after it finishes.

Usage:
    from ailang_integration.runtime.async_stream import StreamingPipeline

    async for chunk in StreamingPipeline.stream(audio_chunks, context):
        send_to_tts(chunk)
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StreamingPipeline:
    """Async streaming pipeline that processes chunks as they arrive.

    Instead of waiting for full audio, this processes partial results
    and yields translated chunks as they become ready.
    """

    def __init__(self, steps: Optional[List[Callable]] = None):
        self._steps: List[Callable] = steps or []
        self._buffer: List[Dict[str, Any]] = []
        self._running = False

    def add_step(self, step: Callable) -> "StreamingPipeline":
        self._steps.append(step)
        return self

    async def stream(
        self,
        input_chunks: AsyncIterator[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Process input chunks through the pipeline, yielding results as ready.

        Args:
            input_chunks: Async iterator of audio/text chunks
            context: Translation context

        Yields:
            Processed chunks with translated text and TTS config
        """
        self._running = True
        chunk_index = 0

        async for chunk in input_chunks:
            if not self._running:
                break

            chunk_index += 1
            start = time.time()

            # Run each step on the chunk
            result = chunk
            for step in self._steps:
                try:
                    if asyncio.iscoroutinefunction(step):
                        result = await step(result, context)
                    else:
                        result = step(result, context)
                except Exception as e:
                    logger.error(f"Stream step failed: {e}")
                    result["_stream_error"] = str(e)
                    break

            elapsed = (time.time() - start) * 1000
            result["_chunk_index"] = chunk_index
            result["_chunk_latency_ms"] = elapsed

            yield result

        self._running = False

    def stop(self) -> None:
        """Stop the streaming pipeline."""
        self._running = False


class ChunkBuffer:
    """Buffers and merges partial results for smooth output.

    Handles the case where STT sends partial transcripts that get
    refined — only yields when confident enough.
    """

    def __init__(self, confidence_threshold: float = 0.7, max_buffer_ms: float = 2000):
        self.confidence_threshold = confidence_threshold
        self.max_buffer_ms = max_buffer_ms
        self._buffer: List[Dict[str, Any]] = []
        self._last_emit_time: float = 0

    def add(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a chunk. Returns merged result if ready to emit, None otherwise."""
        self._buffer.append(chunk)

        confidence = chunk.get("confidence", chunk.get("stt_confidence", 0.5))
        is_final = chunk.get("is_final", False)
        elapsed = (time.time() - self._last_emit_time) * 1000 if self._last_emit_time else 0

        # Emit if: high confidence, final chunk, or buffer timeout
        if is_final or confidence >= self.confidence_threshold or elapsed > self.max_buffer_ms:
            merged = self._merge_buffer()
            self._buffer.clear()
            self._last_emit_time = time.time()
            return merged

        return None

    def _merge_buffer(self) -> Dict[str, Any]:
        """Merge buffered chunks into one."""
        if not self._buffer:
            return {}
        if len(self._buffer) == 1:
            return self._buffer[0]

        # Use the last chunk's text (most refined) with merged metadata
        result = dict(self._buffer[-1])
        result["_chunks_merged"] = len(self._buffer)
        return result

    def flush(self) -> Optional[Dict[str, Any]]:
        """Force emit whatever is in the buffer."""
        if self._buffer:
            merged = self._merge_buffer()
            self._buffer.clear()
            return merged
        return None


async def create_streaming_pipeline(
    steps: List[Callable],
    context: Dict[str, Any],
    confidence_threshold: float = 0.7,
) -> StreamingPipeline:
    """Factory for creating a configured streaming pipeline.

    Args:
        steps: List of pipeline step functions
        context: Translation context
        confidence_threshold: Min confidence to emit chunks

    Returns:
        Configured StreamingPipeline
    """
    pipeline = StreamingPipeline(steps)
    return pipeline
