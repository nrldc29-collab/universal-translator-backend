"""
Database query optimization utilities for the STT application.

This module provides utilities for optimizing database queries, including
pagination, filtering, column selection, index hints, and query validation.
It helps improve database performance and ensure query safety.

The optimization utilities support:
- Query pagination with offset/limit
- Tenant isolation filtering
- Date range filtering
- Soft delete filtering
- Column selection optimization
- Index hinting
- Slow query logging
- Query validation for safety
- Index suggestion based on query patterns

Example:
    from stt_server.database_optimization import get_query_optimizer

    optimizer = get_query_optimizer()
    
    # Add pagination to a query
    query = "SELECT * FROM users"
    paginated = optimizer.add_pagination(query, offset=0, limit=50)
    
    # Add tenant filter
    filtered = optimizer.add_filter_by_tenant(paginated, tenant_id="abc123")
    
    # Validate the query
    is_valid, error = optimizer.validate_query(filtered)
    if not is_valid:
        raise ValueError(f"Invalid query: {error}")
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """
    Helper class for optimizing database queries.
    
    Provides static methods for modifying and validating SQL queries to improve
    performance and ensure safety. Supports common query patterns like pagination,
    filtering, and column optimization.
    """
    
    @staticmethod
    def add_pagination(
        query: str,
        offset: int = 0,
        limit: int = 50,
    ) -> str:
        """
        Add pagination to a SQL query.
        
        Appends LIMIT and OFFSET clauses to control the number of rows returned,
        preventing large result sets that could impact performance.
        
        Args:
            query: The base SQL query
            offset: Number of rows to skip (default: 0)
            limit: Maximum number of rows to return (default: 50)
            
        Returns:
            Query with pagination clause added
        """
        if limit <= 0:
            limit = 50
            logger.debug(f"Invalid limit {limit}, using default 50")
        
        if offset < 0:
            offset = 0
            logger.debug(f"Invalid offset {offset}, using default 0")
        
        paginated_query = f"{query} LIMIT {limit} OFFSET {offset}"
        logger.debug(f"Added pagination: limit={limit}, offset={offset}")
        
        return paginated_query
    
    @staticmethod
    def add_filter_by_tenant(
        query: str,
        tenant_id: str,
        tenant_column: str = "tenant_id",
    ) -> str:
        """
        Add tenant filter to a SQL query.
        
        Adds a WHERE clause to filter results by tenant ID, ensuring multi-tenant
        data isolation. Intelligently handles queries that already have WHERE clauses.
        
        Args:
            query: The base SQL query
            tenant_id: Tenant ID to filter by
            tenant_column: Name of the tenant ID column (default: "tenant_id")
            
        Returns:
            Query with tenant filter added
        """
        # Check if query already has a WHERE clause
        if "WHERE" in query.upper():
            filtered_query = f"{query} AND {tenant_column} = '{tenant_id}'"
        else:
            filtered_query = f"{query} WHERE {tenant_column} = '{tenant_id}'"
        
        logger.debug(f"Added tenant filter: {tenant_column} = '{tenant_id}'")
        return filtered_query
    
    @staticmethod
    def add_date_range_filter(
        query: str,
        date_column: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        """
        Add date range filter to a SQL query.
        
        Adds WHERE clause conditions to filter results by a date range.
        Supports inclusive start and end dates.
        
        Args:
            query: The base SQL query
            date_column: Name of the date column
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            Query with date range filter added
        """
        conditions = []
        
        if start_date:
            conditions.append(f"{date_column} >= '{start_date.isoformat()}'")
        
        if end_date:
            conditions.append(f"{date_column} <= '{end_date.isoformat()}'")
        
        if not conditions:
            logger.debug("No date range conditions provided, returning original query")
            return query
        
        filter_clause = " AND ".join(conditions)
        
        if "WHERE" in query.upper():
            filtered_query = f"{query} AND {filter_clause}"
        else:
            filtered_query = f"{query} WHERE {filter_clause}"
        
        logger.debug(f"Added date range filter: {date_column} between {start_date} and {end_date}")
        return filtered_query
    
    @staticmethod
    def add_soft_delete_filter(
        query: str,
        deleted_at_column: str = "deleted_at",
    ) -> str:
        """
        Add soft delete filter to exclude deleted records.
        
        Adds a WHERE clause to filter out records that have been soft-deleted
        (where the deleted_at column is not NULL).
        
        Args:
            query: The base SQL query
            deleted_at_column: Name of the deleted_at column (default: "deleted_at")
            
        Returns:
            Query with soft delete filter added
        """
        if "WHERE" in query.upper():
            filtered_query = f"{query} AND {deleted_at_column} IS NULL"
        else:
            filtered_query = f"{query} WHERE {deleted_at_column} IS NULL"
        
        logger.debug(f"Added soft delete filter: {deleted_at_column} IS NULL")
        return filtered_query
    
    @staticmethod
    def optimize_select_columns(
        query: str,
        columns: List[str],
    ) -> str:
        """
        Optimize SELECT clause to only include specified columns.
        
        Replaces SELECT * with specific columns to reduce data transfer
        and improve query performance.
        
        Args:
            query: The base SQL query
            columns: List of column names to select
            
        Returns:
            Query with optimized SELECT clause
        """
        if not columns:
            logger.debug("No columns specified, returning original query")
            return query
        
        columns_str = ", ".join(columns)
        
        # Replace SELECT * with specific columns
        if "SELECT *" in query.upper():
            optimized_query = query.replace("SELECT *", f"SELECT {columns_str}")
            logger.debug(f"Optimized SELECT to include columns: {columns_str}")
            return optimized_query
        
        logger.debug("Query does not use SELECT *, no optimization needed")
        return query
    
    @staticmethod
    def add_index_hint(
        query: str,
        index_name: str,
        table_name: Optional[str] = None,
    ) -> str:
        """
        Add index hint to a SQL query (PostgreSQL syntax).
        
        Note: PostgreSQL doesn't support index hints directly. This method
        is provided for databases that do support hints (SQLite, MySQL).
        For PostgreSQL, consider using proper indexes and query planning.
        
        Args:
            query: The base SQL query
            index_name: Name of the index to use
            table_name: Optional table name (for FROM clause)
            
        Returns:
            Query with index hint added (if applicable)
        """
        # This is PostgreSQL-specific syntax (which doesn't actually support hints)
        # For databases that support hints (SQLite, MySQL), this would work
        if table_name:
            hinted_query = query.replace(f"FROM {table_name}", f"FROM {table_name} INDEXED BY {index_name}")
            logger.debug(f"Added index hint: {index_name} on {table_name}")
            return hinted_query
        
        logger.debug("No table name provided, index hint not added")
        return query
    
    @staticmethod
    def log_slow_query(
        query: str,
        duration_ms: float,
        threshold_ms: float = 100.0,
    ) -> None:
        """
        Log slow queries for monitoring.
        
        Logs queries that exceed the specified duration threshold,
        helping identify performance issues.
        
        Args:
            query: The SQL query that was executed
            duration_ms: Execution time in milliseconds
            threshold_ms: Threshold for considering a query slow (default: 100ms)
        """
        if duration_ms > threshold_ms:
            logger.warning(
                "Slow query detected",
                extra={
                    "query": query[:500],  # Truncate long queries
                    "duration_ms": duration_ms,
                    "threshold_ms": threshold_ms,
                },
            )
    
    @staticmethod
    def suggest_indexes(
        table_name: str,
        query_patterns: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Suggest indexes based on query patterns.
        
        Analyzes WHERE clause patterns to suggest potentially beneficial
        indexes. This is a basic heuristic and should be validated with
        actual query performance analysis.
        
        Args:
            table_name: Name of the table
            query_patterns: List of WHERE clause patterns
            
        Returns:
            List of suggested indexes with columns and index names
        """
        suggestions = []
        
        for pattern in query_patterns:
            # Extract column names from simple patterns
            columns = []
            
            # Look for column = value patterns
            if "=" in pattern:
                parts = pattern.split("=")
                if len(parts) >= 2:
                    column = parts[0].strip()
                    if column and not column.startswith("("):
                        columns.append(column)
            
            # Look for column IN patterns
            if " IN " in pattern.upper():
                parts = pattern.upper().split(" IN ")
                if len(parts) >= 2:
                    column = parts[0].strip()
                    if column and not column.startswith("("):
                        columns.append(column)
            
            if columns:
                suggestions.append({
                    "table": table_name,
                    "columns": columns,
                    "index_name": f"idx_{table_name}_{'_'.join(columns)}",
                })
        
        if suggestions:
            logger.info(f"Suggested {len(suggestions)} indexes for table {table_name}")
        
        return suggestions
    
    @staticmethod
    def validate_query(query: str) -> tuple[bool, Optional[str]]:
        """
        Basic SQL query validation.
        
        Performs basic safety checks on SQL queries, including detection
        of dangerous operations without WHERE clauses and warnings for
        SELECT queries without LIMIT clauses.
        
        Args:
            query: The SQL query to validate
            
        Returns:
            Tuple of (is_valid, error_message) where is_valid is True if
            the query passes validation, and error_message contains details
            if validation fails
        """
        if not query or not query.strip():
            logger.warning("Query validation failed: empty query")
            return False, "Query is empty"
        
        query_upper = query.upper()
        
        # Check for dangerous operations
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER"]
        for keyword in dangerous_keywords:
            if keyword in query_upper and "WHERE" not in query_upper:
                logger.error(f"Query validation failed: {keyword} without WHERE clause")
                return False, f"Dangerous operation {keyword} without WHERE clause"
        
        # Check for SELECT without LIMIT on large tables
        if "SELECT" in query_upper and "LIMIT" not in query_upper:
            logger.warning(
                "SELECT query without LIMIT clause",
                extra={"query": query[:200]},
            )
        
        logger.debug("Query validation passed")
        return True, None
    
    @staticmethod
    def get_query_hash(query: str) -> str:
        """
        Generate a hash for query caching/identification.
        
        Normalizes whitespace in the query and generates an MD5 hash,
        useful for query caching, deduplication, and tracking.
        
        Args:
            query: The SQL query
            
        Returns:
            Hash string (MD5 hex digest)
        """
        import hashlib
        # Normalize whitespace
        normalized = " ".join(query.split())
        hash_value = hashlib.md5(normalized.encode()).hexdigest()
        logger.debug(f"Generated query hash: {hash_value}")
        return hash_value


# Global query optimizer instance
_global_optimizer: Optional[QueryOptimizer] = None


def get_query_optimizer() -> QueryOptimizer:
    """
    Get the global query optimizer instance.
    
    Returns a singleton instance of the QueryOptimizer for consistent
    query optimization across the application.
    
    Returns:
        Global QueryOptimizer instance
    """
    global _global_optimizer
    
    if _global_optimizer is None:
        _global_optimizer = QueryOptimizer()
        logger.info("Created global query optimizer instance")
    
    return _global_optimizer
