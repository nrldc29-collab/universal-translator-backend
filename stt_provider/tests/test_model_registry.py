"""
Tests for model registry validation.

This module tests the model ID validation logic for Triton domain models.
Tests verify that only approved model IDs are accepted and unknown models are rejected,
preventing accidental routing to unloaded or unsupported models.

Run tests:
    pytest tests/test_model_registry.py

Purpose:
This ensures that the model registry properly validates model IDs against the approved list,
supporting the Phase 4 domain-model feature for self-hosted accuracy tuning while preventing
routing to unknown or unloaded Triton models.
"""
import logging

import pytest

from stt_server.model_registry import validate_model_id

logger = logging.getLogger(__name__)


def test_accepts_allowed_model_id():
    """
    Test that allowed model IDs are accepted.
    
    Verifies that all approved Triton domain model IDs pass validation
    and are returned unchanged.
    """
    logger.info("Testing allowed model IDs are accepted")
    
    assert validate_model_id("parakeet-general") == "parakeet-general"
    assert validate_model_id("parakeet-medical") == "parakeet-medical"
    assert validate_model_id("parakeet-legal") == "parakeet-legal"
    assert validate_model_id("parakeet-finance") == "parakeet-finance"
    assert validate_model_id("parakeet-contact-center") == "parakeet-contact-center"
    
    logger.info("Allowed model ID acceptance test passed")


def test_rejects_unknown_model_id():
    """
    Test that unknown model IDs are rejected.
    
    Verifies that attempting to validate an unknown or unsupported model ID
    raises a ValueError with an appropriate error message.
    """
    logger.info("Testing unknown model IDs are rejected")
    
    with pytest.raises(ValueError) as exc:
        validate_model_id("unknown-model")

    assert "Unsupported model_id: unknown-model" in str(exc.value)
    
    logger.info("Unknown model ID rejection test passed")
