import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from agents.agent_core import AgentState, AgentTaskStatus
from agents.agent_runtime import AgentRuntime
from agents.planner import AgentPlanner
from agents.registry import AgentRegistry
from api.server import app
from cognition.router.router import CognitiveRouter
from memory.memory_engine import MemoryEngine
from memory.memory_policy import MemoryStatus, MemoryType, MemoryWriteCandidate
from runtime.kernel import CognitiveRuntimeKernel
from synthesis.contradiction_resolver import ContradictionResolver
from synthesis.final_renderer import FinalRenderer, SynthesisContext
from synthesis.response_merger import ResponseMerger, SourceOutput, SourceType
from tools.executor import ToolExecutor
from tools.permissions import PermissionContext, PermissionLevel, ToolPermission
from tools.registry import ToolRequest, ToolStatus, create_default_registry
from tools.sandbox import SandboxManager


class RuntimeKernelTests(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_processes_low_risk_request(self):
        kernel = CognitiveRuntimeKernel()

        response = await kernel.process_user_input("Please design a small test plan.")

        self.assertEqual(response.state, "COMPLETED")
        self.assertEqual(response.intent, "planning")
        self.assertEqual(response.risk_level, "NONE")
        self.assertEqual(response.cognitive_mode, "ANALYTICAL")
        self.assertIn("input_stage", response.active_modules)
        self.assertIn("cognitive_routing_stage", response.active_modules)
        self.assertIn("telemetry_logging_stage", response.active_modules)
        self.assertIn("routing", response.telemetry)
        self.assertIn("synthesis", response.telemetry)
        self.assertGreaterEqual(response.synthesis["coherence_score"], 0.75)
        self.assertNotIn("pipeline", response.response.lower())

    async def test_risk_precheck_reduces_autonomy(self):
        kernel = CognitiveRuntimeKernel()

        response = await kernel.process_user_input("Delete every file in the project.")

        self.assertEqual(response.state, "COMPLETED")
        self.assertEqual(response.risk_level, "HIGH")
        self.assertEqual(response.cognitive_mode, "HIGH_RISK")
        self.assertEqual(response.verification_level, "STRICT")
        self.assertTrue(response.route_plan["risk"]["restricted_tools"])
        self.assertIn("explicit human approval", response.response)
        self.assertNotIn("cognitive router", response.response.lower())

    async def test_critical_risk_requires_approval(self):
        kernel = CognitiveRuntimeKernel()

        response = await kernel.process_user_input("Wipe everything and drop production.")

        self.assertEqual(response.state, "COMPLETED")
        self.assertEqual(response.risk_level, "CRITICAL")
        self.assertEqual(response.cognitive_mode, "HIGH_RISK")
        self.assertIn("explicit human approval", response.response)

    async def test_route_selected_event_is_recorded(self):
        kernel = CognitiveRuntimeKernel()

        response = await kernel.process_user_input("hi")
        telemetry = await kernel.telemetry_snapshot(limit=20)
        event_names = [
            event["event"] for event in telemetry["events"]["events"]
        ]

        self.assertEqual(response.cognitive_mode, "REFLEX")
        self.assertIn("ROUTE_SELECTED", event_names)
        self.assertIn("FINAL_RESPONSE_RENDERED", event_names)

    async def test_memory_integrates_across_sessions(self):
        with TemporaryDirectory() as temp_dir:
            memory_engine = MemoryEngine(
                db_path=Path(temp_dir) / "memory.sqlite3"
            )
            kernel = CognitiveRuntimeKernel(memory_engine=memory_engine)

            await kernel.process_user_input("I prefer TypeScript.")
            response = await kernel.process_user_input(
                "What do you remember about my TypeScript preference?"
            )

            self.assertIn("TypeScript", response.response)
            self.assertGreaterEqual(len(response.telemetry["memory"]["retrieved"]), 1)
            self.assertIn("memory_retrieval_stage", response.active_modules)

    async def test_kernel_executes_explicit_python_tool_request(self):
        with TemporaryDirectory() as temp_dir:
            executor = ToolExecutor(
                sandbox=SandboxManager(workspace_root=temp_dir)
            )
            kernel = CognitiveRuntimeKernel(tool_executor=executor)

            response = await kernel.process_user_input("Run Python: print(2 + 2)")

            self.assertIn("4", response.response)
            self.assertEqual(response.telemetry["tools"]["result_count"], 1)
            self.assertEqual(
                response.telemetry["tools"]["results"][0]["status"],
                "success",
            )
            self.assertIn("tool_execution_stage", response.active_modules)

    async def test_kernel_creates_agent_for_explicit_goal_request(self):
        with TemporaryDirectory() as temp_dir:
            memory_engine = MemoryEngine(db_path=Path(temp_dir) / "memory.sqlite3")
            executor = ToolExecutor(
                sandbox=SandboxManager(workspace_root=temp_dir)
            )
            agent_runtime = AgentRuntime(
                memory_engine=memory_engine,
                tool_executor=executor,
                registry=AgentRegistry(Path(temp_dir) / "agents.state.json"),
            )
            kernel = CognitiveRuntimeKernel(
                memory_engine=memory_engine,
                tool_executor=executor,
                agent_runtime=agent_runtime,
            )

            response = await kernel.process_user_input(
                "Create agent to calculate 2 + 3"
            )

            self.assertIn("5", response.response)
            self.assertEqual(response.telemetry["agents"]["result_count"], 1)
            self.assertEqual(
                response.telemetry["agents"]["results"][0]["state"],
                "COMPLETED",
            )
            self.assertIn("agent_execution_stage", response.active_modules)


class CognitiveRouterTests(unittest.TestCase):
    def test_router_uses_reflex_for_tiny_chat(self):
        router = CognitiveRouter()

        plan = router.route("hi")

        self.assertEqual(plan.mode.value, "REFLEX")
        self.assertEqual(plan.reasoning_depth, 1)
        self.assertFalse(plan.tool_access)
        self.assertFalse(plan.memory_enabled)

    def test_router_expands_for_system_architecture(self):
        router = CognitiveRouter()

        plan = router.route("Design a distributed autonomous AI operating system.")

        self.assertEqual(plan.mode.value, "ANALYTICAL")
        self.assertIn(plan.complexity.complexity.value, {"HIGH", "EXTREME"})
        self.assertGreaterEqual(plan.reasoning_depth, 4)
        self.assertTrue(plan.reflection_enabled)


class SynthesisTests(unittest.TestCase):
    def test_merger_prioritizes_verified_tool_output(self):
        merger = ResponseMerger()

        merged = merger.merge(
            [
                SourceOutput(
                    source=SourceType.REASONING,
                    claims=["The answer is probably B."],
                    confidence=0.62,
                ),
                SourceOutput(
                    source=SourceType.TOOL,
                    claims=["The answer is A."],
                    confidence=0.9,
                    verified=True,
                ),
            ]
        )

        self.assertEqual(merged.claims[0].text, "The answer is A.")

    def test_contradiction_resolver_uses_stronger_evidence(self):
        merger = ResponseMerger()
        resolver = ContradictionResolver()
        merged = merger.merge(
            [
                SourceOutput(
                    source=SourceType.TOOL,
                    claims=["Action allowed."],
                    confidence=0.9,
                    verified=True,
                ),
                SourceOutput(
                    source=SourceType.REASONING,
                    claims=["Action not allowed."],
                    confidence=0.65,
                ),
            ]
        )

        resolved = resolver.resolve(merged)

        self.assertEqual(resolved.claims[0].text, "Action allowed.")
        self.assertEqual(len(resolved.conflicts), 1)

    def test_final_renderer_removes_internal_implementation_terms(self):
        renderer = FinalRenderer()

        result = renderer.render(
            [
                SourceOutput(
                    source=SourceType.REASONING,
                    claims=["The runtime kernel pipeline module accepted it."],
                    confidence=0.9,
                )
            ],
            SynthesisContext(
                session_id="test",
                user_input="help",
                task_type="conversation",
                cognitive_mode="CONVERSATIONAL",
                complexity_level="LOW",
                risk_level="NONE",
                confidence=0.8,
            ),
        )

        lowered = result.response.lower()
        self.assertNotIn("kernel", lowered)
        self.assertNotIn("pipeline", lowered)
        self.assertNotIn("module", lowered)
        self.assertTrue(result.response)


class MemoryEngineTests(unittest.TestCase):
    def test_semantic_memory_can_be_stored_and_retrieved(self):
        with TemporaryDirectory() as temp_dir:
            engine = MemoryEngine(db_path=Path(temp_dir) / "memory.sqlite3")

            write = engine.write(
                MemoryWriteCandidate(
                    memory_type=MemoryType.SEMANTIC,
                    content="User prefers TypeScript",
                    confidence=0.9,
                    importance=0.8,
                    source="test",
                )
            )
            retrieved = engine.retrieve("TypeScript preference", limit=3)

            self.assertTrue(write.stored)
            self.assertEqual(write.status, "active")
            self.assertTrue(retrieved.memories)
            self.assertIn("TypeScript", retrieved.memories[0].record.content)

    def test_sensitive_memory_is_quarantined(self):
        with TemporaryDirectory() as temp_dir:
            engine = MemoryEngine(db_path=Path(temp_dir) / "memory.sqlite3")

            write = engine.write(
                MemoryWriteCandidate(
                    memory_type=MemoryType.SEMANTIC,
                    content="User password is swordfish",
                    confidence=0.9,
                    importance=0.8,
                    source="test",
                )
            )

            self.assertTrue(write.stored)
            self.assertEqual(write.status, "quarantined")
            self.assertEqual(write.policy_action, "require_approval")

    def test_conflicting_memory_is_quarantined(self):
        with TemporaryDirectory() as temp_dir:
            engine = MemoryEngine(db_path=Path(temp_dir) / "memory.sqlite3")

            first = engine.write(
                MemoryWriteCandidate(
                    memory_type=MemoryType.SEMANTIC,
                    content="User prefers TypeScript",
                    confidence=0.9,
                    importance=0.8,
                    source="test",
                )
            )
            second = engine.write(
                MemoryWriteCandidate(
                    memory_type=MemoryType.SEMANTIC,
                    content="User not prefers TypeScript",
                    confidence=0.8,
                    importance=0.8,
                    source="test",
                )
            )

            self.assertTrue(first.stored)
            self.assertTrue(second.stored)
            self.assertEqual(second.status, "quarantined")

    def test_memory_decay_expires_old_low_confidence_memory(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "memory.sqlite3"
            engine = MemoryEngine(db_path=db_path)
            write = engine.write(
                MemoryWriteCandidate(
                    memory_type=MemoryType.EPISODIC,
                    content="Low confidence event",
                    confidence=0.4,
                    importance=0.2,
                    source="test",
                )
            )
            self.assertTrue(write.stored)

            old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            with engine.store._connect() as connection:
                connection.execute(
                    "UPDATE memories SET updated_at = ? WHERE memory_id = ?",
                    (old_time, write.record.memory_id),
                )

            decay = engine.decay()
            records = engine.store.list_records(limit=10)

            self.assertEqual(decay.expired, 1)
            self.assertEqual(records[0].status, MemoryStatus.EXPIRED)

    def test_forget_soft_deletes_memory(self):
        with TemporaryDirectory() as temp_dir:
            engine = MemoryEngine(db_path=Path(temp_dir) / "memory.sqlite3")
            write = engine.write(
                MemoryWriteCandidate(
                    memory_type=MemoryType.SEMANTIC,
                    content="User prefers Python",
                    confidence=0.9,
                    importance=0.8,
                    source="test",
                )
            )

            forget = engine.forget(write.record.memory_id, reason="user correction")
            retrieved = engine.retrieve("Python preference")

            self.assertTrue(forget.forgotten)
            self.assertEqual(forget.status, "expired")
            self.assertFalse(retrieved.memories)


class AgentRuntimeTests(unittest.TestCase):
    def test_planner_creates_task_graph_with_dependencies(self):
        graph = AgentPlanner().plan("Build a small SaaS app")

        self.assertGreaterEqual(len(graph.tasks), 3)
        self.assertTrue(graph.validate_graph().valid)
        self.assertEqual(graph.tasks[0].title, "Clarify objective")

    def test_agent_runtime_runs_calculation_goal(self):
        runtime = self._runtime()

        agent = runtime.create_agent("calculate 7 + 8", auto_plan=True)
        agent = runtime.run_agent(agent.agent_id, max_steps=6)

        self.assertEqual(agent.state, AgentState.COMPLETED)
        self.assertEqual(agent.progress, 1.0)
        self.assertTrue(any(task.result == "15" for task in agent.tasks))

    def test_agent_pause_resume_and_recover(self):
        runtime = self._runtime()
        agent = runtime.create_agent("calculate 2 + 2", auto_plan=True)

        paused = runtime.pause_agent(agent.agent_id)
        self.assertEqual(paused.state, AgentState.PAUSED)
        resumed = runtime.resume_agent(agent.agent_id)
        self.assertEqual(resumed.state, AgentState.EXECUTING)

        tool_task = next(task for task in resumed.tasks if task.tool_request)
        tool_task.status = AgentTaskStatus.FAILED
        tool_task.error = "temporary failure"
        tool_task.attempts = 0
        resumed.transition(AgentState.FAILED, note="test failure")
        runtime.registry.update(resumed)

        recovered = runtime.recover_agent(resumed.agent_id)

        self.assertEqual(recovered.state, AgentState.EXECUTING)
        reset_task = recovered.task_by_id(tool_task.task_id)
        self.assertEqual(reset_task.status, AgentTaskStatus.PENDING)

    def test_coordinator_creates_child_agents(self):
        runtime = self._runtime()
        parent = runtime.create_agent("Plan project", auto_plan=False)

        children = runtime.coordinator.create_child_agents(
            parent,
            ["Research options", "Draft implementation plan"],
        )
        report = runtime.coordinator.coordinate()

        self.assertEqual(len(children), 2)
        self.assertEqual(report.active_agents, 3)

    def _runtime(self) -> AgentRuntime:
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        memory_engine = MemoryEngine(db_path=root / "memory.sqlite3")
        executor = ToolExecutor(sandbox=SandboxManager(workspace_root=root))
        return AgentRuntime(
            memory_engine=memory_engine,
            tool_executor=executor,
            registry=AgentRegistry(root / "agents.state.json"),
        )


class ToolExecutionTests(unittest.TestCase):
    def test_registry_exposes_only_registered_tools(self):
        registry = create_default_registry()
        names = {definition.name for definition in registry.list_tools()}

        self.assertIn("run_python", names)
        self.assertIn("read_file", names)
        self.assertIn("web_search", names)
        self.assertIn("run_system_command", names)

    def test_python_code_runs_in_sandbox(self):
        with TemporaryDirectory() as temp_dir:
            executor = ToolExecutor(sandbox=SandboxManager(workspace_root=temp_dir))
            result = executor.execute(
                ToolRequest(
                    tool_name="run_python",
                    arguments={"code": "print(6 * 7)"},
                ),
                self._limited_context(),
            )

            self.assertEqual(result.status, ToolStatus.SUCCESS)
            self.assertEqual(result.result["stdout"].strip(), "42")

    def test_python_code_blocks_forbidden_import(self):
        with TemporaryDirectory() as temp_dir:
            executor = ToolExecutor(sandbox=SandboxManager(workspace_root=temp_dir))
            result = executor.execute(
                ToolRequest(
                    tool_name="run_python",
                    arguments={"code": "import os\nprint(os.getcwd())"},
                ),
                self._limited_context(),
            )

            self.assertEqual(result.status, ToolStatus.BLOCKED)
            self.assertIn("forbidden import", result.logs[0])

    def test_permission_denies_write_in_read_only_context(self):
        with TemporaryDirectory() as temp_dir:
            executor = ToolExecutor(sandbox=SandboxManager(workspace_root=temp_dir))
            result = executor.execute(
                ToolRequest(
                    tool_name="write_file",
                    arguments={"path": "note.txt", "content": "hello"},
                ),
                PermissionContext(
                    max_level=PermissionLevel.READ_ONLY,
                    allowed_permissions={ToolPermission.FILE_READ},
                ),
            )

            self.assertEqual(result.status, ToolStatus.BLOCKED)
            self.assertIn("LIMITED_WRITE", result.logs[0])

    def test_system_sandbox_blocks_path_traversal(self):
        with TemporaryDirectory() as temp_dir:
            executor = ToolExecutor(sandbox=SandboxManager(workspace_root=temp_dir))
            result = executor.execute(
                ToolRequest(
                    tool_name="read_file",
                    arguments={"path": "../outside.txt"},
                ),
                PermissionContext(
                    max_level=PermissionLevel.READ_ONLY,
                    allowed_permissions={ToolPermission.FILE_READ},
                ),
            )

            self.assertEqual(result.status, ToolStatus.BLOCKED)
            self.assertIn("path traversal", " ".join(result.risk_notes))

    def test_risk_gate_blocks_admin_system_command(self):
        with TemporaryDirectory() as temp_dir:
            executor = ToolExecutor(sandbox=SandboxManager(workspace_root=temp_dir))
            result = executor.execute(
                ToolRequest(
                    tool_name="run_system_command",
                    arguments={"command": "dir"},
                    confirmed=True,
                ),
                PermissionContext(
                    max_level=PermissionLevel.ADMIN,
                    allowed_permissions={ToolPermission.SYSTEM_EXECUTION},
                    confirmed=True,
                ),
            )

            self.assertEqual(result.status, ToolStatus.BLOCKED)
            self.assertIn("critical", " ".join(result.risk_notes).lower())

    def _limited_context(self) -> PermissionContext:
        return PermissionContext(
            max_level=PermissionLevel.LIMITED_WRITE,
            allowed_permissions={
                ToolPermission.CODE_EXECUTION,
                ToolPermission.FILE_READ,
                ToolPermission.FILE_WRITE,
                ToolPermission.WEB_ACCESS,
            },
        )


class ApiBoundaryTests(unittest.TestCase):
    def test_chat_endpoint_returns_clean_user_response(self):
        client = TestClient(app)

        response = client.post("/chat", json={"message": "hi"})
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(data.keys()), {"session_id", "response", "confidence"})
        self.assertNotIn("route_plan", data)
        self.assertNotIn("active_modules", data)
        self.assertNotIn("telemetry", data)
        self.assertEqual(data["response"], "Hi.")

    def test_memory_status_endpoint_is_available(self):
        client = TestClient(app)

        response = client.get("/memory/status")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("by_status", data)
        self.assertIn("by_type", data)

    def test_tools_endpoint_lists_registered_tools(self):
        client = TestClient(app)

        response = client.get("/tools")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(tool["name"] == "run_python" for tool in data["tools"]))

    def test_tools_execute_endpoint_uses_permissions(self):
        client = TestClient(app)

        before = client.get("/telemetry?limit=100").json()
        before_count = len(
            [
                event
                for event in before["events"]["events"]
                if event["event"] == "TOOL_EXECUTED"
            ]
        )
        response = client.post(
            "/tools/execute",
            json={
                "tool_name": "run_python",
                "arguments": {"code": "print(9)"},
                "max_permission_level": "LIMITED_WRITE",
            },
        )
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["stdout"].strip(), "9")
        after = client.get("/telemetry?limit=100").json()
        after_count = len(
            [
                event
                for event in after["events"]["events"]
                if event["event"] == "TOOL_EXECUTED"
            ]
        )
        self.assertEqual(after_count, before_count + 1)

    def test_agents_api_creates_and_runs_agent(self):
        client = TestClient(app)

        response = client.post(
            "/agents",
            json={"goal": "calculate 3 + 4", "run_immediately": True},
        )
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["state"], "COMPLETED")
        self.assertTrue(any(task["result"] == "7" for task in data["tasks"]))


if __name__ == "__main__":
    unittest.main()
