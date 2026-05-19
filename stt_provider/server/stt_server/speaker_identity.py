"""
Speaker identity matching module.

This module provides functionality for matching live speaker embeddings
against enrolled speaker profiles using cosine similarity.
"""
from dataclasses import dataclass
from uuid import UUID
import numpy as np
from typing import Optional, List
import logging

from stt_server.encryption import decrypt_bytes

logger = logging.getLogger(__name__)


@dataclass
class SpeakerIdentityMatch:
    """
    Represents a successful speaker identity match.
    
    Attributes:
        speaker_profile_id: UUID of the matched speaker profile
        display_name: Display name of the matched speaker
        confidence: Cosine similarity confidence score (0.0 to 1.0)
    """
    speaker_profile_id: UUID
    display_name: str
    confidence: float


MIN_SPEAKER_IDENTITY_CONFIDENCE = 0.85
EMBEDDING_MODEL_VERSION = "speaker-embedding-v1"


def cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings.
    
    Cosine similarity measures the cosine of the angle between two vectors,
    providing a value between -1 and 1 where 1 indicates identical direction.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Cosine similarity score between 0.0 and 1.0
    """
    dot_product = np.dot(embedding1, embedding2)
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    
    if norm1 == 0 or norm2 == 0:
        logger.warning("Zero-norm embedding encountered in cosine similarity calculation")
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    
    # Clamp to [0, 1] range
    return max(0.0, min(1.0, similarity))


async def match_speaker_identity(
    db,
    *,
    tenant_id: UUID,
    speaker_embedding: bytes,
    encryption_key: Optional[bytes] = None,
) -> Optional[SpeakerIdentityMatch]:
    """
    Match a live speaker embedding against enrolled speaker profiles.
    
    This function retrieves all active speaker profiles for a tenant,
    decrypts their stored embeddings (if encryption key is provided),
    and computes cosine similarity against the live embedding. The best
    match above the confidence threshold is returned.
    
    Args:
        db: Database connection with async fetch capability
        tenant_id: Tenant UUID to filter speaker profiles
        speaker_embedding: Live speaker embedding as bytes (float32 array)
        encryption_key: Optional encryption key for decrypting stored embeddings.
                      If not provided, function returns None for privacy safety.
    
    Returns:
        SpeakerIdentityMatch if confidence threshold is met, None otherwise.
        Returns None if no encryption key is provided (privacy-safe default).
    
    Raises:
        Does not raise exceptions; returns None on errors for privacy safety.
    """
    # Privacy-safe default: require encryption key
    if not encryption_key:
        logger.debug("No encryption key provided, skipping speaker identity match")
        return None
    
    try:
        # Fetch active speaker profiles for tenant
        rows = await db.fetch(
            """
            SELECT
                id,
                display_name,
                encrypted_embedding,
                embedding_model
            FROM speaker_profiles
            WHERE tenant_id = $1
              AND deleted_at IS NULL
            """,
            tenant_id,
        )

        if not rows:
            logger.debug(f"No speaker profiles found for tenant {tenant_id}")
            return None
        
        # Convert live embedding to numpy array
        live_embedding = np.frombuffer(speaker_embedding, dtype=np.float32)
        
        # Validate live embedding
        if live_embedding.size == 0:
            logger.warning("Empty live embedding provided")
            return None
        
        best_match: Optional[SpeakerIdentityMatch] = None
        best_confidence = 0.0
        
        for row in rows:
            try:
                # Verify embedding model compatibility
                if row.get("embedding_model") != EMBEDDING_MODEL_VERSION:
                    logger.debug(
                        f"Skipping profile {row['id']}: incompatible model version "
                        f"{row.get('embedding_model')}"
                    )
                    continue
                
                # Decrypt stored embedding
                decrypted_bytes = decrypt_bytes(row["encrypted_embedding"], encryption_key)
                stored_embedding = np.frombuffer(decrypted_bytes, dtype=np.float32)
                
                # Validate stored embedding
                if stored_embedding.size == 0:
                    logger.warning(f"Empty stored embedding for profile {row['id']}")
                    continue
                
                # Check embedding dimension compatibility
                if live_embedding.shape != stored_embedding.shape:
                    logger.warning(
                        f"Embedding dimension mismatch for profile {row['id']}: "
                        f"live {live_embedding.shape} vs stored {stored_embedding.shape}"
                    )
                    continue
                
                # Compute similarity
                confidence = cosine_similarity(live_embedding, stored_embedding)
                
                # Track best match above threshold
                if confidence > best_confidence and confidence >= MIN_SPEAKER_IDENTITY_CONFIDENCE:
                    best_confidence = confidence
                    best_match = SpeakerIdentityMatch(
                        speaker_profile_id=row["id"],
                        display_name=row["display_name"],
                        confidence=confidence,
                    )
                    
            except (ValueError, TypeError, RuntimeError) as e:
                # Skip profiles with invalid embeddings or decryption errors
                logger.warning(f"Skipping profile {row.get('id', 'unknown')} due to error: {e}")
                continue
        
        if best_match:
            logger.info(
                f"Speaker identity matched: {best_match.display_name} "
                f"(confidence: {best_match.confidence:.3f})"
            )
        else:
            logger.debug("No speaker identity match above confidence threshold")
        
        return best_match
        
    except Exception as e:
        # Return None on any processing error (privacy-safe)
        logger.error(f"Error in speaker identity matching: {e}", exc_info=True)
        return None

# Transcript event shape for future identity matches:
#
# {
#   "type": "transcript.final",
#   "text": "thanks for joining today",
#   "words": [
#     {
#       "word": "thanks",
#       "start": 0.1,
#       "end": 0.42,
#       "speaker": "spk_0",
#       "speaker_identity": {
#         "speaker_profile_id": "00000000-0000-0000-0000-000000000456",
#         "display_name": "Alex",
#         "confidence": 0.91
#       }
#     }
#   ]
# }
#
# This prepares the speaker-enrollment path for future cross-session identity matching while keeping biometric embeddings private and avoiding low-confidence identity claims. The guide says speaker enrollment should resolve spk_* labels to real names only with privacy controls around encrypted, deletable voice embeddings.
