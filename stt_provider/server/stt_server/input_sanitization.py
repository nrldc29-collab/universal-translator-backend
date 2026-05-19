"""
Input sanitization utilities for security.

This module provides comprehensive input sanitization to prevent common security
vulnerabilities including SQL injection, XSS attacks, and path traversal.
It sanitizes various input types including strings, SQL identifiers, UUIDs,
integers, booleans, lists, and file paths.

The sanitizer provides:
- SQL injection pattern detection and removal
- XSS pattern detection and HTML escaping
- Path traversal prevention
- Type validation and range checking
- Configurable sanitization rules

Example:
    from stt_server.input_sanitization import get_sanitizer

    sanitizer = get_sanitizer()
    
    # Sanitize user input
    safe_string = sanitizer.sanitize_string(user_input)
    
    # Validate UUID
    uuid = sanitizer.sanitize_uuid(user_uuid)
    if uuid is None:
        raise ValueError("Invalid UUID")
    
    # Check for SQL injection
    if sanitizer.check_for_sql_injection(query):
        raise SecurityError("SQL injection detected")
"""
import logging
import re
import html
from typing import Callable, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class InputSanitizer:
    """
    Sanitize user input to prevent injection attacks.
    
    This class provides methods to sanitize various types of user input
    including strings, SQL identifiers, UUIDs, integers, booleans, lists,
    and file paths. It helps prevent common security vulnerabilities like
    SQL injection, XSS, and path traversal attacks.
    
    The sanitizer uses pattern matching to detect and remove malicious
    patterns, applies HTML escaping to prevent XSS, and enforces
    type and range constraints on input values.
    
    Security Features:
        - SQL injection pattern detection and removal
        - XSS pattern detection and HTML escaping
        - Path traversal prevention
        - Input length limits
        - Type validation and range checking
    """
    
    # SQL injection patterns to detect
    SQL_INJECTION_PATTERNS = [
        r"(\bSELECT\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bUNION\b.*\bSELECT\b)",
        r"(--|;|\/\*|\*\/)",
    ]
    
    # XSS patterns to detect
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
    ]
    
    @staticmethod
    def sanitize_string(
        input_string: str,
        max_length: int = 1000,
        allow_html: bool = False,
    ) -> str:
        """
        Sanitize a string input.
        
        Performs comprehensive string sanitization including length truncation,
        null byte removal, HTML escaping, and XSS pattern removal.
        
        Args:
            input_string: The string to sanitize
            max_length: Maximum allowed length (default: 1000)
            allow_html: Whether to allow HTML tags (default: False)
            
        Returns:
            Sanitized string with HTML escaped and XSS patterns removed
        """
        if not isinstance(input_string, str):
            input_string = str(input_string)
        
        original_length = len(input_string)
        
        # Truncate to max length
        if len(input_string) > max_length:
            input_string = input_string[:max_length]
            logger.debug(f"Truncated string from {original_length} to {max_length} characters")
        
        # Remove null bytes
        input_string = input_string.replace("\x00", "")
        
        # Escape HTML unless explicitly allowed
        if not allow_html:
            input_string = html.escape(input_string)
        
        # Remove common XSS patterns
        patterns_removed = 0
        for pattern in InputSanitizer.XSS_PATTERNS:
            if re.search(pattern, input_string, re.IGNORECASE):
                input_string = re.sub(pattern, "", input_string, flags=re.IGNORECASE)
                patterns_removed += 1
        
        if patterns_removed > 0:
            logger.warning(f"Removed {patterns_removed} XSS patterns from input")
        
        return input_string
    
    @staticmethod
    def sanitize_sql_identifier(input_string: str) -> str:
        """
        Sanitize a SQL identifier (table name, column name, etc.).
        
        Removes SQL injection patterns and restricts the identifier to
        only alphanumeric characters, underscores, and hyphens.
        
        Args:
            input_string: The identifier to sanitize
            
        Returns:
            Sanitized identifier with SQL injection patterns removed
        """
        if not isinstance(input_string, str):
            input_string = str(input_string)
        
        original = input_string
        
        # Remove SQL injection patterns
        patterns_removed = 0
        for pattern in InputSanitizer.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_string, re.IGNORECASE):
                input_string = re.sub(pattern, "", input_string, flags=re.IGNORECASE)
                patterns_removed += 1
        
        # Only allow alphanumeric, underscores, and hyphens
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", input_string)
        
        if patterns_removed > 0:
            logger.warning(f"SQL injection patterns removed from identifier: {original[:50]}")
        
        if sanitized != original:
            logger.debug(f"SQL identifier sanitized: {original} -> {sanitized}")
        
        return sanitized
    
    @staticmethod
    def sanitize_uuid(input_string: str) -> Optional[UUID]:
        """
        Sanitize and validate a UUID.
        
        Validates that the input string is a properly formatted UUID.
        Returns None if the string is not a valid UUID.
        
        Args:
            input_string: The UUID string to validate
            
        Returns:
            UUID object if valid, None otherwise
        """
        if not isinstance(input_string, str):
            logger.debug(f"UUID validation failed: not a string (type: {type(input_string)})")
            return None
        
        try:
            uuid = UUID(input_string)
            logger.debug(f"UUID validated successfully: {input_string}")
            return uuid
        except (ValueError, AttributeError) as e:
            logger.debug(f"UUID validation failed for {input_string}: {e}")
            return None
    
    @staticmethod
    def sanitize_integer(
        input_value: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
    ) -> Optional[int]:
        """
        Sanitize and validate an integer input.
        
        Converts the input to an integer and validates it against
        optional minimum and maximum bounds.
        
        Args:
            input_value: The value to sanitize
            min_value: Minimum allowed value (optional)
            max_value: Maximum allowed value (optional)
            
        Returns:
            Integer if valid and within range, None otherwise
        """
        try:
            value = int(input_value)
            
            if min_value is not None and value < min_value:
                logger.debug(f"Integer value {value} below minimum {min_value}")
                return None
            
            if max_value is not None and value > max_value:
                logger.debug(f"Integer value {value} above maximum {max_value}")
                return None
            
            logger.debug(f"Integer validated: {value}")
            return value
        except (ValueError, TypeError) as e:
            logger.debug(f"Integer validation failed for {input_value}: {e}")
            return None
    
    @staticmethod
    def sanitize_boolean(input_value: str) -> Optional[bool]:
        """
        Sanitize and validate a boolean input.
        
        Accepts common boolean representations including:
        - True: "true", "1", "yes", "on" (case-insensitive)
        - False: "false", "0", "no", "off" (case-insensitive)
        
        Args:
            input_value: The value to sanitize
            
        Returns:
            Boolean if valid, None otherwise
        """
        if not isinstance(input_value, str):
            logger.debug(f"Boolean validation failed: not a string (type: {type(input_value)})")
            return None
        
        input_lower = input_value.lower()
        
        if input_lower in ("true", "1", "yes", "on"):
            logger.debug(f"Boolean validated as True: {input_value}")
            return True
        elif input_lower in ("false", "0", "no", "off"):
            logger.debug(f"Boolean validated as False: {input_value}")
            return False
        
        logger.debug(f"Boolean validation failed for: {input_value}")
        return None
    
    @staticmethod
    def sanitize_list(
        input_list: List[str],
        max_items: int = 100,
        item_sanitizer: Optional[Callable[[str], str]] = None,
    ) -> List[str]:
        """
        Sanitize a list of strings.
        
        Sanitizes each item in the list using either a custom sanitizer
        or the default string sanitizer. Enforces a maximum item limit.
        
        Args:
            input_list: The list to sanitize
            max_items: Maximum allowed items (default: 100)
            item_sanitizer: Optional function to sanitize each item
            
        Returns:
            Sanitized list
        """
        if not isinstance(input_list, list):
            logger.debug(f"List sanitization failed: not a list (type: {type(input_list)})")
            return []
        
        original_count = len(input_list)
        
        # Truncate to max items
        if len(input_list) > max_items:
            input_list = input_list[:max_items]
            logger.warning(f"Truncated list from {original_count} to {max_items} items")
        
        sanitized = []
        
        for item in input_list:
            if not isinstance(item, str):
                item = str(item)
            
            if item_sanitizer:
                item = item_sanitizer(item)
            else:
                item = InputSanitizer.sanitize_string(item)
            
            sanitized.append(item)
        
        logger.debug(f"List sanitized: {original_count} items -> {len(sanitized)} items")
        return sanitized
    
    @staticmethod
    def check_for_sql_injection(input_string: str) -> bool:
        """
        Check if input contains SQL injection patterns.
        
        Scans the input string for common SQL injection attack patterns
        including SELECT, INSERT, UPDATE, DELETE, DROP, UNION, and
        SQL comments.
        
        Args:
            input_string: The string to check
            
        Returns:
            True if injection pattern found, False otherwise
        """
        if not isinstance(input_string, str):
            return False
        
        for pattern in InputSanitizer.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_string, re.IGNORECASE):
                logger.warning(f"SQL injection pattern detected: {pattern}")
                return True
        
        return False
    
    @staticmethod
    def check_for_xss(input_string: str) -> bool:
        """
        Check if input contains XSS patterns.
        
        Scans the input string for common XSS attack patterns including
        script tags, javascript: URLs, event handlers, and other
        potentially dangerous HTML elements.
        
        Args:
            input_string: The string to check
            
        Returns:
            True if XSS pattern found, False otherwise
        """
        if not isinstance(input_string, str):
            return False
        
        for pattern in InputSanitizer.XSS_PATTERNS:
            if re.search(pattern, input_string, re.IGNORECASE):
                logger.warning(f"XSS pattern detected: {pattern}")
                return True
        
        return False
    
    @staticmethod
    def sanitize_path(input_string: str) -> str:
        """
        Sanitize a file path to prevent directory traversal.
        
        Removes path traversal attempts (..), normalizes path separators,
        removes leading slashes to prevent absolute paths, and restricts
        to safe characters only.
        
        Args:
            input_string: The path to sanitize
            
        Returns:
            Sanitized path
        """
        if not isinstance(input_string, str):
            input_string = str(input_string)
        
        original = input_string
        
        # Remove null bytes
        input_string = input_string.replace("\x00", "")
        
        # Remove path traversal attempts
        if ".." in input_string:
            logger.warning(f"Path traversal attempt detected: {original}")
            input_string = input_string.replace("..", "")
        
        input_string = input_string.replace("\\", "/")
        
        # Remove leading slashes to prevent absolute paths
        input_string = input_string.lstrip("/")
        
        # Only allow safe characters
        sanitized = re.sub(r"[^a-zA-Z0-9_\-./]", "", input_string)
        
        if sanitized != original:
            logger.debug(f"Path sanitized: {original} -> {sanitized}")
        
        return sanitized


# Global sanitizer instance
_global_sanitizer: Optional[InputSanitizer] = None


def get_sanitizer() -> InputSanitizer:
    """
    Get the global input sanitizer instance.
    
    Returns a singleton instance of the InputSanitizer class for
    consistent input sanitization across the application.
    
    Returns:
        Global InputSanitizer instance
    """
    global _global_sanitizer
    
    if _global_sanitizer is None:
        _global_sanitizer = InputSanitizer()
        logger.info("Created global input sanitizer instance")
    
    return _global_sanitizer
