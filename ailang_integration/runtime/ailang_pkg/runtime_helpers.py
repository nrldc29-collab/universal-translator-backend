"""Runtime helpers called by transpiled AILang code."""
import logging
import os

logger = logging.getLogger("ailang")

_model_cache = {}


def ask_model(model_spec: dict, prompt: str) -> str:
    """Call an LLM with the given prompt. Returns the response string."""
    if not isinstance(model_spec, dict):
        logger.warning(f"ask_model: invalid model_spec {model_spec!r}")
        return ""
    provider = model_spec.get("provider", "anthropic")
    model_name = model_spec.get("name", "claude-haiku-4-5-20251001")

    if provider == "anthropic":
        return _call_anthropic(model_name, str(prompt))
    raise ValueError(f"Unknown provider: {provider!r}")


def _call_anthropic(model_name: str, prompt: str) -> str:
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model_name,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text if msg.content else ""
    except Exception as e:
        logger.error(f"Anthropic call failed: {e}")
        return ""


class AgentInstance:
    """Runtime agent object. Methods are attached dynamically by transpiled code."""

    def __init__(self, name: str, model: dict, instructions: str, tools: list):
        self.name = name
        self.model = model
        self.instructions = instructions
        self.tools = tools
        self._methods = {}

    def call(self, method_name: str, *args, **kwargs):
        """Call a named method on this agent."""
        fn = self._methods.get(method_name)
        if fn is None:
            raise AttributeError(f"Agent {self.name!r} has no method {method_name!r}")
        return fn(*args, **kwargs)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        fn = self._methods.get(name)
        if fn:
            return fn
        raise AttributeError(f"Agent {self.name!r} has no attribute {name!r}")

    def __setattr__(self, name: str, value):
        if name.startswith("_") or name in ("name", "model", "instructions", "tools"):
            super().__setattr__(name, value)
        elif callable(value):
            self._methods[name] = value
        else:
            super().__setattr__(name, value)


def make_agent_class(name: str, model: dict, instructions: str, tools: list) -> AgentInstance:
    """Factory called by transpiled agent declarations."""
    return AgentInstance(name=name, model=model, instructions=instructions, tools=tools)


def _add(a, b):
    """Safe + operator: handles str+str, int+int, list+list, int+float."""
    if isinstance(a, list) and isinstance(b, list):
        return a + b
    if isinstance(a, str) or isinstance(b, str):
        return str(a) + str(b)
    try:
        return a + b
    except TypeError:
        return str(a) + str(b)
