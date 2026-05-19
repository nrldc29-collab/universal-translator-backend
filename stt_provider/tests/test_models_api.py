"""
Tests for models API endpoint.

This module tests the GET /v1/models endpoint that lists available domain models.
Tests verify that all approved Triton domain models are returned and that
parakeet-general is marked as the default model.

Run tests:
    pytest tests/test_models_api.py

Purpose:
This ensures that the models API correctly exposes the approved domain models
for Phase 4 self-hosted accuracy tuning, allowing clients to discover available
models and identify the default model for transcription requests.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_list_models_returns_allowed_domain_models(app):
    """
    Test that list models returns all allowed domain models.
    
    Verifies that the GET /v1/models endpoint returns a 200 status code
    and includes all approved Triton domain model IDs in the response.
    """
    logger.info("Testing list models returns allowed domain models")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v1/models")

    assert response.status_code == 200

    body = response.json()
    model_ids = {model["id"] for model in body["models"]}

    assert "parakeet-general" in model_ids
    assert "parakeet-medical" in model_ids
    assert "parakeet-legal" in model_ids
    assert "parakeet-finance" in model_ids
    assert "parakeet-contact-center" in model_ids
    
    logger.info("List models domain models test passed")


@pytest.mark.asyncio
async def test_list_models_marks_general_as_default(app):
    """
    Test that parakeet-general is marked as the default model.
    
    Verifies that the GET /v1/models endpoint marks parakeet-general
    as the default model in the response, ensuring clients can identify
    which model to use by default.
    """
    logger.info("Testing parakeet-general is marked as default")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v1/models")

    assert response.status_code == 200

    models = response.json()["models"]
    default_models = [
        model
        for model in models
        if model["default"] is True
    ]

    assert len(default_models) == 1
    assert default_models[0]["id"] == "parakeet-general"
    
    logger.info("Default model marking test passed")
