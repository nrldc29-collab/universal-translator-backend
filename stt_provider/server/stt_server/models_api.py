"""
Models API module for listing available transcription models.

This module provides a FastAPI router for exposing the approved domain-specific
transcription models through a REST API endpoint. Supports the Phase 4 domain-model
requirement to surface named models for tenants such as general, medical, legal,
finance, and contact-center.
"""
import logging
from typing import Dict, List

from fastapi import APIRouter

from stt_server.model_registry import ALLOWED_MODEL_IDS

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/v1/models")
async def list_models() -> Dict[str, List[Dict[str, str | bool]]]:
    """
    List all available transcription models.
    
    Returns a list of approved domain-specific models that can be used for
    transcription. Each model includes its ID, domain specialization, and
    whether it is the default model.
    
    Returns:
        Dictionary containing a list of model objects with the following structure:
        - id: Model identifier (e.g., "parakeet-medical")
        - domain: Domain specialization (e.g., "medical")
        - default: Boolean indicating if this is the default model
        
    Example:
        >>> list_models()
        {
            "models": [
                {"id": "parakeet-general", "domain": "general", "default": True},
                {"id": "parakeet-medical", "domain": "medical", "default": False},
                ...
            ]
        }
    """
    logger.info("Listing available transcription models")
    
    models = [
        {
            "id": model_id,
            "domain": model_id.replace("parakeet-", ""),
            "default": model_id == "parakeet-general",
        }
        for model_id in sorted(ALLOWED_MODEL_IDS)
    ]
    
    logger.debug(f"Returning {len(models)} available models")
    
    return {"models": models}
