"""
Metrics collection and Prometheus rendering module.

This module provides data structures for tracking STT service metrics
including session counts, transcript counts, audio statistics, and streaming-specific
metrics. It also provides functions to render metrics in Prometheus format.
"""
from dataclasses import dataclass
from typing import Optional

from stt_server.config import settings
from stt_server.usage import usage_store


@dataclass
class Metrics:
    """
    STT service metrics dataclass.
    
    Tracks various metrics for the STT service including session counts,
    transcript counts, audio statistics, and streaming-specific metrics.
    
    Attributes:
        sessions_started: Total number of sessions started
        sessions_closed: Total number of sessions closed
        partial_transcripts: Total partial transcript events emitted
        final_transcripts: Total final transcript events emitted
        errors: Total structured error events emitted
        audio_frames_received: Total binary audio frames received
        audio_bytes_received: Total binary audio bytes received
        streaming_sessions_active: Current active streaming sessions
        streaming_audio_seconds_processed: Total audio seconds processed in streaming mode
        streaming_time_to_first_partial_ms: Average time to first partial transcript (ms)
        streaming_time_between_partials_ms: Average time between partial transcripts (ms)
        streaming_buffer_overruns: Total buffer overrun events
        streaming_connection_timeouts: Total connection timeout events
        streaming_avg_latency_ms: Average streaming latency in milliseconds
        streaming_latency_samples: Total number of latency samples
        streaming_word_accuracy: Average word accuracy score
        streaming_audio_quality_score: Average audio quality score
        streaming_reconnection_count: Total streaming reconnection attempts
    """
    sessions_started: int = 0
    sessions_closed: int = 0
    partial_transcripts: int = 0
    final_transcripts: int = 0
    errors: int = 0
    audio_frames_received: int = 0
    audio_bytes_received: int = 0
    # Streaming-specific metrics
    streaming_sessions_active: int = 0
    streaming_audio_seconds_processed: float = 0.0
    streaming_time_to_first_partial_ms: float = 0.0
    streaming_time_between_partials_ms: float = 0.0
    streaming_buffer_overruns: int = 0
    streaming_connection_timeouts: int = 0
    # Streaming quality metrics
    streaming_avg_latency_ms: float = 0.0
    streaming_latency_samples: int = 0
    streaming_word_accuracy: float = 0.0
    streaming_audio_quality_score: float = 0.0
    streaming_reconnection_count: int = 0

    def restore_from_usage_store(self) -> None:
        """
        Restore metrics from the usage store.
        
        Aggregates metrics from all API key labels in the usage store
        and updates the current metrics values.
        """
        self.sessions_started = sum(
            counter.sessions_started for counter in usage_store.by_key_label.values()
        )
        self.sessions_closed = sum(
            counter.sessions_closed for counter in usage_store.by_key_label.values()
        )
        self.partial_transcripts = sum(
            counter.partial_transcripts for counter in usage_store.by_key_label.values()
        )
        self.final_transcripts = sum(
            counter.final_transcripts for counter in usage_store.by_key_label.values()
        )
        self.errors = sum(
            counter.errors for counter in usage_store.by_key_label.values()
        )
        self.audio_frames_received = sum(
            counter.audio_frames_received for counter in usage_store.by_key_label.values()
        )
        self.audio_bytes_received = sum(
            counter.audio_bytes_received for counter in usage_store.by_key_label.values()
        )


# Global metrics instance
metrics = Metrics()


def safe_label(value: str) -> str:
    """
    Sanitize a label value for Prometheus metrics.
    
    Escapes special characters that would break Prometheus label formatting.
    
    Args:
        value: Label value to sanitize
        
    Returns:
        Sanitized label value safe for Prometheus
    """
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "_")


def render_prometheus_metrics(
    active_connections: int,
    max_active_connections: int,
    active_connections_by_key_label: Optional[dict[str, int]] = None,
) -> str:
    """
    Render metrics in Prometheus format.
    
    Generates Prometheus-compatible metric output including connection counts,
    session metrics, transcript counts, audio statistics, streaming metrics,
    and per-API-key breakdowns.
    
    Args:
        active_connections: Current active WebSocket connections
        max_active_connections: Maximum allowed active connections
        active_connections_by_key_label: Optional dict of connections by API key label
        
    Returns:
        Prometheus-formatted metrics string
    """
    active_connections_by_key_label = active_connections_by_key_label or {}

    lines = [
        "# HELP stt_active_connections Current active WebSocket STT connections.",
        "# TYPE stt_active_connections gauge",
        f"stt_active_connections {active_connections}",
        "",
        "# HELP stt_key_active_connections Current active WebSocket STT connections "
        "by API key label.",
        "# TYPE stt_key_active_connections gauge",
    ]

    for label, value in sorted(active_connections_by_key_label.items()):
        safe = safe_label(label)
        lines.append(f'stt_key_active_connections{{key_label="{safe}"}} {value}')

    lines.extend(
        [
            "",
            "# HELP stt_max_active_connections Maximum allowed active WebSocket STT connections.",
            "# TYPE stt_max_active_connections gauge",
            f"stt_max_active_connections {max_active_connections}",
            "",
            "# HELP stt_sessions_started_total Total STT sessions started.",
            "# TYPE stt_sessions_started_total counter",
            f"stt_sessions_started_total {metrics.sessions_started}",
            "",
            "# HELP stt_sessions_closed_total Total STT sessions closed.",
            "# TYPE stt_sessions_closed_total counter",
            f"stt_sessions_closed_total {metrics.sessions_closed}",
            "",
            "# HELP stt_partial_transcripts_total Total partial transcript events emitted.",
            "# TYPE stt_partial_transcripts_total counter",
            f"stt_partial_transcripts_total {metrics.partial_transcripts}",
            "",
            "# HELP stt_final_transcripts_total Total final transcript events emitted.",
            "# TYPE stt_final_transcripts_total counter",
            f"stt_final_transcripts_total {metrics.final_transcripts}",
            "",
            "# HELP stt_errors_total Total structured error events emitted.",
            "# TYPE stt_errors_total counter",
            f"stt_errors_total {metrics.errors}",
            "",
            "# HELP stt_audio_frames_received_total Total binary audio frames received.",
            "# TYPE stt_audio_frames_received_total counter",
            f"stt_audio_frames_received_total {metrics.audio_frames_received}",
            "",
            "# HELP stt_audio_bytes_received_total Total binary audio bytes received.",
            "# TYPE stt_audio_bytes_received_total counter",
            f"stt_audio_bytes_received_total {metrics.audio_bytes_received}",
            "",
            "# HELP stt_streaming_sessions_active Current active streaming sessions.",
            "# TYPE stt_streaming_sessions_active gauge",
            f"stt_streaming_sessions_active {metrics.streaming_sessions_active}",
            "",
            "# HELP stt_streaming_audio_seconds_processed_total Total audio seconds processed in streaming mode.",
            "# TYPE stt_streaming_audio_seconds_processed_total counter",
            f"stt_streaming_audio_seconds_processed_total {metrics.streaming_audio_seconds_processed:.2f}",
            "",
            "# HELP stt_streaming_time_to_first_partial_ms Average time to first partial transcript in milliseconds.",
            "# TYPE stt_streaming_time_to_first_partial_ms gauge",
            f"stt_streaming_time_to_first_partial_ms {metrics.streaming_time_to_first_partial_ms:.2f}",
            "",
            "# HELP stt_streaming_time_between_partials_ms Average time between partial transcripts in milliseconds.",
            "# TYPE stt_streaming_time_between_partials_ms gauge",
            f"stt_streaming_time_between_partials_ms {metrics.streaming_time_between_partials_ms:.2f}",
            "",
            "# HELP stt_streaming_buffer_overruns_total Total buffer overrun events.",
            "# TYPE stt_streaming_buffer_overruns_total counter",
            f"stt_streaming_buffer_overruns_total {metrics.streaming_buffer_overruns}",
            "",
            "# HELP stt_streaming_connection_timeouts_total Total connection timeout events.",
            "# TYPE stt_streaming_connection_timeouts_total counter",
            f"stt_streaming_connection_timeouts_total {metrics.streaming_connection_timeouts}",
            "",
            "# HELP stt_streaming_avg_latency_ms Average streaming latency in milliseconds.",
            "# TYPE stt_streaming_avg_latency_ms gauge",
            f"stt_streaming_avg_latency_ms {metrics.streaming_avg_latency_ms:.2f}",
            "",
            "# HELP stt_streaming_latency_samples Total number of latency samples.",
            "# TYPE stt_streaming_latency_samples counter",
            f"stt_streaming_latency_samples {metrics.streaming_latency_samples}",
            "",
            "# HELP stt_streaming_word_accuracy Average word accuracy score.",
            "# TYPE stt_streaming_word_accuracy gauge",
            f"stt_streaming_word_accuracy {metrics.streaming_word_accuracy:.4f}",
            "",
            "# HELP stt_streaming_audio_quality_score Average audio quality score.",
            "# TYPE stt_streaming_audio_quality_score gauge",
            f"stt_streaming_audio_quality_score {metrics.streaming_audio_quality_score:.4f}",
            "",
            "# HELP stt_streaming_reconnection_count Total streaming reconnection attempts.",
            "# TYPE stt_streaming_reconnection_count counter",
            f"stt_streaming_reconnection_count {metrics.streaming_reconnection_count}",
        ]
    )

    # Per-API-key metrics
    lines.extend(
        [
            "",
            "# HELP stt_key_sessions_started_total Total STT sessions started by API key label.",
            "# TYPE stt_key_sessions_started_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        lines.append(
            f'stt_key_sessions_started_total{{key_label="{safe}"}} '
            f"{counter.sessions_started}"
        )

    lines.extend(
        [
            "",
            "# HELP stt_key_sessions_closed_total Total STT sessions closed by API key label.",
            "# TYPE stt_key_sessions_closed_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        lines.append(
            f'stt_key_sessions_closed_total{{key_label="{safe}"}} '
            f"{counter.sessions_closed}"
        )

    lines.extend(
        [
            "",
            "# HELP stt_key_partial_transcripts_total Total partial transcript events "
            "by API key label.",
            "# TYPE stt_key_partial_transcripts_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        lines.append(
            f'stt_key_partial_transcripts_total{{key_label="{safe}"}} '
            f"{counter.partial_transcripts}"
        )

    lines.extend(
        [
            "",
            "# HELP stt_key_final_transcripts_total Total final transcript events "
            "by API key label.",
            "# TYPE stt_key_final_transcripts_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        lines.append(
            f'stt_key_final_transcripts_total{{key_label="{safe}"}} '
            f"{counter.final_transcripts}"
        )

    lines.extend(
        [
            "",
            "# HELP stt_key_errors_total Total structured errors by API key label.",
            "# TYPE stt_key_errors_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        lines.append(f'stt_key_errors_total{{key_label="{safe}"}} {counter.errors}')

    lines.extend(
        [
            "",
            "# HELP stt_key_audio_frames_received_total Total binary audio frames "
            "by API key label.",
            "# TYPE stt_key_audio_frames_received_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        lines.append(
            f'stt_key_audio_frames_received_total{{key_label="{safe}"}} '
            f"{counter.audio_frames_received}"
        )

    lines.extend(
        [
            "",
            "# HELP stt_key_audio_bytes_received_total Total binary audio bytes by API key label.",
            "# TYPE stt_key_audio_bytes_received_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        lines.append(
            f'stt_key_audio_bytes_received_total{{key_label="{safe}"}} '
            f"{counter.audio_bytes_received}"
        )

    total_estimated_audio_seconds = sum(
        counter.estimated_audio_seconds
        for counter in usage_store.by_key_label.values()
    )

    lines.extend(
        [
            "",
            "# HELP stt_estimated_audio_seconds_total Estimated total audio seconds received.",
            "# TYPE stt_estimated_audio_seconds_total counter",
            f"stt_estimated_audio_seconds_total {round(total_estimated_audio_seconds, 3)}",
            "",
            "# HELP stt_key_estimated_audio_seconds_total Estimated total audio "
            "seconds received by API key label.",
            "# TYPE stt_key_estimated_audio_seconds_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        lines.append(
            f'stt_key_estimated_audio_seconds_total{{key_label="{safe}"}} '
            f'{round(counter.estimated_audio_seconds, 3)}'
        )

    total_estimated_cost = round(
        (total_estimated_audio_seconds / 3600) * settings.billing_rate_per_audio_hour,
        6,
    )

    lines.extend(
        [
            "",
            "# HELP stt_estimated_cost_total Estimated total billing cost.",
            "# TYPE stt_estimated_cost_total counter",
            f"stt_estimated_cost_total {total_estimated_cost}",
            "",
            "# HELP stt_key_estimated_cost_total Estimated billing cost by API key label.",
            "# TYPE stt_key_estimated_cost_total counter",
        ]
    )

    for label, counter in sorted(usage_store.by_key_label.items()):
        safe = safe_label(label)
        key_cost = round(
            (counter.estimated_audio_seconds / 3600) * settings.billing_rate_per_audio_hour,
            6,
        )
        lines.append(
            f'stt_key_estimated_cost_total{{key_label="{safe}"}} {key_cost}'
        )

    lines.append("")

    result = "\n".join(lines)
    logger.debug(f"Rendered {len(lines)} Prometheus metric lines")
    return result
