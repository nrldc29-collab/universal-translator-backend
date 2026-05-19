"""Training configuration and scripts for NAIA model distillation."""

from pathlib import Path

from training.local_student import LocalStudentModel

TRAINING_DIR = Path(__file__).parent

__all__ = ["LocalStudentModel", "TRAINING_DIR"]
