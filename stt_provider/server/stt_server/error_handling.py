"""
Error handling utilities for the STT application.

This module provides standardized error handling for the STT service, including
custom exception classes, error codes, and utilities for converting application
exceptions to HTTP responses.

The error handling system supports:
- Hierarchical exception classes for different error types
- Standardized error codes for consistent API responses
- Automatic conversion to HTTP exceptions with appropriate status codes
- Detailed error information including context and metadata

Example:
    from stt_server.error_handling import AuthenticationError, handle_exception

    # Raise custom errors
    raise AuthenticationError("Invalid API key")

    # Convert any exception to HTTP response
    try:
        # Some operation
        pass
    except Exception as e:
        http_exc = handle_exception(e)
        raise http_exc
"""
import logging
from enum import Enum
from typing import Any, Dict, Optional
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """
    Standard error codes for the application.
    
    Error codes are used to identify specific error conditions across the API.
    Each code maps to an appropriate HTTP status code and provides a stable
    identifier for error handling in client applications.
    
    Categories:
        - Authentication errors: 4xx status codes
        - Authorization errors: 403 status code
        - Validation errors: 400 status code
        - Resource errors: 404, 409 status codes
        - Rate limiting errors: 429 status code
        - System errors: 5xx status codes
        - Streaming errors: Various status codes
        - Database errors: 500, 503 status codes
    """
    # Authentication errors
    INVALID_API_KEY = "invalid_api_key"
    MISSING_API_KEY = "missing_api_key"
    EXPIRED_API_KEY = "expired_api_key"
    
    # Authorization errors
    INSUFFICIENT_SCOPE = "insufficient_scope"
    FORBIDDEN = "forbidden"
    
    # Validation errors
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_UUID = "invalid_uuid"
    INVALID_VALUE = "invalid_value"
    VALUE_OUT_OF_RANGE = "value_out_of_range"
    
    # Resource errors
    RESOURCE_NOT_FOUND = "resource_not_found"
    RESOURCE_ALREADY_EXISTS = "resource_already_exists"
    RESOURCE_CONFLICT = "resource_conflict"
    
    # Rate limiting errors
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TOO_MANY_REQUESTS = "too_many_requests"
    CONCURRENT_LIMIT_EXCEEDED = "concurrent_limit_exceeded"
    
    # System errors
    SERVICE_UNAVAILABLE = "service_unavailable"
    BACKEND_UNHEALTHY = "backend_unhealthy"
    INTERNAL_ERROR = "internal_error"
    
    # Streaming errors
    STREAM_LIMIT_EXCEEDED = "stream_limit_exceeded"
    STREAM_TIMEOUT = "stream_timeout"
    INVALID_AUDIO_FORMAT = "invalid_audio_format"
    
    # Database errors
    DATABASE_ERROR = "database_error"
    DATABASE_CONNECTION_FAILED = "database_connection_failed"
    
    # Configuration errors
    CONFIGURATION_ERROR = "configuration_error"


class STTError(Exception):
    """
    Base exception class for STT application errors.
    
    All custom application exceptions inherit from this class, providing
    consistent error information including message, error code, and optional
    details dictionary for additional context.
    
    Attributes:
        message: Human-readable error message
        code: ErrorCode enum value identifying the error type
        details: Optional dictionary with additional error context
    """
    
    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an STTError.
        
        Args:
            message: Human-readable error message
            code: ErrorCode enum value identifying the error type
            details: Optional dictionary with additional error context
        """
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(STTError):
    """
    Authentication related errors.
    
    Raised when authentication fails due to invalid, missing, or expired
    API keys or credentials.
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an AuthenticationError.
        
        Args:
            message: Human-readable error message (default: "Authentication failed")
            details: Optional dictionary with additional error context
        """
        logger.warning(f"Authentication error: {message}")
        super().__init__(message, ErrorCode.INVALID_API_KEY, details)


class AuthorizationError(STTError):
    """
    Authorization related errors.
    
    Raised when a user is authenticated but lacks the required permissions
    or scopes to perform the requested action.
    """
    
    def __init__(
        self,
        message: str = "Authorization failed",
        required_scope: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an AuthorizationError.
        
        Args:
            message: Human-readable error message (default: "Authorization failed")
            required_scope: Optional scope that was required but not granted
            details: Optional dictionary with additional error context
        """
        if details is None:
            details = {}
        if required_scope:
            details["required_scope"] = required_scope
        logger.warning(f"Authorization error: {message}, required_scope={required_scope}")
        super().__init__(message, ErrorCode.INSUFFICIENT_SCOPE, details)


class ValidationError(STTError):
    """
    Validation related errors.
    
    Raised when input validation fails, including invalid data types,
    missing required fields, or values outside acceptable ranges.
    """
    
    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a ValidationError.
        
        Args:
            message: Human-readable error message (default: "Validation failed")
            field: Optional field name that failed validation
            details: Optional dictionary with additional error context
        """
        if details is None:
            details = {}
        if field:
            details["field"] = field
        logger.debug(f"Validation error: {message}, field={field}")
        super().__init__(message, ErrorCode.INVALID_INPUT, details)


class ResourceNotFoundError(STTError):
    """
    Resource not found errors.
    
    Raised when a requested resource cannot be found in the system,
    such as a speaker profile, tenant configuration, or other entity.
    """
    
    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a ResourceNotFoundError.
        
        Args:
            resource_type: Type of resource that was not found
            resource_id: Identifier of the resource that was not found
            details: Optional dictionary with additional error context
        """
        message = f"{resource_type} not found: {resource_id}"
        if details is None:
            details = {}
        details["resource_type"] = resource_type
        details["resource_id"] = resource_id
        logger.debug(f"Resource not found: {resource_type}/{resource_id}")
        super().__init__(message, ErrorCode.RESOURCE_NOT_FOUND, details)


class RateLimitError(STTError):
    """
    Rate limiting errors.
    
    Raised when a client exceeds configured rate limits for API requests,
    concurrent connections, or other resource quotas.
    """
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a RateLimitError.
        
        Args:
            message: Human-readable error message (default: "Rate limit exceeded")
            limit_type: Optional type of limit that was exceeded
            details: Optional dictionary with additional error context
        """
        if details is None:
            details = {}
        if limit_type:
            details["limit_type"] = limit_type
        logger.warning(f"Rate limit exceeded: {message}, limit_type={limit_type}")
        super().__init__(message, ErrorCode.RATE_LIMIT_EXCEEDED, details)


class ServiceUnavailableError(STTError):
    """
    Service unavailable errors.
    
    Raised when a required service or backend is temporarily unavailable,
    such as during maintenance or outages.
    """
    
    def __init__(
        self,
        message: str = "Service unavailable",
        service: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a ServiceUnavailableError.
        
        Args:
            message: Human-readable error message (default: "Service unavailable")
            service: Optional name of the service that is unavailable
            details: Optional dictionary with additional error context
        """
        if details is None:
            details = {}
        if service:
            details["service"] = service
        logger.error(f"Service unavailable: {message}, service={service}")
        super().__init__(message, ErrorCode.SERVICE_UNAVAILABLE, details)


class InternalError(STTError):
    """
    Internal application errors.
    
    Raised for unexpected errors that occur within the application,
    typically indicating a bug or system failure that should be investigated.
    """
    
    def __init__(
        self,
        message: str = "Internal server error",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an InternalError.
        
        Args:
            message: Human-readable error message (default: "Internal server error")
            details: Optional dictionary with additional error context
        """
        logger.error(f"Internal error: {message}")
        super().__init__(message, ErrorCode.INTERNAL_ERROR, details)


def stt_error_to_http_exception(error: STTError) -> HTTPException:
    """
    Convert an STTError to an HTTPException.
    
    Maps the application-specific error code to an appropriate HTTP status code
    and constructs a standardized error response with the error details.
    
    Args:
        error: The STTError to convert
        
    Returns:
        HTTPException with appropriate status code and detail
    """
    status_code_map = {
        ErrorCode.INVALID_API_KEY: status.HTTP_401,
        ErrorCode.MISSING_API_KEY: status.HTTP_401,
        ErrorCode.EXPIRED_API_KEY: status.HTTP_401,
        ErrorCode.INSUFFICIENT_SCOPE: status.HTTP_403,
        ErrorCode.FORBIDDEN: status.HTTP_403,
        ErrorCode.INVALID_INPUT: status.HTTP_400,
        ErrorCode.MISSING_REQUIRED_FIELD: status.HTTP_400,
        ErrorCode.INVALID_UUID: status.HTTP_400,
        ErrorCode.INVALID_VALUE: status.HTTP_400,
        ErrorCode.VALUE_OUT_OF_RANGE: status.HTTP_400,
        ErrorCode.RESOURCE_NOT_FOUND: status.HTTP_404,
        ErrorCode.RESOURCE_ALREADY_EXISTS: status.HTTP_409,
        ErrorCode.RESOURCE_CONFLICT: status.HTTP_409,
        ErrorCode.RATE_LIMIT_EXCEEDED: status.HTTP_429,
        ErrorCode.TOO_MANY_REQUESTS: status.HTTP_429,
        ErrorCode.CONCURRENT_LIMIT_EXCEEDED: status.HTTP_429,
        ErrorCode.STREAM_LIMIT_EXCEEDED: status.HTTP_429,
        ErrorCode.SERVICE_UNAVAILABLE: status.HTTP_503,
        ErrorCode.BACKEND_UNHEALTHY: status.HTTP_503,
        ErrorCode.INTERNAL_ERROR: status.HTTP_500,
        ErrorCode.DATABASE_ERROR: status.HTTP_500,
        ErrorCode.DATABASE_CONNECTION_FAILED: status.HTTP_503,
        ErrorCode.CONFIGURATION_ERROR: status.HTTP_500,
    }
    
    status_code = status_code_map.get(error.code, status.HTTP_500)
    
    detail = {
        "error": error.code.value,
        "message": error.message,
    }
    
    if error.details:
        detail.update(error.details)
    
    logger.debug(f"Converted STTError to HTTPException: {error.code.value} -> {status_code}")
    return HTTPException(status_code=status_code, detail=detail)


def handle_exception(error: Exception) -> HTTPException:
    """
    Handle any exception and convert to appropriate HTTPException.
    
    This is a catch-all exception handler that converts both custom STTError
    exceptions and standard Python exceptions to appropriate HTTP exceptions
    with standardized error responses.
    
    Args:
        error: The exception to handle
        
    Returns:
        HTTPException with appropriate status code and detail
    """
    if isinstance(error, STTError):
        return stt_error_to_http_exception(error)
    
    # Handle known exception types
    if isinstance(error, ValueError):
        logger.debug(f"Converted ValueError to HTTPException: {str(error)}")
        return HTTPException(
            status_code=status.HTTP_400,
            detail={
                "error": ErrorCode.INVALID_VALUE.value,
                "message": str(error),
            },
        )
    
    if isinstance(error, KeyError):
        logger.debug(f"Converted KeyError to HTTPException: {str(error)}")
        return HTTPException(
            status_code=status.HTTP_400,
            detail={
                "error": ErrorCode.MISSING_REQUIRED_FIELD.value,
                "message": f"Missing required field: {str(error)}",
            },
        )
    
    # Generic internal error
    logger.error(f"Unhandled exception converted to internal error: {type(error).__name__}: {str(error)}")
    return HTTPException(
        status_code=status.HTTP_500,
        detail={
            "error": ErrorCode.INTERNAL_ERROR.value,
            "message": "An internal error occurred",
        },
    )


def create_error_response(
    code: ErrorCode,
    message: str,
    status_code: int = 500,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Constructs a dictionary representing a standardized error response that can
    be returned from API endpoints. Includes the error code, message, and
    any additional details.
    
    Args:
        code: Error code from ErrorCode enum
        message: Human-readable error message
        status_code: HTTP status code (for reference, not included in response)
        details: Optional dictionary with additional error context
        
    Returns:
        Dictionary containing standardized error information
    """
    response = {
        "error": code.value,
        "message": message,
    }
    
    if details:
        response.update(details)
    
    logger.debug(f"Created error response: {code.value} - {message}")
    return response
