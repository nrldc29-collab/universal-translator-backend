# NAIA Student Model Training Guide

## Overview

This guide covers training the NAIA student model (Qwen 2.5 3B) using the generated dataset and Unsloth for LoRA fine-tuning.

## Prerequisites

### Hardware Requirements
- GPU with at least 16GB VRAM (for 4-bit quantization training)
- 32GB RAM recommended
- 100GB disk space for models and datasets

### Software Requirements
- Python 3.10+
- CUDA 12.x (if using NVIDIA GPU)
- Git

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Unsloth

```bash
pip install "unsloth[cu121-torch220]"  # For CUDA 12.1, PyTorch 2.2.0
```

### 3. Install llama.cpp (for GGUF conversion)

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make
cd ..
```

## Dataset Preparation

### Option 1: Use Existing Dataset

If you have already generated the dataset:

```bash
python training/prepare_dataset.py
```

This will:
- Convert JSONL files to Unsloth format
- Combine single-shot and pipeline-aware examples
- Output: `dataset/output/combined_unsloth.json`

### Option 2: Generate New Dataset

```bash
python dataset/generate_dataset.py --num-prompts 10000 --format-type both
```

## Training

### Local CPU Training (Default)

On machines without a supported CUDA/Unsloth setup, run:

```bash
python training/run_training.py
```

This is the default training path and will:
- Train the dependency-free local student model
- Save the trained artifact to `models/naia-local-student/local_student_model.json`
- Skip GPU preflight checks
- Work on any Python 3.x platform (no CUDA required)

Run inference with:

```bash
python training/infer_local_student.py "Create a REST API for user authentication with JWT tokens" --structured
```

Evaluate the local artifact with:

```bash
python training/eval_local_student.py
```

### GPU Training (Optional)

To force GPU Unsloth training when available, use:

```bash
python training/run_training.py --fallback-to-local false
```

This requires:
- Python 3.10 or 3.11
- NVIDIA GPU with CUDA
- Unsloth and training dependencies installed

### Manual Training Steps

If you want to run steps individually:

#### Step 1: Prepare Dataset

```bash
python training/prepare_dataset.py
```

#### Step 2: Train with Unsloth

```bash
python training/train.py \
    --base-model Qwen/Qwen2.5-3B-Instruct \
    --dataset-path dataset/output/combined_unsloth.json \
    --output-dir ./naia-student-3b-lora \
    --num-epochs 3 \
    --max-seq-length 4096
```

#### Step 3: Merge LoRA with Base Model

```bash
python training/merge_and_convert.py
```

This will:
- Merge LoRA adapter with base model
- Convert to GGUF format (q4_k_m, q5_k_m, q8_0)

## Training Configuration

### Hyperparameters

Default training parameters in `training/run_training.py`:

- **Base Model**: Qwen/Qwen2.5-3B-Instruct
- **LoRA Rank (r)**: 64
- **LoRA Alpha**: 16
- **Learning Rate**: 2e-4
- **Epochs**: 3
- **Batch Size**: 4
- **Gradient Accumulation**: 4
- **Max Sequence Length**: 4096
- **Quantization**: 4-bit

### Adjusting Parameters

Edit `training/run_training.py` to adjust:

```python
run_full_training_pipeline(
    lora_r=128,  # Increase for more capacity
    learning_rate=1e-4,  # Lower for more stable training
    num_epochs=5,  # Train longer
    batch_size=2,  # Reduce if OOM
)
```

## Monitoring Training

### TensorBoard

Add to training arguments:

```python
training_args = TrainingArguments(
    report_to="tensorboard",
    logging_dir="./logs",
    # ...
)
```

Then:

```bash
tensorboard --logdir ./logs
```

### Console Logging

Training progress is logged to console with:
- Loss per step
- Learning rate
- GPU memory usage
- Training speed

## Output Files

### After Training

```
naia-student-3b-lora/
├── adapter_config.json
├── adapter_model.safetensors
├── tokenizer.json
├── tokenizer_config.json
└── merged/
    ├── config.json
    ├── model.safetensors
    └── tokenizer files
```

### After GGUF Conversion

```
naia-student-3b-gguf/
├── naia-student-3b-q4_k_m.gguf
├── naia-student-3b-q5_k_m.gguf
└── naia-student-3b-q8_0.gguf
```

## Using the Trained Model

### With Unsloth (Python)

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="./naia-student-3b-lora",
    max_seq_length=4096,
    dtype=None,
    load_in_4bit=True,
)

response = model.generate(
    **tokenizer("### Instruction:\nWhat is NAIA?\n\n### Response:", return_tensors="pt"),
    max_new_tokens=512,
)
print(tokenizer.decode(response[0]))
```

### With llama.cpp (GGUF)

```bash
./llama.cpp/main -m naia-student-3b-gguf/naia-student-3b-q4_k_m.gguf \
    -p "### Instruction:\nWhat is NAIA?\n\n### Response:" \
    -n 512
```

## Troubleshooting

### Out of Memory (OOM)

Reduce batch size or gradient accumulation:

```python
batch_size=2,
gradient_accumulation_steps=8,
```

### CUDA Out of Memory

Use CPU-only mode (slower):

```python
load_in_4bit=False,  # Load in full precision on CPU
```

### Slow Training

Increase batch size if GPU memory allows:

```python
batch_size=8,
gradient_accumulation_steps=2,
```

### Poor Quality Results

- Increase training epochs
- Increase LoRA rank (r)
- Use larger dataset
- Check dataset quality

## Advanced Options

### Multi-GPU Training

Use DeepSpeed:

```bash
deepspeed --num_gpus=2 training/train.py
```

### Mixed Precision Training

Enable BF16 if supported:

```python
bf16=True,
fp16=False,
```

### Gradient Checkpointing

Already enabled in Unsloth for memory efficiency.

## Evaluation

After training, evaluate the model:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("./naia-student-3b-lora/merged")
tokenizer = AutoTokenizer.from_pretrained("./naia-student-3b-lora/merged")

# Test with sample prompts
test_prompts = [
    "What is NAIA?",
    "Plan a REST API for user authentication.",
    "Explain the cognitive pipeline.",
]

for prompt in test_prompts:
    inputs = tokenizer(f"### Instruction:\n{prompt}\n\n### Response:", return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=256)
    print(f"Prompt: {prompt}")
    print(f"Response: {tokenizer.decode(outputs[0])}")
    print("-" * 80)
```

## Next Steps

1. **Evaluation**: Run evaluation on test set
2. **Benchmarking**: Compare with base model
3. **Deployment**: Integrate into NAIA runtime
4. **Iteration**: Refine dataset and retrain if needed

## Resources

- [Unsloth Documentation](https://github.com/unslothai/unsloth)
- [Qwen 2.5 Models](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
- [LoRA Paper](https://arxiv.org/abs/2106.09685)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)
