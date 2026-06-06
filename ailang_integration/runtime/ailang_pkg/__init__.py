"""AILang — a simple DSL for defining translation agents and pipelines."""
__version__ = "0.1.0"
from .parser import parse_source
from .transpiler import Transpiler

__all__ = ["parse_source", "Transpiler", "__version__"]
