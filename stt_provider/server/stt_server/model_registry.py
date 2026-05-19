"""
Model registry module for Whisper model validation.

This module provides functionality for validating Whisper model IDs to ensure
only supported models are used for transcription. It prevents routing requests
to unknown or unloaded Triton models while supporting approved domain-specific
models like medical, legal, finance, and contact-center.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Domain-specific model IDs for Phase 4 rollout
ALLOWED_MODEL_IDS = {
    "parakeet-general",
    "parakeet-medical",
    "parakeet-legal",
    "parakeet-finance",
    "parakeet-contact-center",
}

# Supported Whisper model sizes
_SUPPORTED_WHISPER_MODELS = {
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "large-v1": "large-v1",
    "large-v2": "large-v2",
    "large-v3": "large-v3",
}


def validate_model_id(model_id: Optional[str]) -> Optional[str]:
    """
    Validate and return a supported Whisper model ID.
    
    Validates that the provided model ID is one of the supported Whisper
    model sizes. Returns None if model_id is None, otherwise raises
    ValueError for unsupported model IDs.
    
    Args:
        model_id: The model ID to validate, or None to use default
        
    Returns:
        The validated model ID, or None if model_id was None
        
    Raises:
        ValueError: If model_id is not in the supported models list
        
    Example:
        >>> validate_model_id("tiny")
        'tiny'
        >>> validate_model_id("unknown")
        ValueError: Unsupported model_id: 'unknown'. Supported models: tiny, base, small, medium, large-v1, large-v2, large-v3
    """
    if model_id is None:
        logger.debug("Model ID is None, using default")
        return None

    if model_id not in _SUPPORTED_WHISPER_MODELS:
        logger.warning(f"Unsupported model_id requested: '{model_id}'")
        raise ValueError(
            f"Unsupported model_id: '{model_id}'. "
            f"Supported models: {', '.join(sorted(_SUPPORTED_WHISPER_MODELS.keys()))}"
        )

    logger.debug(f"Model ID validated: '{model_id}'")
    return _SUPPORTED_WHISPER_MODELS[model_id]


def get_supported_models() -> list[str]:
    """
    Get the list of supported Whisper model IDs.
    
    Returns a sorted list of all supported Whisper model sizes that
    can be used for transcription.
    
    Returns:
        List of supported model IDs
    """
    return sorted(_SUPPORTED_WHISPER_MODELS.keys())


def get_allowed_domain_models() -> set[str]:
    """
    Get the set of allowed domain-specific model IDs.
    
    Returns the set of approved domain-specific model IDs for Phase 4
    rollout, including medical, legal, finance, and contact-center models.
    
    Returns:
        Set of allowed domain model IDs
    """
    return ALLOWED_MODEL_IDS
