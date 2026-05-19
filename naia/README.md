# NAIA

NAIA is a governed AI runtime prototype with cognition routing, memory, tools, agents, synthesis, telemetry, and constitutional safety controls.

## Integration with Anai Translator

This package is bundled inside the Anai Translator project as `naia/`. The translator backend loads it via `backend/assistant.py`, which:

1. Prepends `naia/` to `sys.path` at import time
2. Instantiates a singleton `CognitiveRuntimeKernel`
3. Exposes `/api/assistant/chat` (HTTP) and `/ws/assistant` (WebSocket) endpoints
4. Gracefully returns HTTP 503 if the kernel cannot load

The assistant can receive translation context from the frontend/mobile so users can ask follow-up questions about their translations.

## Start here

- Constitution: `constitution/constitution.md`
- Runtime kernel: `runtime/kernel.py`
- Cognition router: `cognition/router/router.py`
- Tool governance: `tools/`
- Memory subsystem: `memory/`
- Response synthesis: `synthesis/`
- Operational security notes: `SECRETS.md`, `tools/SANDBOX_SECURITY.md`
- Postgres migration notes: `POSTGRES_MIGRATION.md`
- Training notes: `TRAINING_GUIDE.md`, `training/`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -r requirements.txt
```

Optional local-model dependencies:

```powershell
.\.venv\Scripts\pip install -r requirements-local.txt
```

## Run tests

```powershell
pytest
```

## Lint, type-check, and compile

```powershell
ruff check .
mypy .
python -m compileall .
```

## Module map

- `api/` - FastAPI entrypoint
- `agents/` - agent planning, registry, runtime, and execution bridge
- `cognition/` - task classification, complexity, risk, policies, and routing
- `core/` - shared model client and prompt-template loading
- `dataset/` - dataset generation/evaluation utilities
- `governance/` - approval queue, decision log, and governance hooks
- `memory/` - memory policy, validation, store, indexing, retrieval, consolidation, and RAG
- `runtime/` - event log, scheduler, lifecycle, state, pipeline, and kernel
- `synthesis/` - response merger, contradiction handling, final rendering, formatting, tone, and identity
- `telemetry/` - trace viewing and session replay
- `tools/` - tool registry, permission checks, risk gate, sandbox, and tool helpers
- `training/` - local/student model training utilities

## Generated artifacts

Generated datasets, local model outputs, runtime SQLite databases, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, and virtual environments are ignored by git.

If a generated artifact was accidentally tracked, untrack it without deleting the local file:

```powershell
git rm --cached path/to/generated-file
```
