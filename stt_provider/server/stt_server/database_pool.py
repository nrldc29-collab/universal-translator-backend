"""
Database connection pool configuration.

This module provides configuration management for database connection pools,
including validation of pool settings and environment variable integration.

The configuration supports:
- Minimum and maximum connection limits
- Connection timeout settings
- Idle connection timeout
- Maximum connection lifetime
- Environment variable-based configuration

Environment Variables:
    DB_POOL_MIN_CONNECTIONS: Minimum number of connections (default: 5)
    DB_POOL_MAX_CONNECTIONS: Maximum number of connections (default: 20)
    DB_POOL_CONNECTION_TIMEOUT: Connection timeout in seconds (default: 30)
    DB_POOL_IDLE_TIMEOUT: Idle timeout in seconds (default: 300)
    DB_POOL_MAX_LIFETIME: Maximum connection lifetime in seconds (default: 3600)

Example:
    from stt_server.database_pool import get_pool_config, validate_pool_config

    # Get configuration
    config = get_pool_config()
    
    # Validate configuration
    is_valid, errors = validate_pool_config()
    if not is_valid:
        raise ValueError(f"Invalid config: {errors}")
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class DatabasePoolConfig:
    """
    Database connection pool configuration.
    
    Encapsulates configuration settings for database connection pools,
    including connection limits, timeouts, and lifecycle management.
    Provides methods for creating configuration from environment variables
    and validating the settings.
    
    Attributes:
        min_connections: Minimum number of connections to maintain in the pool
        max_connections: Maximum number of connections allowed in the pool
        connection_timeout: Timeout in seconds for establishing connections
        idle_timeout: Timeout in seconds before idle connections are closed
        max_lifetime: Maximum lifetime in seconds for connections
    """
    
    def __init__(
        self,
        min_connections: int = 5,
        max_connections: int = 20,
        connection_timeout: int = 30,
        idle_timeout: int = 300,
        max_lifetime: int = 3600,
    ):
        """
        Initialize database pool configuration.
        
        Args:
            min_connections: Minimum connections to maintain (default: 5)
            max_connections: Maximum connections allowed (default: 20)
            connection_timeout: Connection timeout in seconds (default: 30)
            idle_timeout: Idle timeout in seconds (default: 300)
            max_lifetime: Maximum connection lifetime in seconds (default: 3600)
        """
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.max_lifetime = max_lifetime
        logger.debug(
            f"DatabasePoolConfig initialized: min={min_connections}, "
            f"max={max_connections}, timeout={connection_timeout}s"
        )
    
    @classmethod
    def from_env(cls) -> "DatabasePoolConfig":
        """
        Create configuration from environment variables.
        
        Reads pool configuration from environment variables with fallback
        to default values if variables are not set.
        
        Returns:
            DatabasePoolConfig instance populated from environment variables
        """
        config = cls(
            min_connections=int(os.environ.get("DB_POOL_MIN_CONNECTIONS", "5")),
            max_connections=int(os.environ.get("DB_POOL_MAX_CONNECTIONS", "20")),
            connection_timeout=int(os.environ.get("DB_POOL_CONNECTION_TIMEOUT", "30")),
            idle_timeout=int(os.environ.get("DB_POOL_IDLE_TIMEOUT", "300")),
            max_lifetime=int(os.environ.get("DB_POOL_MAX_LIFETIME", "3600")),
        )
        logger.info("DatabasePoolConfig loaded from environment variables")
        return config
    
    def validate(self) -> list[str]:
        """
        Validate configuration and return list of errors.
        
        Performs validation checks on the configuration to ensure
        values are within acceptable ranges and logically consistent.
        
        Returns:
            List of error messages; empty list if configuration is valid
        """
        errors = []
        
        if self.min_connections < 1:
            errors.append("DB_POOL_MIN_CONNECTIONS must be >= 1")
            logger.warning(f"Invalid min_connections: {self.min_connections}")
        
        if self.max_connections < self.min_connections:
            errors.append("DB_POOL_MAX_CONNECTIONS must be >= DB_POOL_MIN_CONNECTIONS")
            logger.warning(
                f"max_connections ({self.max_connections}) < min_connections ({self.min_connections})"
            )
        
        if self.max_connections > 100:
            errors.append("DB_POOL_MAX_CONNECTIONS should not exceed 100")
            logger.warning(f"max_connections ({self.max_connections}) exceeds recommended limit of 100")
        
        if self.connection_timeout < 1:
            errors.append("DB_POOL_CONNECTION_TIMEOUT must be >= 1")
            logger.warning(f"Invalid connection_timeout: {self.connection_timeout}")
        
        if self.idle_timeout < 0:
            errors.append("DB_POOL_IDLE_TIMEOUT must be >= 0")
            logger.warning(f"Invalid idle_timeout: {self.idle_timeout}")
        
        if self.max_lifetime < 0:
            errors.append("DB_POOL_MAX_LIFETIME must be >= 0")
            logger.warning(f"Invalid max_lifetime: {self.max_lifetime}")
        
        if errors:
            logger.error(f"DatabasePoolConfig validation failed with {len(errors)} errors")
        else:
            logger.debug("DatabasePoolConfig validation passed")
        
        return errors
    
    def to_dict(self) -> dict:
        """
        Convert configuration to dictionary.
        
        Returns a dictionary representation of the configuration,
        useful for serialization, logging, or API responses.
        
        Returns:
            Dictionary containing all configuration parameters
        """
        return {
            "min_connections": self.min_connections,
            "max_connections": self.max_connections,
            "connection_timeout": self.connection_timeout,
            "idle_timeout": self.idle_timeout,
            "max_lifetime": self.max_lifetime,
        }


def get_pool_config() -> DatabasePoolConfig:
    """
    Get database pool configuration from environment.
    
    Convenience function that creates and returns a DatabasePoolConfig
    instance populated from environment variables.
    
    Returns:
        DatabasePoolConfig instance from environment variables
    """
    config = DatabasePoolConfig.from_env()
    logger.debug("Retrieved database pool configuration")
    return config


def validate_pool_config() -> tuple[bool, list[str]]:
    """
    Validate database pool configuration.
    
    Retrieves the current pool configuration from environment variables
    and validates it. This is useful for startup checks to ensure
    the database pool will function correctly.
    
    Returns:
        Tuple of (is_valid, errors) where is_valid is True if configuration
        passes all validation checks, and errors is a list of error messages
    """
    config = get_pool_config()
    errors = config.validate()
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info("Database pool configuration is valid")
    else:
        logger.error(f"Database pool configuration is invalid: {errors}")
    
    return is_valid, errors
