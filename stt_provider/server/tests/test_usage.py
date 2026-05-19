"""
Tests for usage tracking functionality.

This module tests the usage tracking system which tracks audio processing
usage per API key. Tests verify audio seconds estimation based on bytes,
sample rate, and channels, as well as usage store key label reuse behavior.

Run tests:
    pytest server/tests/test_usage.py

Purpose:
This ensures that the usage tracking system accurately estimates audio
processing time for billing and monitoring purposes, and properly manages
usage counters per API key.
"""
import logging

import pytest

from stt_server import usage

logger = logging.getLogger(__name__)


def test_usage_counter_estimates_audio_seconds(monkeypatch):
    """
    Test that usage counter estimates audio seconds correctly.
    
    Verifies that the UsageCounter correctly calculates estimated audio
    seconds based on bytes received, sample rate, and channel count.
    """
    logger.info("Testing usage counter audio seconds estimation")
    
    monkeypatch.setattr(usage.settings, "sample_rate", 16000)
    monkeypatch.setattr(usage.settings, "channels", 1)

    counter = usage.UsageCounter()
    counter.add_audio_bytes(32000)

    assert counter.estimated_audio_seconds == pytest.approx(1.0)
    assert counter.as_dict()["estimated_audio_seconds"] == 1.0
    
    logger.info("Usage counter audio seconds estimation test passed")


def test_usage_store_reuses_key_labels():
    """
    Test that usage store reuses counters for key labels.
    
    Verifies that the UsageStore returns the same UsageCounter instance
    for the same key label, maintaining consistent tracking per API key.
    """
    logger.info("Testing usage store key label reuse")
    
    store = usage.UsageStore()

    first = store.get("cli")
    second = store.get("cli")
    unknown = store.get("")

    assert first is second
    assert store.by_key_label["cli"] is first
    assert store.by_key_label["unknown"] is unknown
    
    logger.info("Usage store key label reuse test passed")
