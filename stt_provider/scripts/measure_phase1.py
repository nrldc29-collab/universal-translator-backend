"""
Phase 1 performance measurement script for the STT application.

This script measures and summarizes performance metrics for Phase 1 of the
STT system, including time to first partial result and time between partials.
It calculates percentiles, averages, and writes results to a JSON file.

The metrics captured include:
- Time to first partial result (latency to first transcription)
- Time between partial results (inter-partial latency)
- Word Error Rate (WER) with and without hotwords

Example:
    python scripts/measure_phase1.py
"""
import json
import logging
import statistics
import time
from pathlib import Path

logger = logging.getLogger(__name__)

RESULTS_PATH = Path("phase1-results.json")


def percentile(values: list[float], percentile_value: int) -> float:
    """
    Calculate a percentile from a list of values.
    
    Computes the specified percentile value from the sorted list of values.
    Uses linear interpolation between the two closest data points.
    
    Args:
        values: List of numeric values
        percentile_value: Percentile to calculate (0-100)
        
    Returns:
        The percentile value, or 0.0 if the list is empty
    """
    if not values:
        logger.warning("Attempted to calculate percentile on empty list")
        return 0.0

    values_sorted = sorted(values)
    index = round((percentile_value / 100) * (len(values_sorted) - 1))
    result = values_sorted[index]
    
    logger.debug(f"Calculated {percentile_value}th percentile: {result}")
    return result


def summarize_metric(name: str, values: list[float]) -> dict:
    """
    Summarize a metric with statistical calculations.
    
    Calculates count, median (p50), 95th percentile (p95), and average
    for a list of metric values.
    
    Args:
        name: Name of the metric being summarized
        values: List of metric values in milliseconds
        
    Returns:
        Dictionary containing metric name, count, p50, p95, and average
    """
    summary = {
        "metric": name,
        "count": len(values),
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "avg_ms": statistics.mean(values) if values else 0.0,
    }
    
    logger.info(f"Summarized metric '{name}': {summary['count']} samples, "
                f"p50={summary['p50_ms']:.2f}ms, p95={summary['p95_ms']:.2f}ms, "
                f"avg={summary['avg_ms']:.2f}ms")
    
    return summary


def main() -> None:
    """
    Main function to collect and write Phase 1 performance metrics.
    
    Collects timing measurements from WebSocket client, REST transcription
    tests, or load-test harness. Calculates statistical summaries and
    writes results to a JSON file.
    
    Note: This is a template script. Replace the placeholder empty lists
    with actual timing data captured from your measurements.
    """
    logger.info("Starting Phase 1 performance measurement")
    
    # Replace these placeholder values with real timings captured from your
    # WebSocket client, REST transcription tests, or load-test harness.
    time_to_first_partial_ms = []
    time_between_partials_ms = []
    
    logger.warning(
        "Using placeholder empty timing lists. "
        "Replace with actual measurement data before use."
    )

    results = {
        "release": "v0.2.0",
        "captured_at_unix": int(time.time()),
        "metrics": [
            summarize_metric("time_to_first_partial", time_to_first_partial_ms),
            summarize_metric("time_between_partials", time_between_partials_ms),
        ],
        "wer": {
            "baseline_without_hotwords": None,
            "baseline_with_hotwords": None,
        },
    }

    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    logger.info(f"Wrote Phase 1 results to {RESULTS_PATH}")
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
