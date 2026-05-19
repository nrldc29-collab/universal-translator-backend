"""
Tests for speaker embedding encryption functionality.

This module tests the encryption and decryption of speaker embeddings,
ensuring that biometric data is properly encrypted at rest and can be
reliably decrypted by the service. Tests verify round-trip encryption/decryption
and that repeated encryption produces different ciphertext (due to random IV).

Run tests:
    pytest tests/test_encryption.py

Purpose:
This verifies that speaker embeddings are encrypted before storage, can be
decrypted by the service, and do not produce identical ciphertext on repeated
encryption. The guide treats voice embeddings as biometric data that must be
encrypted at rest and deletable.
"""
import logging

from cryptography.fernet import Fernet

from stt_server.encryption import decrypt_bytes, encrypt_bytes

logger = logging.getLogger(__name__)


def test_encrypt_and_decrypt_bytes_round_trip(monkeypatch):
    """
    Test that encryption and decryption produce the original data.
    
    Verifies that a speaker embedding can be encrypted and then decrypted
    to recover the exact original bytes.
    
    Args:
        monkeypatch: Pytest fixture for modifying environment variables
    """
    logger.info("Starting encrypt/decrypt round-trip test")
    
    key = Fernet.generate_key().decode("utf-8")

    monkeypatch.setenv(
        "SPEAKER_EMBEDDING_ENCRYPTION_KEY",
        key,
    )

    raw_embedding = b"speaker-embedding-bytes"
    logger.debug(f"Original embedding length: {len(raw_embedding)} bytes")

    encrypted = encrypt_bytes(raw_embedding)
    logger.debug(f"Encrypted data length: {len(encrypted)} bytes")
    
    decrypted = decrypt_bytes(encrypted)
    logger.debug(f"Decrypted data length: {len(decrypted)} bytes")

    assert encrypted != raw_embedding
    assert decrypted == raw_embedding
    
    logger.info("Encrypt/decrypt round-trip test passed")


def test_encrypt_bytes_returns_different_ciphertext_each_time(monkeypatch):
    """
    Test that repeated encryption produces different ciphertext.
    
    Verifies that encrypting the same data multiple times produces different
    ciphertext each time, which is expected behavior due to random IVs in
    Fernet encryption. This prevents pattern analysis attacks.
    
    Args:
        monkeypatch: Pytest fixture for modifying environment variables
    """
    logger.info("Starting ciphertext variation test")
    
    key = Fernet.generate_key().decode("utf-8")

    monkeypatch.setenv(
        "SPEAKER_EMBEDDING_ENCRYPTION_KEY",
        key,
    )

    raw_embedding = b"speaker-embedding-bytes"

    encrypted_one = encrypt_bytes(raw_embedding)
    encrypted_two = encrypt_bytes(raw_embedding)
    
    logger.debug(f"First encryption length: {len(encrypted_one)} bytes")
    logger.debug(f"Second encryption length: {len(encrypted_two)} bytes")

    assert encrypted_one != encrypted_two
    assert decrypt_bytes(encrypted_one) == raw_embedding
    assert decrypt_bytes(encrypted_two) == raw_embedding
    
    logger.info("Ciphertext variation test passed")
