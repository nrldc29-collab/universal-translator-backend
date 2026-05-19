"""Training environment preflight checks."""

from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class TrainingPreflightResult:
    python_version: str
    platform: str
    has_nvidia_smi: bool
    has_cuda: bool
    installed_modules: dict[str, bool]
    dataset_files: dict[str, int]
    can_train_unsloth: bool
    blockers: list[str]
    warnings: list[str]


def run_training_preflight(dataset_dir: str | Path = "dataset/output") -> TrainingPreflightResult:
    modules = [
        "torch",
        "transformers",
        "datasets",
        "trl",
        "unsloth",
        "peft",
        "bitsandbytes",
        "accelerate",
    ]
    installed_modules = {module: importlib.util.find_spec(module) is not None for module in modules}
    has_nvidia_smi = shutil.which("nvidia-smi") is not None
    has_cuda = False
    warnings: list[str] = []
    blockers: list[str] = []

    if installed_modules["torch"]:
        try:
            import torch

            has_cuda = bool(torch.cuda.is_available())
        except Exception as exc:
            warnings.append(f"torch import failed during CUDA check: {exc}")

    dataset_files = _dataset_file_sizes(Path(dataset_dir))
    major, minor = sys.version_info[:2]

    if platform.system().lower() == "windows":
        blockers.append("Unsloth/bitsandbytes training is not reliably supported on native Windows; use WSL2/Linux with CUDA.")
    if (major, minor) not in {(3, 10), (3, 11)}:
        blockers.append(f"Python {major}.{minor} is unsupported for this training stack; use Python 3.10 or 3.11.")
    missing = [module for module, present in installed_modules.items() if not present]
    if missing:
        blockers.append(f"Missing training modules: {', '.join(missing)}.")
    if not has_nvidia_smi:
        blockers.append("nvidia-smi was not found; an NVIDIA GPU/CUDA environment is required for Qwen 3B LoRA training.")
    if not has_cuda:
        blockers.append("torch.cuda.is_available() is false; CUDA training is unavailable.")
    if not dataset_files:
        blockers.append("No prepared dataset files found under dataset/output.")
    elif dataset_files.get("combined_unsloth.json", 0) < 1_000_000:
        warnings.append("Prepared dataset is very small; this is only suitable for a smoke test, not meaningful distillation.")

    return TrainingPreflightResult(
        python_version=sys.version.replace("\n", " "),
        platform=platform.platform(),
        has_nvidia_smi=has_nvidia_smi,
        has_cuda=has_cuda,
        installed_modules=installed_modules,
        dataset_files=dataset_files,
        can_train_unsloth=not blockers,
        blockers=blockers,
        warnings=warnings,
    )


def print_training_preflight(result: TrainingPreflightResult) -> None:
    print(json.dumps(asdict(result), indent=2))
    if result.can_train_unsloth:
        print("\nPreflight passed. You can start Unsloth training.")
    else:
        print("\nPreflight failed. Resolve blockers before starting real student training.")
        for blocker in result.blockers:
            print(f"- {blocker}")
        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"- {warning}")


def require_unsloth_training_ready(dataset_dir: str | Path = "dataset/output") -> None:
    result = run_training_preflight(dataset_dir)
    if not result.can_train_unsloth:
        print_training_preflight(result)
        raise SystemExit(2)


def _dataset_file_sizes(dataset_dir: Path) -> dict[str, int]:
    if not dataset_dir.exists():
        return {}
    names = [
        "single_shot.jsonl",
        "pipeline_aware.jsonl",
        "single_shot_unsloth.json",
        "pipeline_aware_unsloth.json",
        "combined_unsloth.json",
    ]
    return {name: (dataset_dir / name).stat().st_size for name in names if (dataset_dir / name).exists()}


if __name__ == "__main__":
    print_training_preflight(run_training_preflight())
