"""AILang Bridge — Connects AILang transpiled code to the translator backend."""
from __future__ import annotations
import logging
import os
import sys
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)
_bridge_instance: Optional["AILangBridge"] = None
_bridge_lock = RLock()

def get_bridge() -> "AILangBridge":
    global _bridge_instance
    if _bridge_instance is None:
        with _bridge_lock:
            if _bridge_instance is None:
                _bridge_instance = AILangBridge()
    return _bridge_instance

class AILangBridge:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.agents_dir = self.base_dir / "agents"
        self.pipelines_dir = self.base_dir / "pipelines"
        self.plugins_dir = self.base_dir / "plugins"
        self._loaded_modules: Dict[str, Any] = {}
        self._agent_registry: Dict[str, "AgentProxy"] = {}
        self._function_registry: Dict[str, Callable] = {}
        self._lock = RLock()
        self._ai_providers: Dict[str, Callable] = {}
        self._ailang_available = self._check_ailang()
        if self._ailang_available:
            self._discover_and_load()

    def _check_ailang(self) -> bool:
        try:
            import ailang
            return True
        except ImportError:
            logger.warning("ailang package not found — agents will run in stub mode.")
            return False

    def _discover_and_load(self) -> None:
        # Patch ailang.runtime.ask_model to route through our bridge
        try:
            import ailang.runtime as _rt
            _rt.ask_model = self._route_ai_call
        except Exception:
            pass
        for directory in [self.agents_dir, self.pipelines_dir]:
            if not directory.exists():
                continue
            for ai_file in sorted(directory.glob("*.ai")):
                try:
                    self._load_ai_file(ai_file)
                    logger.info(f"Loaded AILang module: {ai_file.stem}")
                except Exception as e:
                    logger.error(f"Failed to load {ai_file}: {e}")

    def _load_ai_file(self, path: Path) -> None:
        from ailang.parser import parse_source
        from ailang.transpiler import Transpiler
        raw = path.read_bytes()
        source = raw.replace(b"\x00", b"").decode("utf-8-sig").rstrip() + "\n"
        program = parse_source(source)
        transpiler = Transpiler()
        python_code = transpiler.transpile(program)
        namespace = self._build_namespace(path)
        exec(python_code, namespace)
        module_name = path.stem
        self._loaded_modules[module_name] = namespace
        for key, value in namespace.items():
            if hasattr(value, "tool_registry") and hasattr(value, "instructions"):
                self._agent_registry[key] = AgentProxy(key, value, self)
            elif callable(value) and not key.startswith("_"):
                self._function_registry[f"{module_name}.{key}"] = value

    def _build_namespace(self, source_path: Path) -> Dict[str, Any]:
        from ailang.runtime import Model, Agent, define_model, define_agent, register_tool
        import ailang.stdlib as _stdlib
        stdlib_funcs = {}
        for name in getattr(_stdlib, "__all__", []):
            obj = getattr(_stdlib, name, None)
            if obj is not None:
                stdlib_funcs[name] = obj
        namespace = {
            "__builtins__": __builtins__,
            "__file__": str(source_path),
            "Model": Model, "Agent": Agent,
            "define_model": define_model, "define_agent": define_agent,
            "register_tool": register_tool,
            "ask_model": self._route_ai_call,
            **stdlib_funcs,
        }
        return namespace

    def _route_ai_call(self, model_alias, prompt: str, **kwargs) -> str:
        # model_alias may be a Model object or a string
        if hasattr(model_alias, 'model_name'):
            alias_str = model_alias.alias or model_alias.model_name
        else:
            alias_str = str(model_alias)
        if alias_str in self._ai_providers:
            return self._ai_providers[alias_str](prompt, **kwargs)
        try:
            from backend.cip_client import call_llm
            return call_llm(prompt, model=model_alias)
        except (ImportError, Exception) as e:
            logger.warning(f"AI call failed for model '{alias_str}': {e}")
            # Return a structured stub for analysis functions
            if "analyze" in prompt.lower() or "detect" in prompt.lower():
                return '{"domain": "general", "formality": "neutral", "model": "fast", "instructions": [], "require_confirmation": false}'
            return f"[AI:{alias_str}] {prompt[:100]}..."

    def register_ai_provider(self, model_alias: str, provider_fn: Callable) -> None:
        with self._lock:
            self._ai_providers[model_alias] = provider_fn

    def get_agent(self, name: str) -> Optional["AgentProxy"]:
        return self._agent_registry.get(name)

    def call_agent_function(self, agent_name: str, function_name: str, *args, **kwargs) -> Any:
        agent = self._agent_registry.get(agent_name)
        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found. Available: {list(self._agent_registry.keys())}")
        return agent.call(function_name, *args, **kwargs)

    def call_function(self, qualified_name: str, *args, **kwargs) -> Any:
        fn = self._function_registry.get(qualified_name)
        if fn is None:
            raise ValueError(f"Function '{qualified_name}' not found.")
        return fn(*args, **kwargs)

    def list_agents(self) -> List[str]:
        return list(self._agent_registry.keys())

    def list_functions(self) -> List[str]:
        return list(self._function_registry.keys())

    def reload(self) -> None:
        with self._lock:
            self._loaded_modules.clear()
            self._agent_registry.clear()
            self._function_registry.clear()
            if self._ailang_available:
                self._discover_and_load()

class AgentProxy:
    def __init__(self, name: str, agent_obj: Any, bridge: AILangBridge):
        self.name = name
        self._agent = agent_obj
        self._bridge = bridge

    def call(self, function_name: str, *args, **kwargs) -> Any:
        if hasattr(self._agent, "tool_registry") and function_name in self._agent.tool_registry:
            return self._agent.tool_registry[function_name](*args, **kwargs)
        raise AttributeError(f"Agent '{self.name}' has no function '{function_name}'")

    @property
    def instructions(self) -> str:
        return getattr(self._agent, "instructions", "")

    @property
    def tools(self) -> List[str]:
        return list(getattr(self._agent, "tool_registry", {}).keys())

    def __repr__(self) -> str:
        return f"AgentProxy('{self.name}', tools={self.tools})"
