"""
Configuration validation utilities for the STT application.

This module provides comprehensive validation for all application configuration
settings, ensuring that required environment variables are set, values are
within acceptable ranges, and dependencies are properly configured.

The validation system supports:
- Critical configuration validation (errors prevent startup)
- Optional configuration validation (warnings only)
- Per-component validation (database, redis, triton, etc.)
- Startup validation with detailed error reporting

Example:
    from stt_server.config_validation import validate_startup_config

    # Validate all configuration at startup
    try:
        validate_startup_config()
        print("Configuration is valid")
    except ConfigValidationError as e:
        print(f"Configuration error: {e}")
"""
import logging
import os
from typing import List, Tuple
from stt_server.config import settings

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """
    Raised when configuration validation fails.
    
    This exception is raised when critical configuration is invalid or missing,
    preventing the application from starting safely. Contains detailed error
    messages describing which configuration values are invalid.
    """


def validate_database_config() -> List[str]:
    """
    Validate database configuration.
    
    Ensures that the database connection URL is properly configured.
    This is a critical configuration that must be set for the application
    to function.
    
    Returns:
        List of error messages; empty if configuration is valid
    """
    errors = []
    
    if not settings.database_url:
        errors.append("DATABASE_URL is not configured")
        logger.error("Database configuration validation failed: DATABASE_URL not set")
    else:
        logger.debug("Database configuration validated")
    
    return errors


def validate_redis_config() -> List[str]:
    """
    Validate Redis configuration.
    
    Ensures that the Redis connection URL is configured. Redis is used
    for caching and rate limiting, so this is an optional but recommended
    configuration.
    
    Returns:
        List of error messages; empty if configuration is valid
    """
    errors = []
    
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        errors.append("REDIS_URL is not configured")
        logger.warning("Redis configuration validation failed: REDIS_URL not set")
    else:
        logger.debug("Redis configuration validated")
    
    return errors


def validate_triton_config() -> List[str]:
    """
    Validate Triton backend configuration.
    
    When the Triton backend is selected, validates that the required
    Triton configuration (GRPC URL and ASR model) are properly set.
    
    Returns:
        List of error messages; empty if configuration is valid
    """
    errors = []
    
    if settings.stt_backend == "triton":
        grpc_url = os.environ.get("TRITON_GRPC_URL")
        asr_model = os.environ.get("TRITON_ASR_MODEL")
        
        if not grpc_url:
            errors.append("TRITON_GRPC_URL is required when backend is 'triton'")
            logger.error("Triton configuration validation failed: TRITON_GRPC_URL not set")
        
        if not asr_model:
            errors.append("TRITON_ASR_MODEL is required when backend is 'triton'")
            logger.error("Triton configuration validation failed: TRITON_ASR_MODEL not set")
        
        if not errors:
            logger.debug("Triton configuration validated")
    else:
        logger.debug("Triton validation skipped (backend is not 'triton')")
    
    return errors


def validate_api_key_config() -> List[str]:
    """
    Validate API key configuration.
    
    Ensures that the STT API key is configured in non-development
    environments. This is a security requirement for production deployments.
    
    Returns:
        List of error messages; empty if configuration is valid
    """
    errors = []
    
    if settings.env != "dev" and not settings.stt_api_key:
        errors.append("STT_API_KEY must be configured in non-dev environments")
        logger.error(f"API key configuration validation failed for env: {settings.env}")
    else:
        logger.debug("API key configuration validated")
    
    return errors


def validate_encryption_config() -> List[str]:
    """
    Validate encryption configuration.
    
    Validates that the speaker embedding encryption key is at least
    32 bytes long if configured. This ensures proper encryption strength
    for sensitive data.
    
    Returns:
        List of error messages; empty if configuration is valid
    """
    errors = []
    
    encryption_key = os.environ.get("SPEAKER_EMBEDDING_ENCRYPTION_KEY")
    if encryption_key:
        if len(encryption_key) < 32:
            errors.append("SPEAKER_EMBEDDING_ENCRYPTION_KEY must be at least 32 bytes")
            logger.error(
                f"Encryption key validation failed: key length {len(encryption_key)} < 32 bytes"
            )
        else:
            logger.debug("Encryption configuration validated")
    else:
        logger.debug("Encryption configuration not set (optional)")
    
    return errors


def validate_cors_config() -> List[str]:
    """
    Validate CORS configuration.
    
    Ensures that the allowed origins for CORS are properly configured
    and not empty after parsing. This is critical for web client access.
    
    Returns:
        List of error messages; empty if configuration is valid
    """
    errors = []
    
    if not settings.allowed_origins:
        errors.append("ALLOWED_ORIGINS is not configured")
        logger.error("CORS configuration validation failed: ALLOWED_ORIGINS not set")
    else:
        origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
        if not origins:
            errors.append("ALLOWED_ORIGINS is empty after parsing")
            logger.error("CORS configuration validation failed: no valid origins parsed")
        else:
            logger.debug(f"CORS configuration validated with {len(origins)} origins")
    
    return errors


def validate_rate_limit_config() -> List[str]:
    """
    Validate rate limiting configuration.
    
    Ensures that rate limit values are positive and reasonable.
    Rate limits prevent abuse and ensure fair resource allocation.
    
    Returns:
        List of error messages; empty if configuration is valid
    """
    errors = []
    
    if settings.max_streams_per_minute < 1:
        errors.append("MAX_STREAMS_PER_MINUTE must be >= 1")
        logger.error(
            f"Rate limit validation failed: MAX_STREAMS_PER_MINUTE {settings.max_streams_per_minute} < 1"
        )
    
    if settings.max_admin_ops_per_minute < 1:
        errors.append("MAX_ADMIN_OPS_PER_MINUTE must be >= 1")
        logger.error(
            f"Rate limit validation failed: MAX_ADMIN_OPS_PER_MINUTE {settings.max_admin_ops_per_minute} < 1"
        )
    
    if not errors:
        logger.debug("Rate limit configuration validated")
    
    return errors


def validate_audio_config() -> List[str]:
    """
    Validate audio configuration.
    
    Validates audio processing parameters including sample rate,
    frame duration, and VAD mode. Ensures only supported values are used.
    
    Returns:
        List of error messages; empty if configuration is valid
    """
    errors = []
    
    if settings.sample_rate not in (8000, 16000, 48000):
        errors.append(f"SAMPLE_RATE {settings.sample_rate} not supported (must be 8000, 16000, or 48000)")
        logger.error(f"Audio config validation failed: SAMPLE_RATE {settings.sample_rate} not supported")
    
    if settings.frame_ms not in (10, 20, 30):
        errors.append(f"FRAME_MS {settings.frame_ms} not supported (must be 10, 20, or 30)")
        logger.error(f"Audio config validation failed: FRAME_MS {settings.frame_ms} not supported")
    
    if settings.vad_mode not in (0, 1, 2, 3):
        errors.append(f"VAD_MODE {settings.vad_mode} not supported (must be 0, 1, 2, or 3)")
        logger.error(f"Audio config validation failed: VAD_MODE {settings.vad_mode} not supported")
    
    if not errors:
        logger.debug("Audio configuration validated")
    
    return errors


def validate_all_configs() -> Tuple[List[str], List[str]]:
    """
    Validate all configuration and return errors and warnings.
    
    Runs all configuration validators, separating critical errors from
    warnings. Critical errors (database, API key, CORS, rate limits, audio)
    must be fixed before startup. Warnings (redis, triton, encryption) are
    for optional features that can degrade functionality if missing.
    
    Returns:
        Tuple of (errors, warnings) where errors are critical configuration
        issues and warnings are for optional configurations
    """
    errors = []
    warnings = []
    
    logger.info("Starting comprehensive configuration validation")
    
    # Validate critical configs
    errors.extend(validate_database_config())
    errors.extend(validate_api_key_config())
    errors.extend(validate_cors_config())
    errors.extend(validate_rate_limit_config())
    errors.extend(validate_audio_config())
    
    # Validate optional configs (warnings only)
    redis_errors = validate_redis_config()
    if redis_errors:
        warnings.extend(redis_errors)
    
    triton_errors = validate_triton_config()
    if triton_errors:
        warnings.extend(triton_errors)
    
    encryption_errors = validate_encryption_config()
    if encryption_errors:
        warnings.extend(encryption_errors)
    
    logger.info(
        f"Configuration validation complete: {len(errors)} errors, {len(warnings)} warnings"
    )
    
    return errors, warnings


def validate_startup_config() -> None:
    """
    Validate all configuration at startup.
    
    Performs comprehensive configuration validation and logs warnings for
    optional configurations. Raises ConfigValidationError if critical
    configuration is invalid, preventing application startup.
    
    Raises:
        ConfigValidationError: If critical configuration is invalid
    """
    errors, warnings = validate_all_configs()
    
    if warnings:
        logger.warning(f"Configuration warnings ({len(warnings)}):")
        for warning in warnings:
            logger.warning(f"  - {warning}")
    
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(f"Configuration validation failed with {len(errors)} errors")
        raise ConfigValidationError(error_msg)
    
    logger.info("Configuration validation passed")
