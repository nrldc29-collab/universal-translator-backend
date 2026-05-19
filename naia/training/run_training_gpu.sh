#!/bin/bash
# One-click training script for NAIA student model (requires GPU)

set -e

echo "=== NAIA Student Model Training Pipeline ==="
echo ""

# Check for GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: NVIDIA GPU not detected. This script requires a GPU."
    exit 1
fi

echo "GPU detected:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo ""

# Install dependencies
echo "Step 1: Installing dependencies..."
pip install -r requirements.txt
pip install -r training/requirements-gpu.txt
echo ""

echo "Step 1b: Running training preflight..."
python -m training.preflight
echo ""

# Prepare dataset
echo "Step 2: Preparing dataset..."
python training/prepare_dataset.py
echo ""

# Run training
echo "Step 3: Starting LoRA fine-tuning..."
python training/run_training.py
echo ""

# Merge and convert
echo "Step 4: Merging LoRA with base model and converting to GGUF..."
python training/merge_and_convert.py
echo ""

echo "=== Training Complete ==="
echo ""
echo "Output files:"
echo "  - LoRA adapter: ./naia-student-3b-lora/"
echo "  - Merged model: ./naia-student-3b-merged/"
echo "  - GGUF models: ./naia-student-3b-gguf/"
echo ""
echo "To use the trained model, see training/TRAINING_GUIDE.md"
