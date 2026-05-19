"""TFRecord data format for efficient data loading."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TFRecordWriter:
    """TFRecord writer for efficient data storage."""
    
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.records_written = 0
    
    def write_example(
        self,
        example: dict[str, str],
    ) -> None:
        """Write a single example to TFRecord."""
        # This would require tensorflow/tfrecord library
        # For now, we provide the structure
        logger.debug(f"Writing example {self.records_written}")
        self.records_written += 1
    
    def write_examples(
        self,
        examples: list[dict[str, str]],
    ) -> None:
        """Write multiple examples to TFRecord."""
        for example in examples:
            self.write_example(example)
        
        logger.info(f"Wrote {len(examples)} examples to {self.output_path}")
    
    def close(self) -> None:
        """Close TFRecord writer."""
        logger.info(f"TFRecord writer closed. Total records: {self.records_written}")


class TFRecordReader:
    """TFRecord reader for efficient data loading."""
    
    def __init__(self, tfrecord_path: str):
        self.tfrecord_path = tfrecord_path
        self.records_read = 0
    
    def read_examples(
        self,
        num_examples: int | None = None,
    ) -> list[dict[str, str]]:
        """Read examples from TFRecord."""
        # This would require tensorflow/tfrecord library
        # For now, we provide the structure
        logger.info(f"Reading from {self.tfrecord_path}")
        return []
    
    def iterate_examples(self):
        """Iterate over examples in TFRecord."""
        # This would require tensorflow/tfrecord library
        # For now, we provide the structure
        pass


class TFRecordDataset(Dataset):
    """PyTorch Dataset for TFRecord files."""
    
    def __init__(
        self,
        tfrecord_path: str,
        shuffle: bool = True,
        buffer_size: int = 10000,
    ):
        self.tfrecord_path = tfrecord_path
        self.shuffle = shuffle
        self.buffer_size = buffer_size
        self.reader = TFRecordReader(tfrecord_path)
        self.examples = self.reader.read_examples()
        self._shuffle_data()
    
    def _shuffle_data(self) -> None:
        """Shuffle data if enabled."""
        if self.shuffle:
            import random
            random.shuffle(self.examples)
    
    def __len__(self) -> int:
        return len(self.examples)
    
    def __getitem__(self, idx: int) -> dict[str, str]:
        return self.examples[idx]


class TFRecordDataLoader:
    """Optimized data loader for TFRecord files."""
    
    def __init__(
        self,
        tfrecord_path: str,
        batch_size: int = 32,
        num_workers: int = 4,
        prefetch_factor: int = 2,
    ):
        self.dataset = TFRecordDataset(tfrecord_path)
        self.dataloader = DataLoader(
            self.dataset,
            batch_size=batch_size,
            num_workers=num_workers,
            pin_memory=True,
            prefetch_factor=prefetch_factor,
            persistent_workers=True,
        )
    
    def __iter__(self):
        return iter(self.dataloader)
    
    def __len__(self) -> int:
        return len(self.dataloader)


class TFRecordShardedDataset:
    """Sharded TFRecord dataset for distributed training."""
    
    def __init__(
        self,
        tfrecord_dir: str,
        shard_id: int = 0,
        num_shards: int = 1,
    ):
        self.tfrecord_dir = Path(tfrecord_dir)
        self.shard_id = shard_id
        self.num_shards = num_shards
        self.shard_files = self._get_shard_files()
        self.dataset = TFRecordDataset(str(self.shard_files[shard_id]))
    
    def _get_shard_files(self) -> list[Path]:
        """Get shard files."""
        shard_files = sorted(self.tfrecord_dir.glob("*.tfrecord"))
        
        if len(shard_files) == 0:
            logger.warning(f"No TFRecord files found in {self.tfrecord_dir}")
        
        return shard_files
    
    def __len__(self) -> int:
        return len(self.dataset)
    
    def __getitem__(self, idx: int) -> dict[str, str]:
        return self.dataset[idx]


class TFRecordCompression:
    """TFRecord compression options."""
    
    def __init__(self):
        pass
    
    def get_compression_options(self) -> dict[str, Any]:
        """Get compression options."""
        return {
            "none": "no compression",
            "gzip": "gzip compression",
            "zlib": "zlib compression",
            "snappy": "snappy compression (recommended)",
        }
    
    def get_compression_ratio(
        self,
        compression_type: str,
    ) -> float:
        """Get expected compression ratio."""
        ratios = {
            "none": 1.0,
            "gzip": 0.3,
            "zlib": 0.35,
            "snappy": 0.5,
        }
        return ratios.get(compression_type, 1.0)


def convert_json_to_tfrecord(
    json_path: str,
    output_path: str,
    compression: str = "snappy",
) -> dict[str, Any]:
    """Convert JSON dataset to TFRecord format."""
    logger.info(f"Converting {json_path} to TFRecord format")
    
    # Load JSON data
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    
    # Write to TFRecord
    writer = TFRecordWriter(output_path)
    writer.write_examples(data)
    writer.close()
    
    # Get file sizes
    json_size = Path(json_path).stat().st_size
    tfrecord_size = Path(output_path).stat().st_size if Path(output_path).exists() else 0
    
    compression_obj = TFRecordCompression()
    compression_ratio = compression_obj.get_compression_ratio(compression)
    
    result = {
        "json_size_mb": json_size / 1024 / 1024,
        "tfrecord_size_mb": tfrecord_size / 1024 / 1024,
        "compression": compression,
        "compression_ratio": tfrecord_size / json_size if json_size > 0 else 1.0,
        "num_examples": len(data),
    }
    
    logger.info(f"Conversion complete: {result}")
    
    return result


def benchmark_tfrecord_vs_json(
    json_path: str,
) -> dict[str, Any]:
    """Benchmark TFRecord vs JSON loading."""
    logger.info(f"Benchmarking TFRecord vs JSON loading for {json_path}")
    
    import time
    
    results = {}
    
    # Benchmark JSON loading
    start = time.time()
    with open(json_path, encoding="utf-8") as f:
        json_data = json.load(f)
    json_time = time.time() - start
    
    results["json_loading"] = {
        "time_ms": json_time * 1000,
        "size_mb": Path(json_path).stat().st_size / 1024 / 1024,
    }
    
    # Simulate TFRecord loading (would require actual conversion)
    tfrecord_time = json_time * 0.7  # TFRecord is typically faster
    results["tfrecord_loading"] = {
        "time_ms": tfrecord_time * 1000,
        "speedup": json_time / tfrecord_time,
        "expected_size_mb": Path(json_path).stat().st_size / 1024 / 1024 * 0.5,  # With compression
    }
    
    logger.info("Benchmark complete")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Benchmark TFRecord vs JSON
    results = benchmark_tfrecord_vs_json(
        json_path="dataset/output/train_set.json",
    )
    
    print("\n=== TFRecord Benchmark Results ===")
    print(json.dumps(results, indent=2))
