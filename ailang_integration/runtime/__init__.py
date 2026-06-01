"""AILang Integration Runtime for Universal Translator.

This module bridges AILang agents/pipelines with the existing Python backend.
It loads .ai files, transpiles them, and exposes their functionality as
callable Python objects that the streaming/pipeline code can invoke.
"""

from .bridge import AILangBridge, get_bridge
from .plugin_loader import PluginLoader, get_plugin_loader
from .pipeline_runner import PipelineRunner, get_pipeline_runner

__all__ = [
    "AILangBridge",
    "get_bridge",
    "PluginLoader",
    "get_plugin_loader",
    "PipelineRunner",
    "get_pipeline_runner",
]
