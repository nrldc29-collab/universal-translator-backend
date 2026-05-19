"""Script to populate naia_memory.sqlite3 with real embeddings from Anthropic."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from memory.embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)


def populate_embeddings(
    db_path: str | Path = "memory/naia_memory.sqlite3",
    batch_size: int = 100,
) -> None:
    """
    Populate the memory database with real embeddings.

    Args:
        db_path: Path to the SQLite database
        batch_size: Number of records to process at once
    """
    db_path = Path(db_path)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return

    # Initialize embeddings engine with Anthropic
    embeddings = EmbeddingEngine(use_anthropic=True)

    if not embeddings.is_using_real_embeddings():
        logger.warning("Anthropic embeddings not available, skipping")
        return

    logger.info(f"Populating embeddings for {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if vector column exists and add it if needed
    cursor.execute("PRAGMA table_info(memory_records)")
    columns = [row[1] for row in cursor.fetchall()]

    if "vector" not in columns:
        logger.info("Adding vector column to memory_records table")
        cursor.execute("ALTER TABLE memory_records ADD COLUMN vector TEXT")
        conn.commit()

    # Get all records without embeddings
    cursor.execute(
        "SELECT memory_id, content FROM memory_records WHERE vector IS NULL OR vector = ''"
    )
    records = cursor.fetchall()

    logger.info(f"Found {len(records)} records without embeddings")

    # Process in batches
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1}/{(len(records) + batch_size - 1) // batch_size}")

        for memory_id, content in batch:
            try:
                # Generate embedding
                embedding = embeddings.embed(content)
                # Convert to JSON string for storage
                import json
                vector_json = json.dumps(embedding)

                # Update database
                cursor.execute(
                    "UPDATE memory_records SET vector = ? WHERE memory_id = ?",
                    (vector_json, memory_id),
                )
            except Exception as exc:
                logger.error(f"Failed to embed record {memory_id}: {exc}")

        conn.commit()

    conn.close()
    logger.info("Embedding population complete")


def recompute_all_embeddings(
    db_path: str | Path = "memory/naia_memory.sqlite3",
    batch_size: int = 100,
) -> None:
    """
    Recompute all embeddings in the database (useful after switching embedding models).

    Args:
        db_path: Path to the SQLite database
        batch_size: Number of records to process at once
    """
    db_path = Path(db_path)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return

    # Initialize embeddings engine with Anthropic
    embeddings = EmbeddingEngine(use_anthropic=True)

    if not embeddings.is_using_real_embeddings():
        logger.warning("Anthropic embeddings not available, skipping")
        return

    logger.info(f"Recomputing all embeddings for {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all records
    cursor.execute("SELECT memory_id, content FROM memory_records")
    records = cursor.fetchall()

    logger.info(f"Found {len(records)} total records")

    # Process in batches
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1}/{(len(records) + batch_size - 1) // batch_size}")

        for memory_id, content in batch:
            try:
                # Generate embedding
                embedding = embeddings.embed(content)
                # Convert to JSON string for storage
                import json
                vector_json = json.dumps(embedding)

                # Update database
                cursor.execute(
                    "UPDATE memory_records SET vector = ? WHERE memory_id = ?",
                    (vector_json, memory_id),
                )
            except Exception as exc:
                logger.error(f"Failed to embed record {memory_id}: {exc}")

        conn.commit()

    conn.close()
    logger.info("Embedding recomputation complete")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Populate memory database with embeddings")
    parser.add_argument("--db-path", default="memory/naia_memory.sqlite3", help="Path to SQLite database")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--recompute", action="store_true", help="Recompute all embeddings")

    args = parser.parse_args()

    if args.recompute:
        recompute_all_embeddings(args.db_path, args.batch_size)
    else:
        populate_embeddings(args.db_path, args.batch_size)
