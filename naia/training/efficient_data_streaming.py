"""Efficient data streaming for faster data loading."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import Dataset, DataLoader
from datasets import Dataset as HFDataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamingDataset(Dataset):
    """Streaming dataset for large datasets."""
    
    def __init__(
        self,
        data_path: str,
        chunk_size: int = 1000,
        cache_size: int = 10000,
    ):
        self.data_path = data_path
        self.chunk_size = chunk_size
        self.cache_size = cache_size
        self.cache = {}
        self.total_examples = self._count_examples()
    
    def _count_examples(self) -> int:
        """Count total examples in dataset."""
        with open(self.data_path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data)
    
    def _load_chunk(self, chunk_idx: int) -> list[dict[str, str]]:
        """Load a chunk of data."""
        start_idx = chunk_idx * self.chunk_size
        end_idx = min(start_idx + self.chunk_size, self.total_examples)
        
        with open(self.data_path, encoding="utf-8") as f:
            data = json.load(f)
        
        return data[start_idx:end_idx]
    
    def __len__(self) -> int:
        return self.total_examples
    
    def __getitem__(self, idx: int) -> dict[str, str]:
        chunk_idx = idx // self.chunk_size
        
        if chunk_idx not in self.cache:
            # Manage cache size
            if len(self.cache) >= self.cache_size // self.chunk_size:
                self.cache.pop(next(iter(self.cache)))
            
            self.cache[chunk_idx] = self._load_chunk(chunk_idx)
        
        local_idx = idx % self.chunk_size
        return self.cache[chunk_idx][local_idx]


class MemoryMappedDataset:
    """Memory-mapped dataset for efficient access."""
    
    def __init__(self, data_path: str):
        self.data_path = data_path
        self._load_memory_map()
    
    def _load_memory_map(self) -> None:
        """Load data into memory-mapped structure."""
        import numpy as np
        
        with open(self.data_path, encoding="utf-8") as f:
            data = json.load(f)
        
        # Store as numpy arrays for memory mapping
        self.instructions = np.array([ex.get("input", ex.get("instruction", "")) for ex in data], dtype=object)
        self.outputs = np.array([ex.get("output", "") for ex in data], dtype=object)
    
    def __len__(self) -> int:
        return len(self.instructions)
    
    def __getitem__(self, idx: int) -> dict[str, str]:
        return {
            "instruction": self.instructions[idx],
            "output": self.outputs[idx],
        }


class PrefetchDataset:
    """Dataset with prefetching for faster data loading."""
    
    def __init__(
        self,
        base_dataset: Dataset,
        prefetch_factor: int = 2,
    ):
        self.base_dataset = base_dataset
        self.prefetch_factor = prefetch_factor
        self.prefetch_buffer = []
        self._prefetch_initial()
    
    def _prefetch_initial(self) -> None:
        """Prefetch initial batches."""
        for i in range(min(self.prefetch_factor, len(self.base_dataset))):
            self.prefetch_buffer.append(self.base_dataset[i])
    
    def __len__(self) -> int:
        return len(self.base_dataset)
    
    def __getitem__(self, idx: int) -> Any:
        if idx < len(self.prefetch_buffer):
            return self.prefetch_buffer[idx]
        else:
            return self.base_dataset[idx]


class WebDataset:
    """WebDataset for distributed data loading."""
    
    def __init__(
        self,
        data_path: str,
        shard_size: int = 1000,
    ):
        self.data_path = data_path
        self.shard_size = shard_size
        self._create_shards()
    
    def _create_shards(self) -> None:
        """Create data shards."""
        with open(self.data_path, encoding="utf-8") as f:
            data = json.load(f)
        
        output_dir = Path(self.data_path).parent / "shards"
        output_dir.mkdir(exist_ok=True)
        
        for i, shard_idx in enumerate(range(0, len(data), self.shard_size)):
            shard = data[shard_idx:shard_idx + self.shard_size]
            shard_path = output_dir / f"shard_{i:04d}.json"
            
            with open(shard_path, "w", encoding="utf-8") as f:
                json.dump(shard, f)
        
        logger.info(f"Created {len(list(output_dir.glob('*.json')))} shards")
    
    def __len__(self) -> int:
        return len(list((Path(self.data_path).parent / "shards").glob("*.json")))
    
    def __getitem__(self, idx: int) -> list[dict[str, str]]:
        shard_dir = Path(self.data_path).parent / "shards"
        shard_files = sorted(shard_dir.glob("*.json"))
        
        if idx < len(shard_files):
            with open(shard_files[idx], encoding="utf-8") as f:
                return json.load(f)
        return []


class AsyncDataLoader:
    """Async data loader for non-blocking data loading."""
    
    def __init__(
        self,
        dataset: Dataset,
        batch_size: int = 32,
        num_workers: int = 4,
        prefetch_factor: int = 2,
    ):
        self.dataset = dataset
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.prefetch_factor = prefetch_factor
        
        self.dataloader = DataLoader(
            dataset,
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


class CachedDataset:
    """Dataset with caching for repeated access."""
    
    def __init__(
        self,
        base_dataset: Dataset,
        cache_dir: str = ".cache",
    ):
        self.base_dataset = base_dataset
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "dataset_cache.pt"
        
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cached data if available."""
        if self.cache_file.exists():
            logger.info(f"Loading cached data from {self.cache_file}")
            self.cached_data = torch.load(self.cache_file)
        else:
            self.cached_data = None
    
    def _save_cache(self) -> None:
        """Save data to cache."""
        logger.info(f"Saving cached data to {self.cache_file}")
        torch.save(self.cached_data, self.cache_file)
    
    def __len__(self) -> int:
        return len(self.base_dataset)
    
    def __getitem__(self, idx: int) -> Any:
        if self.cached_data is not None:
            return self.cached_data[idx]
        else:
            item = self.base_dataset[idx]
            # Build cache on first pass
            if self.cached_data is None:
                self.cached_data = []
            self.cached_data.append(item)
            return item


class LazyDataset:
    """Lazy loading dataset for memory efficiency."""
    
    def __init__(
        self,
        data_path: str,
        transform: Any | None = None,
    ):
        self.data_path = data_path
        self.transform = transform
        self._load_metadata()
    
    def _load_metadata(self) -> None:
        """Load only metadata."""
        with open(self.data_path, encoding="utf-8") as f:
            data = json.load(f)
        
        self.metadata = [
            {
                "length": len(ex.get("input", ex.get("instruction", ""))) + len(ex.get("output", "")),
                "offset": i,
            }
            for i, ex in enumerate(data)
        ]
    
    def __len__(self) -> int:
        return len(self.metadata)
    
    def __getitem__(self, idx: int) -> dict[str, str]:
        with open(self.data_path, encoding="utf-8") as f:
            data = json.load(f)
        
        item = data[idx]
        
        if self.transform:
            item = self.transform(item)
        
        return item


class StreamingTextDataset:
    """Streaming text dataset for very large datasets."""
    
    def __init__(
        self,
        data_path: str,
        buffer_size: int = 10000,
    ):
        self.data_path = data_path
        self.buffer_size = buffer_size
        self.buffer = []
        self.current_idx = 0
        self.file_handle = open(data_path, encoding="utf-8")
    
    def __del__(self):
        if hasattr(self, 'file_handle'):
            self.file_handle.close()
    
    def _fill_buffer(self) -> None:
        """Fill buffer with data."""
        self.buffer = []
        
        for line in self.file_handle:
            if line.strip():
                try:
                    example = json.loads(line)
                    self.buffer.append(example)
                    if len(self.buffer) >= self.buffer_size:
                        break
                except json.JSONDecodeError:
                    continue
    
    def __len__(self) -> int:
        # Return approximate length
        return self.buffer_size * 100  # Estimate
    
    def __iter__(self):
        while True:
            if not self.buffer:
                self._fill_buffer()
                if not self.buffer:
                    break
            
            for item in self.buffer:
                yield item
            
            self.buffer = []


def benchmark_data_loading_strategies(
    dataset_path: str,
) -> dict[str, Any]:
    """Benchmark different data loading strategies."""
    logger.info(f"Benchmarking data loading strategies for {dataset_path}")
    
    import time
    
    results = {}
    
    # Standard loading
    start = time.time()
    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)
    standard_time = time.time() - start
    results["standard_loading"] = {
        "time_ms": standard_time * 1000,
        "size_mb": Path(dataset_path).stat().st_size / 1024 / 1024,
    }
    
    # Streaming dataset
    streaming_dataset = StreamingDataset(dataset_path, chunk_size=1000)
    start = time.time()
    for i in range(min(100, len(streaming_dataset))):
        _ = streaming_dataset[i]
    streaming_time = time.time() - start
    results["streaming"] = {
        "time_ms": streaming_time * 1000,
        "speedup": standard_time / streaming_time,
    }
    
    # Memory-mapped dataset
    mmap_dataset = MemoryMappedDataset(dataset_path)
    start = time.time()
    for i in range(min(100, len(mmap_dataset))):
        _ = mmap_dataset[i]
    mmap_time = time.time() - start
    results["memory_mapped"] = {
        "time_ms": mmap_time * 1000,
        "speedup": standard_time / mmap_time,
    }
    
    logger.info("Data loading benchmark complete")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Benchmark data loading
    results = benchmark_data_loading_strategies(
        dataset_path="dataset/output/train_set.json",
    )
    
    print("\n=== Data Loading Benchmark Results ===")
    print(json.dumps(results, indent=2))
