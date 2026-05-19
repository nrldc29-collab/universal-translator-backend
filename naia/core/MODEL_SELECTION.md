# Model Selection for NAIA Distillation

## Student Model

**Selected: Qwen 2.5 3B Instruct**

- **Size**: 3B parameters
- **Performance**: Strong reasoning in this size class, better than Llama 3.2 3B
- **License**: Apache 2.0 (commercial-friendly)
- **Hardware**: Runs at 10-30 tok/s on modern laptop CPU at q4 quantization
- **Community**: Well-supported by llama.cpp, extensive tooling

### Alternative Options Considered

- **Llama 3.2 3B Instruct**: Solid general baseline, but Qwen 2.5 has better reasoning
- **Phi-3.5-mini (3.8B)**: Strongest CPU-friendly reasoner, but slightly larger

## Teacher Models

A panel of complementary strong open-weight teachers, each covering a different stage of NAIA's pipeline.

### 1. Reasoning/Planning Teacher
**Qwen 2.5 72B Instruct** or **DeepSeek V3**

- **Role**: Planner and critic stages
- **Why**: Strong reasoning capabilities, handles complex planning tasks
- **Endpoint**: Groq (Llama family) or OpenRouter free tier
- **Cost**: Free tier available through hosted endpoints

### 2. General Chat/Synthesis Teacher
**Llama 3.3 70B Instruct**

- **Role**: Final renderer and tone controller
- **Why**: Excellent general chat capabilities, good at synthesis
- **Endpoint**: Groq (free tier, very fast)
- **Cost**: Free tier available

### 3. Code & Tool Use Teacher
**Qwen 2.5 Coder 32B**

- **Role**: Tool argument construction
- **Why**: Specialized for code generation, understands tool APIs
- **Endpoint**: OpenRouter or Together AI
- **Cost**: Low cost per token

### 4. Safety/Risk Teacher
**Llama Guard 3** or similar

- **Role**: Risk gate evaluation
- **Why**: Safety-trained, specifically designed for content moderation
- **Endpoint**: OpenRouter or Together AI
- **Cost**: Low cost per token

### 5. Long-Context Teacher (Optional)
**Yi 1.5 34B-200K**

- **Role**: Memory-retrieval stage
- **Why**: 200K context window for handling large memory contexts
- **Endpoint**: Together AI
- **Cost**: Higher due to long context, optional

## Hosted Endpoints for Dataset Generation

### Groq (Free Tier)
- **Models**: Llama 3.x family
- **Speed**: Extremely fast (hundreds of tok/s)
- **Cost**: Free tier available
- **Best for**: Llama 3.3 70B for synthesis

### OpenRouter (Free Models)
- **Models**: Wide variety of open-weight models
- **Speed**: Variable
- **Cost**: Free models available, paid for premium
- **Best for**: Qwen 2.5 72B, Qwen Coder 32B

### Together AI
- **Models**: Many open-weight models
- **Speed**: Good
- **Cost**: Pay-per-token, reasonable rates
- **Best for**: Yi 1.5 34B-200K, specialized models

### Fireworks
- **Models**: Fast inference for open models
- **Speed**: Fast
- **Cost**: Pay-per-token
- **Best for**: General purpose

## Training Infrastructure

### GPU Options for LoRA Fine-Tuning

**1× H100**
- **Time**: ~2-4 hours
- **Cost**: ~$10-30
- **Platform**: Lambda Labs, RunPod, etc.

**1× RTX 4090 (Cheaper)**
- **Time**: ~4-8 hours
- **Cost**: ~$5-15
- **Platform**: RunPod, Vast.ai

### Training Framework
- **unsloth**: Optimized for single-GPU training, fast
- **axolotl**: More flexible, good for complex configs

## Final Output

- **Model File**: `naia-student-3b-q4.gguf`
- **Size**: ~2GB
- **Format**: GGUF q4_K_M quantization
- **Inference**: llama-cpp-python integration

## Cost Estimate

- **Dataset Generation**: $0-20 (using free tiers)
- **Training**: $5-30 (single GPU rental)
- **Total**: $5-50 for full pipeline
