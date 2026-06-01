from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

# Expression type alias
Expr = Union[
    'NumberLiteral',
    'StringLiteral',
    'BoolLiteral',
    'NoneLiteral',
    'Identifier',
    'FString',
    'ListLiteral',
    'DictLiteral',
    'UnaryOp',
    'BinaryOp',
    'MemberAccess',
    'IndexAccess',
    'CallExpr',
    'KwArg',
    'AskExpr',
    'PipeExpr',
    'AwaitExpr',
    'StreamExpr',
]


# --- Expression Nodes ---

@dataclass
class NumberLiteral:
    value: float


@dataclass
class StringLiteral:
    value: str


@dataclass
class BoolLiteral:
    value: bool


@dataclass
class NoneLiteral:
    pass


@dataclass
class Identifier:
    name: str


@dataclass
class FString:
    """F-string with interleaved literal parts and expression parts.

    parts is a list where even indices are str literals and odd indices are Expr.
    For f"Hello {name}" the parts would be: ["Hello ", Identifier("name")]
    """
    parts: List[Union[str, 'Expr']] = field(default_factory=list)


@dataclass
class ListLiteral:
    elements: List['Expr'] = field(default_factory=list)


@dataclass
class DictLiteral:
    pairs: List[Tuple['Expr', 'Expr']] = field(default_factory=list)


@dataclass
class UnaryOp:
    op: str
    operand: 'Expr'


@dataclass
class BinaryOp:
    op: str
    left: 'Expr'
    right: 'Expr'


@dataclass
class MemberAccess:
    object: 'Expr'
    member: str


@dataclass
class IndexAccess:
    object: 'Expr'
    index: 'Expr'


@dataclass
class CallExpr:
    callee: 'Expr'
    args: List['Expr'] = field(default_factory=list)
    kwargs: List[Tuple[str, 'Expr']] = field(default_factory=list)


@dataclass
class KwArg:
    """Keyword argument in a function call: name=value"""
    name: str
    value: 'Expr'


@dataclass
class AskExpr:
    model: str
    prompt: 'Expr'
    schema: Optional['Expr'] = None


@dataclass
class PipeExpr:
    """Pipe operator: left |> right — passes left as first arg to right."""
    left: 'Expr'
    right: 'Expr'


@dataclass
class AwaitExpr:
    """Await expression: await some_async_call()"""
    expr: 'Expr'


@dataclass
class StreamExpr:
    """Stream expression: stream iterable — yields from async iterator."""
    expr: 'Expr'


# --- Statement Node type alias ---
ASTNode = Union[
    'ModelDecl',
    'AgentDecl',
    'FunctionDecl',
    'ConstDecl',
    'Assignment',
    'PrintStmt',
    'ReturnStmt',
    'BreakStmt',
    'ContinueStmt',
    'ExprStmt',
    'AskStmt',
    'IfStmt',
    'ForStmt',
    'WhileStmt',
    'TryStmt',
    'ImportDecl',
    'SchemaDecl',
    'AsyncFunctionDecl',
    'OnReloadBlock',
]


# --- Top-level ---

@dataclass
class Program:
    body: List[ASTNode] = field(default_factory=list)


# --- Declaration Nodes ---

@dataclass
class ModelDecl:
    name: str
    provider: str
    model_name: str


@dataclass
class AgentDecl:
    name: str
    model: str
    instructions: str
    tools: List[str] = field(default_factory=list)
    body: List[ASTNode] = field(default_factory=list)


@dataclass
class FunctionDecl:
    name: str
    params: List[str]
    param_types: List[Optional[str]]
    return_type: Optional[str]
    body: List[ASTNode]


@dataclass
class ImportDecl:
    module: str
    names: List[str]


# --- Statement Nodes ---

@dataclass
class ConstDecl:
    name: str
    expr: Expr


@dataclass
class Assignment:
    name: str
    expr: Expr


@dataclass
class IndexAssignment:
    """Assign to an index: obj[key] = expr"""
    obj: Expr
    index: Expr
    expr: Expr


@dataclass
class CompoundAssignment:
    """Compound assignment: x += 1, x -= 1, etc."""
    name: str
    op: str  # '+', '-', '*', '/', '%'
    expr: Expr


@dataclass
class PrintStmt:
    expr: Expr


@dataclass
class ReturnStmt:
    expr: Expr


@dataclass
class BreakStmt:
    pass


@dataclass
class ContinueStmt:
    pass


@dataclass
class ExprStmt:
    expr: Expr


@dataclass
class AskStmt:
    target: Optional[str]
    model: str
    prompt: Expr
    schema: Optional[Expr] = None


@dataclass
class IfStmt:
    condition: Expr
    then_body: List[ASTNode]
    else_body: List[ASTNode] = field(default_factory=list)


@dataclass
class ForStmt:
    var_name: str
    iterable: Expr
    body: List[ASTNode]


@dataclass
class WhileStmt:
    condition: Expr
    body: List[ASTNode]


@dataclass
class TryStmt:
    try_body: List[ASTNode]
    catch_var: Optional[str]
    catch_body: List[ASTNode]


# --- Language Evolution Nodes ---

@dataclass
class SchemaDecl:
    """Schema declaration: schema Name { field: type, ... }"""
    name: str
    fields: List[Tuple[str, str]]  # [(field_name, type_name), ...]


@dataclass
class AsyncFunctionDecl:
    """Async function: async fn name(params) { body }"""
    name: str
    params: List[str]
    param_types: List[Optional[str]]
    return_type: Optional[str]
    body: List['ASTNode']


@dataclass
class OnReloadBlock:
    """on_reload { body } — code that runs when .ai files are hot-reloaded."""
    body: List['ASTNode']
