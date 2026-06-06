"""Plugin Loader — Discovers and manages AILang plugins."""
from __future__ import annotations
import logging
import re
import time
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)
_loader_instance: Optional["PluginLoader"] = None
_loader_lock = RLock()

def get_plugin_loader() -> "PluginLoader":
    global _loader_instance
    if _loader_instance is None:
        with _loader_lock:
            if _loader_instance is None:
                _loader_instance = PluginLoader()
    return _loader_instance

HOOK_POINTS = ["pre_translate", "post_translate", "on_speaker_change", "on_domain_detected", "on_error", "custom_step"]


def _looks_like_ai_artifact(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if re.match(r"^\[(?:AI|AI_ERROR|plugin-ai):", text, re.IGNORECASE):
        return True
    lowered = text.lower()
    if "ensure this " in lowered and "keep meaning:" in lowered:
        return True
    if re.search(r"\[[a-z]{2,}(?:-[a-z0-9]+)?->none\]", text, re.IGNORECASE):
        return True
    return False

class PluginInfo:
    def __init__(self, name: str, version: str, path: Path, hooks: List[str]):
        self.name = name
        self.version = version
        self.path = path
        self.hooks = hooks
        self.enabled = True
        self.load_errors: List[str] = []
        self.hook_execution_count: Dict[str, int] = {hook: 0 for hook in HOOK_POINTS}
        self.hook_errors: Dict[str, int] = {hook: 0 for hook in HOOK_POINTS}
        self.total_executions = 0
        self.total_errors = 0

    def record_hook_execution(self, hook_name: str, success: bool = True) -> None:
        if hook_name in self.hook_execution_count:
            self.hook_execution_count[hook_name] += 1
        self.total_executions += 1
        if not success:
            if hook_name in self.hook_errors:
                self.hook_errors[hook_name] += 1
            self.total_errors += 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "hooks": self.hooks,
            "load_errors": self.load_errors,
            "total_executions": self.total_executions,
            "total_errors": self.total_errors,
            "hook_execution_count": self.hook_execution_count,
            "hook_errors": self.hook_errors,
            "error_rate": self.total_errors / self.total_executions if self.total_executions > 0 else 0,
        }

    def __repr__(self) -> str:
        return f"Plugin('{self.name}' v{self.version}, hooks={self.hooks}, enabled={self.enabled})"

class PluginLoader:
    def __init__(self, plugins_dir: Optional[Path] = None):
        self.plugins_dir = plugins_dir or Path(__file__).parent.parent / "plugins"
        self._plugins: Dict[str, PluginInfo] = {}
        self._hooks: Dict[str, List[Dict[str, Any]]] = {hook: [] for hook in HOOK_POINTS}
        self._namespaces: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
        self._load_time = 0.0
        self._discover_plugins()

    def _discover_plugins(self) -> None:
        start_time = time.time()
        if not self.plugins_dir.exists():
            logger.debug(f"Plugins directory does not exist: {self.plugins_dir}")
            self._load_time = (time.time() - start_time) * 1000
            return
        
        discovered_count = 0
        for ai_file in sorted(self.plugins_dir.glob("*.ai")):
            if ai_file.stem.startswith("_"):
                logger.debug(f"Skipping private plugin: {ai_file.stem}")
                continue
            try:
                self._load_plugin(ai_file)
                discovered_count += 1
            except Exception as e:
                logger.error(f"Failed to load plugin {ai_file.stem}: {e}", exc_info=True)
        
        self._load_time = (time.time() - start_time) * 1000
        logger.info(f"Plugin discovery complete: {discovered_count} plugins loaded in {self._load_time:.2f}ms")

    def _load_plugin(self, path: Path) -> None:
        try:
            from ailang.parser import parse_source
            from ailang.transpiler import Transpiler
            import ailang.stdlib as _stdlib
        except ImportError:
            logger.warning(f"AILang not available, stubbing plugin: {path.stem}")
            info = PluginInfo(name=path.stem, version="0.0.0", path=path, hooks=[])
            info.load_errors.append("ailang package not installed")
            self._plugins[path.stem] = info
            return

        stdlib_funcs = {name: getattr(_stdlib, name) for name in getattr(_stdlib, "__all__", []) if hasattr(_stdlib, name)}

        raw = path.read_bytes()
        source = raw.replace(b"\x00", b"").decode("utf-8-sig").rstrip() + "\n"
        program = parse_source(source)
        transpiler = Transpiler()
        python_code = transpiler.transpile(program)

        namespace: Dict[str, Any] = {
            "__builtins__": __builtins__,
            "__file__": str(path),
            "ask_model": self._plugin_ai_stub,
            **stdlib_funcs,
        }
        exec(python_code, namespace)

        plugin_name = namespace.get("PLUGIN_NAME", path.stem)
        plugin_version = namespace.get("PLUGIN_VERSION", "0.0.0")
        plugin_hooks = namespace.get("PLUGIN_HOOKS", [])

        valid_hooks = [h for h in plugin_hooks if h in HOOK_POINTS]
        info = PluginInfo(name=plugin_name, version=plugin_version, path=path, hooks=valid_hooks)
        self._plugins[plugin_name] = info
        self._namespaces[plugin_name] = namespace

        for hook_name in valid_hooks:
            hook_fn = namespace.get(hook_name)
            if hook_fn and callable(hook_fn):
                self._hooks[hook_name].append({"plugin": plugin_name, "function": hook_fn, "priority": 100})
                logger.info(f"Plugin '{plugin_name}' registered hook: {hook_name}")

    def _plugin_ai_stub(self, model_alias: str, prompt: str, **kwargs) -> str:
        try:
            from .bridge import get_bridge
            return get_bridge()._route_ai_call(model_alias, prompt, **kwargs)
        except Exception as e:
            logger.warning(f"Plugin AI call failed: {e}")
            return f"[plugin-ai:{model_alias}] {prompt[:80]}..."

    def execute_hook(self, hook_name: str, *args, **kwargs) -> Any:
        if hook_name not in self._hooks:
            raise ValueError(f"Unknown hook: {hook_name}")
        handlers = self._hooks[hook_name]
        if not handlers:
            return args[0] if args else None

        if hook_name == "post_translate" and len(args) >= 2:
            original = args[0]
            translated = args[1]
            result = translated
            tail_args = args[2:]
            for handler in handlers:
                plugin_info = self._plugins.get(handler["plugin"])
                if plugin_info and not plugin_info.enabled:
                    continue
                try:
                    fn = handler["function"]
                    candidate = fn(original, result, *tail_args, **kwargs)
                    if isinstance(candidate, str) and not _looks_like_ai_artifact(candidate):
                        result = candidate
                    elif isinstance(candidate, str):
                        logger.warning(
                            "Plugin '%s' hook '%s' returned an internal artifact; keeping previous translation",
                            handler["plugin"],
                            hook_name,
                        )
                    plugin_info.record_hook_execution(hook_name, success=True)
                except Exception as e:
                    logger.error(f"Plugin '{handler['plugin']}' hook '{hook_name}' failed: {e}", exc_info=True)
                    if plugin_info:
                        plugin_info.record_hook_execution(hook_name, success=False)
            return result

        result = args[0] if args else None
        for handler in handlers:
            plugin_info = self._plugins.get(handler["plugin"])
            if plugin_info and not plugin_info.enabled:
                continue
            try:
                fn = handler["function"]
                if hook_name in ("pre_translate", "post_translate"):
                    result = fn(result, *args[1:], **kwargs)
                else:
                    result = fn(*args, **kwargs)
                plugin_info.record_hook_execution(hook_name, success=True)
            except Exception as e:
                logger.error(f"Plugin '{handler['plugin']}' hook '{hook_name}' failed: {e}", exc_info=True)
                if plugin_info:
                    plugin_info.record_hook_execution(hook_name, success=False)
        return result

    def has_hooks(self, hook_name: str) -> bool:
        return bool(self._hooks.get(hook_name))

    def list_plugins(self) -> List[PluginInfo]:
        return list(self._plugins.values())

    def enable_plugin(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = True
            logger.info(f"Plugin '{name}' enabled")
            return True
        logger.warning(f"Plugin '{name}' not found")
        return False

    def disable_plugin(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = False
            logger.info(f"Plugin '{name}' disabled")
            return True
        logger.warning(f"Plugin '{name}' not found")
        return False

    def reload_all(self) -> None:
        with self._lock:
            self._plugins.clear()
            self._namespaces.clear()
            self._hooks = {hook: [] for hook in HOOK_POINTS}
            self._discover_plugins()
            logger.info("All plugins reloaded")

    def get_stats(self) -> Dict[str, Any]:
        """Get plugin loader statistics."""
        total_executions = sum(p.total_executions for p in self._plugins.values())
        total_errors = sum(p.total_errors for p in self._plugins.values())
        return {
            "plugins_dir": str(self.plugins_dir),
            "total_plugins": len(self._plugins),
            "enabled_plugins": sum(1 for p in self._plugins.values() if p.enabled),
            "disabled_plugins": sum(1 for p in self._plugins.values() if not p.enabled),
            "total_hooks_registered": sum(len(hooks) for hooks in self._hooks.values()),
            "load_time_ms": self._load_time,
            "total_executions": total_executions,
            "total_errors": total_errors,
            "error_rate": total_errors / total_executions if total_executions > 0 else 0,
            "plugins": [p.get_stats() for p in self._plugins.values()],
        }
