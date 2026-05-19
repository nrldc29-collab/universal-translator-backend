"""
Tests for tenant rollout configuration.

This module tests the loading and retrieval of tenant rollout configuration.
Tests verify that rollout config includes backend routing, fallback behavior, stream limits,
model selection, and regional routing for the self-hosted tenant-by-tenant rollout.

Run tests:
    pytest tests/test_tenant_rollout.py

Purpose:
This ensures that tenant rollout configuration can be loaded consistently for backend routing,
fallback behavior, stream limits, model selection, and regional routing during the self-hosted
tenant-by-tenant rollout. This supports the guide's Phase 2B requirement for rollout per tenant
tier while keeping Whisper available as fallback.
"""
import logging

from uuid import UUID

import pytest

from stt_server.tenant_rollout import (
    get_tenant_rollout_config,
    list_tenants_by_backend,
)

logger = logging.getLogger(__name__)


TENANT_ID = UUID("00000000-0000-0000-0000-000000000123")


class FakeDb:
    """
    Fake database for testing tenant rollout configuration queries.
    
    Simulates database fetchrow and fetch operations for tenant configuration data.
    """
    async def fetchrow(self, query, tenant_id):
        """
        Simulate database fetchrow operation for tenant config.
        
        Args:
            query: The SQL query that would be executed.
            tenant_id: The tenant ID to fetch configuration for.
            
        Returns:
            A dictionary with tenant configuration if tenant exists, None otherwise.
        """
        if tenant_id != TENANT_ID:
            return None

        return {
            "id": TENANT_ID,
            "backend": "triton",
            "allow_backend_fallback": True,
            "max_concurrent_streams": 100,
            "default_model_id": "parakeet-general",
            "home_region": "us-east-1",
        }

    async def fetch(self, query, backend, limit):
        """
        Simulate database fetch operation for listing tenants by backend.
        
        Args:
            query: The SQL query that would be executed.
            backend: The backend name to filter tenants by.
            limit: The maximum number of results to return.
            
        Returns:
            A list of dictionaries with tenant configuration.
        """
        return [
            {
                "id": TENANT_ID,
                "backend": backend,
                "allow_backend_fallback": True,
                "max_concurrent_streams": 100,
                "default_model_id": "parakeet-general",
                "home_region": "us-east-1",
            }
        ]


@pytest.mark.asyncio
async def test_get_tenant_rollout_config_returns_all_rollout_fields():
    """
    Test that tenant rollout config returns all rollout fields.
    
    Verifies that get_tenant_rollout_config returns a complete configuration object
    with tenant ID, backend, fallback policy, stream limits, default model, and home region.
    """
    logger.info("Testing tenant rollout config returns all rollout fields")
    
    config = await get_tenant_rollout_config(
        FakeDb(),
        TENANT_ID,
    )

    assert config.tenant_id == TENANT_ID
    assert config.backend == "triton"
    assert config.allow_backend_fallback is True
    assert config.max_concurrent_streams == 100
    assert config.default_model_id == "parakeet-general"
    assert config.home_region == "us-east-1"
    
    logger.info("Tenant rollout config fields test passed")


@pytest.mark.asyncio
async def test_get_tenant_rollout_config_raises_for_missing_tenant():
    """
    Test that tenant rollout config raises ValueError for missing tenant.
    
    Verifies that get_tenant_rollout_config raises a ValueError when the tenant
    does not exist in the database.
    """
    logger.info("Testing tenant rollout config raises for missing tenant")
    
    missing_tenant_id = UUID("00000000-0000-0000-0000-000000000999")

    with pytest.raises(ValueError):
        await get_tenant_rollout_config(
            FakeDb(),
            missing_tenant_id,
        )
    
    logger.info("Missing tenant error test passed")


@pytest.mark.asyncio
async def test_list_tenants_by_backend_returns_matching_tenants():
    """
    Test that list_tenants_by_backend returns matching tenants.
    
    Verifies that list_tenants_by_backend returns a list of tenants configured
    for the specified backend, with correct tenant IDs and backend assignments.
    """
    logger.info("Testing list tenants by backend returns matching tenants")
    
    tenants = await list_tenants_by_backend(
        FakeDb(),
        backend="triton",
        limit=100,
    )

    assert len(tenants) == 1
    assert tenants[0].backend == "triton"
    assert tenants[0].tenant_id == TENANT_ID
    
    logger.info("List tenants by backend test passed")
