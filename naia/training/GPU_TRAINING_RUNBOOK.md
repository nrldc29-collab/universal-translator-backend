# GPU Training Runbook

## Current local status

This checkout has a prepared smoke-test dataset at `dataset/output/combined_unsloth.json`, but the current Windows/Python 3.14 environment is not able to run real Qwen 3B Unsloth training.

Run this anytime to verify readiness:

```powershell
python -m training.preflight
```

## Required environment

Use WSL2/Linux with:

- Python 3.10 or 3.11
- NVIDIA GPU with CUDA visible through `nvidia-smi`
- At least 16GB VRAM for Qwen 2.5 3B 4-bit LoRA

## Commands on the GPU machine

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r training/requirements-gpu.txt
python -m training.preflight
python training/prepare_dataset.py
python training/run_training.py
```

If the run completes, outputs are written to:

- `naia-student-3b-lora/`
- `naia-student-3b-lora/merged/`

## Dataset note

The current dataset is only a smoke-test dataset. For a meaningful student, first generate a larger judged dataset:

```bash
python -m dataset.generate_dataset
python training/prepare_dataset.py
python training/run_training.py
```

The dataset generation path requires teacher/judge API keys configured for the selected provider.
