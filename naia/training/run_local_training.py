from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

try:
    from training.local_student import LocalStudentModel
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from training.local_student import LocalStudentModel

logger = logging.getLogger(__name__)


def run_local_training(
    dataset_path: str,
    output_dir: str,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    model = LocalStudentModel.train(dataset_path, output_path)
    metadata = {
        "output_dir": output_dir,
        "artifact": str(output_path / "local_student_model.json"),
        "num_examples": model.artifact["num_examples"],
        "model_type": model.artifact["model_type"],
        "created_at": model.artifact["created_at"],
    }
    summary_path = Path(output_dir) / "training_summary.json"
    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    logger.info(f"Local student training complete: {metadata}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train local CPU NAIA student model")
    parser.add_argument("--dataset-path", default="dataset/output/train_set.json")
    parser.add_argument("--output-dir", default="models/naia-local-student")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    metadata = run_local_training(args.dataset_path, args.output_dir)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
