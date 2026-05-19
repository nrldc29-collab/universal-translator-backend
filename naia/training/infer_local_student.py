from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from training.local_student import LocalStudentModel
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from training.local_student import LocalStudentModel


def main() -> None:
    parser = argparse.ArgumentParser(description="Run inference with local NAIA student model")
    parser.add_argument("prompt")
    parser.add_argument("--model-path", default="models/naia-local-student/local_student_model.json")
    parser.add_argument("--structured", action="store_true")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    model = LocalStudentModel.load(args.model_path)
    result = model.predict(args.prompt, structured=args.structured, top_k=args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
