from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

try:
    from training.local_student import LocalStudentModel, load_training_examples
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from training.local_student import LocalStudentModel, load_training_examples

logger = logging.getLogger(__name__)


def evaluate_against_teacher(
    model_path: str = "models/naia-local-student/local_student_model.json",
    dataset_path: str = "dataset/output/combined_unsloth.json",
) -> dict[str, Any]:
    model = LocalStudentModel.load(model_path)
    examples = load_training_examples(Path(dataset_path))
    
    metrics = {
        "total_examples": len(examples),
        "exact_match": 0,
        "intent_accuracy": 0,
        "complexity_accuracy": 0,
        "risk_accuracy": 0,
        "plan_accuracy": 0,
        "high_confidence_count": 0,
        "confidence_threshold": 0.8,
    }
    
    intent_matches = 0
    complexity_matches = 0
    risk_matches = 0
    plan_matches = 0
    structured_count = 0
    high_confidence_count = 0
    
    for example in examples:
        result = model.predict(example.instruction, structured=example.structured_output is not None, top_k=1)
        confidence = result["confidence"]
        output = result["output"]
        
        if confidence >= metrics["confidence_threshold"]:
            high_confidence_count += 1
        
        if output == example.text_output or output == example.structured_output:
            metrics["exact_match"] += 1
        
        if example.structured_output:
            structured_count += 1
            if isinstance(output, dict):
                if output.get("intent") == example.structured_output.get("intent"):
                    intent_matches += 1
                if output.get("complexity") == example.structured_output.get("complexity"):
                    complexity_matches += 1
                if output.get("risk") == example.structured_output.get("risk"):
                    risk_matches += 1
                if output.get("plan") == example.structured_output.get("plan"):
                    plan_matches += 1
    
    metrics["intent_accuracy"] = round(intent_matches / structured_count, 4) if structured_count else 0.0
    metrics["complexity_accuracy"] = round(complexity_matches / structured_count, 4) if structured_count else 0.0
    metrics["risk_accuracy"] = round(risk_matches / structured_count, 4) if structured_count else 0.0
    metrics["plan_accuracy"] = round(plan_matches / structured_count, 4) if structured_count else 0.0
    metrics["exact_match"] = round(metrics["exact_match"] / len(examples), 4) if examples else 0.0
    metrics["high_confidence_count"] = high_confidence_count
    metrics["high_confidence_rate"] = round(high_confidence_count / len(examples), 4) if examples else 0.0
    
    benchmarks = {
        "target_intent_accuracy": 0.95,
        "target_complexity_accuracy": 0.90,
        "target_risk_accuracy": 0.95,
        "target_exact_match": 0.85,
        "target_high_confidence_rate": 0.80,
    }
    
    passed = (
        metrics["intent_accuracy"] >= benchmarks["target_intent_accuracy"] and
        metrics["complexity_accuracy"] >= benchmarks["target_complexity_accuracy"] and
        metrics["risk_accuracy"] >= benchmarks["target_risk_accuracy"] and
        metrics["exact_match"] >= benchmarks["target_exact_match"] and
        metrics["high_confidence_rate"] >= benchmarks["target_high_confidence_rate"]
    )
    
    metrics["benchmarks"] = benchmarks
    metrics["passed"] = passed
    metrics["model_info"] = {
        "model_type": model.artifact["model_type"],
        "dataset_size": model.artifact["num_examples"],
        "training_config": model.artifact.get("training_config", {}),
    }
    
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate student model against teacher benchmarks")
    parser.add_argument("--model-path", default="models/naia-local-student/local_student_model.json")
    parser.add_argument("--dataset-path", default="dataset/output/combined_unsloth.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    logger.info("Evaluating student model against teacher benchmarks...")
    metrics = evaluate_against_teacher(args.model_path, args.dataset_path)
    
    print("\n=== Evaluation Results ===")
    print(f"Total examples: {metrics['total_examples']}")
    print(f"Exact match accuracy: {metrics['exact_match']:.4f} (target: {metrics['benchmarks']['target_exact_match']})")
    print(f"Intent accuracy: {metrics['intent_accuracy']:.4f} (target: {metrics['benchmarks']['target_intent_accuracy']})")
    print(f"Complexity accuracy: {metrics['complexity_accuracy']:.4f} (target: {metrics['benchmarks']['target_complexity_accuracy']})")
    print(f"Risk accuracy: {metrics['risk_accuracy']:.4f} (target: {metrics['benchmarks']['target_risk_accuracy']})")
    print(f"High confidence rate: {metrics['high_confidence_rate']:.4f} (target: {metrics['benchmarks']['target_high_confidence_rate']})")
    print(f"\nPassed benchmarks: {metrics['passed']}")
    print(f"\nModel info: {json.dumps(metrics['model_info'], indent=2)}")


if __name__ == "__main__":
    main()
