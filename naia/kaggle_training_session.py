"""
NAIA Student — full Kaggle training session.

Paste this entire file into a single Kaggle notebook cell.  Designed for
a Kaggle T4 (16 GB) GPU.  Runs the real end-to-end chain:

    1. Preflight        — GPU/CUDA/dataset sanity checks
    2. Train            — LoRA fine-tune of Qwen2.5-1.5B-Instruct
    3. Eval             — quick perplexity check on a held-out slice
    4. Save adapter     — /kaggle/working/naia-student-lora/
    5. (Optional) Merge — merge LoRA into base, save as fp16

Kaggle setup (manual, one-time):
    • Settings  → Accelerator: GPU T4 x1 (or x2)
    • Settings  → Internet: On
    • Add data  → "naia-dataset" (id: nerlandecardeau/naia-dataset)
                  → makes /kaggle/input/naia-dataset/train_set.json available
    • Save Version → "Save & Run All"  to run end-to-end

The trained adapter lands in /kaggle/working/ and can be downloaded
from the right-hand "Output" pane after the run completes.
"""

# ---------------------------------------------------------------------------
# 0. Install deps  (Kaggle's base image has torch + transformers but not trl/peft/bitsandbytes at the versions we want)
# ---------------------------------------------------------------------------
import subprocess, sys

_PKGS = [
    "transformers==4.45.2",
    "datasets==3.0.1",
    "peft==0.13.2",
    "accelerate==1.0.1",
    "bitsandbytes==0.44.1",
    "trl==0.11.4",
    "sentencepiece",
]
print("Installing deps...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *_PKGS])
print("Done.")

# ---------------------------------------------------------------------------
# 1. Preflight
# ---------------------------------------------------------------------------
import json, os, time
from pathlib import Path

import torch

print("\n--- Preflight ---")
print(f"Python:     {sys.version.split()[0]}")
print(f"PyTorch:    {torch.__version__}")
print(f"CUDA avail: {torch.cuda.is_available()}")
assert torch.cuda.is_available(), "No GPU detected. Enable T4 in Kaggle Settings → Accelerator."
print(f"GPU:        {torch.cuda.get_device_name(0)}")
print(f"GPU mem:    {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

DATASET_PATH = "/kaggle/input/naia-dataset/train_set.json"
assert Path(DATASET_PATH).exists(), (
    f"Dataset missing at {DATASET_PATH}. In the right sidebar click "
    "'Add data' and add nerlandecardeau/naia-dataset."
)
with open(DATASET_PATH, encoding="utf-8") as f:
    raw = json.load(f)
print(f"Dataset:    {len(raw):,} examples at {DATASET_PATH}")
assert raw and "text" in raw[0], (
    "Dataset schema is not {'text': '...'} as expected by SFTTrainer."
)
print(f"Sample[0]:  {raw[0]['text'][:120]}...")

# Kaggle env hygiene
os.environ["WANDB_DISABLED"] = "true"
os.environ["TRANSFORMERS_CACHE"] = "/kaggle/working/.cache"
os.environ["HF_HOME"] = "/kaggle/working/.cache"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# 2. Config
# ---------------------------------------------------------------------------
CONFIG = {
    # 3B base. Fits on a single T4 (16 GB) in 4-bit + LoRA at batch 2 but
    # tight; T4x2 is more comfortable. Drop to "Qwen/Qwen2.5-1.5B-Instruct"
    # if you hit OOM at the first eval_steps boundary.
    "base_model":        "Qwen/Qwen2.5-3B-Instruct",
    "output_dir":        "/kaggle/working/naia-student-3b-lora",
    "merged_dir":        "/kaggle/working/naia-student-3b-merged",
    "max_seq_length":    1024,
    "per_device_batch":  2,            # 2 fits 3B on single T4; bump to 4 on T4x2
    "grad_accum":        8,            # effective batch = 16
    "learning_rate":     2e-4,
    "num_epochs":        2,
    "warmup_ratio":      0.03,
    "lr_scheduler":      "cosine",
    "logging_steps":     20,
    "save_steps":        500,
    "eval_split_frac":   0.02,         # 2% held out for eval
    "lora_r":            16,
    "lora_alpha":        32,
    "lora_dropout":      0.05,
    "target_modules":    ["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj"],
    "do_merge_after":    True,         # merge LoRA into base after training
}
print("\n--- Config ---")
print(json.dumps(CONFIG, indent=2))

# ---------------------------------------------------------------------------
# 3. Load model + tokenizer  (4-bit quantized)
# ---------------------------------------------------------------------------
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

print("\n--- Loading model ---")
bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)
tokenizer = AutoTokenizer.from_pretrained(CONFIG["base_model"], use_fast=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    CONFIG["base_model"],
    quantization_config=bnb,
    device_map="auto",
    torch_dtype=torch.float16,
)
model.config.use_cache = False
model.config.pretraining_tp = 1
print(f"Loaded {CONFIG['base_model']}")

# ---------------------------------------------------------------------------
# 4. LoRA wrap
# ---------------------------------------------------------------------------
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

model = prepare_model_for_kbit_training(model)
lora_cfg = LoraConfig(
    r=CONFIG["lora_r"],
    lora_alpha=CONFIG["lora_alpha"],
    lora_dropout=CONFIG["lora_dropout"],
    target_modules=CONFIG["target_modules"],
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()

# ---------------------------------------------------------------------------
# 5. Datasets — train / eval split
# ---------------------------------------------------------------------------
from datasets import Dataset

ds = Dataset.from_list(raw).shuffle(seed=42)
n_eval = max(64, int(len(ds) * CONFIG["eval_split_frac"]))
eval_ds  = ds.select(range(n_eval))
train_ds = ds.select(range(n_eval, len(ds)))
print(f"\nSplit: {len(train_ds):,} train / {len(eval_ds):,} eval")

# ---------------------------------------------------------------------------
# 6. Train with SFTTrainer (handles the {'text': ...} schema natively)
# ---------------------------------------------------------------------------
from transformers import TrainingArguments
from trl import SFTTrainer, SFTConfig

sft_cfg = SFTConfig(
    output_dir=CONFIG["output_dir"],
    num_train_epochs=CONFIG["num_epochs"],
    per_device_train_batch_size=CONFIG["per_device_batch"],
    per_device_eval_batch_size=CONFIG["per_device_batch"],
    gradient_accumulation_steps=CONFIG["grad_accum"],
    learning_rate=CONFIG["learning_rate"],
    warmup_ratio=CONFIG["warmup_ratio"],
    lr_scheduler_type=CONFIG["lr_scheduler"],
    logging_steps=CONFIG["logging_steps"],
    save_steps=CONFIG["save_steps"],
    save_total_limit=2,
    eval_strategy="steps",
    eval_steps=CONFIG["save_steps"],
    fp16=True,
    bf16=False,
    gradient_checkpointing=True,
    optim="paged_adamw_8bit",
    max_grad_norm=1.0,
    report_to=[],
    dataloader_num_workers=2,
    max_seq_length=CONFIG["max_seq_length"],
    packing=False,
    dataset_text_field="text",
)

trainer = SFTTrainer(
    model=model,
    args=sft_cfg,
    train_dataset=train_ds,
    eval_dataset=eval_ds,
    tokenizer=tokenizer,
)

print("\n--- Training ---")
t0 = time.time()
result = trainer.train()
elapsed = time.time() - t0
print(f"Training done in {elapsed/60:.1f} min")
print(result.metrics)

# ---------------------------------------------------------------------------
# 7. Save adapter + tokenizer
# ---------------------------------------------------------------------------
print("\n--- Saving LoRA adapter ---")
trainer.save_model(CONFIG["output_dir"])
tokenizer.save_pretrained(CONFIG["output_dir"])

summary = {
    "base_model":     CONFIG["base_model"],
    "num_examples":   len(train_ds),
    "num_eval":       len(eval_ds),
    "epochs":         CONFIG["num_epochs"],
    "lora_r":         CONFIG["lora_r"],
    "elapsed_min":    round(elapsed / 60, 1),
    "train_loss":     float(result.metrics.get("train_loss", float("nan"))),
    "created_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
with open(f"{CONFIG['output_dir']}/training_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))

# ---------------------------------------------------------------------------
# 8. Eval — final perplexity on held-out slice
# ---------------------------------------------------------------------------
print("\n--- Final eval ---")
eval_metrics = trainer.evaluate()
import math
ppl = math.exp(eval_metrics["eval_loss"]) if "eval_loss" in eval_metrics else None
print(f"Eval loss: {eval_metrics.get('eval_loss')!r}, Perplexity: {ppl}")

# ---------------------------------------------------------------------------
# 9. Optional merge — collapse LoRA into base weights as fp16
# ---------------------------------------------------------------------------
if CONFIG["do_merge_after"]:
    print("\n--- Merging LoRA into base (fp16) ---")
    del model, trainer
    torch.cuda.empty_cache()

    from peft import PeftModel

    base = AutoModelForCausalLM.from_pretrained(
        CONFIG["base_model"],
        torch_dtype=torch.float16,
        device_map="auto",
    )
    merged = PeftModel.from_pretrained(base, CONFIG["output_dir"])
    merged = merged.merge_and_unload()
    merged.save_pretrained(CONFIG["merged_dir"], safe_serialization=True)
    tokenizer.save_pretrained(CONFIG["merged_dir"])
    print(f"Merged model saved to {CONFIG['merged_dir']}")

print("\nALL DONE. Look in /kaggle/working/ for the adapter and merged model.")
