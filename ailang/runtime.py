import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import get_config


@dataclass
class Model:
    alias: str
    provider: str
    model_name: str
    config: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = {}


@dataclass
class Agent:
    name: str
    model: str
    instructions: str
    tools: List[str]
    body: List[Callable] = None
    tool_registry: Dict[str, Callable] = None
    memory: Optional[Any] = None
    context: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.body is None:
            self.body = []
        if self.tool_registry is None:
            self.tool_registry = {}

    def __getattr__(self, name: str) -> Any:
        """Allow calling registered tools as methods: agent.tool_name(args)."""
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self.tool_registry:
            return self.tool_registry[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


def define_model(
    alias: str,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Model:
    cfg = get_config()
    if provider is None:
        provider = cfg.default_provider
    if model_name is None:
        model_name = cfg.default_model
    return Model(alias=alias, provider=provider, model_name=model_name, config=config or {})


def define_agent(
    name: str,
    model: str,
    instructions: str,
    tools: List[str],
    body: Optional[List[Callable]] = None,
    tool_registry: Optional[Dict[str, Callable]] = None
) -> Agent:
    return Agent(name=name, model=model, instructions=instructions, tools=tools, body=body or [], tool_registry=tool_registry or {})


def register_tool(agent: Agent, tool_name: str, tool_func: Callable) -> None:
    """Register a tool function for an agent."""
    agent.tool_registry[tool_name] = tool_func


def call_tool(agent: Agent, tool_name: str, *args: Any, **kwargs: Any) -> Any:
    """Call a tool on an agent."""
    if tool_name not in agent.tool_registry:
        raise RuntimeError(f"Tool '{tool_name}' not registered for agent '{agent.name}'")
    return agent.tool_registry[tool_name](*args, **kwargs)


def execute_agent(agent: Agent, prompt: str, model_registry: Dict[str, Model] = None, **kwargs: Any) -> str:
    """Execute an agent with a prompt.

    This function runs the agent's body functions (if any) and then
    uses the agent's model to generate a response using the agent's instructions.

    Args:
        agent: The agent to execute
        prompt: The user prompt to process
        model_registry: Optional dict mapping model names to Model instances
        **kwargs: Additional arguments for ask_model
    """
    # Execute body functions if they exist
    if agent.body:
        for func in agent.body:
            if callable(func):
                try:
                    func()
                except Exception:
                    # Body functions may fail, continue execution
                    pass

    # Generate response using the agent's model and instructions
    full_prompt = f"{agent.instructions}\n\nUser: {prompt}"

    # Get the model - handle both Model instances and string references
    if isinstance(agent.model, Model):
        model = agent.model
    elif isinstance(agent.model, str) and model_registry and agent.model in model_registry:
        model = model_registry[agent.model]
    else:
        raise RuntimeError(f"Agent model '{agent.model}' not found in registry. Pass model_registry to execute_agent.")

    return ask_model(model, full_prompt, **kwargs)


def ask_model(model: Model, prompt: str, schema: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, tool_choice: Optional[str] = None, stream: bool = False, **kwargs: Any) -> str:
    """Runtime AI call.

    The default mock provider makes the language runnable without keys.
    Supports multiple AI providers: mock, openai, anthropic.
    Supports structured outputs via JSON schema validation.
    Supports function calling via tools parameter.
    Supports streaming responses for real-time interaction.
    """
    cfg = get_config()

    # Merge config defaults with kwargs
    api_kwargs = {**model.config, **kwargs}
    if "timeout" not in api_kwargs:
        api_kwargs["timeout"] = cfg.timeout

    if model.provider == "mock":
        if schema:
            return f"[mock:{model.model_name}] {prompt} (with schema: {schema})"
        if tools:
            return f"[mock:{model.model_name}] {prompt} (with tools: {len(tools)} tools)"
        if stream:
            return f"[mock:{model.model_name}] {prompt} (streaming)"
        return f"[mock:{model.model_name}] {prompt}"

    if model.provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai package to use provider: openai") from exc
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for provider: openai")
        client = OpenAI(api_key=api_key, timeout=api_kwargs.pop("timeout", cfg.timeout))
        if schema:
            api_kwargs["response_format"] = {"type": "json_object"}
        if tools:
            api_kwargs["tools"] = tools
        if tool_choice:
            api_kwargs["tool_choice"] = tool_choice
        if stream:
            api_kwargs["stream"] = True
            full_response = ""
            for chunk in client.chat.completions.create(
                model=model.model_name,
                messages=[{"role": "user", "content": prompt}],
                **api_kwargs
            ):
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
            return full_response
        response = client.chat.completions.create(
            model=model.model_name,
            messages=[{"role": "user", "content": prompt}],
            **api_kwargs
        )
        return response.choices[0].message.content

    if model.provider == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("Install the anthropic package to use provider: anthropic") from exc
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for provider: anthropic")
        timeout = api_kwargs.pop("timeout", cfg.timeout)
        client = Anthropic(api_key=api_key, timeout=timeout)
        if schema:
            api_kwargs["response_format"] = {"type": "json_object"}
        if tools:
            api_kwargs["tools"] = tools
        if tool_choice:
            api_kwargs["tool_choice"] = tool_choice
        if stream:
            api_kwargs["stream"] = True
            full_response = ""
            with client.messages.stream(
                model=model.model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                **api_kwargs
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
            return full_response
        response = client.messages.create(
            model=model.model_name,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            **api_kwargs
        )
        return response.content[0].text

    raise RuntimeError(f"Unknown model provider: {model.provider}")


def save_agent_state(agent: Agent, path: str) -> None:
    """Save agent state to a file.

    Saves the agent's memory and context to a JSON file for persistence.
    """
    state = {
        "name": agent.name,
        "model": agent.model,
        "instructions": agent.instructions,
        "tools": agent.tools,
        "memory": None,
        "context": None
    }

    # Serialize memory if it exists
    if agent.memory is not None:
        if hasattr(agent.memory, "items"):
            state["memory"] = list(agent.memory.items)
        else:
            state["memory"] = str(agent.memory)

    # Serialize context if it exists
    if agent.context is not None:
        if hasattr(agent.context, "history"):
            state["context"] = agent.context.history
        else:
            state["context"] = str(agent.context)

    Path(path).write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_agent_state(path: str) -> Dict[str, Any]:
    """Load agent state from a file.

    Returns a dictionary containing the saved agent state.
    """
    content = Path(path).read_text(encoding="utf-8")
    return json.loads(content)


def restore_agent_memory(agent: Agent, memory_data: Any) -> None:
    """Restore memory to an agent from saved data.

    The memory_data should be a list of memory items or a Memory object.
    """
    if memory_data is None:
        return

    if isinstance(memory_data, list):
        # Try to restore to a Memory object if stdlib is available
        try:
            from .stdlib import Memory
            mem = Memory()
            for item in memory_data:
                mem.add(
                    content=item.get("content", ""),
                    tags=item.get("tags", []),
                    metadata=item.get("metadata", {})
                )
            agent.memory = mem
        except ImportError:
            agent.memory = memory_data
    else:
        agent.memory = memory_data


def restore_agent_context(agent: Agent, context_data: Any) -> None:
    """Restore context to an agent from saved data.

    The context_data should be a list of messages or a Context object.
    """
    if context_data is None:
        return

    if isinstance(context_data, list):
        # Try to restore to a Context object if stdlib is available
        try:
            from .stdlib import Context
            ctx = Context()
            for msg in context_data:
                ctx.add_message(msg.get("role", "user"), msg.get("content", ""))
            agent.context = ctx
        except ImportError:
            agent.context = context_data
    else:
        agent.context = context_data


def agent_communicate(
    sender: Agent,
    receiver: Agent,
    message: str,
    model_registry: Dict[str, Model] = None,
    **kwargs: Any
) -> str:
    """Enable agent-to-agent communication.

    One agent can send a message to another agent, and the receiver
    will process it using its model and instructions.

    Args:
        sender: The agent sending the message
        receiver: The agent receiving the message
        message: The message to send
        model_registry: Optional dict mapping model names to Model instances
        **kwargs: Additional arguments for ask_model
    """
    # Add message to sender's context if available
    if sender.context is not None:
        try:
            sender.context.add_message("assistant", f"Sent to {receiver.name}: {message}")
        except Exception:
            pass

    # Add message to receiver's context if available
    if receiver.context is not None:
        try:
            receiver.context.add_message(f"{sender.name}", message)
        except Exception:
            pass

    # Process the message using the receiver's model
    full_prompt = f"Message from {sender.name}: {message}\n\n{receiver.instructions}"

    # Get the receiver's model
    if isinstance(receiver.model, Model):
        model = receiver.model
    elif isinstance(receiver.model, str) and model_registry and receiver.model in model_registry:
        model = model_registry[receiver.model]
    else:
        raise RuntimeError(f"Agent model '{receiver.model}' not found in registry")

    response = ask_model(model, full_prompt, **kwargs)

    # Add response to receiver's context if available
    if receiver.context is not None:
        try:
            receiver.context.add_message("assistant", response)
        except Exception:
            pass

    return response


def create_agent_team(agent_registry: Dict[str, Agent]) -> Dict[str, Agent]:
    """Create a team of agents that can communicate with each other.

    Args:
        agent_registry: Dictionary mapping agent names to Agent instances

    Returns:
        The same agent registry, now ready for team operations
    """
    return agent_registry


def team_discussion(
    agents: List[Agent],
    topic: str,
    rounds: int = 1,
    model_registry: Dict[str, Model] = None,
    **kwargs: Any
) -> List[Dict[str, str]]:
    """Facilitate a team discussion among multiple agents.

    Each agent can contribute to the discussion in turn.

    Args:
        agents: List of agents participating in the discussion
        topic: The topic to discuss
        rounds: Number of discussion rounds
        model_registry: Optional dict mapping model names to Model instances
        **kwargs: Additional arguments for ask_model

    Returns:
        List of discussion contributions, each with agent name and message
    """
    discussion = []
    current_topic = topic

    for round_num in range(rounds):
        for agent in agents:
            # Add topic to agent's context if available
            if agent.context is not None:
                try:
                    agent.context.add_message("system", f"Discussion round {round_num + 1}: {current_topic}")
                except Exception:
                    pass

            # Generate contribution
            full_prompt = f"Discussion topic: {current_topic}\n\n{agent.instructions}"

            # Get the agent's model
            if isinstance(agent.model, Model):
                model = agent.model
            elif isinstance(agent.model, str) and model_registry and agent.model in model_registry:
                model = model_registry[agent.model]
            else:
                raise RuntimeError(f"Agent model '{agent.model}' not found in registry")

            contribution = ask_model(model, full_prompt, **kwargs)

            discussion.append({"agent": agent.name, "message": contribution})

            # Update topic based on contribution (simple concatenation for demo)
            if round_num < rounds - 1 or agent != agents[-1]:
                current_topic = f"{current_topic}\n{agent.name}: {contribution}"

    return discussion
