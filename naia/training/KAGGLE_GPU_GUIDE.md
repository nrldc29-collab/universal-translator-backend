# Kaggle GPU Training Guide

This guide explains how to train the NAIA student model on Kaggle's free GPU instances.

## Why Kaggle?

Kaggle offers the best free GPU option for students and researchers:
- **30 hours weekly quota** - generous GPU time
- **9-hour sessions** with background execution
- **20 GB persistent storage** - enough for datasets and checkpoints
- **NVIDIA T4 or P100 GPUs** - better than Colab's K80
- **More reliable GPU access** than Google Colab
- **No credit card required**

## Setup Instructions

### 1. Create Kaggle Account

1. Go to [kaggle.com](https://kaggle.com)
2. Sign up for a free account
3. Verify your email address

### 2. Use Your Uploaded Dataset

Your dataset is already created at:

`https://www.kaggle.com/datasets/nerlandecardeau/naia-dataset`

In your Kaggle notebook, click **Add Data**, search for:

`nerlandecardeau/naia-dataset`

After adding it, the training script expects:

`/kaggle/input/naia-dataset/train_set.json`

### 3. Create a New Notebook

1. Go to [kaggle.com/code](https://kaggle.com/code)
2. Click "New Notebook"
3. Select "GPU" as the accelerator (T4 or P100)
4. Name it something like "naia-student-training"

### 4. Upload Training Script

1. In your notebook, click "Add data" → "Upload"
2. Upload the following files from your local project:
   - `training/kaggle_gpu_training.py`
   - `dataset/output/train_set.json` (if not using Kaggle dataset)
3. Or copy the code directly into notebook cells

### 5. Run Training

Add this to your notebook:

```python
import sys
sys.path.append('/kaggle/working')

from training.kaggle_gpu_training import run_kaggle_gpu_training

# Run training
result = run_kaggle_gpu_training()
print(result)
```

## Training Configuration

The Kaggle training uses these optimized settings:

```python
{
    "gpu_type": "NVIDIA T4",
    "batch_size": 8,
    "gradient_accumulation_steps": 2,
    "max_seq_length": 2048,
    "learning_rate": 2e-4,
    "num_train_epochs": 3,
    "fp16": True,
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "lora_r": 8,
    "lora_alpha": 16,
    "output_dir": "/kaggle/working/naia-gpu-student",
}
```

## Tips for Kaggle Training

1. **Use background execution**: Your training continues even if you close the browser
2. **Save checkpoints**: The script saves checkpoints every 500 steps
3. **Monitor GPU usage**: Check the GPU usage meter to ensure you're using the GPU
4. **Persistent storage**: Your model is saved to `/kaggle/working/` and can be downloaded
5. **Weekly quota**: You get 30 hours per week, plan your training accordingly

## Download Trained Model

After training completes:

1. Go to the "Output" section of your notebook
2. Download the `naia-gpu-student` folder
3. Extract it to your local project: `models/naia-gpu-student/`

## Evaluate Trained Model

Once you've downloaded the model to your local machine:

```bash
python training/evaluate_against_teacher.py --model-path models/naia-gpu-student/adapter_model.bin
```

## Troubleshooting

### GPU Not Available
- Make sure you selected "GPU" as the accelerator when creating the notebook
- Try creating a new notebook with GPU enabled

### Out of Memory
- Reduce `batch_size` in `KAGGLE_GPU_CONFIG`
- Reduce `max_seq_length`
- Use `load_in_8bit=True` (already enabled)

### Session Timeout
- Kaggle sessions last up to 9 hours
- Use background execution to continue training
- Save checkpoints frequently (already configured)

### Dataset Not Found
- Ensure `nerlandecardeau/naia-dataset` is attached to the notebook with **Add Data**
- Check the dataset path matches your upload
- Use the absolute path: `/kaggle/input/naia-dataset/train_set.json`

## Alternative Free GPU Options

If Kaggle doesn't work for you, consider:

1. **Google Colab** - 12-hour sessions, but less reliable
2. **Lightning.ai** - 35 monthly GPU hours, persistent environment
3. **Amazon SageMaker Studio Lab** - AWS's free GPU offering
4. **Gradient by Paperspace** - Free GPU with patience

Kaggle remains the best option for consistent, reliable GPU training.
