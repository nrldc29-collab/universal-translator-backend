"""
API key authentication and authorization utilities.

This module provides functions for managing API keys, validating authentication
credentials, and extracting metadata from API keys such as labels and fingerprints.
"""
import logging
from typing import Optional

from stt_server.config import settings
from stt_server.security import short_hash_secret

logger = logging.getLogger(__name__)


def get_api_key_map() -> dict[str, str]:
    """
    Build a mapping of API keys to their labels.
    
    Parses the configured API keys from settings and builds a dictionary
    mapping each API key to its associated label. Supports both simple
    keys (assigned "unnamed" label) and labeled keys in "label:key" format.
    
    Returns:
        Dictionary mapping API keys to their labels
    """
    keys: dict[str, str] = {}

    # Add default API key if configured
    if settings.stt_api_key:
        keys[settings.stt_api_key] = "default"

    # Parse comma-separated API keys with optional labels
    for item in settings.stt_api_keys.split(","):
        clean_item = item.strip()

        if not clean_item:
            continue

        if ":" in clean_item:
            label, key = clean_item.split(":", 1)
            label = label.strip()
            key = key.strip()

            if key:
                keys[key] = label or "unnamed"
        else:
            keys[clean_item] = "unnamed"

    return keys


def get_allowed_api_keys() -> set[str]:
    """
    Get the set of all allowed API keys.
    
    Returns the set of API keys that are valid for authentication.
    
    Returns:
        Set of allowed API key strings
    """
    return set(get_api_key_map().keys())


def is_valid_api_key(api_key: Optional[str]) -> bool:
    """
    Validate an API key.
    
    Checks if the provided API key is in the set of allowed keys.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        True if the API key is valid, False otherwise
    """
    if not api_key:
        return False

    return api_key in get_allowed_api_keys()


def api_key_fingerprint(api_key: Optional[str]) -> str:
    """
    Generate a fingerprint for an API key.
    
    Creates a short hash of the API key for logging and identification
    purposes without exposing the actual key value.
    
    Args:
        api_key: The API key to fingerprint
        
    Returns:
        Short hash fingerprint of the API key
    """
    return short_hash_secret(api_key)


def api_key_label(api_key: Optional[str]) -> str:
    """
    Get the label associated with an API key.
    
    Returns the configured label for the API key, or an empty string
    if the key is not found or is None.
    
    Args:
        api_key: The API key to look up
        
    Returns:
        Label associated with the API key, or empty string if not found
    """
    if not api_key:
        return ""

    return get_api_key_map().get(api_key, "")
