"""Pipeline Operator — Enables pipe syntax: stt |> translate |> tts

Provides a Python-level pipe operator that chains functions together,
mimicking what a native AILang |> operator would do.

Usage:
    from ailang_integration.runtime.pipe_operator import pipe, PipelineChain

    result = pipe(audio_data, context) |> step_stt |> step_translate |> step_tts
    # or
    chain = PipelineChain([step_stt, step_translate, step_tts])
    result = chain.run(audio_data, context)
"""
from __future__ import annotations
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PipelineChain:
    """Chainable pipeline that supports |> style composition.

    Example:
        chain = PipelineChain()
        chain = chain.then(step_stt).then(step_translate).then(step_tts)
        result = chain.run(input_data, context)
    """

    def __init__(self, steps: Optional[List[Callable]] = None):
        self._steps: List[Tuple[str, Callable]] = []
        if steps:
            for step in steps:
                name = getattr(step, "__name__", str(step))
                self._steps.append((name, step))

    def then(self, step: Callable, name: Optional[str] = None) -> "PipelineChain":
        """Add a step to the chain (returns new chain for immutability)."""
        new_chain = PipelineChain()
        new_chain._steps = list(self._steps)
        step_name = name or getattr(step, "__name__", f"step_{len(new_chain._steps)}")
        new_chain._steps.append((step_name, step))
        return new_chain

    def __or__(self, step: Callable) -> "PipelineChain":
        """Support chain | step syntax."""
        return self.then(step)

    def run(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all steps in sequence."""
        result = data
        timings = []
        for name, step in self._steps:
            start = time.time()
            try:
                result = step(result, context)
            except Exception as e:
                logger.error(f"Pipe step '{name}' failed: {e}")
                result["_pipe_error"] = str(e)
                result["_pipe_failed_at"] = name
                break
            elapsed = (time.time() - start) * 1000
            timings.append((name, elapsed))

        result["_pipe_timings"] = timings
        return result

    @property
    def step_names(self) -> List[str]:
        return [name for name, _ in self._steps]

    def __repr__(self) -> str:
        return " |> ".join(self.step_names)


class PipeValue:
    """Wraps a value for piping with |> syntax.

    Usage:
        result = pipe(data, ctx) >> step_stt >> step_translate >> step_tts
    """

    def __init__(self, data: Dict[str, Any], context: Dict[str, Any]):
        self._data = data
        self._context = context
        self._timings: List[Tuple[str, float]] = []

    def __rshift__(self, step: Callable) -> "PipeValue":
        """Support pipe >> step syntax."""
        name = getattr(step, "__name__", "step")
        start = time.time()
        self._data = step(self._data, self._context)
        elapsed = (time.time() - start) * 1000
        self._timings.append((name, elapsed))
        return self

    @property
    def result(self) -> Dict[str, Any]:
        self._data["_pipe_timings"] = self._timings
        return self._data


def pipe(data: Dict[str, Any], context: Dict[str, Any]) -> PipeValue:
    """Start a pipe chain: pipe(data, ctx) >> step1 >> step2 >> step3"""
    return PipeValue(data, context)


def chain(*steps: Callable) -> PipelineChain:
    """Create a pipeline chain from functions: chain(step1, step2, step3)"""
    return PipelineChain(list(steps))
