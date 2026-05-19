"""Periodic memory consolidation: promote stable episodic to semantic, decay the rest."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ConsolidationConfig(BaseModel):
    """Configuration for memory consolidation."""

    episodic_age_threshold_days: int = Field(default=7, ge=1, le=365)
    access_count_threshold: int = Field(default=3, ge=1, le=50)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    decay_threshold_days: int = Field(default=30, ge=1, le=365)
    max_episodic_memories: int = Field(default=1000, ge=100, le=10000)


class ConsolidationReport(BaseModel):
    """Report from memory consolidation."""

    promoted_count: int = 0
    decayed_count: int = 0
    preserved_count: int = 0
    total_processed: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryConsolidator:
    """Consolidates memory by promoting stable episodic to semantic and decaying old memories."""

    def __init__(
        self,
        db_path: str | Path = "memory/naia_memory.sqlite3",
        config: ConsolidationConfig | None = None,
        use_claude: bool = False,
        claude_model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """
        Initialize the memory consolidator.

        Args:
            db_path: Path to the SQLite database
            config: Consolidation configuration
            use_claude: Whether to use Claude for semantic extraction
            claude_model: Claude model for semantic extraction
        """
        self.db_path = Path(db_path)
        self.config = config or ConsolidationConfig()
        self.use_claude = use_claude
        self.claude_model = claude_model
        self.client: Anthropic | None = None

        if use_claude:
            try:
                import os
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key:
                    self.client = Anthropic(api_key=api_key)
                    logger.info("Memory consolidator initialized with Claude")
            except ImportError:
                logger.warning("Anthropic not installed, Claude consolidation disabled")

    def consolidate(self) -> ConsolidationReport:
        """
        Run memory consolidation process.

        Returns:
            Consolidation report
        """
        if not self.db_path.exists():
            logger.error(f"Database not found: {self.db_path}")
            return ConsolidationReport(total_processed=0)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            report = ConsolidationReport()

            # Get all episodic memories
            cursor.execute(
                """SELECT memory_id, content, confidence, access_count, created_at, last_accessed_at
                   FROM memory_records
                   WHERE memory_type = 'episodic' AND status = 'active'"""
            )
            episodic_records = cursor.fetchall()

            report.total_processed = len(episodic_records)
            now = datetime.now(timezone.utc)

            for record in episodic_records:
                (
                    memory_id,
                    content,
                    confidence,
                    access_count,
                    created_at_str,
                    last_accessed_at_str,
                ) = record

                created_at = datetime.fromisoformat(created_at_str)
                last_accessed_at = datetime.fromisoformat(last_accessed_at_str)
                age_days = (now - created_at).total_seconds() / 86400
                days_since_access = (now - last_accessed_at).total_seconds() / 86400

                # Check if should promote to semantic
                if self._should_promote(
                    age_days, access_count, confidence, content
                ):
                    self._promote_to_semantic(cursor, memory_id, content, confidence)
                    report.promoted_count += 1
                    logger.info(f"Promoted episodic memory {memory_id} to semantic")

                # Check if should decay
                elif self._should_decay(age_days, days_since_access):
                    self._decay_memory(cursor, memory_id)
                    report.decayed_count += 1
                    logger.info(f"Decayed episodic memory {memory_id}")
                else:
                    report.preserved_count += 1

            conn.commit()
            conn.close()

            logger.info(
                f"Consolidation complete: {report.promoted_count} promoted, "
                f"{report.decayed_count} decayed, {report.preserved_count} preserved"
            )

            return report

        except Exception as exc:
            logger.error(f"Consolidation failed: {exc}")
            conn.close()
            return ConsolidationReport(total_processed=0)

    def _should_promote(
        self, age_days: float, access_count: int, confidence: float, content: str
    ) -> bool:
        """Determine if episodic memory should be promoted to semantic."""
        # Check age threshold
        if age_days < self.config.episodic_age_threshold_days:
            return False

        # Check access count
        if access_count < self.config.access_count_threshold:
            return False

        # Check confidence
        if confidence < self.config.confidence_threshold:
            return False

        # Use Claude to evaluate if content is generalizable
        if self.use_claude and self.client:
            return self._evaluate_with_claude(content)

        return True

    def _should_decay(self, age_days: float, days_since_access: float) -> bool:
        """Determine if memory should be decayed."""
        # Decay if very old and not recently accessed
        return (
            age_days > self.config.decay_threshold_days
            and days_since_access > self.config.decay_threshold_days
        )

    def _evaluate_with_claude(self, content: str) -> bool:
        """Use Claude to evaluate if content is generalizable to semantic memory."""
        try:
            system_prompt = """You are NAIA's memory evaluator. Determine if the given episodic memory should be promoted to semantic memory.

Semantic memories are general knowledge, patterns, or rules that apply broadly.
Episodic memories are specific events or experiences.

Evaluate the content and return JSON:
{
  "is_generalizable": true/false,
  "reasoning": "<brief explanation>",
  "suggested_semantic_content": "<generalized version if applicable>"
}"""

            user_prompt = f"""Content: {content}

Should this be promoted to semantic memory? Respond in JSON format."""

            response = self.client.messages.create(
                model=self.claude_model,
                max_tokens=512,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content_response = response.content[0].text

            # Parse JSON
            import json
            import re

            json_match = re.search(r'\{[^}]+\}', content_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("is_generalizable", False)

        except Exception as exc:
            logger.warning("Claude evaluation failed: %s", exc)

        return False

    def _promote_to_semantic(
        self, cursor: sqlite3.Cursor, memory_id: str, content: str, confidence: float
    ) -> None:
        """Promote episodic memory to semantic memory."""
        # Extract semantic content if using Claude
        semantic_content = content
        if self.use_claude and self.client:
            try:
                semantic_content = self._extract_semantic_content(content)
            except Exception:
                logger.warning("semantic_content_extraction_failed, using raw content")
                semantic_content = content

        # Update the record to semantic type
        cursor.execute(
            """UPDATE memory_records
               SET memory_type = 'semantic', content = ?, importance = 1.0
               WHERE memory_id = ?""",
            (semantic_content, memory_id),
        )

    def _extract_semantic_content(self, content: str) -> str:
        """Extract generalized semantic content from episodic memory."""
        try:
            system_prompt = """Extract the generalized knowledge or pattern from this episodic memory.

Return JSON:
{
  "semantic_content": "<generalized version>"
}"""

            user_prompt = f"Episodic memory: {content}"

            response = self.client.messages.create(
                model=self.claude_model,
                max_tokens=512,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content_response = response.content[0].text

            # Parse JSON
            import json
            import re

            json_match = re.search(r'\{[^}]+\}', content_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("semantic_content", content)

        except Exception as exc:
            logger.warning("Semantic extraction failed: %s", exc)

        return content

    def _decay_memory(self, cursor: sqlite3.Cursor, memory_id: str) -> None:
        """Decay a memory by reducing its importance or marking as inactive."""
        cursor.execute(
            """UPDATE memory_records
               SET status = 'archived', importance = importance * 0.5
               WHERE memory_id = ?""",
            (memory_id,),
        )

    def enforce_memory_limit(self) -> int:
        """Enforce maximum episodic memory limit by decaying oldest memories."""
        if not self.db_path.exists():
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Count episodic memories
            cursor.execute(
                """SELECT COUNT(*) FROM memory_records
                   WHERE memory_type = 'episodic' AND status = 'active'"""
            )
            count = cursor.fetchone()[0]

            if count <= self.config.max_episodic_memories:
                return 0

            # Decay oldest memories to stay under limit
            excess = count - self.config.max_episodic_memories
            cursor.execute(
                """UPDATE memory_records
                   SET status = 'archived'
                   WHERE memory_id IN (
                     SELECT memory_id FROM memory_records
                     WHERE memory_type = 'episodic' AND status = 'active'
                     ORDER BY last_accessed_at ASC
                     LIMIT ?
                   )""",
                (excess,),
            )

            conn.commit()
            conn.close()

            logger.info(f"Decayed {excess} old episodic memories to stay under limit")
            return excess

        except Exception as exc:
            logger.error(f"Memory limit enforcement failed: {exc}")
            conn.close()
            return 0
