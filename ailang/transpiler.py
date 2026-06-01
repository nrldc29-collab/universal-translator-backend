from __future__ import annotations

from .ast_nodes import (
    AgentDecl,
    AskExpr,
    AskStmt,
    Assignment,
    ASTNode,
    BinaryOp,
    BoolLiteral,
    BreakStmt,
    CallExpr,
    CompoundAssignment,
    ConstDecl,
    ContinueStmt,
    DictLiteral,
    Expr,
    ExprStmt,
    ForStmt,
    FString,
    FunctionDecl,
    Identifier,
    IfStmt,
    ImportDecl,
    IndexAccess,
    IndexAssignment,
    KwArg,
    ListLiteral,
    MemberAccess,
    ModelDecl,
    NoneLiteral,
    NumberLiteral,
    PrintStmt,
    Program,
    ReturnStmt,
    StringLiteral,
    TryStmt,
    UnaryOp,
    WhileStmt,
    PipeExpr,
    AwaitExpr,
    StreamExpr,
    SchemaDecl,
    AsyncFunctionDecl,
    OnReloadBlock,
)
from .parser import parse_source


class Transpiler:
    def __init__(self, source_path: str | None = None) -> None:
        self.lines: list[str] = []
        self.indent: int = 0
        self.imported_modules: list[str] = []
        self.source_path = source_path  # For resolving relative .ai imports

    def emit(self, line: str = "") -> None:
        self.lines.append("    " * self.indent + line)

    def transpile(self, program: Program) -> str:
        # Collect imports first
        for node in program.body:
            if isinstance(node, ImportDecl):
                self.imported_modules.append(node.module)

        # Runtime header
        self.emit("from ailang.stdlib import *")
        self.emit("from ailang.runtime import define_model, define_agent, ask_model, register_tool, call_tool")

        # Emit imports — Python stdlib as `import module`, .ai modules as inlined code
        for node in program.body:
            if isinstance(node, ImportDecl):
                self.visit_import_header(node)

        self.emit("")
        for node in program.body:
            if isinstance(node, ImportDecl):
                continue  # Already handled in header
            self.visit(node)
            self.emit("")
        if any(isinstance(node, FunctionDecl) and node.name == "main" for node in program.body):
            self.emit('if __name__ == "__main__":')
            self.indent += 1
            self.emit("main()")
            self.indent -= 1
        return "\n".join(self.lines).rstrip() + "\n"

    # --- Expression visitor ---

    def visit_expr(self, expr: Expr) -> str:
        if isinstance(expr, NumberLiteral):
            if isinstance(expr.value, int):
                return str(expr.value)
            return str(expr.value)

        if isinstance(expr, StringLiteral):
            return repr(expr.value)

        if isinstance(expr, BoolLiteral):
            return "True" if expr.value else "False"

        if isinstance(expr, NoneLiteral):
            return "None"

        if isinstance(expr, Identifier):
            return expr.name

        if isinstance(expr, FString):
            return self._emit_fstring(expr)

        if isinstance(expr, ListLiteral):
            elements = ", ".join(self.visit_expr(e) for e in expr.elements)
            return f"[{elements}]"

        if isinstance(expr, DictLiteral):
            pairs = ", ".join(
                f"{self.visit_expr(k)}: {self.visit_expr(v)}" for k, v in expr.pairs
            )
            return "{" + pairs + "}"

        if isinstance(expr, UnaryOp):
            operand = self.visit_expr(expr.operand)
            if expr.op == "not":
                return f"(not {operand})"
            return f"({expr.op}{operand})"

        if isinstance(expr, BinaryOp):
            left = self.visit_expr(expr.left)
            right = self.visit_expr(expr.right)
            return f"({left} {expr.op} {right})"

        if isinstance(expr, MemberAccess):
            obj = self.visit_expr(expr.object)
            return f"{obj}.{expr.member}"

        if isinstance(expr, IndexAccess):
            obj = self.visit_expr(expr.object)
            index = self.visit_expr(expr.index)
            return f"{obj}[{index}]"

        if isinstance(expr, CallExpr):
            callee = self.visit_expr(expr.callee)
            parts: list[str] = []
            for a in expr.args:
                if isinstance(a, KwArg):
                    parts.append(f"{a.name}={self.visit_expr(a.value)}")
                else:
                    parts.append(self.visit_expr(a))
            # Also handle kwargs from the CallExpr.kwargs field
            for name, value in expr.kwargs:
                parts.append(f"{name}={self.visit_expr(value)}")
            return f"{callee}({', '.join(parts)})"

        if isinstance(expr, KwArg):
            return f"{expr.name}={self.visit_expr(expr.value)}"

        if isinstance(expr, AskExpr):
            prompt = self.visit_expr(expr.prompt)
            if expr.schema:
                schema = self.visit_expr(expr.schema)
                return f"ask_model({expr.model}, {prompt}, schema={schema})"
            return f"ask_model({expr.model}, {prompt})"

        if isinstance(expr, PipeExpr):
            # a |> b transpiles to b(a)
            # a |> b(x) transpiles to b(a, x) — insert as first arg
            left = self.visit_expr(expr.left)
            if isinstance(expr.right, CallExpr):
                callee = self.visit_expr(expr.right.callee)
                args = [left] + [self.visit_expr(a) for a in expr.right.args]
                return f"{callee}({', '.join(args)})"
            else:
                right = self.visit_expr(expr.right)
                return f"{right}({left})"

        if isinstance(expr, AwaitExpr):
            inner = self.visit_expr(expr.expr)
            return f"(await {inner})"

        if isinstance(expr, StreamExpr):
            inner = self.visit_expr(expr.expr)
            return f"__ailang_stream__({inner})"

        raise TypeError(f"Unknown expression node: {expr!r}")

    def _emit_fstring(self, node: FString) -> str:
        """Generate a Python f-string from FString node."""
        parts: list[str] = []
        for part in node.parts:
            if isinstance(part, str):
                # Literal string part — escape braces for f-string
                escaped = part.replace("\\", "\\\\").replace("{", "{{").replace("}", "}}")
                parts.append(escaped)
            else:
                # Expression part
                parts.append("{" + self.visit_expr(part) + "}")
        # Use repr-style quoting: if the string contains double quotes, use single quotes
        content = "".join(parts)
        if '"' not in content:
            return 'f"' + content + '"'
        if "'" not in content:
            return "f'" + content + "'"
        # Both quote types — use double quotes and escape internal double quotes
        return 'f"' + content.replace('"', '\\"') + '"'

    # --- Statement visitors ---

    def visit(self, node: ASTNode) -> None:
        if isinstance(node, ModelDecl):
            self.visit_model(node)
        elif isinstance(node, AgentDecl):
            self.visit_agent(node)
        elif isinstance(node, FunctionDecl):
            self.visit_function(node)
        elif isinstance(node, ConstDecl):
            self.visit_const(node)
        elif isinstance(node, Assignment):
            self.emit(f"{node.name} = {self.visit_expr(node.expr)}")
        elif isinstance(node, IndexAssignment):
            self.emit(f"{self.visit_expr(node.obj)}[{self.visit_expr(node.index)}] = {self.visit_expr(node.expr)}")
        elif isinstance(node, CompoundAssignment):
            op_map = {"+": "+", "-": "-", "*": "*", "/": "/", "%": "%"}
            op = op_map.get(node.op, "+")
            self.emit(f"{node.name} {op}= {self.visit_expr(node.expr)}")
        elif isinstance(node, PrintStmt):
            # If the expr is a CallExpr on "print", emit it directly (multi-arg print)
            if isinstance(node.expr, CallExpr) and isinstance(node.expr.callee, Identifier) and node.expr.callee.name == "print":
                self.emit(self.visit_expr(node.expr))
            else:
                self.emit(f"print({self.visit_expr(node.expr)})")
        elif isinstance(node, ReturnStmt):
            self.emit(f"return {self.visit_expr(node.expr)}")
        elif isinstance(node, BreakStmt):
            self.emit("break")
        elif isinstance(node, ContinueStmt):
            self.emit("continue")
        elif isinstance(node, AskStmt):
            self.visit_ask(node)
        elif isinstance(node, IfStmt):
            self.visit_if(node)
        elif isinstance(node, ForStmt):
            self.visit_for(node)
        elif isinstance(node, WhileStmt):
            self.visit_while(node)
        elif isinstance(node, TryStmt):
            self.visit_try(node)
        elif isinstance(node, ImportDecl):
            self.visit_import(node)
        elif isinstance(node, ExprStmt):
            self.emit(self.visit_expr(node.expr))
        elif isinstance(node, SchemaDecl):
            self.visit_schema(node)
        elif isinstance(node, AsyncFunctionDecl):
            self.visit_async_function(node)
        elif isinstance(node, OnReloadBlock):
            self.visit_on_reload(node)
        else:
            raise TypeError(f"Unknown AST node: {node!r}")

    def visit_model(self, node: ModelDecl) -> None:
        self.emit(
            f"{node.name} = define_model({node.name!r}, provider={node.provider!r}, model_name={node.model_name!r})"
        )

    def visit_agent(self, node: AgentDecl) -> None:
        # Transpile agent body functions
        for stmt in node.body:
            self.visit(stmt)

        # Create body list with references to transpiled functions
        body_name = f"{node.name}_body" if node.body else "None"
        if node.body:
            self.emit(f"{body_name} = []")
            for stmt in node.body:
                if isinstance(stmt, FunctionDecl):
                    self.emit(f"{body_name}.append({stmt.name})")

        # Create the agent
        self.emit(
            f"{node.name} = define_agent({node.name!r}, model={node.model!r}, "
            f"instructions={node.instructions!r}, tools={node.tools!r}, body={body_name})"
        )

        # Register body functions as tools
        for stmt in node.body:
            if isinstance(stmt, FunctionDecl):
                self.emit(f"register_tool({node.name}, {stmt.name!r}, {stmt.name})")

    def _map_type(self, type_name: str | None) -> str | None:
        """Map AILang type names to Python type names."""
        if type_name is None:
            return None
        type_map = {
            "string": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "list": "list",
            "dict": "dict",
            "none": "None",
            "any": "Any",
        }
        return type_map.get(type_name, type_name)

    def visit_function(self, node: FunctionDecl) -> None:
        params_with_types = []
        for i, param in enumerate(node.params):
            if i < len(node.param_types) and node.param_types[i]:
                params_with_types.append(f"{param}: {self._map_type(node.param_types[i])}")
            else:
                params_with_types.append(param)

        return_type = f" -> {self._map_type(node.return_type)}" if node.return_type else ""

        self.emit(f"def {node.name}({', '.join(params_with_types)}){return_type}:")
        self.indent += 1
        if not node.body:
            self.emit("pass")
        for stmt in node.body:
            self.visit(stmt)
        self.indent -= 1

    def visit_const(self, node: ConstDecl) -> None:
        self.emit(f"{node.name} = {self.visit_expr(node.expr)}")

    def visit_ask(self, node: AskStmt) -> None:
        prompt = self.visit_expr(node.prompt)
        if node.schema:
            schema = self.visit_expr(node.schema)
            code = f"ask_model({node.model}, {prompt}, schema={schema})"
        else:
            code = f"ask_model({node.model}, {prompt})"
        if node.target:
            self.emit(f"{node.target} = {code}")
        else:
            self.emit(code)

    def visit_if(self, node: IfStmt) -> None:
        self.emit(f"if {self.visit_expr(node.condition)}:")
        self.indent += 1
        if node.then_body:
            for stmt in node.then_body:
                self.visit(stmt)
        else:
            self.emit("pass")
        self.indent -= 1
        if node.else_body:
            self.emit("else:")
            self.indent += 1
            for stmt in node.else_body:
                self.visit(stmt)
            self.indent -= 1

    def visit_for(self, node: ForStmt) -> None:
        self.emit(f"for {node.var_name} in {self.visit_expr(node.iterable)}:")
        self.indent += 1
        if node.body:
            for stmt in node.body:
                self.visit(stmt)
        else:
            self.emit("pass")
        self.indent -= 1

    def visit_while(self, node: WhileStmt) -> None:
        self.emit(f"while {self.visit_expr(node.condition)}:")
        self.indent += 1
        if node.body:
            for stmt in node.body:
                self.visit(stmt)
        else:
            self.emit("pass")
        self.indent -= 1

    def visit_try(self, node: TryStmt) -> None:
        self.emit("try:")
        self.indent += 1
        if node.try_body:
            for stmt in node.try_body:
                self.visit(stmt)
        else:
            self.emit("pass")
        self.indent -= 1
        if node.catch_body:
            except_clause = "except"
            if node.catch_var:
                except_clause += f" Exception as {node.catch_var}"
            self.emit(f"{except_clause}:")
            self.indent += 1
            for stmt in node.catch_body:
                self.visit(stmt)
            self.indent -= 1

    def visit_schema(self, node: SchemaDecl) -> None:
        """Transpile schema to a Python dataclass with validation."""
        self.emit("from dataclasses import dataclass as _dataclass, field as _field")
        self.emit(f"@_dataclass")
        self.emit(f"class {node.name}:")
        self.indent += 1
        type_map = {"string": "str", "int": "int", "float": "float", "bool": "bool", "list": "list", "dict": "dict"}
        for field_name, field_type in node.fields:
            py_type = type_map.get(field_type, field_type)
            default = '""' if py_type == "str" else "0" if py_type in ("int", "float") else "False" if py_type == "bool" else "_field(default_factory=list)" if py_type == "list" else "_field(default_factory=dict)" if py_type == "dict" else "None"
            self.emit(f"{field_name}: {py_type} = {default}")
        self.emit("@classmethod")
        self.emit(f"def validate(cls, data):")
        self.indent += 1
        self.emit("if not isinstance(data, dict): return cls()")
        args = ", ".join(f"{fn}=data.get({fn!r})" for fn, _ in node.fields)
        self.emit(f"return cls({args})")
        self.indent -= 1
        self.indent -= 1

    def visit_async_function(self, node: AsyncFunctionDecl) -> None:
        """Transpile async fn to Python async def."""
        params_with_types = []
        for i, param in enumerate(node.params):
            if i < len(node.param_types) and node.param_types[i]:
                params_with_types.append(f"{param}: {self._map_type(node.param_types[i])}")
            else:
                params_with_types.append(param)
        return_type = f" -> {self._map_type(node.return_type)}" if node.return_type else ""
        self.emit(f"async def {node.name}({', '.join(params_with_types)}){return_type}:")
        self.indent += 1
        if not node.body:
            self.emit("pass")
        for stmt in node.body:
            self.visit(stmt)
        self.indent -= 1

    def visit_on_reload(self, node: OnReloadBlock) -> None:
        """Transpile on_reload {} to a registered callback function."""
        self.emit("def __on_reload__():")
        self.indent += 1
        if not node.body:
            self.emit("pass")
        for stmt in node.body:
            self.visit(stmt)
        self.indent -= 1
        self.emit("# Register on_reload callback")
        self.emit("try:")
        self.indent += 1
        self.emit("from ailang_integration.runtime.hot_reload import get_hot_reloader as _get_hr")
        self.emit("_get_hr().on_reload = lambda changes: __on_reload__()")
        self.indent -= 1
        self.emit("except ImportError:")
        self.indent += 1
        self.emit("pass")
        self.indent -= 1

    def visit_import_header(self, node: ImportDecl) -> None:
        """Emit import at the top of the file.

        For Python stdlib/third-party modules: emit `import module` or `from module import names`.
        For .ai modules: resolve, transpile, and inline the Python code.
        """
        # Convert slash notation to dot notation for resolution
        module_name = node.module.replace("/", ".")

        # Check if this is a local .ai module
        try:
            from pathlib import Path

            from .modules import _is_python_stdlib, resolve_module

            if not _is_python_stdlib(module_name):
                importing_file = Path(self.source_path) if self.source_path else None
                search_paths = [str(importing_file.parent)] if importing_file else None
                resolved = None
                try:
                    resolved = resolve_module(module_name, search_paths, importing_file)
                except Exception:
                    pass  # Not an .ai module, fall through to Python import

                if resolved is not None:
                    # Create a namespace object so that module_name.func() works
                    # Use the last component of the module path as the namespace name
                    # e.g. libs/math_utils → math_utils, utils → utils
                    namespace_name = module_name.rsplit(".", 1)[-1].rsplit("/", 1)[-1]
                    self.emit("import types")
                    self.emit(f"{namespace_name} = types.SimpleNamespace()")
                    # Inline the transpiled .ai module code (skip runtime headers)
                    for line in resolved.python_code.rstrip("\n").split("\n"):
                        stripped = line.strip()
                        # Skip duplicate runtime imports and if __name__ guards
                        if (stripped.startswith("from ailang.") or
                                stripped.startswith("if __name__") or
                                stripped.startswith("    main()")):
                            continue
                        self.emit(line)
                    # Attach exported functions and variables to the namespace
                    for export_name in resolved.exports:
                        self.emit(f"{namespace_name}.{export_name} = {export_name}")
                    self.emit("")
                    return
        except ImportError:
            pass

        # Standard Python import
        if node.names == ["*"]:
            self.emit(f"import {module_name}")
        else:
            names_str = ", ".join(node.names)
            self.emit(f"from {module_name} import {names_str}")

    def visit_import(self, node: ImportDecl) -> None:
        # Imports are emitted in the header; this is a no-op at position
        pass


def transpile_source(source: str, source_path: str | None = None) -> str:
    return Transpiler(source_path=source_path).transpile(parse_source(source))
