"""
Pagination utilities for API responses.

This module provides data classes and functions for handling pagination in API responses.
It includes validation of pagination parameters, calculation of database query offsets and limits,
and construction of paginated response metadata.

Classes:
    PaginationParams: Data class for pagination parameters with validation.
    PaginatedResponse: Generic Pydantic model for paginated API responses.

Functions:
    paginate: Create a paginated response dictionary from items and metadata.
    get_pagination_params: Create PaginationParams from query parameters.

Usage:
    Use PaginationParams to parse and validate pagination query parameters.
    Use paginate to construct paginated response dictionaries for API endpoints.
    Use PaginatedResponse as the response model for FastAPI endpoints.
"""
import logging
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, List, Dict
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PaginationParams:
    """
    Pagination parameters for API requests.
    
    Validates and stores pagination parameters including page number and page size.
    Enforces constraints: page >= 1, page_size between 1 and 100.
    
    Attributes:
        page: Current page number (1-indexed, default 1).
        page_size: Number of items per page (default 50, max 100).
    """
    page: int = 1
    page_size: int = 50
    
    def __post_init__(self) -> None:
        """
        Validate pagination parameters after initialization.
        
        Raises:
            ValueError: If page < 1 or page_size is outside [1, 100].
        """
        # Validate page
        if self.page < 1:
            raise ValueError("page must be >= 1")
        
        # Validate page_size
        if self.page_size < 1:
            raise ValueError("page_size must be >= 1")
        if self.page_size > 100:
            raise ValueError("page_size must be <= 100")
        
        logger.debug(f"Pagination params validated: page={self.page}, page_size={self.page_size}")
    
    @property
    def offset(self) -> int:
        """
        Calculate offset for database queries.
        
        Returns:
            The offset (number of items to skip) for the current page.
        """
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """
        Get limit for database queries.
        
        Returns:
            The maximum number of items to return for the current page.
        """
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response model for API endpoints.
    
    Provides a standardized structure for paginated API responses including
    the items for the current page and metadata about pagination state.
    
    Attributes:
        items: List of items in the current page.
        total: Total number of items across all pages.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
        total_pages: Total number of pages.
        has_next: Whether there is a next page.
        has_previous: Whether there is a previous page.
    """
    items: List[T] = Field(..., description="List of items in the current page")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")
    
    class Config:
        """Pydantic configuration for PaginatedResponse."""
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 50,
                "total_pages": 2,
                "has_next": True,
                "has_previous": False,
            }
        }


def paginate(items: List[Any], total: int, params: PaginationParams) -> Dict[str, Any]:
    """
    Create paginated response from items and total count.
    
    Constructs a dictionary with pagination metadata including the items
    for the current page, total count, and navigation flags.
    
    Args:
        items: List of items for the current page.
        total: Total number of items across all pages.
        params: Pagination parameters for the current request.
        
    Returns:
        Dictionary with pagination metadata including items, total, page,
        page_size, total_pages, has_next, and has_previous.
    """
    total_pages = (total + params.page_size - 1) // params.page_size
    
    result = {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": total_pages,
        "has_next": params.page < total_pages,
        "has_previous": params.page > 1,
    }
    
    logger.debug(f"Paginated response created: page={params.page}/{total_pages}, items={len(items)}, total={total}")
    
    return result


def get_pagination_params(page: int = 1, page_size: int = 50) -> PaginationParams:
    """
    Create pagination parameters from query params.
    
    Factory function to create a PaginationParams instance from
    query string parameters with default values.
    
    Args:
        page: Page number (default 1).
        page_size: Items per page (default 50, max 100).
        
    Returns:
        PaginationParams instance with validated parameters.
    """
    return PaginationParams(page=page, page_size=page_size)
