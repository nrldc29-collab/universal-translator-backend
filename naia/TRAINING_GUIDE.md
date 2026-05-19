# NAIA Model Distillation Guide

This guide walks through the complete process of training and deploying a local student model for NAIA via knowledge distillation from larger teacher models.

## Overview

The distillation pipeline consists of 5 main steps:

1. **Model Selection**: Choose student (Qwen 2.5 3B) and teacher models
2. **Dataset Generation**: Generate training data using teacher models
3. **Training**: LoRA fine-tune the student model
4. **Quantization**: Convert to GGUF format for efficient inference
5. **Integration**: Deploy the model in NAIA's core infrastructure

## Prerequisites

- Python 3.10+
- GPU access (for training) - can rent from RunPod, Lambda Labs, etc.
- API keys for teacher model endpoints (Groq, OpenRouter, Together AI, etc.)
- ~10-50GB disk space for datasets and model weights

## Step 1: Model Selection

**Student Model**: Qwen 2.5 3B Instruct
- 3B parameters, runs at 10-30 tok/s on CPU at q4 quantization
- Apache 2.0 license
- Strong reasoning in this size class

**Teacher Models**:
- **Reasoning/Planning**: Qwen 2.5 72B or DeepSeek V3
- **General Chat/Synthesis**: Llama 3.3 70B Instruct
- **Code & Tool Use**: Qwen 2.5 Coder 32B
- **Safety/Risk**: Llama Guard 3

See `core/MODEL_SELECTION.md` for detailed model selection rationale.

## Step 2: Dataset Generation

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up API keys for teacher models
export OPENROUTER_API_KEY="your-key"
export GROQ_API_KEY="your-key"
# or add to .env file
```

### Generate Prompts

```python
from dataset.prompt_curator import PromptCurator

curator = PromptCurator(seed_prompts_path="dataset/seed_prompts.json")
prompts = curator.sample_prompts(n=10000)  # Generate 10K prompts
```

### Generate Traces with Teachers

```python
from dataset.teacher_client import TeacherClient
from dataset.trace_logger import TraceLogger
from core.templates import format_template

teacher_client = TeacherClient(provider="openrouter")
trace_logger = TraceLogger(output_dir="dataset/traces")

for prompt in prompts:
    trace_logger.start_trace(prompt["input"])
    
    # Run through NAIA pipeline stages with teachers
    for stage in ["classifier", "planner", "risk_gate", "synthesizer"]:
        template = format_template(stage, input=prompt["input"], ...)
        result = teacher_client.generate(
            model="qwen/qwen-2.5-72b-instruct",
            messages=[{"role": "user", "content": template}],
        )
        trace_logger.log_stage(stage, {"input": prompt["input"]}, {"output": result}, "qwen-72b")
    
    trace = trace_logger.end_trace()
    trace_logger.save_trace(trace)
```

### Judge and Filter Traces

```python
from dataset.judge import TraceJudge

judge = TraceJudge(teacher_client, judge_model="qwen/qwen-2.5-72b-instruct")
traces = trace_logger.get_all_traces()
filtered_traces = judge.filter_traces(traces, min_score=0.7)
```

### Convert to Training Data

```python
import json

training_data = []
for trace in filtered_traces:
    # Single-shot format
    single_shot = {
        "text": f"User: {trace['input']}\nAssistant: {trace['stages']['synthesizer']['output']}"
    }
    training_data.append(single_shot)
    
    # Pipeline-aware format (structured)
    pipeline_aware = {
        "text": f"User: {trace['input']}\n\n" + "\n".join([
            f"{stage}: {data['output']}"
            for stage, data in trace['stages'].items()
        ])
    }
    training_data.append(pipeline_aware)

with open("dataset/training_data.jsonl", "w") as f:
    for item in training_data:
        f.write(json.dumps(item) + "\n")
```

**Expected Output**: ~30-100MB JSONL file with 30K high-quality examples

**Time**: ~2-4 hours wall-clock on laptop (teachers do the heavy lifting)

## Step 3: Training the Student Model

### Option A: Using unsloth (Recommended)

```bash
# Install unsloth
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# Train
python training/train.py \
    --base-model Qwen/Qwen2.5-3B-Instruct \
    --dataset-path dataset/training_data.jsonl \
    --output-dir ./naia-student-3b-lora \
    --lora-r 64 \
    --lora-alpha 16 \
    --learning-rate 2e-4 \
    --num-epochs 3 \
    --max-seq-length 4096
```

### Option B: Using Axolotl

```bash
# Install axolotl
pip install axolotl

# Train with config
accelerate launch -m axolotl.cli.train training/axolotl_config.yaml
```

### Training Parameters

- **LoRA Rank**: 64
- **LoRA Alpha**: 16
- **Learning Rate**: 2e-4
- **Epochs**: 2-3
- **Sequence Length**: 4096
- **Batch Size**: 4 (per device)
- **Gradient Accumulation**: 4

### GPU Options

**1× H100**
- Time: ~2-4 hours
- Cost: ~$10-30
- Platform: Lambda Labs, RunPod

**1× RTX 4090 (Cheaper)**
- Time: ~4-8 hours
- Cost: ~$5-15
- Platform: RunPod, Vast.ai

## Step 4: Quantization to GGUF

### Merge LoRA Weights

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-3B-Instruct",
    max_seq_length=4096,
    dtype=None,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=64,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0.05,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

# Load trained LoRA weights
model.load_adapter("./naia-student-3b-lora")

# Merge and save
merged_model = model.merge_and_unload()
merged_model.save_pretrained("./naia-student-3b-merged")
tokenizer.save_pretrained("./naia-student-3b-merged")
```

### Convert to GGUF

```bash
# Install llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make

# Convert to GGUF q4_K_M
./convert-hf-to-gguf.py ../naia-student-3b-merged \
    --outfile ../naia-student-3b-q4.gguf \
    --quantize q4_k_m

# Final output: ~2GB GGUF file
```

## Step 5: Integration with NAIA

### Initialize Global Client

```python
from core import initialize_global_client

# Initialize on startup
initialize_global_client(
    model_path="./naia-student-3b-q4.gguf",
    n_ctx=4096,
    n_gpu_layers=-1,  # Use all GPU layers if available
)
```

### Enable Local Model in Pipeline Stages

```python
from cognition.router.classifier import TaskClassifier
from agents.planner import AgentPlanner

# Enable local model for classifier
classifier = TaskClassifier(use_local_model=True)

# Enable local model for planner
planner = AgentPlanner(use_local_model=True)
```

### Configuration

Add to your NAIA configuration:

```python
# In runtime/pipeline.py or similar
from core import initialize_global_client

# On kernel initialization
model_path = os.getenv("NAIA_MODEL_PATH", "./naia-student-3b-q4.gguf")
initialize_global_client(model_path)
```

## Cost Summary

| Step | Cost |
|------|------|
| Dataset Generation (API calls) | $0-20 (using free tiers) |
| GPU Rental (training) | $5-30 |
| **Total** | **$5-50** |

## Time Summary

| Step | Time |
|------|------|
| Dataset Generation | 2-4 hours (laptop) |
| Training (H100) | 2-4 hours |
| Training (4090) | 4-8 hours |
| Quantization | 10-30 minutes |
| **Total** | **4-12 hours** |

## Troubleshooting

### Model Not Loading

```bash
# Check llama.cpp compatibility
llama-cli --help

# Verify GGUF file
llama-cli -m naia-student-3b-q4.gguf --prompt "test"
```

### Training Issues

- Reduce batch size if OOM
- Reduce sequence length if slow
- Check dataset format (valid JSONL)

### Integration Issues

- Verify `llama-cpp-python` installation
- Check model path is correct
- Enable GPU layers if available for better performance

## Next Steps

After deployment:

1. Monitor performance metrics (latency, throughput)
2. Collect feedback on model quality
3. Iterate with additional training data if needed
4. Consider model expansion (larger student model) if performance insufficient

## References

- [Qwen 2.5 Models](https://huggingface.co/Qwen)
- [unsloth Documentation](https://github.com/unslothai/unsloth)
- [llama.cpp Documentation](https://github.com/ggerganov/llama.cpp)
- [NAIA Constitution](constitution/constitution.md)
