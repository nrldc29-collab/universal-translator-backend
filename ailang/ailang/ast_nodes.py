"""AST node definitions for AILang."""
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Program:
    body: List[Any] = field(default_factory=list)

# --- Declarations ---
@dataclass
class ModelDecl:
    name: str
    provider: str
    model_name: str

@dataclass
class ConstDecl:
    name: str
    value: Any

@dataclass
class FnDecl:
    name: str
    params: List[str]
    body: List[Any]

@dataclass
class AgentDecl:
    name: str
    model_ref: str
    instructions: Optional[str]
    tools: List[str]
    methods: List['FnDecl']

# --- Statements ---
@dataclass
class ReturnStmt:
    value: Any

@dataclass
class AssignStmt:
    name: str
    value: Any

@dataclass
class ExprStmt:
    expr: Any

@dataclass
class IfStmt:
    condition: Any
    then_body: List[Any]
    else_body: List[Any] = field(default_factory=list)

@dataclass
class ForStmt:
    var: str
    iterable: Any
    body: List[Any]

@dataclass
class BreakStmt:
    pass

# --- Expressions ---
@dataclass
class BinOp:
    op: str
    left: Any
    right: Any

@dataclass
class UnaryOp:
    op: str
    operand: Any

@dataclass
class CallExpr:
    func: str
    args: List[Any]

@dataclass
class MethodCallExpr:
    obj: str
    method: str
    args: List[Any]

@dataclass
class AskExpr:
    model_ref: str
    prompt: Any

@dataclass
class IndexExpr:
    obj: Any
    index: Any

@dataclass
class FStringExpr:
    parts: List[Any]  # mix of strings and expressions

@dataclass
class Identifier:
    name: str

@dataclass
class Literal:
    value: Any  # str, int, float, bool, None

@dataclass
class ListLiteral:
    elements: List[Any]

@dataclass
class DictLiteral:
    pairs: List[tuple]  # list of (key_expr, value_expr)
