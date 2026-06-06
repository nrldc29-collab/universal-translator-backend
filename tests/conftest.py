"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_usage_limiter():
    from backend.security import usage_limiter

    usage_limiter.reset()
    yield
    usage_limiter.reset()
