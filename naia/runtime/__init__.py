"""NAIA cognitive runtime package."""

__all__ = ["CognitiveRuntimeKernel", "KernelResponse"]


def __getattr__(name: str):
    if name in {"CognitiveRuntimeKernel", "KernelResponse"}:
        from runtime.kernel import CognitiveRuntimeKernel, KernelResponse

        return {
            "CognitiveRuntimeKernel": CognitiveRuntimeKernel,
            "KernelResponse": KernelResponse,
        }[name]
    raise AttributeError(name)
