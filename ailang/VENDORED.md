# Vendored: AILang runtime

This directory is a vendored copy of the **AILang** DSL runtime (lexer, parser,
transpiler, typechecker, runtime, stdlib). It is imported as `ailang` by
`ailang_integration/runtime/bridge.py`, which transpiles and executes the `.ai`
translation agents in `ailang_integration/agents/`.

## Why vendored
The upstream `ailang` package (v0.1.0) is not published to PyPI, so it cannot be
installed via `requirements*.txt`. Vendoring makes the repository self-contained
and lets the production Docker image run the AILang agents instead of silently
degrading to stub mode. The upstream `LICENSE` is preserved alongside the code.

## What the backend uses
Only these modules are imported by the bridge:

- `ailang.parser` (`parse_source`)
- `ailang.transpiler` (`Transpiler`)
- `ailang.runtime` (`Model`, `Agent`, `define_model`, `define_agent`, `register_tool`)
- `ailang.stdlib`

`api.py`, `cli.py`, and `repl.py` are AILang's own CLI/REPL/HTTP tooling and are
**not** used by the translator backend (they depend on `flask`/`flask-cors`).

## Activation
Agents call out to an LLM via `ailang_integration/runtime/bridge.py::_route_ai_call`,
which uses OpenAI when `OPENAI_API_KEY` is set, then falls back to the CIP brain,
then to structured stubs. Set `OPENAI_API_KEY` in the deployment environment to
activate the features.

## Maintenance
Do not edit files here directly. Update upstream AILang and re-vendor.
