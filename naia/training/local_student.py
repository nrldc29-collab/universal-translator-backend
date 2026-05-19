from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass
class StudentExample:
    instruction: str
    output: Any
    text_output: str
    structured_output: dict[str, Any] | None


class LocalStudentModel:
    def __init__(self, artifact: dict[str, Any]) -> None:
        self.artifact = artifact
        self.idf = artifact["idf"]
        self.examples = artifact["examples"]
        self.classifiers = artifact.get("classifiers", {})
        self.training_config = artifact.get("training_config", {})
        self.use_semantic_features = artifact.get("use_semantic_features", False)

    @classmethod
    def train(cls, dataset_path: str | Path, output_dir: str | Path) -> "LocalStudentModel":
        dataset_path = Path(dataset_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        examples = load_training_examples(dataset_path)
        if not examples:
            raise ValueError(f"No training examples found in {dataset_path}")

        idf = train_idf([example.instruction for example in examples])
        trained_examples = []
        for index, example in enumerate(examples):
            vector = tfidf_vector(example.instruction, idf)
            semantic_features = _compute_semantic_features(example.instruction)
            trained_examples.append(
                {
                    "id": index,
                    "instruction": example.instruction,
                    "output": example.output,
                    "text_output": example.text_output,
                    "structured_output": example.structured_output,
                    "vector": vector,
                    "norm": vector_norm(vector),
                    "semantic_features": semantic_features,
                }
            )

        classifiers = train_pipeline_classifiers(examples)
        training_config = {
            "dataset_size": len(examples),
            "idf_vocab_size": len(idf),
            "classifier_count": len(classifiers),
            "training_date": datetime.now(timezone.utc).isoformat(),
            "use_semantic_features": True,
        }
        artifact = {
            "model_type": "naia_local_tfidf_student",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_path": str(dataset_path),
            "num_examples": len(examples),
            "idf": idf,
            "examples": trained_examples,
            "classifiers": classifiers,
            "training_config": training_config,
            "use_semantic_features": True,
        }

        model_path = output_dir / "local_student_model.json"
        metadata_path = output_dir / "metadata.json"
        with open(model_path, "w", encoding="utf-8") as file:
            json.dump(artifact, file, ensure_ascii=False, indent=2)
        with open(metadata_path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "model_type": artifact["model_type"],
                    "created_at": artifact["created_at"],
                    "dataset_path": artifact["dataset_path"],
                    "num_examples": artifact["num_examples"],
                    "artifact_file": str(model_path),
                },
                file,
                ensure_ascii=False,
                indent=2,
            )

        return cls(artifact)

    @classmethod
    def load(cls, model_path: str | Path) -> "LocalStudentModel":
        with open(model_path, encoding="utf-8") as file:
            artifact = json.load(file)
        return cls(artifact)

    def predict(self, prompt: str, structured: bool = False, top_k: int = 5) -> dict[str, Any]:
        query_vector = tfidf_vector(prompt, self.idf)
        query_norm = vector_norm(query_vector)
        
        if self.use_semantic_features:
            query_semantic = _compute_semantic_features(prompt)
        
        scored = []
        for example in self.examples:
            score = cosine_similarity(query_vector, query_norm, example["vector"], example["norm"])
            
            if self.use_semantic_features:
                semantic_score = _semantic_similarity(query_semantic, example.get("semantic_features"))
                ngram_score = _compute_ngram_overlap(prompt, example["instruction"])
                # Adjusted weights to favor exact TF-IDF matches more strongly
                score = 0.8 * score + 0.15 * semantic_score + 0.05 * ngram_score
            
            scored.append((score, example))
        
        if structured:
            scored.sort(key=lambda item: (item[0], bool(item[1].get("structured_output"))), reverse=True)
        else:
            scored.sort(key=lambda item: item[0], reverse=True)
        
        best_score, best = scored[0]
        neighbors = [
            {
                "score": round(score, 4),
                "instruction": example["instruction"],
            }
            for score, example in scored[:top_k]
        ]

        if structured:
            output = best.get("structured_output") or {}
            if not output:
                output = {
                    "intent": self._classify("intent", prompt),
                    "complexity": self._classify("complexity", prompt),
                    "risk": self._classify("risk", prompt),
                    "plan": None,
                    "answer": best["text_output"],
                }
            else:
                output = dict(output)
                output.setdefault("intent", self._classify("intent", prompt))
                output.setdefault("complexity", self._classify("complexity", prompt))
                output.setdefault("risk", self._classify("risk", prompt))
                output.setdefault("answer", best["text_output"])
            return {
                "output": output,
                "confidence": round(best_score, 4),
                "neighbors": neighbors,
            }

        return {
            "output": best["text_output"],
            "confidence": round(best_score, 4),
            "neighbors": neighbors,
        }

    def _classify(self, classifier_name: str, prompt: str) -> str | None:
        classifier = self.classifiers.get(classifier_name)
        if not classifier:
            return None
        return predict_naive_bayes(prompt, classifier)


def load_training_examples(dataset_path: Path) -> list[StudentExample]:
    if dataset_path.suffix == ".jsonl":
        rows = []
        with open(dataset_path, encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    rows.append(json.loads(line))
    else:
        with open(dataset_path, encoding="utf-8") as file:
            rows = json.load(file)

    examples = []
    for row in rows:
        example = parse_training_row(row)
        if example:
            examples.append(example)
    return examples


def parse_training_row(row: dict[str, Any]) -> StudentExample | None:
    if "text" in row:
        instruction, output = parse_instruction_response(row["text"])
    else:
        instruction = row.get("instruction") or row.get("input")
        output = row.get("output")

    if not instruction or output is None:
        return None

    structured_output = None
    if isinstance(output, dict):
        structured_output = output
        text_output = json.dumps(output, ensure_ascii=False)
    elif isinstance(output, str):
        text_output = output
        structured_output = try_parse_json_object(output)
    else:
        text_output = json.dumps(output, ensure_ascii=False)

    return StudentExample(
        instruction=str(instruction).strip(),
        output=output,
        text_output=text_output.strip(),
        structured_output=structured_output,
    )


def parse_instruction_response(text: str) -> tuple[str | None, str | None]:
    marker = "### Response:"
    if marker not in text:
        return None, None
    instruction_part, response_part = text.split(marker, 1)
    instruction = instruction_part.replace("### Instruction:", "", 1).strip()
    response = response_part.strip()
    return instruction, response


def try_parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text) if len(token) > 1]


def train_idf(documents: list[str]) -> dict[str, float]:
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(tokenize(document)))
    total_documents = max(len(documents), 1)
    return {
        token: math.log((1 + total_documents) / (1 + frequency)) + 1.0
        for token, frequency in document_frequency.items()
    }


def tfidf_vector(text: str, idf: dict[str, float]) -> dict[str, float]:
    tokens = tokenize(text)
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {
        token: (count / total) * idf[token]
        for token, count in counts.items()
        if token in idf
    }


def vector_norm(vector: dict[str, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values()))


def cosine_similarity(
    left: dict[str, float],
    left_norm: float,
    right: dict[str, float],
    right_norm: float,
) -> float:
    if not left_norm or not right_norm:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    dot = sum(value * right.get(token, 0.0) for token, value in left.items())
    return dot / (left_norm * right_norm)


def _compute_semantic_features(text: str) -> dict[str, float]:
    tokens = tokenize(text)
    return {
        "length": len(text),
        "token_count": len(tokens),
        "avg_token_length": sum(len(t) for t in tokens) / len(tokens) if tokens else 0,
        "has_numbers": any(c.isdigit() for c in text),
        "has_upper": any(c.isupper() for c in text),
        "unique_tokens": len(set(tokens)) / len(tokens) if tokens else 0,
    }

def _semantic_similarity(query_features: dict[str, float], example_features: dict[str, float] | None) -> float:
    if not example_features:
        return 0.5
    
    length_diff = abs(query_features["length"] - example_features["length"]) / max(query_features["length"], example_features["length"], 1)
    token_diff = abs(query_features["token_count"] - example_features["token_count"]) / max(query_features["token_count"], example_features["token_count"], 1)
    unique_diff = abs(query_features["unique_tokens"] - example_features["unique_tokens"])
    
    score = 1.0 - (length_diff + token_diff + unique_diff) / 3
    return max(0.0, min(1.0, score))


def _compute_ngram_overlap(query: str, example: str, n: int = 2) -> float:
    """Compute n-gram overlap between query and example."""
    query_tokens = tokenize(query)
    example_tokens = tokenize(example)
    
    query_ngrams = set()
    example_ngrams = set()
    
    for i in range(len(query_tokens) - n + 1):
        query_ngrams.add(tuple(query_tokens[i:i+n]))
    
    for i in range(len(example_tokens) - n + 1):
        example_ngrams.add(tuple(example_tokens[i:i+n]))
    
    if not query_ngrams or not example_ngrams:
        return 0.0
    
    overlap = len(query_ngrams & example_ngrams)
    union = len(query_ngrams | example_ngrams)
    
    return overlap / union if union > 0 else 0.0


def train_pipeline_classifiers(examples: list[StudentExample]) -> dict[str, Any]:
    labeled: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for example in examples:
        output = example.structured_output
        if not output:
            continue
        for name in ("intent", "complexity", "risk"):
            value = output.get(name)
            if value is not None:
                labeled[name].append((example.instruction, str(value)))
    return {name: train_naive_bayes(rows) for name, rows in labeled.items() if rows}


def train_naive_bayes(rows: list[tuple[str, str]]) -> dict[str, Any]:
    labels = sorted({label for _, label in rows})
    vocabulary = sorted({token for text, _ in rows for token in tokenize(text)})
    label_counts: Counter[str] = Counter(label for _, label in rows)
    token_counts: dict[str, Counter[str]] = {label: Counter() for label in labels}
    token_totals: Counter[str] = Counter()

    for text, label in rows:
        tokens = tokenize(text)
        token_counts[label].update(tokens)
        token_totals[label] += len(tokens)

    total_rows = len(rows)
    vocabulary_size = max(len(vocabulary), 1)
    return {
        "labels": labels,
        "vocabulary": vocabulary,
        "label_log_priors": {
            label: math.log(label_counts[label] / total_rows)
            for label in labels
        },
        "token_log_likelihoods": {
            label: {
                token: math.log((token_counts[label][token] + 1) / (token_totals[label] + vocabulary_size))
                for token in vocabulary
            }
            for label in labels
        },
        "unknown_log_likelihoods": {
            label: math.log(1 / (token_totals[label] + vocabulary_size))
            for label in labels
        },
    }


def predict_naive_bayes(text: str, classifier: dict[str, Any]) -> str | None:
    tokens = tokenize(text)
    scores = {}
    for label in classifier["labels"]:
        score = classifier["label_log_priors"][label]
        likelihoods = classifier["token_log_likelihoods"][label]
        unknown = classifier["unknown_log_likelihoods"][label]
        for token in tokens:
            score += likelihoods.get(token, unknown)
        scores[label] = score
    if not scores:
        return None
    return max(scores.items(), key=lambda item: item[1])[0]
