from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from memory.embeddings import EmbeddingEngine
from memory.indexer import MemoryIndexer
from memory.memory_engine import MemoryEngine
from memory.memory_policy import MemoryPolicyEngine, MemoryType, MemoryWriteCandidate
from memory.memory_store import MemoryStore
from memory.memory_validator import MemoryValidator
from memory.multi_tenant import MultiTenantMemoryStore
from memory.rag_retrieval import RAGRetrievalRequest, RAGRetriever
from runtime.events import EventLog
from runtime.lifecycle import LifecycleManager, LifecycleState
from runtime.scheduler import RuntimeBudgets, Scheduler, SchedulerRejected
from runtime.state import CognitiveState
from tools.api_tools import api_get
from tools.code_tools import run_python
from tools.risk_gate import ToolRiskGate
from tools.sandbox import SandboxManager
from tools.system_tools import list_directory, read_file, run_system_command_review, write_file
from tools.web_tools import fetch_url, web_search
from tools.registry import ToolRequest, create_default_registry


def candidate(content: str, **kwargs) -> MemoryWriteCandidate:
    return MemoryWriteCandidate(
        memory_type=kwargs.pop("memory_type", MemoryType.SEMANTIC),
        content=content,
        confidence=kwargs.pop("confidence", 0.8),
        importance=kwargs.pop("importance", 0.7),
        source="test",
        **kwargs,
    )


def test_memory_engine_store_retriever_happy_and_failure_paths(tmp_path: Path) -> None:
    engine = MemoryEngine(db_path=tmp_path / "memory.sqlite3")
    write_result = engine.write(candidate("User prefers concise Python examples"))
    assert write_result.stored is True
    assert write_result.record is not None

    duplicate = engine.write(candidate("User prefers concise Python examples"))
    assert duplicate.stored is False
    assert duplicate.status == "rejected"

    retrieved = engine.retrieve("concise python", limit=3)
    assert retrieved.memories
    assert "concise" in retrieved.injected_context.lower()

    forgotten = engine.forget(write_result.record.memory_id, reason="test cleanup")
    assert forgotten.forgotten is True
    missing_forget = engine.forget("missing", reason="test cleanup")
    assert missing_forget.forgotten is False


def test_memory_policy_validator_indexer_embeddings_paths(tmp_path: Path) -> None:
    policy = MemoryPolicyEngine()
    assert policy.decide_write(candidate("")).action.value == "reject"
    assert policy.decide_write(candidate("password is abc")).requires_approval is True

    embeddings = EmbeddingEngine(dimensions=16)
    vector = embeddings.embed("hello hello world")
    assert len(vector) == 16
    assert embeddings.similarity(vector, vector) == pytest.approx(1.0)
    assert embeddings.similarity(vector, [1.0]) == 0.0

    store = MemoryStore(tmp_path / "store.sqlite3")
    first = store.write(
        candidate("Deploy uses blue green"),
        vector=embeddings.embed("Deploy uses blue green"),
        status=policy.decide_write(candidate("Deploy uses blue green")).status,
        sensitivity="normal",
        topic="deploy",
        decay_rate=0.01,
    )
    validator = MemoryValidator(embeddings)
    assert validator.validate(candidate("Deploy uses blue green"), [first]).action == "reject"
    assert validator.validate(candidate("Deploy does not use blue green"), [first]).action in {"allow", "quarantine"}

    indexer = MemoryIndexer()
    assert indexer.topic_for(candidate("alpha beta beta")) == "beta"
    assert indexer.extract_topics("the alpha beta gamma", limit=2) == ["alpha", "beta"]


def test_rag_and_multi_tenant_paths(tmp_path: Path) -> None:
    engine = MemoryEngine(db_path=tmp_path / "rag.sqlite3")
    engine.write(candidate("Paris is the capital of France", memory_type=MemoryType.SEMANTIC))
    rag = RAGRetriever(engine.store, engine.embeddings)
    result = rag.retrieve(RAGRetrievalRequest(query="capital France", min_similarity=0.0))
    assert result.semantic_memories
    assert "Paris" in result.combined_context

    tenant_store = MultiTenantMemoryStore(tmp_path / "tenant.sqlite3")
    assert tenant_store.create_tenant("tenant-a") is True
    assert tenant_store.create_tenant("tenant-a") is False
    tenant_store.store("tenant-a", "tenant isolated memory", "semantic", user_id="u1")
    assert tenant_store.get_tenant_stats("tenant-a")["total_records"] == 1
    assert tenant_store.retrieve("tenant-b") == []
    assert tenant_store.delete_tenant("tenant-a") is True


def test_tool_helpers_and_risk_gate_paths(tmp_path: Path) -> None:
    sandbox = SandboxManager(tmp_path, allow_subprocess_fallback=True)
    assert write_file({"path": "note.txt", "content": "hello"}, sandbox).status == "success"
    assert read_file({"path": "note.txt"}, sandbox).result["content"] == "hello"
    assert list_directory({"path": "."}, sandbox).status == "success"
    assert read_file({"path": "..\\secret.txt"}, sandbox).status == "blocked"
    assert run_system_command_review({"command": "dir"}, sandbox).status == "blocked"
    assert run_python({"code": "print('ok')"}, sandbox).status == "success"
    assert run_python({"code": "import os"}, sandbox).status == "blocked"
    assert api_get({"url": "https://example.com"}, sandbox).status == "blocked"
    assert fetch_url({"url": "http://127.0.0.1"}, sandbox).status == "blocked"
    assert web_search({"query": ""}, sandbox).status == "failed"

    registry = create_default_registry()
    gate = ToolRiskGate()
    command_def = registry.require("run_system_command")
    decision = gate.evaluate(
        command_def,
        ToolRequest(tool_name="run_system_command", arguments={"command": "rm -rf /"}),
    )
    assert decision.blocked is True
    code_def = registry.require("run_python")
    risky_code = gate.evaluate(
        code_def,
        ToolRequest(tool_name="run_python", arguments={"code": "eval('1+1')"}),
    )
    assert risky_code.blocked is True


@pytest.mark.anyio
async def test_scheduler_and_lifecycle_edges(tmp_path: Path) -> None:
    event_log = EventLog(tmp_path / "events.sqlite3")
    scheduler = Scheduler(
        event_log,
        RuntimeBudgets(max_runtime_seconds=0.2, max_tool_calls=1, max_concurrent_tasks=1),
    )
    assert await scheduler.run(
        task_name="ok",
        module="test",
        session_id="s1",
        task_factory=lambda: asyncio.sleep(0, result="done"),
    ) == "done"
    await scheduler.record_tool_call("s1")
    with pytest.raises(SchedulerRejected):
        await scheduler.record_tool_call("s1")
    with pytest.raises(asyncio.TimeoutError):
        await scheduler.run(
            task_name="timeout",
            module="test",
            session_id="s1",
            task_factory=lambda: asyncio.sleep(1),
            timeout_seconds=0.01,
        )

    lifecycle = LifecycleManager(event_log)
    state = CognitiveState(user_input="hello")
    await lifecycle.start(state)
    await lifecycle.verify(state)
    await lifecycle.complete(state)
    assert state.lifecycle_state == LifecycleState.COMPLETED.value
    assert state.session_id not in lifecycle.active_sessions()

    failed = CognitiveState(user_input="bad")
    await lifecycle.start(failed)
    await lifecycle.fail(failed, "boom")
    assert failed.errors == ["boom"]
