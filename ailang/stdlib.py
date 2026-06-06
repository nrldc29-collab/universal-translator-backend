"""
AILang Standard Library

Common utility functions for ailang programs.
This module is automatically available to ailang programs.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

__all__ = [
    # String utilities
    "split", "join", "lower", "upper", "strip", "trim", "replace", "contains",
    "starts_with", "ends_with", "length",
    # List utilities
    "first", "last", "rest", "take", "drop", "slice", "reverse", "sort", "unique", "flatten",
    # Number utilities
    "add", "subtract", "multiply", "divide", "floor", "ceil", "round_number",
    "min_value", "max_value", "sum_items", "average",
    # JSON utilities
    "parse_json", "to_json",
    # File utilities
    "read_file", "write_file", "append_file", "file_exists",
    # AI-specific utilities
    "format_prompt", "extract_json", "truncate_text", "count_tokens",
    # Dict utilities
    "get_value", "keys", "values", "items",
    # Type conversion
    "to_string", "to_int", "to_float", "to_bool",
    # Debug utilities
    "log", "debug", "error",
    # Context management
    "Context", "create_context", "add_to_context", "get_context_history",
    # Memory management
    "Memory", "create_memory", "add_to_memory", "search_memory",
    # Tool execution
    "execute_tool", "format_tool_result",
    # Data structure utilities
    "make_list", "make_dict", "list_get", "list_append", "list_length",
    "dict_get", "dict_set", "dict_keys", "dict_values", "dict_items",
    # Vector/embedding
    "create_embedding", "cosine_similarity", "VectorStore", "create_vector_store",
    # RAG
    "RAGSystem", "create_rag_system",
    # Environment
    "get_env", "set_env", "has_env",
    # Schema
    "define_schema", "validate_schema", "format_schema_prompt",
    # Tool registry
    "ToolRegistry", "create_tool_registry", "register_tool", "call_tool",
    "format_tools_for_ai",
    # Token stream
    "TokenStream", "create_token_stream", "stream_print", "stream_collect",
    # HTTP
    "http_get", "http_post", "http_put", "http_delete",
    # Date/Time
    "get_current_time", "get_current_timestamp", "format_timestamp",
    "parse_datetime", "sleep",
    # String formatting
    "format_string", "pad_left", "pad_right", "center_text", "truncate",
    # Data manipulation
    "map_list", "filter_list", "reduce_list", "find_item", "unique_list", "sort_list",
    # File system
    "list_files", "dir_exists", "create_directory", "delete_file", "get_file_size",
    "read_file_content", "write_file_content", "append_file_content",
    # Extended JSON
    "json_get_path", "json_set_path", "json_merge", "json_flatten",
    # Validation
    "validate_required", "validate_type", "validate_email", "validate_url",
    # Logger
    "Logger", "create_logger",
    # Module system
    "import_module", "import_from", "get_module_info",
    # Debugger
    "Debugger", "create_debugger", "breakpoint_if", "inspect_variable",
    # Testing
    "TestCase", "TestSuite", "create_test_case", "create_test_suite",
]

# String utilities

def split(text: str, separator: str = " ") -> List[str]:
    """Split a string into a list of substrings."""
    return text.split(separator)


def join(items: List[str], separator: str = " ") -> str:
    """Join a list of strings into a single string."""
    return separator.join(items)


def lower(text: str) -> str:
    """Convert string to lowercase."""
    return text.lower()


def upper(text: str) -> str:
    """Convert string to uppercase."""
    return text.upper()


def strip(text: str) -> str:
    """Remove leading and trailing whitespace."""
    return text.strip() if text else ""


def trim(text: str) -> str:
    """Remove leading and trailing whitespace. Alias for strip()."""
    return text.strip() if text else ""


def replace(text: str, old: str, new: str) -> str:
    """Replace occurrences of old with new in text."""
    if not text or not old:
        return text or ""
    return text.replace(old, new)


def contains(text: str, substring: str) -> bool:
    """Check if text contains substring."""
    if not text or not substring:
        return False
    return substring in text


def starts_with(text: str, prefix: str) -> bool:
    """Check if text starts with prefix."""
    if not text or not prefix:
        return False
    return text.startswith(prefix)


def ends_with(text: str, suffix: str) -> bool:
    """Check if text ends with suffix."""
    if not text or not suffix:
        return False
    return text.endswith(suffix)


def length(text: str) -> int:
    """Get the length of a string."""
    if text is None:
        return 0
    return len(text)


# List utilities

def first(items: List[Any]) -> Any:
    """Get the first item of a list."""
    return items[0] if items else None


def last(items: List[Any]) -> Any:
    """Get the last item of a list."""
    return items[-1] if items else None


def rest(items: List[Any]) -> List[Any]:
    """Get all items except the first."""
    return items[1:] if items else []


def take(items: List[Any], n: int) -> List[Any]:
    """Take the first n items from a list."""
    return items[:n]


def drop(items: List[Any], n: int) -> List[Any]:
    """Drop the first n items from a list."""
    return items[n:]


def slice(obj, start, end=None) -> Any:
    """Slice a list or string. AILang slice(obj, start, end) — NOT Python's built-in slice."""
    try:
        if end is None:
            return obj[int(start):]
        return obj[int(start):int(end)]
    except Exception:
        return obj


def reverse(items: List[Any]) -> List[Any]:
    """Reverse a list."""
    return list(reversed(items))


def sort(items: List[Any]) -> List[Any]:
    """Sort a list."""
    return sorted(items)


def unique(items: List[Any]) -> List[Any]:
    """Get unique items from a list."""
    return list(dict.fromkeys(items))


def flatten(items: List[List[Any]]) -> List[Any]:
    """Flatten a list of lists into a single list."""
    result = []
    for item in items:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


# Number utilities

def add(x: float, y: float) -> float:
    """Add two numbers."""
    return x + y


def subtract(x: float, y: float) -> float:
    """Subtract y from x."""
    return x - y


def multiply(x: float, y: float) -> float:
    """Multiply two numbers."""
    return x * y


def divide(x: float, y: float) -> float:
    """Divide x by y. Returns float('inf') for division by zero."""
    if y == 0:
        if x == 0:
            return float("nan")
        return float("inf") if x > 0 else float("-inf")
    return x / y


def floor(x: float) -> int:
    """Round down to the nearest integer."""
    return int(x)


def ceil(x: float) -> int:
    """Round up to the nearest integer."""
    import math
    return math.ceil(x)


def round_number(x: float, decimals: int = 0) -> float:
    """Round a number to specified decimal places."""
    return round(x, decimals)


def min_value(items: List[float]) -> float:
    """Get the minimum value from a list."""
    return min(items) if items else 0


def max_value(items: List[float]) -> float:
    """Get the maximum value from a list."""
    return max(items) if items else 0


def sum_items(items: List[float]) -> float:
    """Sum all items in a list."""
    return sum(items)


def average(items: List[float]) -> float:
    """Calculate the average of a list of numbers."""
    return sum(items) / len(items) if items else 0


# JSON utilities

def parse_json(text: str) -> Any:
    """Parse a JSON string into a Python object."""
    return json.loads(text)


def to_json(obj: Any) -> str:
    """Convert a Python object to a JSON string."""
    return json.dumps(obj)


# File utilities

def read_file(path: str) -> str:
    """Read the contents of a file. Returns empty string on error."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def write_file(path: str, content: str) -> None:
    """Write content to a file. Raises on error."""
    Path(path).write_text(content, encoding="utf-8")


def append_file(path: str, content: str) -> None:
    """Append content to a file. Raises on error."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)


def file_exists(path: str) -> bool:
    """Check if a file exists."""
    return Path(path).exists()


# AI-specific utilities

def format_prompt(template: str, variables: Dict[str, str]) -> str:
    """Format a prompt template with variables."""
    for key, value in variables.items():
        template = template.replace(f"{{{key}}}", value)
    return template


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from AI response text."""
    try:
        # Try to find JSON between curly braces
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        return None
    except json.JSONDecodeError:
        return None


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def count_tokens(text: str) -> int:
    """Estimate token count (rough approximation: ~4 chars per token)."""
    return len(text) // 4


# Dict utilities

def get_value(d: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a value from a dictionary with a default."""
    return d.get(key, default)


def keys(d: Dict[str, Any]) -> List[str]:
    """Get all keys from a dictionary."""
    return list(d.keys())


def values(d: Dict[str, Any]) -> List[Any]:
    """Get all values from a dictionary."""
    return list(d.values())


def items(d: Dict[str, Any]) -> List[tuple]:
    """Get all key-value pairs from a dictionary."""
    return list(d.items())


# Type conversion utilities

def to_string(value: Any) -> str:
    """Convert a value to a string."""
    return str(value)


def to_int(value: Any) -> int:
    """Convert a value to an integer."""
    return int(value)


def to_float(value: Any) -> float:
    """Convert a value to a float."""
    return float(value)


def to_bool(value: Any) -> bool:
    """Convert a value to a boolean."""
    return bool(value)


# Debug utilities

def log(message: str) -> None:
    """Print a log message."""
    print(f"[LOG] {message}")


def debug(message: str) -> None:
    """Print a debug message."""
    print(f"[DEBUG] {message}")


def error(message: str) -> None:
    """Print an error message."""
    print(f"[ERROR] {message}", file=__import__("sys").stderr)


# AI Context Management

class Context:
    """Manages conversation context for AI interactions."""

    def __init__(self, max_history: int = 10):
        self.history: List[Dict[str, str]] = []
        self.max_history = max_history
        self.metadata: Dict[str, Any] = {}

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def get_history(self) -> List[Dict[str, str]]:
        """Get the conversation history."""
        return self.history.copy()

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata for the context."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from the context."""
        return self.metadata.get(key, default)

    def clear(self) -> None:
        """Clear the conversation history."""
        self.history.clear()

    def to_prompt(self) -> str:
        """Convert history to a prompt string."""
        lines = []
        for msg in self.history:
            lines.append(f"{msg['role']}: {msg['content']}")
        return "\n".join(lines)


def create_context(max_history: int = 10) -> Context:
    """Create a new context for managing conversation history."""
    return Context(max_history)


def add_to_context(ctx: Context, role: str, content: str) -> None:
    """Add a message to the context."""
    ctx.add_message(role, content)


def get_context_history(ctx: Context) -> List[Dict[str, str]]:
    """Get the conversation history from context."""
    return ctx.get_history()


# AI Memory Management

class Memory:
    """Manages persistent memory for AI agents."""

    def __init__(self, max_items: int = 100):
        self.items: List[Dict[str, Any]] = []
        self.max_items = max_items
        self.tags: Dict[str, List[int]] = {}

    def add(self, content: str, tags: List[str] = None, metadata: Dict[str, Any] = None) -> int:
        """Add an item to memory. Returns the item index."""
        if tags is None:
            tags = []
        if metadata is None:
            metadata = {}

        item = {
            "content": content,
            "tags": tags,
            "metadata": metadata,
            "timestamp": __import__("time").time()
        }

        self.items.append(item)
        index = len(self.items) - 1

        # Index by tags
        for tag in tags:
            if tag not in self.tags:
                self.tags[tag] = []
            self.tags[tag].append(index)

        # Enforce max items
        if len(self.items) > self.max_items:
            self.items.pop(0)
            # Rebuild tag indices
            self._rebuild_tags()

        return index

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memory by content (simple keyword matching)."""
        results = []
        query_lower = query.lower()

        for item in self.items:
            if query_lower in item["content"].lower():
                results.append(item)
                if len(results) >= limit:
                    break

        return results

    def search_by_tag(self, tag: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memory by tag."""
        if tag not in self.tags:
            return []

        results = []
        for index in self.tags[tag]:
            if index < len(self.items):
                results.append(self.items[index])
                if len(results) >= limit:
                    break

        return results

    def get_recent(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get the most recent items from memory."""
        return self.items[-count:]

    def clear(self) -> None:
        """Clear all items from memory."""
        self.items.clear()
        self.tags.clear()

    def _rebuild_tags(self) -> None:
        """Rebuild tag indices."""
        self.tags.clear()
        for i, item in enumerate(self.items):
            for tag in item["tags"]:
                if tag not in self.tags:
                    self.tags[tag] = []
                self.tags[tag].append(i)


def create_memory(max_items: int = 100) -> Memory:
    """Create a new memory store."""
    return Memory(max_items)


def add_to_memory(mem: Memory, content: str, tags: List[str] = None, metadata: Dict[str, Any] = None) -> int:
    """Add an item to memory."""
    return mem.add(content, tags, metadata)


def search_memory(mem: Memory, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search memory by content."""
    return mem.search(query, limit)


# AI Tool Execution

def execute_tool(tool_name: str, params: Dict[str, Any]) -> Any:
    """Execute a tool with given parameters (placeholder for future implementation)."""
    # This would integrate with the agent tool registration system
    return f"Tool {tool_name} executed with params: {params}"


def format_tool_result(result: Any) -> str:
    """Format a tool result for inclusion in AI prompt."""
    return to_string(result)


# Data Structure Utilities (alternative to list/dict literals)

def make_list(*items: Any) -> List[Any]:
    """Create a list from arguments."""
    return list(items)


def make_dict(*key_value_pairs: Any) -> Dict[str, Any]:
    """Create a dictionary from alternating key-value pairs.

    Usage: make_dict("key1", value1, "key2", value2, ...)
    """
    result = {}
    if len(key_value_pairs) % 2 != 0:
        raise ValueError("make_dict requires an even number of arguments (key-value pairs)")
    for i in range(0, len(key_value_pairs), 2):
        key = key_value_pairs[i]
        value = key_value_pairs[i + 1]
        result[key] = value
    return result


def list_get(lst: List[Any], index: int, default: Any = None) -> Any:
    """Get an item from a list with optional default."""
    try:
        return lst[index]
    except IndexError:
        return default


def list_append(lst: List[Any], item: Any) -> List[Any]:
    """Append an item to a list and return the new list."""
    lst.append(item)
    return lst


def list_length(lst: List[Any]) -> int:
    """Get the length of a list."""
    return len(lst)


def dict_get(d: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a value from a dictionary with optional default."""
    return d.get(key, default)


def dict_set(d: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
    """Set a value in a dictionary and return the dictionary."""
    d[key] = value
    return d


def dict_keys(d: Dict[str, Any]) -> List[str]:
    """Get all keys from a dictionary."""
    return list(d.keys())


def dict_values(d: Dict[str, Any]) -> List[Any]:
    """Get all values from a dictionary."""
    return list(d.values())


def dict_items(d: Dict[str, Any]) -> List[tuple]:
    """Get all key-value pairs from a dictionary."""
    return list(d.items())


# Async/Concurrent Operations

async def async_ask(model, prompt: str, **kwargs: Any) -> str:
    """Async version of ask_model for concurrent AI operations.

    This is a placeholder that wraps the synchronous ask_model.
    In a full implementation, this would use async OpenAI/Anthropic clients.
    """
    from .runtime import ask_model
    return ask_model(model, prompt, **kwargs)


async def gather_tasks(*tasks) -> List[Any]:
    """Gather results from multiple async tasks.

    This is a simplified implementation. In a full async implementation,
    this would use asyncio.gather.
    """
    results = []
    for task in tasks:
        if hasattr(task, '__await__'):
            # It's a coroutine
            try:
                result = await task
            except:
                # Fallback for non-async environments
                result = task
        else:
            result = task
        results.append(result)
    return results


async def parallel_ask(model, prompts: List[str], **kwargs: Any) -> List[str]:
    """Make multiple AI calls in parallel.

    Args:
        model: The AI model to use
        prompts: List of prompts to process
        **kwargs: Additional arguments for ask_model

    Returns:
        List of responses in the same order as prompts
    """
    tasks = [async_ask(model, prompt, **kwargs) for prompt in prompts]
    return await gather_tasks(*tasks)


# Vector Embeddings and Semantic Search

def create_embedding(text: str, model: str = "mock") -> List[float]:
    """Create a vector embedding for text.

    This is a simplified mock implementation. In production, this would
    use OpenAI embeddings, sentence-transformers, or similar.

    Args:
        text: The text to embed
        model: The embedding model to use

    Returns:
        A vector representation of the text
    """
    # Simple hash-based embedding for demonstration
    # In production, use real embedding models
    import hashlib
    hash_obj = hashlib.sha256(text.encode())
    hash_hex = hash_obj.hexdigest()
    # Convert hex to float vector
    vector = []
    for i in range(0, len(hash_hex), 2):
        hex_pair = hash_hex[i:i+2]
        value = int(hex_pair, 16) / 255.0
        vector.append(value)
    return vector


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score between 0 and 1
    """
    if len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


class VectorStore:
    """Simple vector store for semantic search."""

    def __init__(self, embedding_model: str = "mock"):
        self.vectors: List[Dict[str, Any]] = []
        self.embedding_model = embedding_model

    def add(self, text: str, metadata: Dict[str, Any] = None) -> int:
        """Add a text to the vector store.

        Args:
            text: The text to add
            metadata: Optional metadata to store with the text

        Returns:
            Index of the added item
        """
        if metadata is None:
            metadata = {}

        embedding = create_embedding(text, self.embedding_model)
        item = {
            "text": text,
            "embedding": embedding,
            "metadata": metadata
        }
        self.vectors.append(item)
        return len(self.vectors) - 1

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar texts.

        Args:
            query: The search query
            top_k: Number of results to return

        Returns:
            List of similar texts with similarity scores
        """
        query_embedding = create_embedding(query, self.embedding_model)

        results = []
        for item in self.vectors:
            similarity = cosine_similarity(query_embedding, item["embedding"])
            results.append({
                "text": item["text"],
                "metadata": item["metadata"],
                "similarity": similarity
            })

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def clear(self) -> None:
        """Clear all vectors from the store."""
        self.vectors.clear()


def create_vector_store(embedding_model: str = "mock") -> VectorStore:
    """Create a new vector store.

    Args:
        embedding_model: The embedding model to use

    Returns:
        A new VectorStore instance
    """
    return VectorStore(embedding_model)


# RAG (Retrieval-Augmented Generation) Utilities

class RAGSystem:
    """Retrieval-Augmented Generation system."""

    def __init__(self, model, vector_store: VectorStore):
        self.model = model
        self.vector_store = vector_store

    def add_document(self, text: str, metadata: Dict[str, Any] = None) -> None:
        """Add a document to the RAG system."""
        self.vector_store.add(text, metadata)

    def query(self, question: str, top_k: int = 3) -> str:
        """Query the RAG system.

        Args:
            question: The question to answer
            top_k: Number of relevant documents to retrieve

        Returns:
            The AI-generated answer based on retrieved context
        """
        # Retrieve relevant documents
        results = self.vector_store.search(question, top_k)

        # Build context from retrieved documents
        context_parts = []
        for result in results:
            context_parts.append(f"Document: {result['text']}")
        context = "\n\n".join(context_parts)

        # Generate answer with context
        prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer the question based on the context above."

        from .runtime import ask_model
        return ask_model(self.model, prompt)


def create_rag_system(model, embedding_model: str = "mock") -> RAGSystem:
    """Create a new RAG system.

    Args:
        model: The AI model to use for answering
        embedding_model: The embedding model for semantic search

    Returns:
        A new RAGSystem instance
    """
    vector_store = create_vector_store(embedding_model)
    return RAGSystem(model, vector_store)


# Environment Variables

def get_env(key: str, default: str = "") -> str:
    """Get an environment variable.

    Args:
        key: The environment variable name
        default: Default value if not found

    Returns:
        The environment variable value or default
    """
    import os
    return os.getenv(key, default)


def set_env(key: str, value: str) -> None:
    """Set an environment variable.

    Args:
        key: The environment variable name
        value: The value to set
    """
    import os
    os.environ[key] = value


def has_env(key: str) -> bool:
    """Check if an environment variable exists.

    Args:
        key: The environment variable name

    Returns:
        True if the variable exists, False otherwise
    """
    import os
    return key in os.environ


# Structured Output Schema Support

def define_schema(type_name: str, properties: Dict[str, str], required: List[str] = None) -> Dict[str, Any]:
    """Define a JSON schema for structured output.

    Args:
        type_name: The type name (e.g., "object", "string", "number")
        properties: Dictionary mapping property names to their types
        required: List of required property names

    Returns:
        A schema dictionary
    """
    if required is None:
        required = []

    return {
        "type": type_name,
        "properties": properties,
        "required": required
    }


def validate_schema(data: Any, schema: Dict[str, Any]) -> bool:
    """Validate data against a schema.

    Args:
        data: The data to validate
        schema: The schema to validate against

    Returns:
        True if valid, False otherwise
    """
    # Simple validation for common cases
    if schema.get("type") == "object":
        if not isinstance(data, dict):
            return False
        for prop in schema.get("required", []):
            if prop not in data:
                return False
    elif schema.get("type") == "string":
        if not isinstance(data, str):
            return False
    elif schema.get("type") == "number":
        if not isinstance(data, (int, float)):
            return False

    return True


def format_schema_prompt(prompt: str, schema: Dict[str, Any]) -> str:
    """Format a prompt with schema instructions.

    Args:
        prompt: The original prompt
        schema: The schema for structured output

    Returns:
        A formatted prompt with schema instructions
    """
    schema_desc = f"Output must match this JSON schema: {schema}"
    return f"{prompt}\n\n{schema_desc}"


# Tool Execution with Automatic Function Calling

class ToolRegistry:
    """Registry for tools that can be called by AI agents."""

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, func: Callable, schema: Dict[str, Any] = None) -> None:
        """Register a tool.

        Args:
            name: Tool name
            func: Tool function
            schema: Optional schema for tool parameters
        """
        self.tools[name] = func
        if schema:
            self.schemas[name] = schema

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a registered tool.

        Args:
            name: Tool name
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Tool execution result
        """
        if name not in self.tools:
            raise RuntimeError(f"Tool '{name}' not registered")
        return self.tools[name](*args, **kwargs)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self.tools.keys())

    def get_schema(self, name: str) -> Dict[str, Any]:
        """Get the schema for a tool.

        Args:
            name: Tool name

        Returns:
            Tool schema or empty dict if not found
        """
        return self.schemas.get(name, {})


def create_tool_registry() -> ToolRegistry:
    """Create a new tool registry.

    Returns:
        A new ToolRegistry instance
    """
    return ToolRegistry()


def register_tool(registry: ToolRegistry, name: str, func: Callable, schema: Dict[str, Any] = None) -> None:
    """Register a tool in the registry.

    Args:
        registry: The tool registry
        name: Tool name
        func: Tool function
        schema: Optional schema for tool parameters
    """
    registry.register(name, func, schema)


def call_tool(registry: ToolRegistry, name: str, *args: Any, **kwargs: Any) -> Any:
    """Call a tool from the registry.

    Args:
        registry: The tool registry
        name: Tool name
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Tool execution result
    """
    return registry.call(name, *args, **kwargs)


def format_tools_for_ai(registry: ToolRegistry) -> str:
    """Format tool descriptions for AI prompt.

    Args:
        registry: The tool registry

    Returns:
        Formatted string describing available tools
    """
    lines = ["Available tools:"]
    for tool_name in registry.list_tools():
        schema = registry.get_schema(tool_name)
        if schema:
            lines.append(f"- {tool_name}: {schema}")
        else:
            lines.append(f"- {tool_name}")
    return "\n".join(lines)


# Streaming Token-by-Token Output

class TokenStream:
    """Stream for processing AI responses token by token."""

    def __init__(self, text: str = ""):
        self.text = text
        self.position = 0
        self.tokens: List[str] = []
        self._tokenize()

    def _tokenize(self) -> None:
        """Simple tokenization by splitting on spaces and punctuation."""
        import re
        # Split on whitespace and keep punctuation
        self.tokens = re.findall(r'\w+|[^\w\s]', self.text)

    def next_token(self) -> str:
        """Get the next token.

        Returns:
            The next token or empty string if at end
        """
        if self.position >= len(self.tokens):
            return ""
        token = self.tokens[self.position]
        self.position += 1
        return token

    def has_more(self) -> bool:
        """Check if there are more tokens.

        Returns:
            True if more tokens available
        """
        return self.position < len(self.tokens)

    def reset(self) -> None:
        """Reset the stream to the beginning."""
        self.position = 0

    def get_remaining(self) -> str:
        """Get the remaining text from current position.

        Returns:
            Remaining text
        """
        return " ".join(self.tokens[self.position:])


def create_token_stream(text: str) -> TokenStream:
    """Create a token stream from text.

    Args:
        text: The text to tokenize

    Returns:
        A new TokenStream instance
    """
    return TokenStream(text)


def stream_print(text: str, delay: float = 0.05) -> None:
    """Print text token by token with delay.

    Args:
        text: The text to stream
        delay: Delay between tokens in seconds
    """
    import time
    stream = create_token_stream(text)
    while stream.has_more():
        token = stream.next_token()
        print(token, end=" ", flush=True)
        time.sleep(delay)
    print()


def stream_collect(text: str, callback: Callable[[str], None]) -> None:
    """Stream text token by token with a callback.

    Args:
        text: The text to stream
        callback: Function to call for each token
    """
    stream = create_token_stream(text)
    while stream.has_more():
        token = stream.next_token()
        callback(token)


# HTTP Client Utilities

def http_get(url: str, headers: Dict[str, str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Make an HTTP GET request.

    Args:
        url: The URL to request
        headers: Optional HTTP headers
        timeout: Request timeout in seconds

    Returns:
        Dictionary with status, headers, and data
    """
    import urllib.error
    import urllib.request

    if headers is None:
        headers = {}

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            return {
                "status": response.status,
                "headers": dict(response.headers),
                "data": data
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers) if e.headers else {},
            "data": e.read().decode('utf-8') if e.readable() else "",
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": 0,
            "headers": {},
            "data": "",
            "error": str(e)
        }


def http_post(url: str, data: str = None, json_data: Any = None, headers: Dict[str, str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Make an HTTP POST request.

    Args:
        url: The URL to request
        data: Raw string data to send
        json_data: Data to send as JSON
        headers: Optional HTTP headers
        timeout: Request timeout in seconds

    Returns:
        Dictionary with status, headers, and data
    """
    import json as json_module
    import urllib.error
    import urllib.request

    if headers is None:
        headers = {}

    body = None
    if json_data is not None:
        body = json_module.dumps(json_data).encode('utf-8')
        headers["Content-Type"] = "application/json"
    elif data is not None:
        body = data.encode('utf-8')

    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response_data = response.read().decode('utf-8')
            return {
                "status": response.status,
                "headers": dict(response.headers),
                "data": response_data
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers) if e.headers else {},
            "data": e.read().decode('utf-8') if e.readable() else "",
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": 0,
            "headers": {},
            "data": "",
            "error": str(e)
        }


def http_put(url: str, data: str = None, json_data: Any = None, headers: Dict[str, str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Make an HTTP PUT request.

    Args:
        url: The URL to request
        data: Raw string data to send
        json_data: Data to send as JSON
        headers: Optional HTTP headers
        timeout: Request timeout in seconds

    Returns:
        Dictionary with status, headers, and data
    """
    import json as json_module
    import urllib.error
    import urllib.request

    if headers is None:
        headers = {}

    body = None
    if json_data is not None:
        body = json_module.dumps(json_data).encode('utf-8')
        headers["Content-Type"] = "application/json"
    elif data is not None:
        body = data.encode('utf-8')

    req = urllib.request.Request(url, data=body, headers=headers, method='PUT')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response_data = response.read().decode('utf-8')
            return {
                "status": response.status,
                "headers": dict(response.headers),
                "data": response_data
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers) if e.headers else {},
            "data": e.read().decode('utf-8') if e.readable() else "",
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": 0,
            "headers": {},
            "data": "",
            "error": str(e)
        }


def http_delete(url: str, headers: Dict[str, str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Make an HTTP DELETE request.

    Args:
        url: The URL to request
        headers: Optional HTTP headers
        timeout: Request timeout in seconds

    Returns:
        Dictionary with status, headers, and data
    """
    import urllib.error
    import urllib.request

    if headers is None:
        headers = {}

    req = urllib.request.Request(url, headers=headers, method='DELETE')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            return {
                "status": response.status,
                "headers": dict(response.headers),
                "data": data
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers) if e.headers else {},
            "data": e.read().decode('utf-8') if e.readable() else "",
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": 0,
            "headers": {},
            "data": "",
            "error": str(e)
        }


# Date/Time Utilities

def get_current_time() -> str:
    """Get the current time as an ISO format string.

    Returns:
        Current time in ISO format
    """
    import datetime
    return datetime.datetime.now().isoformat()


def get_current_timestamp() -> float:
    """Get the current Unix timestamp.

    Returns:
        Current Unix timestamp (seconds since epoch)
    """
    import time
    return time.time()


def format_timestamp(timestamp: float, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a timestamp as a string.

    Args:
        timestamp: Unix timestamp
        format_str: Format string (default: "%Y-%m-%d %H:%M:%S")

    Returns:
        Formatted date/time string
    """
    import datetime
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime(format_str)


def parse_datetime(date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> float:
    """Parse a date/time string to a timestamp.

    Args:
        date_str: Date/time string
        format_str: Format string (default: "%Y-%m-%d %H:%M:%S")

    Returns:
        Unix timestamp
    """
    import datetime
    dt = datetime.datetime.strptime(date_str, format_str)
    return dt.timestamp()


def sleep(seconds: float) -> None:
    """Sleep for a specified number of seconds.

    Args:
        seconds: Number of seconds to sleep
    """
    import time
    time.sleep(seconds)


# String Formatting Utilities

def format_string(template: str, **kwargs: Any) -> str:
    """Format a string with named placeholders.

    Args:
        template: String with {placeholder} syntax
        **kwargs: Values for placeholders

    Returns:
        Formatted string
    """
    return template.format(**kwargs)


def pad_left(text: str, length: int, char: str = " ") -> str:
    """Pad a string on the left.

    Args:
        text: The text to pad
        length: Target length
        char: Character to pad with

    Returns:
        Padded string
    """
    return text.rjust(length, char)


def pad_right(text: str, length: int, char: str = " ") -> str:
    """Pad a string on the right.

    Args:
        text: The text to pad
        length: Target length
        char: Character to pad with

    Returns:
        Padded string
    """
    return text.ljust(length, char)


def center_text(text: str, length: int, char: str = " ") -> str:
    """Center a string within a width.

    Args:
        text: The text to center
        length: Target length
        char: Character to pad with

    Returns:
        Centered string
    """
    return text.center(length, char)


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate a string to a maximum length.

    Args:
        text: The text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


# Data Manipulation Utilities

def map_list(items: List[Any], func: Callable[[Any], Any]) -> List[Any]:
    """Apply a function to each item in a list.

    Args:
        items: List of items
        func: Function to apply

    Returns:
        List of transformed items
    """
    return [func(item) for item in items]


def filter_list(items: List[Any], predicate: Callable[[Any], bool]) -> List[Any]:
    """Filter items based on a predicate.

    Args:
        items: List of items
        predicate: Function that returns True to keep item

    Returns:
        Filtered list
    """
    return [item for item in items if predicate(item)]


def reduce_list(items: List[Any], func: Callable[[Any, Any], Any], initial: Any = None) -> Any:
    """Reduce a list to a single value.

    Args:
        items: List of items
        func: Function that takes accumulator and item
        initial: Initial accumulator value

    Returns:
        Reduced value
    """
    if initial is not None:
        result = initial
        for item in items:
            result = func(result, item)
        return result
    else:
        result = items[0]
        for item in items[1:]:
            result = func(result, item)
        return result


def find_item(items: List[Any], predicate: Callable[[Any], bool]) -> Any:
    """Find the first item matching a predicate.

    Args:
        items: List of items
        predicate: Function that returns True for matching items

    Returns:
        First matching item or None
    """
    for item in items:
        if predicate(item):
            return item
    return None


def unique_list(items: List[Any]) -> List[Any]:
    """Get unique items from a list.

    Args:
        items: List of items

    Returns:
        List of unique items
    """
    seen = []
    result = []
    for item in items:
        if item not in seen:
            seen.append(item)
            result.append(item)
    return result


def sort_list(items: List[Any], key: Callable[[Any], Any] = None, reverse: bool = False) -> List[Any]:
    """Sort a list.

    Args:
        items: List of items
        key: Optional key function for sorting
        reverse: Sort in descending order

    Returns:
        Sorted list
    """
    if key:
        return sorted(items, key=key, reverse=reverse)
    return sorted(items, reverse=reverse)


# File System Utilities

def list_files(directory: str, pattern: str = "*") -> List[str]:
    """List files in a directory.

    Args:
        directory: Directory path
        pattern: File pattern (glob-style)

    Returns:
        List of file paths
    """
    import glob
    import os
    full_pattern = os.path.join(directory, pattern)
    return glob.glob(full_pattern)


def dir_exists(path: str) -> bool:
    """Check if a directory exists.

    Args:
        path: Directory path

    Returns:
        True if directory exists
    """
    import os
    return os.path.isdir(path)


def create_directory(path: str) -> None:
    """Create a directory.

    Args:
        path: Directory path
    """
    import os
    os.makedirs(path, exist_ok=True)


def delete_file(path: str) -> None:
    """Delete a file.

    Args:
        path: File path
    """
    import os
    os.remove(path)


def get_file_size(path: str) -> int:
    """Get file size in bytes.

    Args:
        path: File path

    Returns:
        File size in bytes
    """
    import os
    return os.path.getsize(path)


def read_file_content(path: str) -> str:
    """Read file content as string.

    Args:
        path: File path

    Returns:
        File content
    """
    with open(path, encoding='utf-8') as f:
        return f.read()


def write_file_content(path: str, content: str) -> None:
    """Write content to a file.

    Args:
        path: File path
        content: Content to write
    """
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def append_file_content(path: str, content: str) -> None:
    """Append content to a file.

    Args:
        path: File path
        content: Content to append
    """
    with open(path, 'a', encoding='utf-8') as f:
        f.write(content)


# Extended JSON Utilities

def json_get_path(data: Any, path: str, default: Any = None) -> Any:
    """Get a value from nested JSON using dot notation.

    Args:
        data: JSON data (dict or list)
        path: Dot-separated path (e.g., "user.address.city")
        default: Default value if path not found

    Returns:
        Value at path or default
    """
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            if key not in current:
                return default
            current = current[key]
        elif isinstance(current, list) and key.isdigit():
            index = int(key)
            if index >= len(current):
                return default
            current = current[index]
        else:
            return default
    return current


def json_set_path(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    """Set a value in nested JSON using dot notation.

    Args:
        data: JSON data (dict)
        path: Dot-separated path
        value: Value to set

    Returns:
        Modified data
    """
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    return data


def json_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two JSON objects.

    Args:
        base: Base object
        update: Object to merge into base

    Returns:
        Merged object
    """
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = json_merge(result[key], value)
        else:
            result[key] = value
    return result


def json_flatten(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
    """Flatten nested JSON object.

    Args:
        data: Nested JSON object
        separator: Separator for keys

    Returns:
        Flattened object
    """
    def _flatten(obj, parent_key=""):
        items = {}
        for key, value in obj.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            if isinstance(value, dict):
                items.update(_flatten(value, new_key))
            else:
                items[new_key] = value
        return items
    return _flatten(data)


# Validation Utilities

def validate_required(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """Validate that required fields are present.

    Args:
        data: Data to validate
        required_fields: List of required field names

    Returns:
        List of missing fields (empty if all present)
    """
    missing = []
    for field in required_fields:
        if field not in data:
            missing.append(field)
    return missing


def validate_type(data: Any, expected_type: str) -> bool:
    """Validate data type.

    Args:
        data: Data to validate
        expected_type: Expected type ("string", "number", "boolean", "object", "array")

    Returns:
        True if type matches
    """
    if expected_type == "string":
        return isinstance(data, str)
    elif expected_type == "number":
        return isinstance(data, (int, float))
    elif expected_type == "boolean":
        return isinstance(data, bool)
    elif expected_type == "object":
        return isinstance(data, dict)
    elif expected_type == "array":
        return isinstance(data, list)
    return False


def validate_email(email: str) -> bool:
    """Validate email format (simple check).

    Args:
        email: Email address

    Returns:
        True if appears valid
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """Validate URL format (simple check).

    Args:
        url: URL string

    Returns:
        True if appears valid
    """
    import re
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url))


# Logging Utilities

class Logger:
    """Simple logging utility."""

    def __init__(self, name: str = "ailang", level: str = "INFO"):
        self.name = name
        self.level = level
        self.levels = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}

    def _should_log(self, level: str) -> bool:
        """Check if message should be logged."""
        return self.levels.get(level, 1) >= self.levels.get(self.level, 1)

    def debug(self, message: str) -> None:
        """Log debug message."""
        if self._should_log("DEBUG"):
            print(f"[DEBUG] {self.name}: {message}")

    def info(self, message: str) -> None:
        """Log info message."""
        if self._should_log("INFO"):
            print(f"[INFO] {self.name}: {message}")

    def warn(self, message: str) -> None:
        """Log warning message."""
        if self._should_log("WARN"):
            print(f"[WARN] {self.name}: {message}")

    def error(self, message: str) -> None:
        """Log error message."""
        if self._should_log("ERROR"):
            print(f"[ERROR] {self.name}: {message}")


def create_logger(name: str = "ailang", level: str = "INFO") -> Logger:
    """Create a new logger.

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARN, ERROR)

    Returns:
        Logger instance
    """
    return Logger(name, level)


# Module System Utilities

def import_module(module_name: str) -> Any:
    """Import a Python module.

    Args:
        module_name: Name of the module to import

    Returns:
        The imported module
    """
    import importlib
    return importlib.import_module(module_name)


def import_from(module_name: str, name: str) -> Any:
    """Import a specific attribute from a module.

    Args:
        module_name: Name of the module
        name: Name of the attribute to import

    Returns:
        The imported attribute
    """
    from importlib import import_module
    module = import_module(module_name)
    return getattr(module, name)


def get_module_info(module: Any) -> Dict[str, Any]:
    """Get information about a module.

    Args:
        module: The module to inspect

    Returns:
        Dictionary with module information
    """
    import inspect
    return {
        "name": getattr(module, "__name__", "unknown"),
        "file": getattr(module, "__file__", None),
        "doc": getattr(module, "__doc__", None),
        "functions": [name for name, obj in inspect.getmembers(module, inspect.isfunction)],
        "classes": [name for name, obj in inspect.getmembers(module, inspect.isclass)]
    }


# Debugging Tools

class Debugger:
    """Simple debugger for AILang programs."""

    def __init__(self):
        self.breakpoints: Dict[str, List[int]] = {}
        self.step_mode = False
        self.current_line = 0
        self.call_stack: List[Dict[str, Any]] = []

    def set_breakpoint(self, file: str, line: int) -> None:
        """Set a breakpoint at a specific line.

        Args:
            file: File path
            line: Line number
        """
        if file not in self.breakpoints:
            self.breakpoints[file] = []
        if line not in self.breakpoints[file]:
            self.breakpoints[file].append(line)

    def clear_breakpoint(self, file: str, line: int) -> None:
        """Clear a breakpoint.

        Args:
            file: File path
            line: Line number
        """
        if file in self.breakpoints and line in self.breakpoints[file]:
            self.breakpoints[file].remove(line)
            if not self.breakpoints[file]:
                del self.breakpoints[file]

    def has_breakpoint(self, file: str, line: int) -> bool:
        """Check if there's a breakpoint at a location.

        Args:
            file: File path
            line: Line number

        Returns:
            True if breakpoint exists
        """
        return file in self.breakpoints and line in self.breakpoints[file]

    def toggle_step(self) -> bool:
        """Toggle step mode.

        Returns:
            New step mode state
        """
        self.step_mode = not self.step_mode
        return self.step_mode

    def enter_function(self, name: str, args: Dict[str, Any] = None) -> None:
        """Enter a function call.

        Args:
            name: Function name
            args: Function arguments
        """
        self.call_stack.append({
            "name": name,
            "args": args or {},
            "line": self.current_line
        })

    def exit_function(self) -> Optional[Dict[str, Any]]:
        """Exit current function.

        Returns:
            Function info or None if no function to exit
        """
        if self.call_stack:
            return self.call_stack.pop()
        return None

    def get_call_stack(self) -> List[Dict[str, Any]]:
        """Get current call stack.

        Returns:
            List of function call information
        """
        return self.call_stack.copy()

    def print_traceback(self) -> None:
        """Print current call stack."""
        print("Call Stack:")
        for i, frame in enumerate(reversed(self.call_stack)):
            args_str = ", ".join(f"{k}={v}" for k, v in frame["args"].items())
            print(f"  {i}: {frame['name']}({args_str}) at line {frame['line']}")


def create_debugger() -> Debugger:
    """Create a new debugger instance.

    Returns:
        Debugger instance
    """
    return Debugger()


def breakpoint_if(condition: bool, debugger: Debugger = None) -> None:
    """Break execution if condition is true.

    Args:
        condition: Condition to check
        debugger: Optional debugger instance
    """
    if condition:
        import sys
        print(f"Breakpoint hit at line {sys._getframe().f_back.f_lineno}")
        if debugger:
            debugger.print_traceback()
        import pdb
        pdb.set_trace()


def inspect_variable(var: Any, name: str = "variable") -> Dict[str, Any]:
    """Inspect a variable and return its properties.

    Args:
        var: Variable to inspect
        name: Variable name

    Returns:
        Dictionary with variable information
    """
    return {
        "name": name,
        "type": type(var).__name__,
        "value": str(var),
        "size": len(var) if hasattr(var, "__len__") else None,
        "attributes": [attr for attr in dir(var) if not attr.startswith("_")]
    }


# Unit Testing Framework

class TestCase:
    """Base class for test cases."""

    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.errors: List[str] = []

    def assert_equal(self, actual: Any, expected: Any, message: str = "") -> None:
        """Assert that two values are equal.

        Args:
            actual: Actual value
            expected: Expected value
            message: Optional message
        """
        if actual != expected:
            msg = message or f"Expected {expected!r}, got {actual!r}"
            self.failed += 1
            self.errors.append(f"assert_equal failed: {msg}")
        else:
            self.passed += 1

    def assert_not_equal(self, actual: Any, expected: Any, message: str = "") -> None:
        """Assert that two values are not equal.

        Args:
            actual: Actual value
            expected: Expected value
            message: Optional message
        """
        if actual == expected:
            msg = message or f"Expected {expected!r} to not equal {actual!r}"
            self.failed += 1
            self.errors.append(f"assert_not_equal failed: {msg}")
        else:
            self.passed += 1

    def assert_true(self, condition: bool, message: str = "") -> None:
        """Assert that a condition is true.

        Args:
            condition: Condition to check
            message: Optional message
        """
        if not condition:
            msg = message or "Expected condition to be True"
            self.failed += 1
            self.errors.append(f"assert_true failed: {msg}")
        else:
            self.passed += 1

    def assert_false(self, condition: bool, message: str = "") -> None:
        """Assert that a condition is false.

        Args:
            condition: Condition to check
            message: Optional message
        """
        if condition:
            msg = message or "Expected condition to be False"
            self.failed += 1
            self.errors.append(f"assert_false failed: {msg}")
        else:
            self.passed += 1

    def assert_raises(self, func: Callable, exception_type: type, message: str = "") -> None:
        """Assert that a function raises an exception.

        Args:
            func: Function to call
            exception_type: Expected exception type
            message: Optional message
        """
        try:
            func()
            msg = message or f"Expected {exception_type.__name__} to be raised"
            self.failed += 1
            self.errors.append(f"assert_raises failed: {msg}")
        except exception_type:
            self.passed += 1
        except Exception as e:
            msg = message or f"Expected {exception_type.__name__}, got {type(e).__name__}"
            self.failed += 1
            self.errors.append(f"assert_raises failed: {msg}")

    def report(self) -> None:
        """Print test results."""
        total = self.passed + self.failed
        print(f"\nTest Case: {self.name}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total: {total}")
        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  - {error}")


class TestSuite:
    """Test suite for organizing multiple test cases."""

    def __init__(self, name: str = "Test Suite"):
        self.name = name
        self.test_cases: List[TestCase] = []

    def add_test(self, test_case: TestCase) -> None:
        """Add a test case to the suite.

        Args:
            test_case: Test case to add
        """
        self.test_cases.append(test_case)

    def run(self) -> None:
        """Run all test cases in the suite."""
        print(f"\nRunning {self.name}")
        print("=" * 50)

        total_passed = 0
        total_failed = 0

        for test_case in self.test_cases:
            test_case.report()
            total_passed += test_case.passed
            total_failed += test_case.failed

        print("\nSuite Results:")
        print(f"Total Passed: {total_passed}")
        print(f"Total Failed: {total_failed}")
        print(f"Success Rate: {(total_passed / (total_passed + total_failed) * 100) if (total_passed + total_failed) > 0 else 0:.1f}%")


def create_test_case(name: str) -> TestCase:
    """Create a new test case.

    Args:
        name: Test case name

    Returns:
        TestCase instance
    """
    return TestCase(name)


def create_test_suite(name: str = "Test Suite") -> TestSuite:
    """Create a new test suite.

    Args:
        name: Test suite name

    Returns:
        TestSuite instance
    """
    return TestSuite(name)
