"""
Role-Based Access Control (RBAC) module.

This module provides scope-based authorization for the STT service.
It defines available scopes and a function to check if a required scope
is present in the user's granted scopes.
"""
import logging
from enum import StrEnum
from typing import List, Optional

from fastapi import HTTPException, Header, status

logger = logging.getLogger(__name__)


class Scope(StrEnum):
    """
    Available authorization scopes for the STT service.
    
    Scopes define what operations a user or API key is authorized to perform.
    Each scope represents a specific permission level.
    
    Attributes:
        STT_STREAM: Permission to stream audio for real-time transcription
        STT_TRANSCRIBE: Permission to transcribe audio files
        USAGE_READ: Permission to read usage statistics
        ADMIN_ALL: Permission for all admin operations (wildcard scope)
    """
    STT_STREAM = "stt:stream"
    STT_TRANSCRIBE = "stt:transcribe"
    USAGE_READ = "usage:read"
    ADMIN_ALL = "admin:*"


def require_scope(scopes: List[str], required_scope: Scope) -> None:
    """
    Check if the required scope is present in the user's granted scopes.
    
    This function validates that the user has the necessary scope to perform
    an operation. If the required scope is not present, it raises an HTTP 403
    Forbidden exception with details about the missing scope.
    
    The ADMIN_ALL scope grants access to all operations and is treated as a wildcard.
    
    Args:
        scopes: List of scope strings granted to the user
        required_scope: The scope required for the operation
        
    Raises:
        HTTPException: 403 Forbidden if the required scope is not present
    """
    logger.debug(f"Checking scope: required={required_scope.value}, granted={scopes}")
    
    # Check if the required scope value is in the scopes list (string comparison)
    if required_scope.value not in scopes:
        logger.warning(f"Scope check failed: required scope '{required_scope.value}' not in granted scopes")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "insufficient_scope",
                "required_scope": required_scope.value,
                "message": f"This operation requires the '{required_scope.value}' scope",
            },
        )

    # Admin wildcard grants access to everything
    if Scope.ADMIN_ALL in scopes:
        logger.debug("Authorization granted via ADMIN_ALL wildcard scope")
        return

    # Check if the required Scope enum is in the scopes list
    if required_scope in scopes:
        logger.debug(f"Authorization granted: scope '{required_scope.value}' found in granted scopes")
        return

    logger.warning(f"Scope check failed: required scope '{required_scope.value}' not in granted scopes")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "insufficient_scope",
            "required_scope": required_scope.value,
        },
    )


def get_api_key(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract API key from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        API key string

    Raises:
        HTTPException: If authorization header is missing or invalid
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    if authorization.startswith("Bearer "):
        return authorization[7:]

    return authorization


def get_tenant(x_tenant_id: Optional[str] = Header(None)) -> str:
    """
    Extract tenant ID from X-Tenant-ID header.

    Args:
        x_tenant_id: X-Tenant-ID header value

    Returns:
        Tenant ID string

    Raises:
        HTTPException: If tenant ID header is missing
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")

    return x_tenant_id
