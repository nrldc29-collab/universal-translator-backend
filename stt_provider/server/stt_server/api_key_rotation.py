"""
API key rotation and lifecycle management.

This module provides functionality for managing API key rotation, including secure key
generation, hashing, scheduling rotations, and managing grace periods for old keys.

The rotation manager supports:
- Secure API key generation using cryptographically strong random bytes
- Key hashing for secure storage
- Scheduled and manual key rotations
- Grace period support for old keys during transitions
- Cleanup of expired rotation records

Environment Variables:
    API_KEY_ROTATION_DAYS: Default rotation interval in days (default: 90)
    API_KEY_GRACE_PERIOD_DAYS: Grace period for old keys in days (default: 7)

Example:
    manager = APIKeyRotationManager(default_rotation_days=90, grace_period_days=7)
    new_key, new_hash = manager.rotate_key(key_id, old_key_hash, "security_update")
"""
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class APIKeyRotation:
    """
    Represents an API key rotation event.
    
    Tracks the details of a key rotation including the old and new key hashes,
    rotation timestamp, expiration of grace period, and the reason for rotation.
    
    Attributes:
        key_id: Unique identifier for the API key
        old_key_hash: Hash of the previous key (for verification during grace period)
        new_key_hash: Hash of the newly generated key
        rotated_at: Unix timestamp when rotation occurred
        expires_at: Optional Unix timestamp when grace period ends
        rotation_reason: Reason for rotation (e.g., "scheduled", "manual", "security")
    """


class APIKeyRotationManager:
    """
    Manage API key rotation and lifecycle.
    
    Provides methods for generating secure API keys, hashing keys for storage,
    scheduling and performing rotations, and managing the grace period during
    which old keys remain valid.
    
    Attributes:
        default_rotation_days: Default number of days between scheduled rotations
        grace_period_days: Number of days old keys remain valid after rotation
        _rotations: Internal storage for rotation records
    """
    
    def __init__(
        self,
        default_rotation_days: int = 90,
        grace_period_days: int = 7,
    ):
        """
        Initialize the API key rotation manager.
        
        Args:
            default_rotation_days: Default rotation interval in days (default: 90)
            grace_period_days: Grace period for old keys in days (default: 7)
        """
        self.default_rotation_days = default_rotation_days
        self.grace_period_days = grace_period_days
        self._rotations: Dict[UUID, APIKeyRotation] = {}
        logger.info(
            f"Initialized APIKeyRotationManager: rotation_days={default_rotation_days}, "
            f"grace_period_days={grace_period_days}"
        )
    
    def generate_api_key(self, prefix: str = "stt_") -> str:
        """
        Generate a new secure API key.
        
        Uses cryptographically strong random bytes to generate a secure API key
        with URL-safe encoding for safe transmission.
        
        Args:
            prefix: Prefix for the API key (default: "stt_")
            
        Returns:
            New API key string with the specified prefix
        """
        # Generate 32 bytes of random data and encode as base64-like string
        random_bytes = secrets.token_bytes(32)
        key_suffix = secrets.token_urlsafe(32)
        api_key = f"{prefix}{key_suffix}"
        logger.debug(f"Generated new API key with prefix: {prefix}")
        return api_key
    
    def hash_key(self, api_key: str) -> str:
        """
        Hash an API key for secure storage.
        
        Uses SHA-256 to hash the API key. In production, consider using a
        dedicated password hashing algorithm like bcrypt or Argon2 with proper
        salt management.
        
        Args:
            api_key: The API key to hash
            
        Returns:
            Hexadecimal string of the hashed key
        """
        # In production, use a proper cryptographic hash like bcrypt or Argon2
        import hashlib
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        logger.debug("Hashed API key for storage")
        return key_hash
    
    def schedule_rotation(
        self,
        key_id: UUID,
        old_key_hash: str,
        new_key_hash: str,
        rotation_reason: str = "scheduled",
    ) -> APIKeyRotation:
        """
        Schedule an API key rotation event.
        
        Records a rotation event with timestamps for the rotation and the
        end of the grace period during which the old key remains valid.
        
        Args:
            key_id: Unique identifier for the API key
            old_key_hash: Hash of the old key being rotated
            new_key_hash: Hash of the new key
            rotation_reason: Reason for rotation (default: "scheduled")
            
        Returns:
            APIKeyRotation instance representing the scheduled rotation
        """
        rotation = APIKeyRotation(
            key_id=key_id,
            old_key_hash=old_key_hash,
            new_key_hash=new_key_hash,
            rotated_at=time.time(),
            expires_at=time.time() + (self.grace_period_days * 86400),
            rotation_reason=rotation_reason,
        )
        
        self._rotations[key_id] = rotation
        logger.info(
            f"Scheduled rotation for key {key_id}: reason={rotation_reason}, "
            f"grace_period={self.grace_period_days} days"
        )
        return rotation
    
    def rotate_key(
        self,
        key_id: UUID,
        old_key_hash: str,
        rotation_reason: str = "manual",
    ) -> tuple[str, str]:
        """
        Rotate an API key, generating a new one.
        
        Generates a new secure API key, hashes it, and records the rotation
        event. The old key remains valid during the grace period.
        
        Args:
            key_id: Unique identifier for the API key
            old_key_hash: Hash of the old key (for verification)
            rotation_reason: Reason for rotation (default: "manual")
            
        Returns:
            Tuple of (new_api_key, new_key_hash)
        """
        # Generate new key
        new_api_key = self.generate_api_key()
        new_key_hash = self.hash_key(new_api_key)
        
        # Record rotation
        self.schedule_rotation(
            key_id=key_id,
            old_key_hash=old_key_hash,
            new_key_hash=new_key_hash,
            rotation_reason=rotation_reason,
        )
        
        logger.info(f"Rotated key {key_id}: reason={rotation_reason}")
        return new_api_key, new_key_hash
    
    def get_rotation_status(self, key_id: UUID) -> Optional[APIKeyRotation]:
        """
        Get rotation status for a specific key.
        
        Args:
            key_id: Unique identifier for the API key
            
        Returns:
            APIKeyRotation instance if found, None otherwise
        """
        rotation = self._rotations.get(key_id)
        if rotation:
            logger.debug(f"Retrieved rotation status for key {key_id}")
        else:
            logger.debug(f"No rotation status found for key {key_id}")
        return rotation
    
    def is_old_key_valid(self, key_id: UUID, key_hash: str) -> bool:
        """
        Check if an old key is still valid during grace period.
        
        Validates whether a key hash matches the old key from a recent rotation
        and whether the grace period has not yet expired.
        
        Args:
            key_id: Unique identifier for the API key
            key_hash: Hash of the key to validate
            
        Returns:
            True if the key is still valid (old key in grace period), False otherwise
        """
        rotation = self._rotations.get(key_id)
        
        if not rotation:
            logger.debug(f"No rotation record for key {key_id}, key invalid")
            return False
        
        # Check if this is the old key
        if rotation.old_key_hash != key_hash:
            logger.debug(f"Key hash does not match old key for {key_id}")
            return False
        
        # Check if still within grace period
        if rotation.expires_at and time.time() < rotation.expires_at:
            logger.debug(f"Old key for {key_id} is still within grace period")
            return True
        
        logger.debug(f"Old key for {key_id} has expired beyond grace period")
        return False
    
    def cleanup_expired_rotations(self) -> int:
        """
        Remove expired rotation records.
        
        Cleans up rotation records whose grace period has expired to prevent
        unbounded memory growth.
        
        Returns:
            Number of rotations cleaned up
        """
        current_time = time.time()
        to_remove = []
        
        for key_id, rotation in self._rotations.items():
            if rotation.expires_at and current_time > rotation.expires_at:
                to_remove.append(key_id)
        
        for key_id in to_remove:
            del self._rotations[key_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} expired rotation records")
        else:
            logger.debug("No expired rotation records to clean up")
        
        return len(to_remove)
    
    def get_rotation_summary(self) -> dict:
        """
        Get a summary of all rotations.
        
        Returns statistics about the current state of rotation records,
        including active and expired counts and breakdown by reason.
        
        Returns:
            Dictionary containing rotation statistics
        """
        current_time = time.time()
        
        summary = {
            "total_rotations": len(self._rotations),
            "active_rotations": 0,
            "expired_rotations": 0,
            "rotations_by_reason": {},
        }
        
        for rotation in self._rotations.values():
            if rotation.expires_at and current_time < rotation.expires_at:
                summary["active_rotations"] += 1
            else:
                summary["expired_rotations"] += 1
            
            reason = rotation.rotation_reason
            summary["rotations_by_reason"][reason] = summary["rotations_by_reason"].get(reason, 0) + 1
        
        logger.debug(f"Rotation summary: {summary}")
        return summary


# Global rotation manager instance
_global_rotation_manager: Optional[APIKeyRotationManager] = None


def get_rotation_manager() -> APIKeyRotationManager:
    """
    Get the global API key rotation manager instance.
    
    Creates and returns a singleton instance of the rotation manager,
    configured via environment variables.
    
    Environment Variables:
        API_KEY_ROTATION_DAYS: Default rotation interval in days (default: 90)
        API_KEY_GRACE_PERIOD_DAYS: Grace period for old keys in days (default: 7)
        
    Returns:
        The global APIKeyRotationManager instance
    """
    global _global_rotation_manager
    
    if _global_rotation_manager is None:
        import os
        _global_rotation_manager = APIKeyRotationManager(
            default_rotation_days=int(os.environ.get("API_KEY_ROTATION_DAYS", "90")),
            grace_period_days=int(os.environ.get("API_KEY_GRACE_PERIOD_DAYS", "7")),
        )
        logger.info("Created global API key rotation manager")
    
    return _global_rotation_manager
