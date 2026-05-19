from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from training.local_student import LocalStudentModel, load_training_examples
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from training.local_student import LocalStudentModel, load_training_examples


def evaluate_local_student(
    model_path: str = "models/naia-local-student/local_student_model.json",
    dataset_path: str = "dataset/output/combined_unsloth.json",
) -> dict:
    model = LocalStudentModel.load(model_path)
    examples = load_training_examples(Path(dataset_path))
    exact_output_matches = 0
    intent_matches = 0
    structured_count = 0

    for example in examples:
        result = model.predict(example.instruction, structured=example.structured_output is not None, top_k=1)
        output = result["output"]
        if output == example.text_output or output == example.structured_output:
            exact_output_matches += 1
        if example.structured_output:
            structured_count += 1
            predicted_intent = output.get("intent") if isinstance(output, dict) else None
            if predicted_intent == example.structured_output.get("intent"):
                intent_matches += 1

    total = len(examples)
    return {
        "model_path": model_path,
        "dataset_path": dataset_path,
        "total_examples": total,
        "exact_output_accuracy": round(exact_output_matches / total, 4) if total else 0.0,
        "structured_examples": structured_count,
        "structured_intent_accuracy": round(intent_matches / structured_count, 4) if structured_count else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local NAIA student model")
    parser.add_argument("--model-path", default="models/naia-local-student/local_student_model.json")
    parser.add_argument("--dataset-path", default="dataset/output/combined_unsloth.json")
    args = parser.parse_args()

    result = evaluate_local_student(args.model_path, args.dataset_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
