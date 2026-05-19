"""FastAPI entrypoint for the NAIA cognitive runtime kernel."""

import json
import os
from typing import Any

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request, Security, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from agents.agent_core import AgentState
from governance.approval_queue import ApprovalQueue
from governance.decision_log import DecisionLog
from memory.memory_policy import MemoryType, MemoryWriteCandidate
from runtime.events import EventType
from runtime.kernel import CognitiveRuntimeKernel, KernelResponse
from tools.permissions import PermissionContext, PermissionLevel, ToolPermission
from tools.registry import ToolRequest, ToolResult


# ---- API key authentication -----------------------------------------------
#
# Configure with the NAIA_API_KEYS environment variable. Format is a
# comma-separated list of ``KEY:LEVEL`` pairs, e.g.
#   NAIA_API_KEYS="reader_abc:READ_ONLY,writer_xyz:LIMITED_WRITE,ops:ADMIN"
# Without any keys configured the server runs in development mode and
# treats every request as ``LIMITED_WRITE`` -- DO NOT do this in production.

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

API_KEY_PERMISSIONS: dict[str, PermissionLevel] = {}
if os.getenv("NAIA_API_KEYS"):
    for mapping in os.getenv("NAIA_API_KEYS").split(","):
        if ":" in mapping:
            key, level = mapping.split(":", 1)
            API_KEY_PERMISSIONS[key.strip()] = PermissionLevel(level.strip())
        else:
            # Legacy format: key only, default to LIMITED_WRITE.
            API_KEY_PERMISSIONS[mapping.strip()] = PermissionLevel.LIMITED_WRITE


limiter = Limiter(key_func=get_remote_address)


async def verify_api_key(
    api_key: str = Security(api_key_header),
) -> tuple[str, PermissionLevel]:
    """Verify the API key in the request header and return its level."""
    if not API_KEY_PERMISSIONS:
        # Development mode: no keys configured, allow with LIMITED_WRITE.
        return "dev", PermissionLevel.LIMITED_WRITE
    if api_key not in API_KEY_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key, API_KEY_PERMISSIONS[api_key]


# ---- App + middleware -----------------------------------------------------

app = FastAPI(
    title="NAIA Cognitive Runtime Kernel",
    version="0.2.0",
    description="Small, observable runtime kernel for governed cognition.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten for production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

kernel = CognitiveRuntimeKernel()
decision_log = DecisionLog()
approval_queue = ApprovalQueue()

# Wire governance into the pipeline so HIGH/CRITICAL paths go through
# our shared decision_log + approval_queue rather than the pipeline's
# defaults.
kernel.pipeline.decision_log = decision_log
kernel.pipeline.approval_queue = approval_queue


# ---- Request / response models --------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    response: str
    confidence: float

    @classmethod
    def from_kernel_response(cls, response: KernelResponse) -> "ChatResponse":
        return cls(
            session_id=response.session_id,
            response=response.response,
            confidence=response.confidence,
        )


class MemoryWriteRequest(BaseModel):
    memory_type: MemoryType
    content: str = Field(min_length=1)
    context: str = ""
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = "api"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryForgetRequest(BaseModel):
    reason: str = Field(min_length=1)


class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    # ``max_permission_level`` is deprecated -- permission level is now
    # derived from the authenticated API key.


class AgentCreateRequest(BaseModel):
    goal: str = Field(min_length=1)
    run_immediately: bool = True
    max_steps: int = Field(default=6, ge=1, le=25)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunRequest(BaseModel):
    max_steps: int = Field(default=6, ge=1, le=25)


class ApprovalActionRequest(BaseModel):
    reviewed_by: str = Field(min_length=1)
    review_notes: str = ""


# ---- Health and chat -------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "naia-cognitive-runtime-kernel",
        "kernel": "ready",
        "scheduler": kernel.scheduler.snapshot(),
        "memory": kernel.pipeline.memory_engine.status(),
        "tools": {
            "registered": len(kernel.pipeline.tool_executor.registry.list_tools())
        },
        "agents": kernel.pipeline.agent_runtime.status(),
    }


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(
    request: Request,
    payload: ChatRequest = Body(...),
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> ChatResponse:
    response = await kernel.process_user_input(
        payload.message,
        source="http",
        metadata=payload.metadata,
    )
    return ChatResponse.from_kernel_response(response)


@app.post("/chat/stream")
@limiter.limit("10/minute")
async def chat_stream(
    request: Request,
    payload: ChatRequest = Body(...),
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> StreamingResponse:
    async def stream():
        yield json.dumps({"event": "started"}) + "\n"
        response = await kernel.process_user_input(
            payload.message,
            source="http_stream",
            metadata=payload.metadata,
        )
        yield json.dumps(
            {
                "event": "completed",
                "response": ChatResponse.from_kernel_response(response).model_dump(
                    mode="json"
                ),
            }
        ) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = ChatRequest.model_validate(await websocket.receive_json())
            await websocket.send_json({"event": "started"})
            response = await kernel.process_user_input(
                payload.message,
                source="websocket",
                metadata=payload.metadata,
            )
            await websocket.send_json(
                {
                    "event": "completed",
                    "response": ChatResponse.from_kernel_response(
                        response
                    ).model_dump(mode="json"),
                }
            )
    except WebSocketDisconnect:
        return


# ---- Telemetry / events ----------------------------------------------------


@app.get("/telemetry")
@limiter.limit("30/minute")
async def telemetry(
    request: Request,
    limit: int = 100,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    bounded_limit = max(1, min(limit, 1000))
    return await kernel.telemetry_snapshot(limit=bounded_limit)


@app.get("/events")
@limiter.limit("30/minute")
async def events_list(
    request: Request,
    limit: int = 100,
    session_id: str | None = None,
    event_type: str | None = None,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    bounded_limit = max(1, min(limit, 1000))
    events = await kernel.event_log.list_events(
        limit=bounded_limit, session_id=session_id, event_type=event_type
    )
    return {
        "count": len(events),
        "events": [event.model_dump(mode="json") for event in events],
        "statistics": kernel.event_log.get_statistics(),
    }


@app.get("/events/statistics")
@limiter.limit("30/minute")
async def events_statistics(
    request: Request,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    return kernel.event_log.get_statistics()


# ---- Memory ---------------------------------------------------------------


@app.get("/memory/status")
@limiter.limit("30/minute")
async def memory_status(
    request: Request,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    return kernel.pipeline.memory_engine.status()


@app.get("/memory/search")
@limiter.limit("30/minute")
async def memory_search(
    request: Request,
    query: str,
    limit: int = 5,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    bounded_limit = max(1, min(limit, 25))
    result = kernel.pipeline.memory_engine.retrieve(query, limit=bounded_limit)
    return {
        "query": query,
        "injected_context": result.injected_context,
        "memories": [
            {
                "memory_id": item.record.memory_id,
                "memory_type": item.record.memory_type.value,
                "content": item.record.content,
                "confidence": item.record.confidence,
                "importance": item.record.importance,
                "status": item.record.status.value,
                "topic": item.record.topic,
                "score": item.score,
            }
            for item in result.memories
        ],
    }


@app.post("/memory")
@limiter.limit("20/minute")
async def memory_write(
    request: MemoryWriteRequest,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    result = kernel.pipeline.memory_engine.write(
        MemoryWriteCandidate(
            memory_type=request.memory_type,
            content=request.content,
            context=request.context,
            confidence=request.confidence,
            importance=request.importance,
            source=request.source,
            metadata=request.metadata,
        )
    )
    return result.model_dump(mode="json")


@app.post("/memory/decay")
@limiter.limit("5/minute")
async def memory_decay(
    request: Request,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    result = kernel.pipeline.memory_engine.decay()
    return result.model_dump(mode="json")


@app.delete("/memory/{memory_id}")
@limiter.limit("20/minute")
async def memory_forget(
    request: Request,
    memory_id: str,
    payload: MemoryForgetRequest = Body(...),
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    result = kernel.pipeline.memory_engine.forget(memory_id, reason=payload.reason)
    return result.model_dump(mode="json")


# ---- Tools ----------------------------------------------------------------


@app.get("/tools")
@limiter.limit("30/minute")
async def tools_list(
    request: Request,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    return {
        "tools": [
            definition.model_dump(mode="json")
            for definition in kernel.pipeline.tool_executor.registry.list_tools()
        ]
    }


@app.post("/tools/execute", response_model=ToolResult)
@limiter.limit("20/minute")
async def tools_execute(
    request: Request,
    payload: ToolExecuteRequest = Body(...),
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> ToolResult:
    api_key, permission_level = auth
    tool_request = ToolRequest(
        tool_name=payload.tool_name,
        arguments=payload.arguments,
        confirmed=payload.confirmed,
        user_intent="direct api tool execution",
    )
    context = PermissionContext(
        max_level=permission_level,
        allowed_permissions=_allowed_permissions_for_level(permission_level),
        confirmed=payload.confirmed,
        reason="direct api request",
    )
    result = kernel.pipeline.tool_executor.execute(tool_request, context)
    await kernel.event_log.emit(
        EventType.TOOL_EXECUTED,
        module="tools.executor",
        session_id=None,
        latency_ms=result.execution_time * 1000,
        details={
            "source": "api",
            "tool_name": result.tool_name,
            "status": result.status.value,
            "result": result.result,
            "logs": result.logs,
            "risk_notes": result.risk_notes,
            "metadata": result.metadata,
        },
    )
    # Return HTTP 403 for blocked/refused tool executions per constitutional
    # invariant 12 (least privilege) and 11 (external effects must be
    # visible and intentional).
    if result.status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Tool execution blocked by risk gate",
                "tool_name": result.tool_name,
                "risk_notes": result.risk_notes,
                "logs": result.logs,
            },
        )
    return result


def _allowed_permissions_for_level(level: PermissionLevel) -> set[ToolPermission]:
    """Derive the tool-permission set granted to a given API key level."""
    permissions = {ToolPermission.FILE_READ, ToolPermission.WEB_ACCESS}
    if level in {
        PermissionLevel.LIMITED_WRITE,
        PermissionLevel.FULL_WRITE,
        PermissionLevel.ADMIN,
    }:
        permissions.update(
            {
                ToolPermission.API_ACCESS,
                ToolPermission.CODE_EXECUTION,
                ToolPermission.FILE_WRITE,
            }
        )
    if level in {PermissionLevel.FULL_WRITE, PermissionLevel.ADMIN}:
        permissions.add(ToolPermission.SYSTEM_EXECUTION)
    return permissions


# ---- Agents ---------------------------------------------------------------


@app.get("/agents")
@limiter.limit("30/minute")
async def agents_list(
    request: Request,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    return kernel.pipeline.agent_runtime.status()


@app.post("/agents")
@limiter.limit("10/minute")
async def agents_create(
    request: Request,
    payload: AgentCreateRequest = Body(...),
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    agent = kernel.pipeline.agent_runtime.create_agent(
        payload.goal,
        metadata={"source": "api", **payload.metadata},
        auto_plan=True,
    )
    await kernel.event_log.emit(
        EventType.AGENT_CREATED,
        module="agents.agent_runtime",
        details=kernel.pipeline.agent_runtime.summarize_agent(agent),
    )
    if payload.run_immediately:
        agent = kernel.pipeline.agent_runtime.run_agent(
            agent.agent_id,
            max_steps=payload.max_steps,
        )
        event = (
            EventType.AGENT_COMPLETED
            if agent.state == AgentState.COMPLETED
            else EventType.AGENT_FAILED
            if agent.state == AgentState.FAILED
            else EventType.AGENT_TASK_COMPLETED
        )
        await kernel.event_log.emit(
            event,
            module="agents.agent_runtime",
            details=kernel.pipeline.agent_runtime.summarize_agent(agent),
        )
    return kernel.pipeline.agent_runtime.summarize_agent(agent)


@app.get("/agents/{agent_id}")
@limiter.limit("30/minute")
async def agents_get(
    request: Request,
    agent_id: str,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    agent = kernel.pipeline.agent_runtime.registry.require(agent_id)
    return kernel.pipeline.agent_runtime.summarize_agent(agent)


@app.post("/agents/{agent_id}/step")
@limiter.limit("20/minute")
async def agents_step(
    request: Request,
    agent_id: str,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    agent = kernel.pipeline.agent_runtime.step_agent(agent_id)
    await kernel.event_log.emit(
        EventType.AGENT_TASK_COMPLETED,
        module="agents.agent_runtime",
        details=kernel.pipeline.agent_runtime.summarize_agent(agent),
    )
    return kernel.pipeline.agent_runtime.summarize_agent(agent)


@app.post("/agents/{agent_id}/run")
@limiter.limit("10/minute")
async def agents_run(
    request: Request,
    agent_id: str,
    payload: AgentRunRequest = Body(...),
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    agent = kernel.pipeline.agent_runtime.run_agent(
        agent_id,
        max_steps=payload.max_steps,
    )
    event = (
        EventType.AGENT_COMPLETED
        if agent.state == AgentState.COMPLETED
        else EventType.AGENT_FAILED
        if agent.state == AgentState.FAILED
        else EventType.AGENT_TASK_COMPLETED
    )
    await kernel.event_log.emit(
        event,
        module="agents.agent_runtime",
        details=kernel.pipeline.agent_runtime.summarize_agent(agent),
    )
    return kernel.pipeline.agent_runtime.summarize_agent(agent)


@app.post("/agents/{agent_id}/pause")
@limiter.limit("20/minute")
async def agents_pause(
    request: Request,
    agent_id: str,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    agent = kernel.pipeline.agent_runtime.pause_agent(agent_id)
    return kernel.pipeline.agent_runtime.summarize_agent(agent)


@app.post("/agents/{agent_id}/resume")
@limiter.limit("20/minute")
async def agents_resume(
    request: Request,
    agent_id: str,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    agent = kernel.pipeline.agent_runtime.resume_agent(agent_id)
    return kernel.pipeline.agent_runtime.summarize_agent(agent)


@app.post("/agents/{agent_id}/recover")
@limiter.limit("10/minute")
async def agents_recover(
    request: Request,
    agent_id: str,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    agent = kernel.pipeline.agent_runtime.recover_agent(agent_id)
    await kernel.event_log.emit(
        EventType.AGENT_RECOVERED,
        module="agents.agent_runtime",
        details=kernel.pipeline.agent_runtime.summarize_agent(agent),
    )
    return kernel.pipeline.agent_runtime.summarize_agent(agent)


@app.delete("/agents/{agent_id}")
@limiter.limit("20/minute")
async def agents_destroy(
    request: Request,
    agent_id: str,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    return {"destroyed": kernel.pipeline.agent_runtime.registry.destroy(agent_id)}


# ---- Governance -----------------------------------------------------------


@app.get("/governance/decisions")
@limiter.limit("30/minute")
async def governance_decisions(
    request: Request,
    limit: int = 100,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    bounded_limit = max(1, min(limit, 1000))
    decisions = decision_log.list_recent(limit=bounded_limit)
    return {
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
        "statistics": decision_log.get_statistics(),
    }


@app.get("/governance/decisions/{decision_id}")
@limiter.limit("30/minute")
async def governance_decision_get(
    request: Request,
    decision_id: str,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    decision = decision_log.get_by_id(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return decision.model_dump(mode="json")


@app.get("/governance/decisions/session/{session_id}")
@limiter.limit("30/minute")
async def governance_decisions_by_session(
    request: Request,
    session_id: str,
    limit: int = 100,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    bounded_limit = max(1, min(limit, 1000))
    decisions = decision_log.list_by_session(session_id, limit=bounded_limit)
    return {
        "session_id": session_id,
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
    }


@app.get("/governance/approvals")
@limiter.limit("30/minute")
async def governance_approvals(
    request: Request,
    limit: int = 100,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    bounded_limit = max(1, min(limit, 1000))
    approvals = approval_queue.list_pending(limit=bounded_limit)
    return {
        "approvals": [approval.model_dump(mode="json") for approval in approvals],
        "statistics": approval_queue.get_statistics(),
    }


@app.get("/governance/approvals/{request_id}")
@limiter.limit("30/minute")
async def governance_approval_get(
    request: Request,
    request_id: str,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    approval = approval_queue.get_by_id(request_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    return approval.model_dump(mode="json")


@app.get("/governance/approvals/session/{session_id}")
@limiter.limit("30/minute")
async def governance_approvals_by_session(
    request: Request,
    session_id: str,
    limit: int = 100,
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    bounded_limit = max(1, min(limit, 1000))
    approvals = approval_queue.list_by_session(session_id, limit=bounded_limit)
    return {
        "session_id": session_id,
        "approvals": [approval.model_dump(mode="json") for approval in approvals],
    }


@app.post("/governance/approvals/{request_id}/approve")
@limiter.limit("20/minute")
async def governance_approval_approve(
    request: Request,
    request_id: str,
    payload: ApprovalActionRequest = Body(...),
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    approval = approval_queue.approve(
        request_id, payload.reviewed_by, payload.review_notes
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="approval request not found or not pending")
    return approval.model_dump(mode="json")


@app.post("/governance/approvals/{request_id}/deny")
@limiter.limit("20/minute")
async def governance_approval_deny(
    request: Request,
    request_id: str,
    payload: ApprovalActionRequest = Body(...),
    auth: tuple[str, PermissionLevel] = Security(verify_api_key),
) -> dict[str, Any]:
    approval = approval_queue.deny(
        request_id, payload.reviewed_by, payload.review_notes
    )
    if approval is None:
        return {"error": "approval request not found or not pending"}
    return approval.model_dump(mode="json")


if __name__ == "__main__":
    uvicorn.run("api.server:app", host="127.0.0.1", port=8000, reload=True)




