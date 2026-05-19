@echo off
REM One-click training script for NAIA student model (requires GPU)

echo === NAIA Student Model Training Pipeline ===
echo.

REM Check for GPU
where nvidia-smi >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: NVIDIA GPU not detected. This script requires a GPU.
    echo Please run this on a machine with NVIDIA GPU and CUDA installed.
    pause
    exit /b 1
)

echo GPU detected:
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo.

REM Install dependencies
echo Step 1: Installing dependencies...
pip install -r requirements.txt
pip install -r training\requirements-gpu.txt
echo.

echo Step 1b: Running training preflight...
python -m training.preflight
if %ERRORLEVEL% NEQ 0 (
    echo Preflight failed. See training\GPU_TRAINING_RUNBOOK.md.
    pause
    exit /b 1
)
echo.

REM Prepare dataset
echo Step 2: Preparing dataset...
python training/prepare_dataset.py
echo.

REM Run training
echo Step 3: Starting LoRA fine-tuning...
echo This may take several hours depending on your GPU...
python training/run_training.py
echo.

REM Merge and convert
echo Step 4: Merging LoRA with base model and converting to GGUF...
python training/merge_and_convert.py
echo.

echo === Training Complete ===
echo.
echo Output files:
echo   - LoRA adapter: .\naia-student-3b-lora\
echo   - Merged model: .\naia-student-3b-merged\
echo   - GGUF models: .\naia-student-3b-gguf\
echo.
echo To use the trained model, see training\TRAINING_GUIDE.md
pause
