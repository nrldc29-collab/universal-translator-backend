"""
Security utilities for sensitive data handling.

This module provides functions for redacting sensitive information in URLs and secrets,
hashing secrets for comparison without storing plaintext, and other security-related utilities.
"""
import hashlib
import logging
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

# Query parameter keys that contain sensitive information
SENSITIVE_QUERY_KEYS = {"api_key", "token", "access_token", "key"}


def redact_secret(value: Optional[str], visible_prefix: int = 4) -> str:
    """
    Redact a secret value for logging or display purposes.
    
    Shows only the first few characters of the secret followed by asterisks.
    This allows verification of the secret without exposing the full value.
    
    Args:
        value: The secret value to redact
        visible_prefix: Number of characters to show at the beginning
        
    Returns:
        Redacted secret string with only the prefix visible
    """
    if not value:
        logger.debug("Redacting empty secret value")
        return ""

    if len(value) <= visible_prefix:
        logger.debug("Secret too short for partial redaction, using full redaction")
        return "***"

    redacted = f"{value[:visible_prefix]}***"
    logger.debug(f"Secret redacted with {visible_prefix} visible characters")
    return redacted


def hash_secret(value: Optional[str]) -> str:
    """
    Hash a secret value using SHA-256.
    
    Creates a one-way hash of the secret for comparison purposes.
    Useful for verifying secrets without storing plaintext values.
    
    Args:
        value: The secret value to hash
        
    Returns:
        Hexadecimal SHA-256 hash of the secret
    """
    if not value:
        logger.debug("Hashing empty secret value")
        return ""

    hash_value = hashlib.sha256(value.encode("utf-8")).hexdigest()
    logger.debug("Secret hashed using SHA-256")
    return hash_value


def short_hash_secret(value: Optional[str]) -> str:
    """
    Create a short hash of a secret value.
    
    Returns the first 12 characters of the SHA-256 hash.
    Useful for compact identifiers and logging.
    
    Args:
        value: The secret value to hash
        
    Returns:
        First 12 characters of the SHA-256 hash
    """
    digest = hash_secret(value)

    if not digest:
        logger.debug("Short hash failed: empty digest")
        return ""

    short_hash = digest[:12]
    logger.debug(f"Short hash generated (12 characters)")
    return short_hash


def redact_url(url: str) -> str:
    """
    Redact sensitive query parameters from a URL.
    
    Removes or masks sensitive parameters like API keys, tokens, and access tokens
    from the query string to prevent them from being logged or displayed.
    
    Args:
        url: The URL to redact
        
    Returns:
        URL with sensitive query parameters redacted
    """
    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)

    redacted_pairs = []
    redacted_count = 0

    for key, value in query_pairs:
        if key.lower() in SENSITIVE_QUERY_KEYS:
            redacted_pairs.append((key, redact_secret(value)))
            redacted_count += 1
        else:
            redacted_pairs.append((key, value))

    if redacted_count > 0:
        logger.debug(f"Redacted {redacted_count} sensitive parameters from URL")

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(redacted_pairs),
            parts.fragment,
        )
    )
