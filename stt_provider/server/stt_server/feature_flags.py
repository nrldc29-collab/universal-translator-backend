"""
Feature flag management for the STT application.

This module provides a comprehensive feature flag system that allows dynamic
control over application features without code changes. Feature flags support
different data types, tenant-specific overrides, and environment variable
configuration.

The feature flag system supports:
- Multiple flag types: boolean, string, integer, float
- Tenant-specific overrides for per-tenant configuration
- Environment variable overrides for deployment-time configuration
- Runtime enable/disable of flags
- Comprehensive flag information and querying

Environment Variables:
    Feature flags can be overridden using environment variables with the
    prefix FEATURE_FLAG_. For example, FEATURE_FLAG_ENABLE_SPEAKER_IDENTITY=true

Example:
    from stt_server.feature_flags import get_feature_flags, is_enabled

    # Get the global manager
    manager = get_feature_flags()
    
    # Check if a boolean flag is enabled
    if is_enabled("enable_backend_fallback"):
        # Use backend fallback logic
        pass
    
    # Get flag value with tenant override
    max_streams = manager.get_flag("max_concurrent_streams", tenant_id="tenant-123")
"""
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FlagType(str, Enum):
    """
    Types of feature flags.
    
    Defines the supported data types for feature flag values, which determines
    how values are parsed from environment variables and validated.
    """
    BOOLEAN = "boolean"
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"


@dataclass
class FeatureFlag:
    """
    Represents a feature flag.
    
    A feature flag contains configuration for a toggleable feature, including
    its key, data type, default value, description, enabled state, and any
    tenant-specific overrides.
    
    Attributes:
        key: Unique identifier for the feature flag
        flag_type: Data type of the flag value (FlagType enum)
        default_value: Default value when no override is present
        description: Human-readable description of the flag's purpose
        is_enabled: Whether the flag is currently active
        tenant_specific: Dictionary mapping tenant IDs to override values
    """
    key: str
    flag_type: FlagType
    default_value: Any
    description: str = ""
    is_enabled: bool = True
    tenant_specific: Dict[str, Any] = field(default_factory=dict)


class FeatureFlagManager:
    """
    Manage feature flags for the application.
    
    This class provides a centralized registry for feature flags, supporting
    registration, retrieval, tenant-specific overrides, and environment variable
    configuration. It initializes with a set of default flags for common
    application features.
    
    The manager supports a priority hierarchy for flag values:
    1. Tenant-specific overrides (highest priority)
    2. Environment variable overrides
    3. Default value (lowest priority)
    """
    
    def __init__(self):
        """Initialize the feature flag manager with default flags."""
        self._flags: Dict[str, FeatureFlag] = {}
        self._initialize_default_flags()
        logger.info("FeatureFlagManager initialized with default flags")
    
    def _initialize_default_flags(self) -> None:
        """
        Initialize default feature flags.
        
        Registers a set of default feature flags for common application features
        including speaker identity, backend fallback, metrics, webhooks, compression,
        concurrency limits, timeouts, and circuit breaker functionality.
        """
        default_flags = [
            FeatureFlag(
                key="enable_speaker_identity",
                flag_type=FlagType.BOOLEAN,
                default_value=False,
                description="Enable speaker identity matching",
            ),
            FeatureFlag(
                key="enable_backend_fallback",
                flag_type=FlagType.BOOLEAN,
                default_value=True,
                description="Enable automatic backend fallback",
            ),
            FeatureFlag(
                key="enable_streaming_metrics",
                flag_type=FlagType.BOOLEAN,
                default_value=True,
                description="Enable streaming metrics collection",
            ),
            FeatureFlag(
                key="enable_webhook_notifications",
                flag_type=FlagType.BOOLEAN,
                default_value=False,
                description="Enable webhook notifications",
            ),
            FeatureFlag(
                key="enable_request_compression",
                flag_type=FlagType.BOOLEAN,
                default_value=True,
                description="Enable response compression",
            ),
            FeatureFlag(
                key="max_concurrent_streams",
                flag_type=FlagType.INTEGER,
                default_value=10,
                description="Maximum concurrent streams per tenant",
            ),
            FeatureFlag(
                key="stream_timeout_seconds",
                flag_type=FlagType.INTEGER,
                default_value=300,
                description="Maximum streaming session duration in seconds",
            ),
            FeatureFlag(
                key="enable_circuit_breaker",
                flag_type=FlagType.BOOLEAN,
                default_value=True,
                description="Enable circuit breaker for external dependencies",
            ),
        ]
        
        for flag in default_flags:
            self._flags[flag.key] = flag
        
        logger.debug(f"Initialized {len(default_flags)} default feature flags")
    
    def register_flag(self, flag: FeatureFlag) -> None:
        """
        Register a new feature flag.
        
        Adds a new feature flag to the manager. If a flag with the same key
        already exists, it will be overwritten.
        
        Args:
            flag: FeatureFlag instance to register
        """
        self._flags[flag.key] = flag
        logger.debug(f"Registered feature flag: {flag.key}")
    
    def get_flag(
        self,
        key: str,
        tenant_id: Optional[str] = None,
    ) -> Any:
        """
        Get the value of a feature flag.
        
        Retrieves the flag value following the priority hierarchy:
        1. Tenant-specific override (if tenant_id provided)
        2. Environment variable override
        3. Default value (if flag is enabled)
        
        Args:
            key: Flag key to retrieve
            tenant_id: Optional tenant ID for tenant-specific overrides
            
        Returns:
            Flag value, or None if flag not found
        """
        flag = self._flags.get(key)
        
        if not flag:
            logger.debug(f"Feature flag not found: {key}")
            return None
        
        # Check for tenant-specific override
        if tenant_id and str(tenant_id) in flag.tenant_specific:
            value = flag.tenant_specific[str(tenant_id)]
            logger.debug(f"Using tenant-specific override for {key}: {value}")
            return value
        
        # Check if flag is enabled
        if not flag.is_enabled:
            logger.debug(f"Flag {key} is disabled, returning default: {flag.default_value}")
            return flag.default_value
        
        # Check environment variable override
        env_key = f"FEATURE_FLAG_{key.upper()}"
        env_value = os.environ.get(env_key)
        
        if env_value is not None:
            parsed_value = self._parse_env_value(env_value, flag.flag_type)
            logger.debug(f"Using environment variable override for {key}: {parsed_value}")
            return parsed_value
        
        logger.debug(f"Using default value for {key}: {flag.default_value}")
        return flag.default_value
    
    def set_tenant_override(
        self,
        key: str,
        tenant_id: str,
        value: Any,
    ) -> bool:
        """
        Set a tenant-specific override for a flag.
        
        Allows per-tenant configuration of feature flags, enabling different
        behavior for different tenants without code changes.
        
        Args:
            key: Flag key to override
            tenant_id: Tenant ID for the override
            value: Override value
            
        Returns:
            True if override was set, False if flag not found
        """
        flag = self._flags.get(key)
        
        if not flag:
            logger.warning(f"Cannot set override: flag {key} not found")
            return False
        
        flag.tenant_specific[tenant_id] = value
        logger.info(f"Set tenant-specific override for {key}: tenant={tenant_id}, value={value}")
        return True
    
    def remove_tenant_override(
        self,
        key: str,
        tenant_id: str,
    ) -> bool:
        """
        Remove a tenant-specific override for a flag.
        
        Removes a previously set tenant-specific override, causing the flag
        to revert to its default or environment variable value.
        
        Args:
            key: Flag key to remove override from
            tenant_id: Tenant ID to remove override for
            
        Returns:
            True if override was removed, False if not found
        """
        flag = self._flags.get(key)
        
        if not flag or tenant_id not in flag.tenant_specific:
            logger.debug(f"Cannot remove override: flag {key} or tenant {tenant_id} not found")
            return False
        
        del flag.tenant_specific[tenant_id]
        logger.info(f"Removed tenant-specific override for {key}: tenant={tenant_id}")
        return True
    
    def enable_flag(self, key: str) -> bool:
        """
        Enable a feature flag.
        
        Sets the flag's enabled state to true, allowing it to return values
        from environment variables or defaults.
        
        Args:
            key: Flag key to enable
            
        Returns:
            True if flag was enabled, False if flag not found
        """
        flag = self._flags.get(key)
        
        if not flag:
            logger.warning(f"Cannot enable flag {key}: not found")
            return False
        
        flag.is_enabled = True
        logger.info(f"Enabled feature flag: {key}")
        return True
    
    def disable_flag(self, key: str) -> bool:
        """
        Disable a feature flag.
        
        Sets the flag's enabled state to false, causing it to always return
        the default value regardless of environment variable overrides.
        
        Args:
            key: Flag key to disable
            
        Returns:
            True if flag was disabled, False if flag not found
        """
        flag = self._flags.get(key)
        
        if not flag:
            logger.warning(f"Cannot disable flag {key}: not found")
            return False
        
        flag.is_enabled = False
        logger.info(f"Disabled feature flag: {key}")
        return True
    
    def _parse_env_value(self, value: str, flag_type: FlagType) -> Any:
        """
        Parse environment variable value based on flag type.
        
        Converts string values from environment variables to the appropriate
        Python type based on the flag's data type.
        
        Args:
            value: String value from environment variable
            flag_type: Flag type to parse as
            
        Returns:
            Parsed value in the appropriate type
        """
        if flag_type == FlagType.BOOLEAN:
            parsed = value.lower() in ("true", "1", "yes", "on")
        elif flag_type == FlagType.INTEGER:
            parsed = int(value)
        elif flag_type == FlagType.FLOAT:
            parsed = float(value)
        else:
            parsed = value
        
        logger.debug(f"Parsed env value: {value} -> {parsed} (type: {flag_type.value})")
        return parsed
    
    def get_all_flags(self) -> Dict[str, FeatureFlag]:
        """
        Get all registered feature flags.
        
        Returns a copy of all registered flags to prevent external modification
        of the internal registry.
        
        Returns:
            Dictionary mapping flag keys to FeatureFlag instances
        """
        return self._flags.copy()
    
    def get_flag_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific flag.
        
        Returns comprehensive information about a feature flag including its
        configuration, current state, and any tenant-specific overrides.
        
        Args:
            key: Flag key to get information for
            
        Returns:
            Dictionary with flag information, or None if flag not found
        """
        flag = self._flags.get(key)
        
        if not flag:
            logger.debug(f"Flag info requested but not found: {key}")
            return None
        
        info = {
            "key": flag.key,
            "type": flag.flag_type.value,
            "default_value": flag.default_value,
            "description": flag.description,
            "is_enabled": flag.is_enabled,
            "tenant_overrides": flag.tenant_specific,
        }
        
        logger.debug(f"Retrieved flag info for {key}")
        return info


# Global feature flag manager instance
_global_manager: Optional[FeatureFlagManager] = None


def get_feature_flags() -> FeatureFlagManager:
    """
    Get the global feature flag manager instance.
    
    Returns a singleton instance of the FeatureFlagManager for consistent
    feature flag management across the application.
    
    Returns:
        Global FeatureFlagManager instance
    """
    global _global_manager
    
    if _global_manager is None:
        _global_manager = FeatureFlagManager()
        logger.info("Created global feature flag manager instance")
    
    return _global_manager


def is_enabled(
    key: str,
    tenant_id: Optional[str] = None,
    default: bool = False,
) -> bool:
    """
    Check if a boolean feature flag is enabled.
    
    Convenience function for checking boolean feature flags. Retrieves the
    flag value and converts it to a boolean, returning the provided default
    if the flag is not found.
    
    Args:
        key: Flag key to check
        tenant_id: Optional tenant ID for tenant-specific overrides
        default: Default value if flag not found (default: False)
        
    Returns:
        True if flag is enabled, False otherwise
    """
    manager = get_feature_flags()
    value = manager.get_flag(key, tenant_id)
    
    if value is None:
        logger.debug(f"Flag {key} not found, returning default: {default}")
        return default
    
    return bool(value)
