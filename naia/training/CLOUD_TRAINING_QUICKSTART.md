# Cloud GPU Training Quickstart

End-to-end guide for fine-tuning **Qwen 2.5 3B Instruct** into NAIA's student model
using LoRA on a rented cloud GPU. Total time start-to-finish: **~30-60 minutes**.
Total cost: **~$2-8** depending on provider.

This is the path you take when the local CPU TF-IDF student isn't enough and
you want a real instruction-tuned student NAIA's pipeline can call.

---

## TL;DR

```bash
# On a fresh RunPod / Vast.ai / Lambda Linux+CUDA box:
git clone <your-fork-of-naia> && cd naia
python3.11 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r training/requirements-gpu.txt
python -m training.preflight                          # verifies CUDA + deps
python training/prepare_dataset.py                    # builds combined_unsloth.json
python training/run_training.py                       # LoRA fine-tune (~30 min on 4090)
python training/merge_and_convert.py                  # merge + GGUF q4_k_m
# Download ./naia-student-3b-gguf/naia-student-3b-q4_k_m.gguf back to your laptop.
```

That's it. Everything below is "what each step does" and "what to do when it
breaks".

---

## 1. Pick a provider

| Provider | GPU | Hourly | Notes |
|---|---|---|---|
| **RunPod** (recommended) | RTX 4090 24 GB | $0.34-0.44 | Easiest UI, on-demand pods, web SSH. |
| RunPod | A100 40 GB | $1.19 | Faster (~1.5x) but more expensive per hour. |
| **Vast.ai** | RTX 4090 24 GB | $0.25-0.40 | Cheaper but variable availability/quality. |
| Lambda Labs | A10 24 GB | $0.75 | Stable, US-based, no marketplace dynamics. |
| Modal / Replicate | A100 | varies | Pay-per-second; easiest if you script the whole run. |

For this run, an **RTX 4090 on RunPod** is the right default. 24 GB VRAM is
plenty for Qwen 3B + 4-bit LoRA + sequence length 4096.

## 2. Spin up the pod

On RunPod:

1. Sign in → **Pods** → **+ Deploy**
2. Filter: **GPU = RTX 4090**, **Disk = 50 GB**
3. Template: **PyTorch 2.4** (or any CUDA 12.1 image)
4. Container start command: leave as default
5. Click **Deploy On-Demand**, wait 30s for it to boot

When the pod shows "Running", click **Connect → Start Web Terminal**.

## 3. Upload your code

Two options depending on whether your naia/ folder is in git:

**(a) From git** (recommended once you `git init`):
```bash
git clone <your-fork-of-naia> && cd naia
```

**(b) Via SCP from your laptop** (if not in git yet):
```powershell
# from your Windows machine
scp -P <pod-ssh-port> -r C:\Users\nrldc\OneDrive\Desktop\naia root@<pod-ip>:/workspace/
```

Either way, you should end up with `/workspace/naia/` (or your cwd of choice)
containing the full repo.

## 4. Install dependencies

```bash
cd naia
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r training/requirements-gpu.txt
```

This pulls torch 2.4 + transformers + unsloth + peft + bitsandbytes (~4 GB).

## 5. Preflight

```bash
python -m training.preflight
```

You should see something like:

```json
{
  "python_version": "3.11.x",
  "has_nvidia_smi": true,
  "has_cuda": true,
  "installed_modules": { "torch": true, "transformers": true, ... },
  "can_train_unsloth": true
}
```

If `can_train_unsloth` is `false`, the printed blockers tell you exactly what to
fix (missing module, wrong Python version, no GPU).

## 6. Prepare the dataset

```bash
python training/prepare_dataset.py
```

This reads `dataset/output/single_shot.jsonl` and `pipeline_aware.jsonl` and
produces `dataset/output/combined_unsloth.json` (~22 MB, ~51,000 examples).
The training code reads this single file.

If you want more data first (the dataset caps at ~51k unique-ish examples from
the seed prompts), one of these:

- **Free, more variations**: edit `dataset/generate_simple_dataset.py` and add
  more entries to the `variations` list in `_generate_variation`, then re-run.
- **Paid, real teacher output**: configure an API key for OpenRouter / Groq /
  Together in `dataset/teacher_client.py`, then run
  `python dataset/generate_dataset.py`. This calls real teacher LLMs to
  generate examples (a few cents to a few dollars depending on volume).

For a first end-to-end run, **just use what's there** -- 51k is enough for a
meaningful distillation and the cost is zero.

## 7. Train

```bash
python training/run_training.py
```

What this does:

1. Loads `Qwen/Qwen2.5-3B-Instruct` in 4-bit (uses ~3 GB VRAM).
2. Adds LoRA adapters: rank 64, alpha 16, dropout 0.05, target modules
   q/k/v/o/gate/up/down proj.
3. Trains for 3 epochs on `dataset/output/combined_unsloth.json`.
4. Saves the LoRA adapter to `./naia-student-3b-lora/`.
5. Also writes a merged-16bit copy to `./naia-student-3b-lora/merged/`.

Expected wall-clock on RTX 4090 with 40,800 train examples, 3 epochs, 4096
sequence length, batch 4 + grad-accum 4:

- **~25-40 minutes**
- VRAM usage: ~14-18 GB
- Cost: ~$0.20-0.30 of pod time

You'll see training-loss logs every 10 steps. Eval-loss every 500 steps. The
run is **stateful** -- if your pod dies, restart it and re-run; it auto-resumes
from `./naia-student-3b-lora/checkpoint-XXX/` thanks to
`resume_from_checkpoint=auto`.

## 8. Convert to GGUF for local inference

```bash
# Install llama.cpp once
git clone https://github.com/ggerganov/llama.cpp /opt/llama.cpp
cd /opt/llama.cpp && make -j && cd -

# Convert
python training/merge_and_convert.py
```

Produces three GGUF files in `./naia-student-3b-gguf/`:

| File | Size | Quality |
|---|---|---|
| `naia-student-3b-q4_k_m.gguf` | ~2.0 GB | Recommended. Runs on your i5-6400 at ~3-5 tok/s. |
| `naia-student-3b-q5_k_m.gguf` | ~2.4 GB | Slightly better quality, slower CPU inference. |
| `naia-student-3b-q8_0.gguf`   | ~3.5 GB | Highest quality, slowest on CPU. |

## 9. Download to your laptop

```bash
# On the pod, list outputs
ls -lh ./naia-student-3b-gguf/

# From your laptop, pull the q4_k_m file (the others are optional)
scp -P <pod-ssh-port> root@<pod-ip>:/workspace/naia/naia-student-3b-gguf/naia-student-3b-q4_k_m.gguf C:\Users\nrldc\.naia\models\
```

The default model path NAIA looks for is `~/.naia/models/`. Rename to whatever
your `NAIA_LOCAL_MODEL_PATH` env var points at, then run NAIA -- the pipeline
will use the new model automatically via `core.model_client.initialize_global_client`.

## 10. Tear down the pod

In the RunPod UI: **Stop Pod** (or Terminate if you don't need the disk).
**Forgetting this is the #1 way to burn money** -- a forgotten pod at $0.40/hr
costs $10/day.

---

## Cost summary

| Item | Cost |
|---|---|
| 1 hour RTX 4090 (training, conversion, buffer) | $0.40 |
| Disk (50 GB during the run) | $0.10 |
| Bandwidth (download 2 GB GGUF) | $0 (most providers don't charge egress at this volume) |
| **Total** | **~$0.50-$2** |

Well under the $5-15 budget. The extra budget gives you room for a second
training run with hyperparameter tweaks or a larger dataset.

---

## What can go wrong, and what to do

**`pip install unsloth` fails on the pod**
The unsloth package requires a specific torch+CUDA combination. Try:
```bash
pip install "unsloth[cu121-torch240] @ git+https://github.com/unslothai/unsloth.git"
```

**`CUDA out of memory` during training**
Halve `micro_batch_size` (4 → 2) and double `gradient_accumulation_steps`
(4 → 8) in `training/run_training.py`. Effective batch size stays the same;
VRAM use drops ~40%.

**Training loss diverges / NaN**
Drop the learning rate from `2e-4` to `1e-4` in `training/run_training.py`.

**`convert-hf-to-gguf.py: command not found`**
The merge_and_convert script expects llama.cpp's converter. Either install
llama.cpp at `/opt/llama.cpp` and put it on PATH, or run the converter
manually:
```bash
python /opt/llama.cpp/convert_hf_to_gguf.py ./naia-student-3b-lora/merged \
    --outfile ./naia-student-3b-q4_k_m.gguf --outtype q4_k_m
```

**Pod disconnects mid-training**
Reconnect and re-run `python training/run_training.py`. Auto-resume picks up
from the last checkpoint, you lose at most 500 steps (~30 seconds of work).

---

## What this gives you

A 3B-parameter Qwen-derived student that:

- Has been fine-tuned on NAIA's 51k pipeline examples.
- Runs on your laptop CPU at ~3-5 tokens/sec via llama.cpp.
- Plugs into NAIA's runtime via `core.model_client.initialize_global_client`.
- Replaces the keyword classifier and template planner with actual model
  inference for intent / complexity / risk / plan / answer.

Compared to the local TF-IDF student already trained:

| | Local TF-IDF | Cloud LoRA Qwen 3B |
|---|---|---|
| Size | 55 MB JSON | 2 GB GGUF |
| Training time | 21 sec on your CPU | 30 min on rented GPU |
| Inference latency | ~40 ms / call | ~200-500 ms / call |
| Routing accuracy on test set | ~70% exact, 100% intent | typically 85-92% exact |
| Generation quality | retrieval-only | real generative |
| Cost to retrain | $0 | ~$0.50 |
