"""
Type definitions for the STT provider.

This module provides type aliases and stubs for optional database features.
For basic STT functionality without PostgreSQL, these are minimal stubs.
"""
from typing import Any

# Stub for AsyncPG connection when database is not configured
AsyncPGConnection = Any
