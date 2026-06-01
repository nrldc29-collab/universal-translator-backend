"""AILang static type checker.

Performs type checking on the AST after parsing, before transpilation.
Reports type errors but does not prevent transpilation (warnings mode by default).
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    ConstDecl,
    ContinueStmt,
    DictLiteral,
    Expr,
    ForStmt,
    FString,
    FunctionDecl,
    Identifier,
    IfStmt,
    ImportDecl,
    IndexAccess,
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
)
from .parser import parse_source


# Type representation
@dataclass(frozen=True)
class AILangType:
    """Represents a type in the AILang type system."""
    name: str

    def is_compatible_with(self, other: AILangType) -> bool:
        if self == ANY or other == ANY:
            return True
        if self == other:
            return True
        # numeric compatibility
        if self == INT and other == FLOAT:
            return True  # int is assignable to float
        return False

    def __repr__(self) -> str:
        return self.name


# Predefined types
ANY = AILangType("any")
INT = AILangType("int")
FLOAT = AILangType("float")
NUMBER = AILangType("number")  # int or float
STRING = AILangType("string")
BOOL = AILangType("bool")
NONE_TYPE = AILangType("none")
LIST = AILangType("list")
DICT = AILangType("dict")
MODEL = AILangType("model")
AGENT = AILangType("agent")
UNKNOWN = AILangType("unknown")
VOID = AILangType("void")


def parse_type_name(name: str | None) -> AILangType:
    """Convert a type annotation string to an AILangType."""
    if name is None:
        return ANY
    mapping = {
        "int": INT,
        "float": FLOAT,
        "number": NUMBER,
        "string": STRING,
        "str": STRING,
        "bool": BOOL,
        "none": NONE_TYPE,
        "list": LIST,
        "dict": DICT,
        "model": MODEL,
        "agent": AGENT,
        "any": ANY,
        "void": VOID,
    }
    return mapping.get(name.lower(), AILangType(name.lower()))


@dataclass
class TypeIssue:
    """A type checking issue (error or warning)."""
    message: str
    line: int
    col: int
    severity: str = "error"  # "error" or "warning"
    node_type: str = ""


@dataclass
class Scope:
    """A variable scope for type tracking."""
    parent: Scope | None = None
    variables: dict[str, AILangType] = field(default_factory=dict)
    return_type: AILangType | None = None

    def lookup(self, name: str) -> AILangType | None:
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def define(self, name: str, type_: AILangType) -> None:
        self.variables[name] = type_

    def child(self, return_type: AILangType | None = None) -> Scope:
        return Scope(parent=self, return_type=return_type or self.return_type)


class TypeChecker:
    """Walks the AST and checks type annotations."""

    def __init__(self) -> None:
        self.issues: list[TypeIssue] = []
        self.global_scope = Scope()
        self.current_scope = self.global_scope
        self._init_builtins()

    def _init_builtins(self) -> None:
        """Register built-in functions and types."""
        builtins = {
            "print": AILangType("callable"),
            "len": INT,
            "range": LIST,
            "int": INT,
            "float": FLOAT,
            "str": STRING,
            "bool": BOOL,
            "list": LIST,
            "dict": DICT,
            "true": BOOL,
            "false": BOOL,
            "none": NONE_TYPE,
            # Stdlib functions
            "to_string": STRING,
            "to_int": INT,
            "to_float": FLOAT,
            "string_length": INT,
            "string_contains": BOOL,
            "string_starts_with": BOOL,
            "string_ends_with": BOOL,
            "string_replace": STRING,
            "string_lower": STRING,
            "string_upper": STRING,
            "string_split": LIST,
            "string_join": STRING,
            "string_trim": STRING,
            "list_first": ANY,
            "list_last": ANY,
            "list_rest": LIST,
            "list_length": INT,
            "list_append": LIST,
            "list_contains": BOOL,
            "dict_get": ANY,
            "dict_set": DICT,
            "dict_keys": LIST,
            "dict_values": LIST,
            "dict_has_key": BOOL,
            "parse_json": DICT,
            "to_json": STRING,
            "read_file": STRING,
            "write_file": VOID,
            "append_file": VOID,
            "file_exists": BOOL,
            "get_env": STRING,
            "set_env": VOID,
            "sleep": VOID,
            "format_string": STRING,
            "get_current_time": STRING,
            # Math
            "abs": INT,
            "min": INT,
            "max": INT,
            "floor": INT,
            "ceil": INT,
            "round": INT,
            "sqrt": FLOAT,
            "pow": FLOAT,
            "log": FLOAT,
            "sin": FLOAT,
            "cos": FLOAT,
        }
        for name, type_ in builtins.items():
            self.global_scope.define(name, type_)

    def check(self, program: Program) -> list[TypeIssue]:
        """Run type checking on a program and return a list of issues."""
        self.issues = []
        # First pass: register all top-level declarations
        for node in program.body:
            self._register_declaration(node)
        # Second pass: check all nodes
        for node in program.body:
            self._check_node(node)
        return self.issues

    def _error(self, message: str, line: int = 0, col: int = 0, node_type: str = "") -> None:
        self.issues.append(TypeIssue(message, line, col, "error", node_type))

    def _warning(self, message: str, line: int = 0, col: int = 0, node_type: str = "") -> None:
        self.issues.append(TypeIssue(message, line, col, "warning", node_type))

    def _register_declaration(self, node: ASTNode) -> None:
        """Register top-level declarations so they're available before checking."""
        if isinstance(node, FunctionDecl):
            self.global_scope.define(node.name, AILangType("callable"))
        elif isinstance(node, ConstDecl):
            expr_type = self._infer_expr_type(node.expr)
            self.global_scope.define(node.name, expr_type)
        elif isinstance(node, ModelDecl):
            self.global_scope.define(node.name, MODEL)
        elif isinstance(node, AgentDecl):
            self.global_scope.define(node.name, AGENT)

    def _check_node(self, node: ASTNode) -> None:
        if isinstance(node, ModelDecl):
            self._check_model(node)
        elif isinstance(node, AgentDecl):
            self._check_agent(node)
        elif isinstance(node, FunctionDecl):
            self._check_function(node)
        elif isinstance(node, ConstDecl):
            self._check_const(node)
        elif isinstance(node, Assignment):
            self._check_assignment(node)
        elif isinstance(node, PrintStmt):
            self._infer_expr_type(node.expr)
        elif isinstance(node, ReturnStmt):
            self._check_return(node)
        elif isinstance(node, IfStmt):
            self._check_if(node)
        elif isinstance(node, ForStmt):
            self._check_for(node)
        elif isinstance(node, WhileStmt):
            self._check_while(node)
        elif isinstance(node, TryStmt):
            self._check_try(node)
        elif isinstance(node, AskStmt):
            self._check_ask(node)
        elif isinstance(node, ImportDecl):
            pass  # Imports are handled at transpile time
        elif isinstance(node, BreakStmt):
            pass
        elif isinstance(node, ContinueStmt):
            pass
        else:
            # Expression statement
            if hasattr(node, "expr"):
                self._infer_expr_type(getattr(node, "expr"))

    # --- Expression type inference ---

    def _infer_expr_type(self, expr: Expr) -> AILangType:
        """Infer the type of an expression."""
        if isinstance(expr, NumberLiteral):
            if isinstance(expr.value, int):
                return INT
            return FLOAT

        if isinstance(expr, StringLiteral):
            return STRING

        if isinstance(expr, BoolLiteral):
            return BOOL

        if isinstance(expr, NoneLiteral):
            return NONE_TYPE

        if isinstance(expr, Identifier):
            var_type = self.current_scope.lookup(expr.name)
            if var_type is None:
                var_type = self.global_scope.lookup(expr.name)
            if var_type is None:
                self._warning(
                    f"Undefined variable '{expr.name}'",
                    0, 0, "Identifier"
                )
                return UNKNOWN
            return var_type

        if isinstance(expr, FString):
            return STRING

        if isinstance(expr, ListLiteral):
            return LIST

        if isinstance(expr, DictLiteral):
            return DICT

        if isinstance(expr, UnaryOp):
            operand_type = self._infer_expr_type(expr.operand)
            if expr.op == "-":
                if operand_type not in (INT, FLOAT, NUMBER, ANY, UNKNOWN):
                    self._error(
                        f"Cannot apply unary '-' to type '{operand_type.name}'",
                        0, 0, "UnaryOp"
                    )
                return operand_type if operand_type in (INT, FLOAT) else INT
            if expr.op == "not":
                if operand_type not in (BOOL, ANY, UNKNOWN):
                    self._warning(
                        f"Applying 'not' to non-boolean type '{operand_type.name}'",
                        0, 0, "UnaryOp"
                    )
                return BOOL
            return UNKNOWN

        if isinstance(expr, BinaryOp):
            return self._infer_binary_type(expr)

        if isinstance(expr, MemberAccess):
            obj_type = self._infer_expr_type(expr.object)
            # Model.ask → string result
            if obj_type == MODEL:
                if expr.member in ("ask",):
                    return STRING
            # Agent methods
            if obj_type == AGENT:
                return ANY
            # Common member types
            if obj_type == STRING:
                string_methods = {
                    "length": INT, "upper": STRING, "lower": STRING,
                    "strip": STRING, "split": LIST, "replace": STRING,
                }
                return string_methods.get(expr.member, ANY)
            if obj_type in (LIST, DICT):
                if expr.member == "length":
                    return INT
                return ANY
            return ANY

        if isinstance(expr, IndexAccess):
            obj_type = self._infer_expr_type(expr.object)
            idx_type = self._infer_expr_type(expr.index)
            if obj_type == LIST:
                if idx_type not in (INT, ANY, UNKNOWN):
                    self._error(
                        f"List index must be int, got '{idx_type.name}'",
                        0, 0, "IndexAccess"
                    )
                return ANY
            if obj_type == DICT:
                return ANY
            return ANY

        if isinstance(expr, CallExpr):
            return self._infer_call_type(expr)

        if isinstance(expr, AskExpr):
            return STRING

        if isinstance(expr, KwArg):
            return self._infer_expr_type(expr.value)

        return UNKNOWN

    def _infer_binary_type(self, expr: BinaryOp) -> AILangType:
        """Infer the type of a binary operation."""
        left_type = self._infer_expr_type(expr.left)
        right_type = self._infer_expr_type(expr.right)

        # Arithmetic operators
        if expr.op in ("+", "-", "*", "/", "%"):
            if left_type in (ANY, UNKNOWN) or right_type in (ANY, UNKNOWN):
                return NUMBER
            # String concatenation
            if expr.op == "+" and left_type == STRING and right_type == STRING:
                return STRING
            # String + something else
            if expr.op == "+" and (left_type == STRING or right_type == STRING):
                if left_type != STRING or right_type != STRING:
                    self._error(
                        f"Cannot add '{left_type.name}' and '{right_type.name}'",
                        0, 0, "BinaryOp"
                    )
                return STRING
            # Numeric arithmetic
            if left_type in (INT, FLOAT, NUMBER) and right_type in (INT, FLOAT, NUMBER):
                if left_type == FLOAT or right_type == FLOAT:
                    return FLOAT
                if expr.op == "/":
                    return FLOAT  # Division always returns float
                return INT
            self._error(
                f"Cannot apply '{expr.op}' to types '{left_type.name}' and '{right_type.name}'",
                0, 0, "BinaryOp"
            )
            return UNKNOWN

        # Comparison operators
        if expr.op in (">", "<", ">=", "<="):
            if left_type not in (INT, FLOAT, NUMBER, ANY, UNKNOWN) or right_type not in (INT, FLOAT, NUMBER, ANY, UNKNOWN):
                self._error(
                    f"Cannot compare '{left_type.name}' and '{right_type.name}' with '{expr.op}'",
                    0, 0, "BinaryOp"
                )
            return BOOL

        # Equality operators
        if expr.op in ("==", "!="):
            if not left_type.is_compatible_with(right_type) and not right_type.is_compatible_with(left_type):
                if left_type not in (ANY, UNKNOWN) and right_type not in (ANY, UNKNOWN):
                    self._warning(
                        f"Comparing different types '{left_type.name}' and '{right_type.name}'",
                        0, 0, "BinaryOp"
                    )
            return BOOL

        # Logical operators
        if expr.op in ("and", "or"):
            return BOOL

        return UNKNOWN

    def _infer_call_type(self, expr: CallExpr) -> AILangType:
        """Infer the return type of a function call."""
        # Check argument count for known functions
        if isinstance(expr.callee, Identifier):
            func_name = expr.callee.name
            # Built-in functions
            builtins = {
                "len": INT,
                "range": LIST,
                "int": INT,
                "float": FLOAT,
                "str": STRING,
                "bool": BOOL,
                "list": LIST,
                "dict": DICT,
                "print": VOID,
            }
            if func_name in builtins:
                return builtins[func_name]

        if isinstance(expr.callee, MemberAccess):
            # Method calls: obj.method(args)
            obj_type = self._infer_expr_type(expr.callee.object)
            # For model.ask, agent methods, etc.
            if obj_type == MODEL:
                return STRING

        return ANY

    # --- Node-specific checks ---

    def _check_model(self, node: ModelDecl) -> None:
        if not node.provider:
            self._error(f"Model '{node.name}' missing provider", 0, 0, "ModelDecl")
        if not node.model_name:
            self._error(f"Model '{node.name}' missing model name", 0, 0, "ModelDecl")

    def _check_agent(self, node: AgentDecl) -> None:
        model_type = self.global_scope.lookup(node.model)
        if model_type is None:
            self._error(
                f"Agent '{node.name}' references undefined model '{node.model}'",
                0, 0, "AgentDecl"
            )
        elif model_type != MODEL:
            self._error(
                f"Agent '{node.name}' model '{node.model}' is not a model (got '{model_type.name}')",
                0, 0, "AgentDecl"
            )
        # Check agent body
        agent_scope = self.current_scope.child()
        old_scope = self.current_scope
        self.current_scope = agent_scope
        for stmt in node.body:
            self._check_node(stmt)
        self.current_scope = old_scope

    def _check_function(self, node: FunctionDecl) -> None:
        # Create a new scope for the function
        func_scope = self.current_scope.child(
            return_type=parse_type_name(node.return_type)
        )
        # Register parameters
        for i, param in enumerate(node.params):
            param_type = parse_type_name(node.param_types[i] if i < len(node.param_types) else None)
            func_scope.define(param, param_type)

        old_scope = self.current_scope
        self.current_scope = func_scope

        # Check function body
        has_return = False
        for stmt in node.body:
            self._check_node(stmt)
            if isinstance(stmt, ReturnStmt):
                has_return = True

        # Check return type annotation matches actual returns
        if node.return_type and node.return_type not in ("void", "none"):
            expected_return = parse_type_name(node.return_type)
            if expected_return != VOID and not has_return and node.body:
                self._warning(
                    f"Function '{node.name}' declares return type '{node.return_type}' but may not return a value",
                    0, 0, "FunctionDecl"
                )

        self.current_scope = old_scope

    def _check_const(self, node: ConstDecl) -> None:
        expr_type = self._infer_expr_type(node.expr)
        self.current_scope.define(node.name, expr_type)

    def _check_assignment(self, node: Assignment) -> None:
        expr_type = self._infer_expr_type(node.expr)
        # Check if variable already has a type (from earlier assignment or declaration)
        existing = self.current_scope.lookup(node.name)
        if existing and existing != UNKNOWN and expr_type != UNKNOWN:
            if not existing.is_compatible_with(expr_type):
                self._warning(
                    f"Variable '{node.name}' was '{existing.name}', now assigned '{expr_type.name}'",
                    0, 0, "Assignment"
                )
        self.current_scope.define(node.name, expr_type)

    def _check_return(self, node: ReturnStmt) -> None:
        expr_type = self._infer_expr_type(node.expr)
        if self.current_scope.return_type and self.current_scope.return_type not in (ANY, VOID):
            if not self.current_scope.return_type.is_compatible_with(expr_type):
                self._error(
                    f"Return type mismatch: expected '{self.current_scope.return_type.name}', got '{expr_type.name}'",
                    0, 0, "ReturnStmt"
                )

    def _check_if(self, node: IfStmt) -> None:
        cond_type = self._infer_expr_type(node.condition)
        if cond_type not in (BOOL, ANY, UNKNOWN):
            self._warning(
                f"If condition is '{cond_type.name}', expected 'bool'",
                0, 0, "IfStmt"
            )
        for stmt in node.then_body:
            self._check_node(stmt)
        for stmt in node.else_body:
            self._check_node(stmt)

    def _check_for(self, node: ForStmt) -> None:
        iter_type = self._infer_expr_type(node.iterable)
        if iter_type not in (LIST, ANY, UNKNOWN):
            self._warning(
                f"For iterable is '{iter_type.name}', expected 'list'",
                0, 0, "ForStmt"
            )
        loop_scope = self.current_scope.child()
        loop_scope.define(node.var_name, ANY)
        old_scope = self.current_scope
        self.current_scope = loop_scope
        for stmt in node.body:
            self._check_node(stmt)
        self.current_scope = old_scope

    def _check_while(self, node: WhileStmt) -> None:
        cond_type = self._infer_expr_type(node.condition)
        if cond_type not in (BOOL, ANY, UNKNOWN):
            self._warning(
                f"While condition is '{cond_type.name}', expected 'bool'",
                0, 0, "WhileStmt"
            )
        for stmt in node.body:
            self._check_node(stmt)

    def _check_try(self, node: TryStmt) -> None:
        for stmt in node.try_body:
            self._check_node(stmt)
        catch_scope = self.current_scope.child()
        if node.catch_var:
            catch_scope.define(node.catch_var, ANY)
        old_scope = self.current_scope
        self.current_scope = catch_scope
        for stmt in node.catch_body:
            self._check_node(stmt)
        self.current_scope = old_scope

    def _check_ask(self, node: AskStmt) -> None:
        # Check that model exists
        model_type = self.global_scope.lookup(node.model)
        if model_type is None:
            self._error(
                f"Ask references undefined model '{node.model}'",
                0, 0, "AskStmt"
            )
        elif model_type != MODEL:
            self._error(
                f"Ask model '{node.model}' is not a model (got '{model_type.name}')",
                0, 0, "AskStmt"
            )
        # Check prompt is string-like
        prompt_type = self._infer_expr_type(node.prompt)
        if prompt_type not in (STRING, ANY, UNKNOWN):
            self._warning(
                f"Ask prompt is '{prompt_type.name}', expected 'string'",
                0, 0, "AskStmt"
            )
        # Register result variable
        if node.target:
            self.current_scope.define(node.target, STRING)


def check_source(source: str) -> list[TypeIssue]:
    """Parse and type-check AILang source code."""
    program = parse_source(source)
    checker = TypeChecker()
    return checker.check(program)
