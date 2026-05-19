"""
Application configuration settings for True Streaming STT Provider.

This module defines the Settings class using Pydantic for type-safe configuration
management. Settings are loaded from environment variables with validation rules
and default values for development environments.

Environment Variables:
    STT_API_KEY: Main API key for STT requests
    STT_API_KEYS: Comma-separated list of API keys
    ADMIN_API_KEY: Admin API key for administrative operations
    DATABASE_URL: PostgreSQL database connection URL
    REDIS_URL: Redis connection URL
    TRITON_GRPC_URL: Triton gRPC server URL
    SPEAKER_EMBEDDING_ENCRYPTION_KEY: Encryption key for speaker embeddings (min 32 bytes)

Example .env file:
    STT_API_KEY=sk-1234567890abcdef
    ADMIN_API_KEY=sk-admin-1234567890abcdef
    DATABASE_URL=postgresql://user:pass@localhost:5432/stt
    REDIS_URL=redis://localhost:6379
"""
import logging
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application configuration settings with Pydantic validation.
    
    This class defines all configuration settings for the True Streaming STT
    Provider, including server settings, authentication, transcription options,
    audio parameters, session limits, database connections, and security settings.
    Settings are loaded from environment variables with type validation and
    sensible defaults for development.
    
    Attributes:
        model_config: Pydantic settings configuration for loading from .env files
        app_name: Application name
        env: Environment (dev, staging, prod)
        host: Server host address
        port: Server port number
        stt_api_key: Main API key for STT requests
        stt_api_keys: Comma-separated list of API keys
        admin_api_key: Admin API key for administrative operations
        transcription_language: Default transcription language code
        whisper_model_size: Whisper model size
        whisper_device: Whisper device type (cpu, cuda, auto)
        whisper_compute_type: Whisper compute type
        sample_rate: Audio sample rate in Hz
        channels: Audio channels (1=mono, 2=stereo)
        frame_ms: Frame duration in milliseconds
        vad_mode: VAD aggressiveness level (0-3)
        max_session_seconds: Maximum session duration in seconds
        idle_timeout_seconds: Idle timeout in seconds
        max_audio_frame_bytes: Maximum audio frame size in bytes
        max_connections_per_key: Max connections per API key
        max_active_connections: Max active connections total
        allowed_origins: Comma-separated list of allowed CORS origins
        billing_rate_per_audio_hour: Billing rate per audio hour
        enable_admin_reset: Enable admin reset endpoint
        database_url: PostgreSQL database URL
        database_pool_min: Minimum database pool size
        database_pool_max: Maximum database pool size
        redis_url: Redis connection URL
        triton_grpc_url: Triton gRPC URL
        triton_asr_model: Triton ASR model name
        stt_backend: STT backend to use (whisper or triton)
        speaker_embedding_encryption_key: Encryption key for speaker embeddings
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="True Streaming STT Provider", description="Application name")
    env: Literal["dev", "staging", "prod"] = Field(default="dev", description="Environment")
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")

    # Authentication settings
    stt_api_key: str = Field(default="", description="Main API key for STT requests")
    stt_api_keys: str = Field(default="", description="Comma-separated list of API keys")
    admin_api_key: str = Field(default="", description="Admin API key for administrative operations")

    # Transcription settings
    transcription_language: str = Field(default="en", description="Default transcription language")
    whisper_model_size: Literal["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"] = Field(
        default="base", description="Whisper model size"
    )
    whisper_device: Literal["cpu", "cuda", "auto"] = Field(default="cpu", description="Whisper device")
    whisper_compute_type: Literal["int8", "float16", "float32"] = Field(default="int8", description="Whisper compute type")

    # Audio settings
    sample_rate: Literal[8000, 16000, 48000] = Field(default=16000, description="Audio sample rate in Hz")
    channels: Literal[1, 2] = Field(default=1, description="Audio channels (1=mono, 2=stereo)")
    frame_ms: Literal[10, 20, 30] = Field(default=30, description="Frame duration in milliseconds")
    vad_mode: Literal[0, 1, 2, 3] = Field(default=2, description="VAD aggressiveness (0-3)")

    # Session settings
    max_session_seconds: int = Field(default=1800, ge=60, description="Maximum session duration in seconds")
    idle_timeout_seconds: int = Field(default=60, ge=10, description="Idle timeout in seconds")
    max_audio_frame_bytes: int = Field(default=262144, ge=1024, description="Maximum audio frame size in bytes")

    # Connection settings
    max_connections_per_key: int = Field(default=3, ge=1, description="Max connections per API key")
    max_active_connections: int = Field(default=10, ge=1, description="Max active connections total")

    # CORS settings
    allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated list of allowed CORS origins"
    )

    # Billing settings
    billing_rate_per_audio_hour: float = Field(default=0.0, ge=0.0, description="Billing rate per audio hour")

    # Admin settings
    enable_admin_reset: bool = Field(default=False, description="Enable admin reset endpoint")

    # Database settings
    database_url: str = Field(default="", description="PostgreSQL database URL")
    database_pool_min: int = Field(default=5, ge=1, description="Minimum database pool size")
    database_pool_max: int = Field(default=20, ge=1, description="Maximum database pool size")

    # Redis settings
    redis_url: str = Field(default="", description="Redis connection URL")

    # Triton settings
    triton_grpc_url: str = Field(default="", description="Triton gRPC URL")
    triton_asr_model: str = Field(default="", description="Triton ASR model name")
    stt_backend: Literal["whisper", "triton"] = Field(default="whisper", description="STT backend to use")

    # Security settings
    speaker_embedding_encryption_key: str = Field(
        default="",
        min_length=32,
        description="Encryption key for speaker embeddings (min 32 bytes)"
    )

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        """
        Validate environment is one of allowed values.
        
        Args:
            v: Environment value to validate
            
        Returns:
            Validated environment value
            
        Raises:
            ValueError: If environment is not one of dev, staging, prod
        """
        if v not in ["dev", "staging", "prod"]:
            logger.error(f"Invalid environment: {v}")
            raise ValueError(f"env must be one of 'dev', 'staging', 'prod', got '{v}'")
        logger.debug(f"Environment validated: {v}")
        return v

    @field_validator("stt_api_key", "admin_api_key")
    @classmethod
    def validate_api_keys(cls, v: str, info) -> str:
        """
        Validate API keys are set in non-dev environments.
        
        Args:
            v: API key value to validate
            info: Pydantic field info containing all field values
            
        Returns:
            Validated API key value
            
        Raises:
            ValueError: If API key is not set in production environment
        """
        if info.data.get("env") == "prod" and not v:
            logger.error("API key must be set in production environment")
            raise ValueError("API key must be set in production environment")
        return v

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, v: str) -> str:
        """
        Validate allowed origins format.
        
        Args:
            v: Allowed origins string to validate
            
        Returns:
            Validated allowed origins string
            
        Raises:
            ValueError: If allowed_origins is empty
        """
        if not v:
            logger.error("allowed_origins cannot be empty")
            raise ValueError("allowed_origins cannot be empty")
        logger.debug(f"Allowed origins validated: {v}")
        return v

    def get_allowed_origins_list(self) -> list[str]:
        """
        Parse allowed_origins into a list.
        
        Splits the comma-separated allowed_origins string into a list of
        individual origin strings, stripping whitespace.
        
        Returns:
            List of allowed origin strings
        """
        origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        logger.debug(f"Parsed {len(origins)} allowed origins")
        return origins

    def get_api_keys_list(self) -> list[str]:
        """
        Parse stt_api_keys into a list.
        
        Splits the comma-separated stt_api_keys string into a list of
        individual API key strings, stripping whitespace.
        
        Returns:
            List of API key strings, or empty list if not configured
        """
        if not self.stt_api_keys:
            logger.debug("No additional API keys configured")
            return []
        keys = [key.strip() for key in self.stt_api_keys.split(",") if key.strip()]
        logger.debug(f"Parsed {len(keys)} additional API keys")
        return keys

    def is_prod(self) -> bool:
        """
        Check if running in production environment.
        
        Returns:
            True if environment is prod, False otherwise
        """
        return self.env == "prod"

    def is_dev(self) -> bool:
        """
        Check if running in development environment.
        
        Returns:
            True if environment is dev, False otherwise
        """
        return self.env == "dev"


settings = Settings()
logger.info(f"Configuration loaded for environment: {settings.env}")
