"""
Bulk operation utilities for the STT application.

This module provides utilities for processing bulk operations on lists of items,
with support for error handling, validation, and result aggregation. It includes
Pydantic models for request/response validation and async processing functions.

The bulk operations support:
- Processing multiple items with a single function
- Configurable error handling (stop on first error or continue)
- Result aggregation with success/failure statistics
- Request size validation
- Detailed error reporting with item indices

Example:
    from stt_server.bulk_operations import process_bulk_operation, validate_bulk_request_size

    async def create_item(item):
        # Process a single item
        return await db.insert(item)

    # Validate request size
    is_valid, error = validate_bulk_request_size(items, max_size=100)
    if not is_valid:
        raise ValueError(error)

    # Process bulk operation
    result = await process_bulk_operation(items, create_item, stop_on_error=False)
    print(f"Successful: {result.successful}, Failed: {result.failed}")
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class BulkOperationResult:
    """
    Result of a bulk operation.
    
    Contains statistics and results from processing a bulk operation,
    including counts of successful and failed operations, error details,
    and the results of successful operations.
    
    Attributes:
        successful: Number of items processed successfully
        failed: Number of items that failed to process
        errors: List of error dictionaries with index and error information
        results: List of results from successful operations
    """
    successful: int
    failed: int
    errors: List[Dict[str, Any]]
    results: List[Any]


class BulkRequest(BaseModel):
    """
    Base model for bulk requests.
    
    Pydantic model for validating bulk operation requests, including
    the list of items to process and configuration for error handling.
    
    Attributes:
        items: List of items to process (required)
        stop_on_error: Whether to stop processing on first error (default: False)
    """
    items: List[Any] = Field(..., description="List of items to process")
    stop_on_error: bool = Field(default=False, description="Stop processing on first error")


class BulkResponse(BaseModel):
    """
    Response model for bulk operations.
    
    Pydantic model for bulk operation responses, providing statistics
    on the operation outcome including success/failure counts and
    detailed error information.
    
    Attributes:
        successful: Number of successful operations
        failed: Number of failed operations
        total: Total number of operations attempted
        results: Results from successful operations
        errors: Errors from failed operations with index and message
    """
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    total: int = Field(..., description="Total number of operations")
    results: List[Any] = Field(default_factory=list, description="Results of successful operations")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Errors from failed operations")
    
    class Config:
        json_schema_extra = {
            "example": {
                "successful": 10,
                "failed": 2,
                "total": 12,
                "results": [],
                "errors": [
                    {
                        "index": 5,
                        "error": "validation_error",
                        "message": "Invalid data",
                    }
                ],
            }
        }


async def process_bulk_operation(
    items: List[Any],
    process_func,
    stop_on_error: bool = False,
) -> BulkOperationResult:
    """
    Process a bulk operation on a list of items.
    
    Iterates through the list of items and applies the provided async processing
    function to each. Collects results and errors, with configurable error handling
    to either stop on the first error or continue processing all items.
    
    Args:
        items: List of items to process
        process_func: Async function to process each item
        stop_on_error: Whether to stop processing on first error (default: False)
        
    Returns:
        BulkOperationResult with statistics and results
    """
    successful = 0
    failed = 0
    errors = []
    results = []
    
    logger.info(f"Starting bulk operation on {len(items)} items (stop_on_error={stop_on_error})")
    
    for index, item in enumerate(items):
        try:
            result = await process_func(item)
            results.append(result)
            successful += 1
            logger.debug(f"Successfully processed item {index}")
        except Exception as e:
            failed += 1
            error_info = {
                "index": index,
                "error": type(e).__name__,
                "message": str(e),
            }
            errors.append(error_info)
            logger.warning(f"Failed to process item {index}: {type(e).__name__}: {str(e)}")
            
            if stop_on_error:
                logger.info(f"Stopping bulk operation due to error at index {index}")
                break
    
    logger.info(
        f"Bulk operation completed: {successful} successful, {failed} failed, "
        f"{len(items) - successful - failed} skipped"
    )
    
    return BulkOperationResult(
        successful=successful,
        failed=failed,
        errors=errors,
        results=results,
    )


def validate_bulk_request_size(items: List[Any], max_size: int = 100) -> tuple[bool, str | None]:
    """
    Validate bulk request size.
    
    Validates that the bulk request contains items and does not exceed
    the maximum allowed size. This prevents oversized requests that
    could overwhelm the system.
    
    Args:
        items: List of items to validate
        max_size: Maximum allowed number of items (default: 100)
        
    Returns:
        Tuple of (is_valid, error_message) where is_valid is True if
        the request passes validation, and error_message is None if valid
        or contains the error message if invalid
    """
    if len(items) == 0:
        logger.warning("Bulk request validation failed: empty request")
        return False, "Bulk request cannot be empty"
    
    if len(items) > max_size:
        logger.warning(
            f"Bulk request validation failed: {len(items)} items exceeds maximum of {max_size}"
        )
        return False, f"Bulk request too large: {len(items)} items exceeds maximum of {max_size}"
    
    logger.debug(f"Bulk request size validated: {len(items)} items (max: {max_size})")
    return True, None
