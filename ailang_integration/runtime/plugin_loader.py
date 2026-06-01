"""Plugin Loader — Discovers and manages AILang plugins."""
from __future__ import annotations
import logging
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

class PluginInfo:
    def __init__(self, name: str, version: str, path: Path, hooks: List[str]):
        self.name = name
        self.version = version
        self.path = path
        self.hooks = hooks
        self.enabled = True
        self.load_errors: List[str] = []
    def __repr__(self) -> str:
        return f"Plugin('{self.name}' v{self.version}, hooks={self.hooks})"

class PluginLoader:
    def __init__(self, plugins_dir: Optional[Path] = None):
        self.plugins_dir = plugins_dir or Path(__file__).parent.parent / "plugins"
        self._plugins: Dict[str, PluginInfo] = {}
        self._hooks: Dict[str, List[Dict[str, Any]]] = {hook: [] for hook in HOOK_POINTS}
        self._namespaces: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
        self._discover_plugins()

    def _discover_plugins(self) -> None:
        if not self.plugins_dir.exists():
            return
        for ai_file in sorted(self.plugins_dir.glob("*.ai")):
            if ai_file.stem.startswith("_"):
                continue
            try:
                self._load_plugin(ai_file)
            except Exception as e:
                logger.error(f"Failed to load plugin {ai_file.stem}: {e}")

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
        except Exception:
            return f"[plugin-ai:{model_alias}] {prompt[:80]}..."

    def execute_hook(self, hook_name: str, *args, **kwargs) -> Any:
        if hook_name not in self._hooks:
            raise ValueError(f"Unknown hook: {hook_name}")
        handlers = self._hooks[hook_name]
        if not handlers:
            return args[0] if args else None
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
            except Exception as e:
                logger.error(f"Plugin '{handler['plugin']}' hook '{hook_name}' failed: {e}")
        return result

    def has_hooks(self, hook_name: str) -> bool:
        return bool(self._hooks.get(hook_name))

    def list_plugins(self) -> List[PluginInfo]:
        return list(self._plugins.values())

    def enable_plugin(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = True
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = False
            return True
        return False

    def reload_all(self) -> None:
        with self._lock:
            self._plugins.clear()
            self._namespaces.clear()
            self._hooks = {hook: [] for hook in HOOK_POINTS}
            self._discover_plugins()
