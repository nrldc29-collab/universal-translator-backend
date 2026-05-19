# NAIA Student — Kaggle Training Runbook

End-to-end steps to fine-tune the NAIA student model on Kaggle's free T4 GPU
using the `kaggle_training_session.py` script in this folder.

## What this run does

A single Kaggle notebook that executes the full training chain:

1. **Preflight** — verifies GPU/CUDA/dataset are present
2. **Load** — Qwen/Qwen2.5-3B-Instruct in 4-bit (NF4) quantization
3. **LoRA wrap** — rank 16, alpha 32, on q/k/v/o + gate/up/down projections
4. **Train** — 2 epochs over `train_set.json` (51k examples) with `SFTTrainer`
5. **Eval** — perplexity on a 2% held-out slice
6. **Save** — LoRA adapter at `/kaggle/working/naia-student-3b-lora/`
7. **Merge** — collapse LoRA into the base model as fp16 at `/kaggle/working/naia-student-3b-merged/`

Expected wall-clock on a single T4: roughly **2–3 hours** for 3B (vs ~1–2 hr for the 1.5B
variant). T4 x2 cuts that roughly in half. Eval + merge add a few extra minutes.
The merged fp16 model lands at ~6 GB.

## Prerequisites

You already have everything:

- ✅ Dataset on Kaggle: `nerlandecardeau/naia-dataset` (you previously uploaded it)
- ✅ Training script: `naia/kaggle_training_session.py` (in this repo)
- ✅ Kaggle account with GPU quota (~30 hrs/week free)

If the Kaggle dataset is stale, re-upload it from
`naia/kaggle_upload/train_set.json` (or from the larger
`naia/dataset/output/combined_unsloth.json` if you want all 51k examples).

## Step-by-step

### 1. Create a new Kaggle notebook

Go to https://www.kaggle.com/code → **New Notebook**.

### 2. Enable GPU

Right sidebar → **Settings**:
- **Accelerator**: `GPU T4 x1` (use `T4 x2` if you want to upgrade to the
  3B base model — see "Bumping to 3B" below)
- **Internet**: `On` (required to install `trl`, `peft`, `bitsandbytes`)
- **Persistence**: leave as default

### 3. Attach the dataset

Right sidebar → **Input** → **Add Data** → search `naia-dataset` →
add **nerlandecardeau/naia-dataset**.

This makes `/kaggle/input/naia-dataset/train_set.json` available to the notebook.

### 4. Paste the script

Open `naia/kaggle_training_session.py` from this repo, copy the **entire
file**, and paste it into a single Kaggle notebook cell.

(Yes, one cell. The script is structured to run top-to-bottom and prints
section headers so you can follow progress in the cell output.)

### 5. Run

Either:
- Click **Run All** to run interactively (you can watch the loss curve), or
- **Save Version → Save & Run All** for a background commit run that
  survives browser closes (recommended for the 1–2 hr training).

### 6. Download the model

When the run finishes, the right sidebar **Output** pane shows:

- `naia-student-lora/` — LoRA adapter (~50 MB)
- `naia-student-merged/` — full merged fp16 model (~3 GB for the 1.5B base)
- `naia-student-lora/training_summary.json` — run metrics

Download whichever you need. The LoRA adapter is what plugs back into the
translator's assistant; the merged model is convenient for standalone
inference.

## Falling back to 1.5B

If you hit OOM at the first eval/checkpoint boundary on single T4, drop
to the 1.5B base by editing the script's `CONFIG`:

```python
"base_model": "Qwen/Qwen2.5-1.5B-Instruct",
"output_dir": "/kaggle/working/naia-student-lora",
"merged_dir": "/kaggle/working/naia-student-merged",
"per_device_batch": 4,
"grad_accum": 4,
```

This is much more comfortable on a single T4 but produces a smaller student.

## Speeding up on T4 x2

If you've upgraded the accelerator to T4 x2, you can bump throughput:

```python
"per_device_batch": 4,
"grad_accum": 4,
```

Effective batch stays 16, but you're now processing 8 examples per
forward pass across both GPUs.

## Wiring the trained adapter back into the translator

Once you have the trained model, put the adapter folder somewhere the
translator backend can read it (e.g. `naia/models/naia-student-lora/`),
then point `naia`'s local-model loader at it. The integration we just
added (`backend/assistant.py`) goes through the NAIA kernel, which uses
naia's own model routing — point it at the LoRA path in naia's config,
not at the translator code.

## What to watch for

- **OOM in step 6**: drop `per_device_batch` to 2 and bump `grad_accum`
  to 8. Effective batch size stays 16.
- **Slow tokenization**: lower `max_seq_length` from 1024 to 768.
- **Notebook restart after install**: if the deps install requires a
  kernel restart, just click Run All again — the install line is idempotent.
- **Dataset not found**: re-check step 3. The path must be exactly
  `/kaggle/input/naia-dataset/train_set.json`.

## What I can do from here

I can't actually run training on Kaggle for you (no Kaggle credentials,
and the GPU is on their side). What I *can* do next, if you want:

- Verify the script runs cleanly in a CPU dry-run mode against a small
  slice
- Update the dataset metadata + re-package `kaggle_upload/` with the
  newer `combined_unsloth.json` (51k examples) or `ultimate_unsloth.json`
  (larger)
- Pre-build the prompt template the trained model will see at inference
  so it matches the training format exactly
- Wire the merged model path into `naia`'s local-model loader so the
  assistant uses it after you download
