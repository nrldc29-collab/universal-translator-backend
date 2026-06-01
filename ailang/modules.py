"""AILang module resolver for importing .ai files.

Resolves `import mymodule` to find `mymodule.ai` on disk, transpile it,
and make its exports available to the importing module.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .ast_nodes import (
    AgentDecl,
    ConstDecl,
    FunctionDecl,
    ImportDecl,
    ModelDecl,
    Program,
)
from .errors import AILangRuntimeError
from .parser import parse_source
from .transpiler import Transpiler

# Default search paths for .ai modules
DEFAULT_SEARCH_PATHS: list[str] = ["."]

# Cache of already-resolved modules to avoid re-parsing
_MODULE_CACHE_MAX = 64
_module_cache: dict[str, ResolvedModule] = {}

# Track modules currently being resolved (circular import detection)
_resolving: set[str] = set()


class ResolvedModule:
    """A fully resolved AILang module."""

    def __init__(self, name: str, path: Path, program: Program, python_code: str) -> None:
        self.name = name
        self.path = path
        self.program = program
        self.python_code = python_code
        self.exports: dict[str, str] = {}  # name -> type (function, const, model, agent)

    def __repr__(self) -> str:
        return f"ResolvedModule({self.name!r}, {self.path})"


def reset_cache() -> None:
    """Clear the module cache. Useful for testing."""
    global _module_cache, _resolving
    _module_cache = {}
    _resolving = set()


def find_module(module_name: str, search_paths: list[str] | None = None) -> Path | None:
    """Find an .ai module file on disk.

    Supports:
    - `import utils` → `utils.ai`
    - `import libs.math_utils` → `libs/math_utils.ai`
    - `import libs/math_utils` → `libs/math_utils.ai`

    Search order:
    1. Relative to the importing file's directory (if any)
    2. Directories in search_paths
    3. AILANG_PATH environment variable directories
    """
    if search_paths is None:
        search_paths = DEFAULT_SEARCH_PATHS.copy()

    # Also check AILANG_PATH env var
    ailang_path = getattr(sys, "ailang_path", None)
    if ailang_path:
        search_paths.extend(ailang_path.split(";") if ";" in ailang_path else ailang_path.split(":"))

    # Convert dot notation to path: libs.math_utils → libs/math_utils
    # Slash notation stays as-is: libs/math_utils → libs/math_utils
    relative_path = module_name.replace(".", "/")
    candidates = [f"{relative_path}.ai"]

    for search_dir in search_paths:
        base = Path(search_dir)
        for candidate in candidates:
            full_path = base / candidate
            if full_path.exists() and full_path.is_file():
                return full_path.resolve()
        # Also check subdirectories matching the module name
        subdir = base / relative_path
        if subdir.is_dir():
            init_path = subdir / "init.ai"
            if init_path.exists():
                return init_path.resolve()

    return None


def resolve_module(
    module_name: str,
    search_paths: list[str] | None = None,
    importing_file: Path | None = None,
) -> ResolvedModule:
    """Resolve and transpile an AILang module.

    Args:
        module_name: The module name to resolve
        search_paths: Directories to search for .ai files
        importing_file: Path of the file doing the import (for relative resolution)

    Returns:
        A ResolvedModule with the parsed AST and transpiled Python code

    Raises:
        AILangRuntimeError: If the module cannot be found or has circular imports
    """
    # Check cache first
    if module_name in _module_cache:
        return _module_cache[module_name]

    # Circular import detection
    if module_name in _resolving:
        raise AILangRuntimeError(
            f"Circular import detected: '{module_name}' is already being resolved"
        )

    _resolving.add(module_name)

    try:
        # Build search paths: start with importing file's directory
        paths = list(search_paths) if search_paths else []
        if importing_file:
            paths.insert(0, str(importing_file.parent))

        # Find the module file
        module_path = find_module(module_name, paths)
        if module_path is None:
            raise AILangRuntimeError(
                f"Module '{module_name}' not found. Searched: {paths}"
            )

        # Parse the module source
        try:
            source = module_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise AILangRuntimeError(
                f"Module '{module_name}' at {module_path} is not valid UTF-8: {exc}"
            ) from exc
        except PermissionError as exc:
            raise AILangRuntimeError(
                f"Permission denied reading module '{module_name}' at {module_path}"
            ) from exc
        program = parse_source(source)

        # Resolve any sub-imports in this module first
        for node in program.body:
            if isinstance(node, ImportDecl):
                if not _is_python_stdlib(node.module):
                    resolve_module(node.module, paths, module_path)

        # Transpile to Python
        transpiler = Transpiler()
        python_code = transpiler.transpile(program)

        # Build the resolved module
        resolved = ResolvedModule(module_name, module_path, program, python_code)

        # Extract exports (functions, consts, models, agents)
        for node in program.body:
            if isinstance(node, FunctionDecl):
                resolved.exports[node.name] = "function"
            elif isinstance(node, ConstDecl):
                resolved.exports[node.name] = "const"
            elif isinstance(node, ModelDecl):
                resolved.exports[node.name] = "model"
            elif isinstance(node, AgentDecl):
                resolved.exports[node.name] = "agent"

        # Cache the result
        _module_cache[module_name] = resolved
        # Evict oldest entries if cache is too large
        if len(_module_cache) > _MODULE_CACHE_MAX:
            oldest = next(iter(_module_cache))
            del _module_cache[oldest]
        return resolved

    finally:
        _resolving.discard(module_name)


def _is_python_stdlib(module_name: str) -> bool:
    """Check if a module name is likely a Python standard library module."""
    # Common Python stdlib modules
    stdlib_modules = {
        "abc", "argparse", "array", "ast", "asyncio", "base64", "bisect",
        "calendar", "collections", "configparser", "contextlib", "copy",
        "csv", "datetime", "decimal", "difflib", "email", "enum",
        "fileinput", "fnmatch", "fractions", "functools", "glob", "gzip",
        "hashlib", "heapq", "html", "http", "importlib", "inspect", "io",
        "itertools", "json", "keyword", "linecache", "logging", "math",
        "mmap", "multiprocessing", "numbers", "operator", "os", "pathlib",
        "pickle", "platform", "pprint", "queue", "random", "re", "secrets",
        "shutil", "signal", "socket", "sqlite3", "statistics", "string",
        "struct", "subprocess", "sys", "tarfile", "tempfile", "textwrap",
        "threading", "time", "traceback", "typing", "unittest", "urllib",
        "uuid", "venv", "warnings", "weakref", "xml", "zipfile", "zlib",
        # Common third-party
        "numpy", "pandas", "requests", "flask", "django", "pytest",
        "openai", "anthropic",
    }
    top_level = module_name.split(".")[0]
    return top_level in stdlib_modules
