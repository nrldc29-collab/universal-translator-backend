"""
Async/await consistency checker utilities.

This module provides utilities to ensure async/await consistency across the codebase,
helping prevent common issues like missing await keywords, blocking calls in async functions,
and improper use of async context managers.

The checker detects:
- Missing await keywords on async function calls
- Blocking operations in async functions (time.sleep, subprocess.run, etc.)
- Async functions that don't use await or async patterns
- Sync functions calling async functions without proper handling

Example:
    from stt_server.async_consistency import check_async_consistency

    # Check a single file
    result = check_async_consistency("server/stt_server/main.py")
    print(f"Found {result['total_issues']} issues")

    # Check entire directory
    result = check_async_consistency("server/stt_server/")
    for file_path, issues in result['files'].items():
        print(f"{file_path}: {len(issues)} issues")
"""
import asyncio
import ast
import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AsyncConsistencyChecker:
    """
    Check Python files for async/await consistency issues.
    
    This class analyzes Python source code to detect common async/await anti-patterns
    and potential issues that could lead to blocking behavior or incorrect async usage.
    
    The checker performs the following analyses:
    - Missing await keywords on async function calls
    - Blocking operations in async functions
    - Async functions without await or async patterns
    - Sync functions calling async functions improperly
    
    Attributes:
        issues: List of detected issues, each containing file, line, message, and severity
    """
    
    def __init__(self):
        """Initialize the checker with an empty issues list."""
        self.issues: List[Dict[str, Any]] = []
        logger.debug("Initialized AsyncConsistencyChecker")
    
    def check_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Check a single Python file for async/await consistency issues.
        
        Parses the Python file and runs all consistency checks to detect potential
        async/await anti-patterns and issues.
        
        Args:
            file_path: Path to the Python file to check
            
        Returns:
            List of issues found, each containing file, line, message, and severity
        """
        self.issues = []
        logger.debug(f"Checking async consistency for file: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            # Run all checks
            self._check_missing_await(tree, file_path)
            self._check_blocking_in_async(tree, file_path)
            self._check_async_without_await(tree, file_path)
            self._check_sync_calling_async(tree, file_path)
            
            logger.info(f"Checked {file_path}: found {len(self.issues)} issues")
            
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path} at line {e.lineno}: {e.msg}")
            self.issues.append({
                'file': file_path,
                'line': e.lineno,
                'message': f"Syntax error: {e.msg}",
                'severity': 'error',
            })
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
            self.issues.append({
                'file': file_path,
                'line': 0,
                'message': f"Error analyzing file: {str(e)}",
                'severity': 'error',
            })
        
        return self.issues
    
    def _check_missing_await(self, tree: ast.AST, file_path: str) -> None:
        """
        Check for missing await keywords on async function calls.
        
        Detects calls to functions with names suggesting async behavior (e.g.,
        functions starting with 'async_' or ending with '_async') that are not
        preceded by the await keyword.
        
        Args:
            tree: AST tree of the Python file
            file_path: Path to the file being checked
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                continue
            
            # Check if we're calling an async function without await
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    # Check if attribute name suggests async
                    if func.attr.startswith('async_') or func.attr.endswith('_async'):
                        logger.debug(
                            f"Possible missing await in {file_path} line {node.lineno}: {func.attr}"
                        )
                        self.issues.append({
                            'file': file_path,
                            'line': node.lineno,
                            'message': f"Possible missing await on async function call: {func.attr}",
                            'severity': 'warning',
                        })
    
    def _check_blocking_in_async(self, tree: ast.AST, file_path: str) -> None:
        """
        Check for blocking operations in async functions.
        
        Detects calls to known blocking functions (time.sleep, subprocess.run, etc.)
        within async functions, which can block the event loop.
        
        Args:
            tree: AST tree of the Python file
            file_path: Path to the file being checked
        """
        blocking_calls = {
            'time.sleep',
            'subprocess.run',
            'os.system',
            'requests.get',
            'requests.post',
            'urllib.request.urlopen',
        }
        
        for node in ast.walk(tree):
            # Find async functions
            if isinstance(node, ast.AsyncFunctionDef):
                # Check for blocking calls within
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func_name = self._get_call_name(child)
                        if func_name in blocking_calls:
                            logger.debug(
                                f"Blocking call {func_name} in async function at {file_path} line {child.lineno}"
                            )
                            self.issues.append({
                                'file': file_path,
                                'line': child.lineno,
                                'message': f"Blocking call {func_name} in async function",
                                'severity': 'warning',
                            })
    
    def _check_async_without_await(self, tree: ast.AST, file_path: str) -> None:
        """
        Check for async functions that don't use await.
        
        Detects async functions that don't contain any await statements, yield expressions,
        or async context managers, which may indicate they should be synchronous functions.
        
        Args:
            tree: AST tree of the Python file
            file_path: Path to the file being checked
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Check if function body contains any await
                has_await = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Await):
                        has_await = True
                        break
                
                if not has_await:
                    # Check if it's a generator or has other async patterns
                    has_yield = any(isinstance(child, (ast.Yield, ast.YieldFrom)) 
                                 for child in ast.walk(node))
                    has_async_for = any(isinstance(child, ast.AsyncFor) 
                                      for child in ast.walk(node))
                    has_async_with = any(isinstance(child, ast.AsyncWith) 
                                       for child in ast.walk(node))
                    
                    if not (has_yield or has_async_for or has_async_with):
                        logger.debug(
                            f"Async function '{node.name}' in {file_path} has no await, yield, or async context"
                        )
                        self.issues.append({
                            'file': file_path,
                            'line': node.lineno,
                            'message': f"Async function '{node.name}' has no await, yield, or async context",
                            'severity': 'info',
                        })
    
    def _check_sync_calling_async(self, tree: ast.AST, file_path: str) -> None:
        """
        Check for sync functions calling async functions without proper handling.
        
        Detects synchronous functions that call async functions without using
        await or running them in an event loop, which will cause runtime errors.
        
        Args:
            tree: AST tree of the Python file
            file_path: Path to the file being checked
        """
        async_functions = set()
        
        # First pass: collect async function names
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                async_functions.add(node.name)
        
        # Second pass: check sync functions calling async functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func_name = self._get_call_name(child)
                        if func_name in async_functions:
                            logger.debug(
                                f"Sync function calling async function '{func_name}' in {file_path} line {child.lineno}"
                            )
                            self.issues.append({
                                'file': file_path,
                                'line': child.lineno,
                                'message': f"Sync function calling async function '{func_name}' without await",
                                'severity': 'warning',
                            })
    
    def _get_call_name(self, call_node: ast.Call) -> Optional[str]:
        """
        Extract the name of a function call.
        
        Attempts to extract the function name from a Call AST node, handling
        simple names, attributes, and nested calls.
        
        Args:
            call_node: AST Call node to extract name from
            
        Returns:
            Function name if found, None otherwise
        """
        func = call_node.func
        
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            return func.attr
        elif isinstance(func, ast.Call):
            return self._get_call_name(func)
        
        return None
    
    def check_directory(self, directory: str, pattern: str = "*.py") -> Dict[str, List[Dict[str, Any]]]:
        """
        Check all Python files in a directory.
        
        Recursively finds all Python files matching the pattern and runs
        async/await consistency checks on each.
        
        Args:
            directory: Directory path to check
            pattern: File pattern to match (default: *.py)
            
        Returns:
            Dictionary mapping file paths to lists of issues
        """
        results = {}
        logger.info(f"Checking directory {directory} with pattern {pattern}")
        
        for file_path in Path(directory).rglob(pattern):
            if file_path.is_file():
                issues = self.check_file(str(file_path))
                if issues:
                    results[str(file_path)] = issues
        
        logger.info(f"Checked directory: found issues in {len(results)} files")
        return results


def check_async_consistency(file_or_dir: str) -> Dict[str, Any]:
    """
    Check async/await consistency for a file or directory.
    
    Convenience function that creates a checker instance and runs checks
    on the specified path, handling both files and directories.
    
    Args:
        file_or_dir: Path to file or directory to check
        
    Returns:
        Dictionary with check results including total issues and file-specific issues
    """
    logger.info(f"Starting async consistency check for: {file_or_dir}")
    checker = AsyncConsistencyChecker()
    path = Path(file_or_dir)
    
    if path.is_file():
        issues = checker.check_file(str(path))
        result = {
            'total_issues': len(issues),
            'files': {str(path): issues} if issues else {},
        }
    elif path.is_dir():
        file_issues = checker.check_directory(str(path))
        total = sum(len(issues) for issues in file_issues.values())
        result = {
            'total_issues': total,
            'files': file_issues,
        }
    else:
        logger.warning(f"Path does not exist: {file_or_dir}")
        result = {
            'total_issues': 0,
            'files': {},
            'error': f"Path does not exist: {file_or_dir}",
        }
    
    logger.info(f"Completed async consistency check: {result['total_issues']} total issues")
    return result


def ensure_async_context(func):
    """
    Decorator to ensure a function is called in an async context.
    
    This decorator raises an error if the decorated function is called
    outside of an async context (i.e., not within a running event loop).
    This is useful for functions that must be called with await or within
    an event loop to function correctly.
    
    Args:
        func: Function to decorate (can be sync or async)
        
    Returns:
        Wrapped function that checks for async context before execution
        
    Raises:
        RuntimeError: If called outside of an async context
        
    Example:
        @ensure_async_context
        def my_function():
            # This will raise RuntimeError if not called from async context
            pass
    """
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
            logger.debug(f"Function {func.__name__} called in async context")
        except RuntimeError:
            logger.error(f"Function {func.__name__} called outside async context")
            raise RuntimeError(
                f"{func.__name__} must be called from an async context. "
                "Use 'await' or run it in an event loop."
            )
        return func(*args, **kwargs)
    
    return wrapper
