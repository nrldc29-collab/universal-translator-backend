"""
Tests for speaker identity matching functionality.

This module contains tests for speaker identity matching using cosine similarity,
including tests for the match_speaker_identity function and cosine_similarity utility.
"""
from uuid import UUID
from typing import Optional

import pytest
import numpy as np

from stt_server.speaker_identity import match_speaker_identity, cosine_similarity, MIN_SPEAKER_IDENTITY_CONFIDENCE
from stt_server.encryption import encrypt_bytes, generate_fernet_key


TENANT_ID = UUID("00000000-0000-0000-0000-000000000123")


class FakeDbNoProfiles:
    """Fake database implementation that returns no speaker profiles."""
    
    async def fetch(self, query, tenant_id):
        """Return empty list indicating no profiles exist."""
        return []


class FakeDbWithProfiles:
    """Fake database implementation with a single speaker profile."""
    
    def __init__(self, encryption_key: bytes):
        """
        Initialize with encryption key for test data.
        
        Args:
            encryption_key: Encryption key for embedding data
        """
        self.encryption_key = encryption_key
        
    async def fetch(self, query, tenant_id):
        """
        Return a single test speaker profile.
        
        Args:
            query: SQL query (ignored in fake)
            tenant_id: Tenant ID (ignored in fake)
            
        Returns:
            List containing one speaker profile with encrypted embedding
        """
        # Create a test embedding
        test_embedding = np.random.randn(128).astype(np.float32)
        encrypted = encrypt_bytes(test_embedding.tobytes())
        
        return [
            {
                "id": UUID("00000000-0000-0000-0000-000000000456"),
                "display_name": "Alex",
                "encrypted_embedding": encrypted,
                "embedding_model": "speaker-embedding-v1",
            }
        ]


@pytest.mark.asyncio
async def test_match_speaker_identity_returns_none_when_no_profiles_exist():
    """Test that match_speaker_identity returns None when no profiles exist."""
    logger.info("Testing match_speaker_identity returns None when no profiles exist")
    
    match = await match_speaker_identity(
        FakeDbNoProfiles(),
        tenant_id=TENANT_ID,
        speaker_embedding=b"live-speaker-embedding",
    )

    assert match is None
    logger.info("No profiles test passed")


@pytest.mark.asyncio
async def test_match_speaker_identity_returns_none_without_encryption_key():
    """Test that match_speaker_identity returns None without encryption key (privacy-safe)."""
    logger.info("Testing match_speaker_identity returns None without encryption key")
    
    match = await match_speaker_identity(
        FakeDbWithProfiles(generate_fernet_key().encode()),
        tenant_id=TENANT_ID,
        speaker_embedding=b"live-speaker-embedding",
        encryption_key=None,
    )

    assert match is None
    logger.info("No encryption key test passed")


@pytest.mark.asyncio
async def test_match_speaker_identity_with_encryption_key():
    """Test that match_speaker_identity returns a match when embedding matches."""
    logger.info("Testing match_speaker_identity with encryption key")
    encryption_key = generate_fernet_key().encode()
    
    # Create a test embedding
    test_embedding = np.random.randn(128).astype(np.float32)
    
    class FakeDbWithMatchingProfile:
        """Fake database with a profile matching the test embedding."""
        
        async def fetch(self, query, tenant_id):
            """Return profile with encrypted test embedding."""
            encrypted = encrypt_bytes(test_embedding.tobytes(), encryption_key)
            
            return [
                {
                    "id": UUID("00000000-0000-0000-0000-000000000456"),
                    "display_name": "Alex",
                    "encrypted_embedding": encrypted,
                    "embedding_model": "speaker-embedding-v1",
                }
            ]
    
    match = await match_speaker_identity(
        FakeDbWithMatchingProfile(),
        tenant_id=TENANT_ID,
        speaker_embedding=test_embedding.tobytes(),
        encryption_key=encryption_key,
    )

    # Should return a match with high confidence (same embedding)
    assert match is not None
    assert match.display_name == "Alex"
    assert match.confidence >= MIN_SPEAKER_IDENTITY_CONFIDENCE
    logger.info("Encryption key match test passed")


@pytest.mark.asyncio
async def test_match_speaker_identity_with_low_confidence():
    """Test that match_speaker_identity returns None when confidence is below threshold."""
    logger.info("Testing match_speaker_identity with low confidence")
    encryption_key = generate_fernet_key().encode()
    
    # Create different embeddings (orthogonal)
    test_embedding = np.random.randn(128).astype(np.float32)
    different_embedding = np.random.randn(128).astype(np.float32)
    
    class FakeDbWithDifferentProfile:
        """Fake database with a profile different from test embedding."""
        
        async def fetch(self, query, tenant_id):
            """Return profile with different encrypted embedding."""
            encrypted = encrypt_bytes(different_embedding.tobytes(), encryption_key)
            
            return [
                {
                    "id": UUID("00000000-0000-0000-0000-000000000456"),
                    "display_name": "Alex",
                    "encrypted_embedding": encrypted,
                    "embedding_model": "speaker-embedding-v1",
                }
            ]
    
    match = await match_speaker_identity(
        FakeDbWithDifferentProfile(),
        tenant_id=TENANT_ID,
        speaker_embedding=test_embedding.tobytes(),
        encryption_key=encryption_key,
    )

    # Should return None for low confidence match
    assert match is None
    logger.info("Low confidence test passed")


@pytest.mark.asyncio
async def test_match_speaker_identity_with_incompatible_model():
    """Test that match_speaker_identity skips profiles with incompatible model version."""
    logger.info("Testing match_speaker_identity with incompatible model")
    encryption_key = generate_fernet_key().encode()
    
    test_embedding = np.random.randn(128).astype(np.float32)
    
    class FakeDbWithIncompatibleModel:
        """Fake database with profile using incompatible model version."""
        
        async def fetch(self, query, tenant_id):
            """Return profile with incompatible embedding model."""
            encrypted = encrypt_bytes(test_embedding.tobytes(), encryption_key)
            
            return [
                {
                    "id": UUID("00000000-0000-0000-0000-000000000456"),
                    "display_name": "Alex",
                    "encrypted_embedding": encrypted,
                    "embedding_model": "speaker-embedding-v2",  # Incompatible version
                }
            ]
    
    match = await match_speaker_identity(
        FakeDbWithIncompatibleModel(),
        tenant_id=TENANT_ID,
        speaker_embedding=test_embedding.tobytes(),
        encryption_key=encryption_key,
    )

    # Should return None due to incompatible model
    assert match is None
    logger.info("Incompatible model test passed")


def test_cosine_similarity_identical_vectors():
    """Test cosine similarity returns 1.0 for identical vectors."""
    logger.info("Testing cosine similarity with identical vectors")
    vec1 = np.array([1.0, 0.0, 0.0])
    vec2 = np.array([1.0, 0.0, 0.0])
    similarity = cosine_similarity(vec1, vec2)
    assert similarity == 1.0
    logger.info("Identical vectors test passed")


def test_cosine_similarity_orthogonal_vectors():
    """Test cosine similarity returns 0.0 for orthogonal vectors."""
    logger.info("Testing cosine similarity with orthogonal vectors")
    vec1 = np.array([1.0, 0.0, 0.0])
    vec2 = np.array([0.0, 1.0, 0.0])
    similarity = cosine_similarity(vec1, vec2)
    assert similarity == 0.0
    logger.info("Orthogonal vectors test passed")


def test_cosine_similarity_zero_vectors():
    """Test cosine similarity returns 0.0 when one vector is zero."""
    logger.info("Testing cosine similarity with zero vector")
    vec1 = np.array([0.0, 0.0, 0.0])
    vec2 = np.array([1.0, 0.0, 0.0])
    similarity = cosine_similarity(vec1, vec2)
    assert similarity == 0.0
    logger.info("Zero vector test passed")


def test_cosine_similarity_opposite_vectors():
    """Test cosine similarity returns 0.0 for opposite vectors (clamped to [0,1])."""
    logger.info("Testing cosine similarity with opposite vectors")
    vec1 = np.array([1.0, 0.0, 0.0])
    vec2 = np.array([-1.0, 0.0, 0.0])
    similarity = cosine_similarity(vec1, vec2)
    assert similarity == 0.0  # Clamped to [0, 1]
    logger.info("Opposite vectors test passed")


def test_cosine_similarity_partial_match():
    """Test cosine similarity for partially matching vectors."""
    logger.info("Testing cosine similarity with partial match")
    vec1 = np.array([1.0, 1.0, 0.0])
    vec2 = np.array([1.0, 0.0, 0.0])
    similarity = cosine_similarity(vec1, vec2)
    assert 0.0 < similarity < 1.0
    logger.info("Partial match test passed")

# Run:
#
# pytest tests/test_speaker_identity.py
#
# This verifies the current identity-matching stub is privacy-safe: it does not guess speaker identity before the real embedding similarity model and confidence threshold are implemented. The guide requires speaker enrollment to resolve spk_* labels to real names only with strong privacy controls for encrypted, deletable biometric voice embeddings.
