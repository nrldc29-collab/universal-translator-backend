"""Data format optimization for faster training."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from datasets import Dataset
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def convert_to_parquet(
    json_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Convert JSON dataset to Parquet format for faster loading."""
    logger.info(f"Converting {json_path} to Parquet format")
    
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    
    # Convert to Arrow table
    table = pa.Table.from_pylist(data)
    
    # Write to Parquet
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    pq.write_table(table, output_file, compression='snappy')
    
    file_size = output_file.stat().st_size
    logger.info(f"Parquet file saved: {file_size / 1024 / 1024:.2f} MB")
    
    return {
        "original_format": "json",
        "new_format": "parquet",
        "original_size": Path(json_path).stat().st_size,
        "new_size": file_size,
        "compression_ratio": file_size / Path(json_path).stat().st_size,
    }


def convert_to_arrow(
    json_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Convert JSON dataset to Arrow format for faster loading."""
    logger.info(f"Converting {json_path} to Arrow format")
    
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    
    # Convert to Arrow table
    table = pa.Table.from_pylist(data)
    
    # Write to Arrow
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with pa.output_stream(output_file) as stream:
        table.write(stream)
    
    file_size = output_file.stat().st_size
    logger.info(f"Arrow file saved: {file_size / 1024 / 1024:.2f} MB")
    
    return {
        "original_format": "json",
        "new_format": "arrow",
        "original_size": Path(json_path).stat().st_size,
        "new_size": file_size,
        "compression_ratio": file_size / Path(json_path).stat().st_size,
    }


def create_memory_mapped_dataset(
    json_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Create memory-mapped dataset for faster access."""
    logger.info(f"Creating memory-mapped dataset from {json_path}")
    
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    
    # Create memory-mapped arrays
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Store instructions and outputs as memory-mapped arrays
    instructions = [ex.get("input", ex.get("instruction", "")) for ex in data]
    outputs = [ex.get("output", "") for ex in data]
    
    # Save as numpy memory-mapped files
    instructions_array = np.array(instructions, dtype=object)
    outputs_array = np.array(outputs, dtype=object)
    
    np.save(output_dir / "instructions.npy", instructions_array)
    np.save(output_dir / "outputs.npy", outputs_array)
    
    total_size = (output_dir / "instructions.npy").stat().st_size + (output_dir / "outputs.npy").stat().st_size
    logger.info(f"Memory-mapped dataset created: {total_size / 1024 / 1024:.2f} MB")
    
    return {
        "original_format": "json",
        "new_format": "memory_mapped",
        "original_size": Path(json_path).stat().st_size,
        "new_size": total_size,
    }


def optimize_dataset_structure(
    json_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Optimize dataset structure for faster training."""
    logger.info(f"Optimizing dataset structure for {json_path}")
    
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    
    # Normalize structure
    optimized_data = []
    for example in data:
        optimized_data.append({
            "instruction": example.get("input", example.get("instruction", "")),
            "output": example.get("output", ""),
            "length": len(example.get("input", example.get("instruction", ""))) + len(example.get("output", "")),
        })
    
    # Sort by length for better batching
    optimized_data.sort(key=lambda x: x["length"])
    
    # Remove length field (it was just for sorting)
    for item in optimized_data:
        del item["length"]
    
    # Save optimized dataset
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(optimized_data, f, indent=2)
    
    file_size = output_file.stat().st_size
    logger.info(f"Optimized dataset saved: {file_size / 1024 / 1024:.2f} MB")
    
    return {
        "original_count": len(data),
        "optimized_count": len(optimized_data),
        "original_size": Path(json_path).stat().st_size,
        "optimized_size": file_size,
    }


def benchmark_data_formats(
    json_path: str,
    output_dir: str,
) -> dict[str, Any]:
    """Benchmark different data formats for loading speed."""
    import time
    
    logger.info(f"Benchmarking data formats for {json_path}")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # Benchmark JSON
    start = time.time()
    with open(json_path, encoding="utf-8") as f:
        json_data = json.load(f)
    json_time = time.time() - start
    results["json"] = {"load_time": json_time, "size": Path(json_path).stat().st_size}
    
    # Benchmark Parquet
    parquet_path = output_path / "dataset.parquet"
    convert_to_parquet(json_path, str(parquet_path))
    
    start = time.time()
    parquet_data = pq.read_table(parquet_path).to_pylist()
    parquet_time = time.time() - start
    results["parquet"] = {
        "load_time": parquet_time,
        "size": parquet_path.stat().st_size,
        "speedup": json_time / parquet_time,
    }
    
    # Benchmark Arrow
    arrow_path = output_path / "dataset.arrow"
    convert_to_arrow(json_path, str(arrow_path))
    
    start = time.time()
    with pa.memory_map(arrow_path) as source:
        arrow_data = pa.ipc.open_stream(source).read_all().to_pylist()
    arrow_time = time.time() - start
    results["arrow"] = {
        "load_time": arrow_time,
        "size": arrow_path.stat().st_size,
        "speedup": json_time / arrow_time,
    }
    
    # Save benchmark results
    results_file = output_path / "benchmark_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Benchmark results saved to {results_file}")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Benchmark different formats
    results = benchmark_data_formats(
        json_path="dataset/output/train_set.json",
        output_dir="dataset/benchmark",
    )
    
    print("\n=== Data Format Benchmark Results ===")
    print(json.dumps(results, indent=2))
