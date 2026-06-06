"""AILang Bridge — Connects AILang transpiled code to the translator backend."""
from __future__ import annotations
import logging
import os
import sys
import time
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


def reset_bridge() -> None:
    """Reset the singleton bridge instance (for testing)."""
    global _bridge_instance
    with _bridge_lock:
        _bridge_instance = None

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
        self._call_count = 0
        self._call_errors = 0
        self._call_latency_ms = []
        self._max_latency_samples = 100
        if self._ailang_available:
            self._discover_and_load()

    def _check_ailang(self) -> bool:
        try:
            import ailang
            logger.info("AILang package found and available")
            return True
        except ImportError:
            logger.warning("ailang package not found — agents will run in stub mode.")
            return False

    def _discover_and_load(self) -> None:
        # Patch ailang.runtime.ask_model to route through our bridge
        try:
            import ailang.runtime as _rt
            _rt.ask_model = self._route_ai_call
            logger.debug("Patched ailang.runtime.ask_model")
        except Exception as e:
            logger.warning(f"Failed to patch ailang.runtime: {e}")
        
        # Patch runtime_helpers.ask_model in ALL locations where it might be imported from.
        # Transpiled code does 'from ailang.runtime_helpers import ask_model', which can
        # resolve to either the vendored inner package or the integration package.
        for _helper_module in [
            "ailang_integration.runtime.ailang_pkg.runtime_helpers",
            "ailang.ailang.runtime_helpers",
            "ailang.runtime_helpers",
        ]:
            try:
                import importlib
                _rh = importlib.import_module(_helper_module)
                _rh.ask_model = self._route_ai_call
                logger.debug(f"Patched {_helper_module}.ask_model")
            except Exception as e:
                logger.debug(f"Could not patch {_helper_module}: {e}")
        
        loaded_count = 0
        for directory in [self.agents_dir, self.pipelines_dir]:
            if not directory.exists():
                logger.debug(f"Directory does not exist: {directory}")
                continue
            for ai_file in sorted(directory.glob("*.ai")):
                try:
                    self._load_ai_file(ai_file)
                    loaded_count += 1
                    logger.info(f"Loaded AILang module: {ai_file.stem}")
                except Exception as e:
                    logger.error(f"Failed to load {ai_file}: {e}", exc_info=True)
        
        logger.info(f"AILang discovery complete: {loaded_count} modules loaded")

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
            "null": None,  # AILang null keyword maps to Python None
            "trim": str.strip,  # AILang trim maps to Python str.strip
            **stdlib_funcs,
        }
        return namespace

    def _route_ai_call(self, model_alias, prompt: str, **kwargs) -> str:
        start_time = time.time()
        self._call_count += 1
        
        try:
            # model_alias may be a Model object or a string
            if hasattr(model_alias, 'model_name'):
                alias_str = model_alias.alias or model_alias.model_name
            else:
                alias_str = str(model_alias)
            
            if alias_str in self._ai_providers:
                result = self._ai_providers[alias_str](prompt, **kwargs)
                self._record_latency(start_time)
                return result
            
            # --- Ollama: local LLM, zero cost, no API key needed ---
            ollama_result = self._try_ollama(alias_str, prompt, **kwargs)
            if ollama_result is not None:
                self._record_latency(start_time)
                return ollama_result
            
            # --- OpenAI: cloud LLM, requires OPENAI_API_KEY ---
            openai_result = self._try_openai(alias_str, prompt, **kwargs)
            if openai_result is not None:
                self._record_latency(start_time)
                return openai_result
            
            # --- CIP brain fallback ---
            cip_result = self._try_cip(alias_str, prompt, **kwargs)
            if cip_result is not None:
                self._record_latency(start_time)
                return cip_result
            
            # --- Structured stub fallback ---
            self._record_latency(start_time)
            return self._stub_response(alias_str, prompt)
            
        except Exception as e:
            self._call_errors += 1
            logger.error(f"Unexpected error in _route_ai_call: {e}", exc_info=True)
            return self._stub_response(alias_str, prompt, error=str(e))

    def _try_ollama(self, alias_str: str, prompt: str, **kwargs) -> Optional[str]:
        """Try Ollama local LLM. Returns response string or None."""
        ollama_enabled = os.environ.get("OLLAMA_ENABLED", "").lower() in ("true", "1", "yes")
        if not ollama_enabled:
            return None
        
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        ollama_model = os.environ.get("OLLAMA_MODEL", "mistral")
        ollama_timeout = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "30"))
        
        # Map AILang model aliases to Ollama model names
        model_mapping = {
            "claude": ollama_model,
            "fast": ollama_model,
            "gpt-4": ollama_model,
            "gpt-3.5": ollama_model,
        }
        target_model = model_mapping.get(alias_str, ollama_model)
        
        try:
            import json
            from urllib.request import Request, urlopen
            from urllib.error import URLError, HTTPError
            
            # Check availability first (cached check)
            try:
                req = Request(
                    f"{ollama_url}/api/tags",
                    headers={"User-Agent": "AnaiTranslator/1.0"},
                )
                with urlopen(req, timeout=2.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "") for m in data.get("models", [])]
                    model_base = target_model.split(":")[0]
                    if not any(model_base in m for m in models):
                        logger.debug(f"Ollama model '{target_model}' not found, skipping")
                        return None
            except (URLError, HTTPError, TimeoutError, OSError):
                logger.debug("Ollama service not reachable, skipping")
                return None
            
            # Build a focused prompt for the Ollama model
            system_prompt = (
                "You are a translation intelligence assistant. "
                "Respond with valid JSON only. No markdown, no explanation outside JSON."
            )
            
            payload = json.dumps({
                "model": target_model,
                "prompt": f"{system_prompt}\n\n{prompt}",
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 512},
            }).encode("utf-8")
            
            req = Request(
                f"{ollama_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "AnaiTranslator/1.0"},
                method="POST",
            )
            
            with urlopen(req, timeout=ollama_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            result = data.get("response", "").strip()
            if not result:
                logger.warning("Ollama returned empty response")
                return None
            
            # Clean up common LLM response artifacts
            for prefix in ("Translation:", "Translated:", "Here is the translation:",
                           "Response:", "Answer:", "Result:"):
                if result.lower().startswith(prefix.lower()):
                    result = result[len(prefix):].strip()
            
            logger.info("ollama_agent_call ok model=%s alias=%s", target_model, alias_str)
            return result
            
        except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError, KeyError) as exc:
            logger.debug(f"Ollama call failed: {exc}")
            return None

    def _try_openai(self, alias_str: str, prompt: str, **kwargs) -> Optional[str]:
        """Try OpenAI cloud LLM. Returns response string or None."""
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key or openai_key.startswith("your_api"):
            return None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            model_mapping = {
                "claude": "gpt-4o",
                "fast": "gpt-4o-mini",
                "gpt-4": "gpt-4o",
                "gpt-3.5": "gpt-4o-mini",
            }
            openai_model = model_mapping.get(alias_str, "gpt-4o-mini")
            response = client.chat.completions.create(
                model=openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )
            result = response.choices[0].message.content
            logger.info("openai_agent_call ok model=%s alias=%s", openai_model, alias_str)
            return result
        except ImportError:
            logger.debug("OpenAI package not available, skipping")
            return None
        except Exception as e:
            logger.warning(f"OpenAI call failed: {e}, skipping")
            return None

    def _try_cip(self, alias_str: str, prompt: str, **kwargs) -> Optional[str]:
        """Try CIP brain fallback. Returns response string or None."""
        try:
            from backend.cip_client import call_cip_brain
            result_dict = call_cip_brain(prompt, "en", session_id="ailang_bridge", fallback_translation="", context={"prompt": prompt})
            if result_dict and "translation" in result_dict and result_dict["translation"]:
                return result_dict["translation"]
        except (ImportError, Exception):
            pass
        return None

    def _stub_response(self, alias_str: str, prompt: str, error: str = "") -> str:
        """Return structured stub responses for common agent operations."""
        lowered = prompt.lower()
        if "analyze" in lowered or "detect" in lowered:
            return '{"domain": "general", "formality": "neutral", "model": "fast", "instructions": [], "require_confirmation": false}'
        elif "extract" in lowered or "entities" in lowered:
            return '{"people": [], "places": [], "objects": [], "pronoun_map": {"he": null, "she": null, "they": null, "it": null}}'
        elif "resolve" in lowered or "reference" in lowered:
            if not error:
                import re as _re
                _m = _re.search(r'(?:in|text)[:\s]+(.+?)(?:\.?\s*(?:Return|Reply|Answer|$))', prompt, _re.IGNORECASE)
                return _m.group(1).strip() if _m else ""
            return prompt
        elif "compare" in lowered or "similarity" in lowered:
            return '{"similarity_score": 0.8, "key_differences": [], "meaning_preserved": true, "critical_loss": false}'
        if error:
            return f"[AI_ERROR:{alias_str}] {error[:100]}"
        return f"[AI:{alias_str}] {prompt[:100]}..."

    def _record_latency(self, start_time: float) -> None:
        latency_ms = (time.time() - start_time) * 1000
        self._call_latency_ms.append(latency_ms)
        if len(self._call_latency_ms) > self._max_latency_samples:
            self._call_latency_ms = self._call_latency_ms[-self._max_latency_samples:]

    def register_ai_provider(self, model_alias: str, provider_fn: Callable) -> None:
        with self._lock:
            self._ai_providers[model_alias] = provider_fn
            logger.info(f"Registered AI provider for model: {model_alias}")

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
            logger.info("AILang bridge reloaded")

    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        avg_latency = sum(self._call_latency_ms) / len(self._call_latency_ms) if self._call_latency_ms else 0
    def get_stats(self):
        avg_latency = sum(self._call_latency_ms) / len(self._call_latency_ms) if self._call_latency_ms else 0
        return {
            "ailang_available": self._ailang_available,
            "agents_loaded": len(self._agent_registry),
            "functions_loaded": len(self._function_registry),
            "modules_loaded": len(self._loaded_modules),
            "ai_providers": list(self._ai_providers.keys()),
            "total_calls": self._call_count,
            "total_errors": self._call_errors,
            "error_rate": self._call_errors / self._call_count if self._call_count > 0 else 0,
            "avg_latency_ms": avg_latency,
            "base_dir": str(self.base_dir),
        }


class AgentProxy:
    def __init__(self, name, agent_obj, bridge):
        self.name = name
        self._agent = agent_obj
        self._bridge = bridge
        self._call_count = 0

    def call(self, function_name, *args, **kwargs):
        self._call_count += 1
        if hasattr(self._agent, "tool_registry") and function_name in self._agent.tool_registry:
            return self._agent.tool_registry[function_name](*args, **kwargs)
        raise AttributeError(f"Agent '{self.name}' has no function '{function_name}'")

    @property
    def instructions(self):
        return getattr(self._agent, "instructions", "")

    @property
    def tools(self):
        return list(getattr(self._agent, "tool_registry", {}).keys())

    def get_stats(self):
        return {"name": self.name, "tools": self.tools, "call_count": self._call_count}

    def __repr__(self):
        return f"AgentProxy('{self.name}', tools={self.tools})"
