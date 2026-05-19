"""
Encryption utilities for sensitive data.

This module provides encryption and decryption functions using Fernet symmetric encryption
from the cryptography library. It is used to protect sensitive data like speaker embeddings.
"""
import base64
import os
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def get_encryption_key() -> bytes:
    """
    Get the encryption key from environment variable.
    
    Retrieves the SPEAKER_EMBEDDING_ENCRYPTION_KEY environment variable,
    validates it meets minimum length requirements, and returns it as bytes.
    
    Returns:
        Encryption key as bytes (must be at least 32 bytes for Fernet)
        
    Raises:
        RuntimeError: If environment variable is not set or key is invalid
        ValueError: If key is shorter than minimum required length
    """
    raw_key = os.environ.get("SPEAKER_EMBEDDING_ENCRYPTION_KEY")
    
    if not raw_key:
        raise RuntimeError(
            "SPEAKER_EMBEDDING_ENCRYPTION_KEY environment variable is not set. "
            "Please set a valid Fernet key (32+ bytes)."
        )

    try:
        key_bytes = raw_key.encode("utf-8")
        if len(key_bytes) < 32:
            raise ValueError(
                f"Encryption key must be at least 32 bytes, got {len(key_bytes)} bytes"
            )
        return key_bytes
    except Exception as exc:
        raise RuntimeError(
            "Invalid SPEAKER_EMBEDDING_ENCRYPTION_KEY. "
            "Ensure the environment variable is set with a valid Fernet key (32+ bytes)."
        ) from exc


def encrypt_bytes(value: bytes, encryption_key: Optional[bytes] = None) -> bytes:
    """
    Encrypt bytes using Fernet symmetric encryption.
    
    Args:
        value: Data to encrypt
        encryption_key: Optional encryption key. If not provided, will attempt
                      to get from environment variable.
                      
    Returns:
        Encrypted bytes
        
    Raises:
        RuntimeError: If no encryption key is provided and environment variable is not set
        ValueError: If value is empty
    """
    if not value:
        raise ValueError("Cannot encrypt empty data")
    
    key = encryption_key or get_encryption_key()
    
    try:
        fernet = Fernet(key)
        encrypted = fernet.encrypt(value)
        logger.debug("Successfully encrypted data")
        return encrypted
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_bytes(value: bytes, encryption_key: Optional[bytes] = None) -> bytes:
    """
    Decrypt bytes using Fernet symmetric encryption.
    
    Args:
        value: Data to decrypt
        encryption_key: Optional encryption key. If not provided, will attempt
                      to get from environment variable.
                      
    Returns:
        Decrypted bytes
        
    Raises:
        RuntimeError: If no encryption key is provided and environment variable is not set
        InvalidToken: If decryption fails (wrong key or corrupted data)
        ValueError: If value is empty
    """
    if not value:
        raise ValueError("Cannot decrypt empty data")
    
    key = encryption_key or get_encryption_key()
    
    try:
        fernet = Fernet(key)
        decrypted = fernet.decrypt(value)
        logger.debug("Successfully decrypted data")
        return decrypted
    except InvalidToken as e:
        logger.error("Decryption failed: Invalid token (wrong key or corrupted data)")
        raise
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise


def generate_fernet_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    This function generates a cryptographically secure key suitable for use
    with Fernet encryption. The key should be stored securely and used as the
    SPEAKER_EMBEDDING_ENCRYPTION_KEY environment variable.
    
    Returns:
        URL-safe base64-encoded Fernet key as a string
        
    Example:
        >>> key = generate_fernet_key()
        >>> print(key)
        'Z7mQr9K5p8X4vN2wJ6tY1sF3gH0lP5uV8rA2bC4dE6fG8hI0jK2lM4nO6pQ8rS0tU2vW4xY6z'
    """
    key = Fernet.generate_key()
    logger.info("Generated new Fernet encryption key")
    return key.decode("utf-8")


def validate_fernet_key(key: str) -> bool:
    """
    Validate if a key is a valid Fernet key.
    
    Args:
        key: Key string to validate
        
    Returns:
        True if key is valid, False otherwise
    """
    try:
        key_bytes = key.encode("utf-8")
        if len(key_bytes) < 32:
            return False
        
        # Try to create a Fernet instance with the key
        Fernet(key_bytes)
        return True
    except Exception:
        return False
