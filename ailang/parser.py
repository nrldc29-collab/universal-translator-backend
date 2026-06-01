from __future__ import annotations

from dataclasses import dataclass

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
from .errors import ParseError
from .lexer import Token, lex

# Operator precedence levels (higher = binds tighter)
PREC_PIPE = 1       # |> binds loosest (left-to-right chaining)
PREC_OR = 2
PREC_AND = 3
PREC_EQUALITY = 4
PREC_COMPARISON = 5
PREC_ADD = 6
PREC_MUL = 7
PREC_UNARY = 8
PREC_POSTFIX = 9

BINARY_OP_PRECEDENCE = {
    "PIPE_GT": PREC_PIPE,
    "OR": PREC_OR,
    "AND": PREC_AND,
    "EQ": PREC_EQUALITY,
    "NEQ": PREC_EQUALITY,
    "LT": PREC_COMPARISON,
    "GT": PREC_COMPARISON,
    "LTE": PREC_COMPARISON,
    "GTE": PREC_COMPARISON,
    "PLUS": PREC_ADD,
    "MINUS": PREC_ADD,
    "STAR": PREC_MUL,
    "SLASH": PREC_MUL,
    "PERCENT": PREC_MUL,
    # Postfix / call / member access / index — highest precedence
    "DOT": PREC_POSTFIX,
    "LBRACKET": PREC_POSTFIX,
    "LPAREN": PREC_POSTFIX,
}


class Parser:
    MAX_EXPR_DEPTH = 200  # Prevent stack overflow from deeply nested expressions

    def __init__(self, tokens: list[Token], source: str = "") -> None:
        self.tokens: list[Token] = tokens
        self.pos: int = 0
        self.source = source
        self.errors: list[ParseError] = []
        self.recovery_mode: bool = False
        self._expr_depth: int = 0

    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def match(self, *kinds: str) -> bool:
        if self.current().kind in kinds:
            self.pos += 1
            return True
        return False

    def expect(self, kind: str) -> Token:
        tok = self.current()
        if tok.kind != kind:
            error = ParseError(
                f"Expected {kind}, got {tok.kind} ('{tok.value}')",
                tok.line, tok.col, self.source
            )
            if self.recovery_mode:
                self.errors.append(error)
                # If the current token is what we expected, we'd have consumed it.
                # Since it's not, try to advance to avoid infinite loops.
                if tok.kind != "EOF":
                    self.pos += 1
                return tok  # Return current token as a placeholder
            raise error
        self.pos += 1
        return tok

    def skip_newlines(self) -> None:
        while self.match("NEWLINE"):
            pass

    # Synchronization tokens — points where we can resume parsing after an error
    SYNC_TOKENS = {
        "FN", "MODEL", "AGENT", "IMPORT", "RBRACE", "EOF",
        "IF", "FOR", "WHILE", "TRY", "PRINT", "RETURN",
        "BREAK", "CONTINUE", "CONST", "ASK",
        "SCHEMA", "ASYNC", "ON_RELOAD",
    }

    def synchronize(self) -> None:
        """Skip tokens until we reach a synchronization point.

        This allows the parser to recover from errors and continue
        finding more errors in the rest of the source.
        """
        max_skip = 1000  # Safety limit to prevent infinite loops
        skipped = 0
        while self.current().kind != "EOF" and skipped < max_skip:
            if self.current().kind in self.SYNC_TOKENS:
                return
            if self.current().kind == "RBRACE":
                return
            self.pos += 1
            skipped += 1

    # --- Top-level parsing ---

    def parse(self) -> Program:
        body: list[ASTNode] = []
        self.skip_newlines()
        while self.current().kind != "EOF":
            # Consume stray closing braces only in recovery mode
            if self.current().kind == "RBRACE":
                if self.recovery_mode:
                    self.pos += 1
                    self.skip_newlines()
                    continue
                else:
                    tok = self.current()
                    raise ParseError(
                        "Unexpected RBRACE",
                        tok.line, tok.col, self.source
                    )
            try:
                if self.current().kind == "MODEL":
                    body.append(self.parse_model())
                elif self.current().kind == "AGENT":
                    body.append(self.parse_agent())
                elif self.current().kind == "FN":
                    body.append(self.parse_function())
                elif self.current().kind == "IMPORT":
                    body.append(self.parse_import())
                elif self.current().kind == "SCHEMA":
                    body.append(self.parse_schema())
                elif self.current().kind == "ASYNC":
                    body.append(self.parse_async_function())
                elif self.current().kind == "ON_RELOAD":
                    body.append(self.parse_on_reload())
                else:
                    body.append(self.parse_statement())
            except ParseError as e:
                if self.recovery_mode:
                    self.errors.append(e)
                    self.synchronize()
                    # Skip past any stray RBRACE after synchronization
                    while self.current().kind == "RBRACE":
                        self.pos += 1
                else:
                    raise
            self.skip_newlines()

        # If we collected errors, raise the first one
        # unless we're in explicit recovery mode
        if self.errors and not self.recovery_mode:
            raise self.errors[0]
        return Program(body)

    # --- Declarations ---

    def parse_model(self) -> ModelDecl:
        self.expect("MODEL")
        name: str = self.expect("IDENT").value
        self.expect("LBRACE")
        provider: str = "mock"
        model_name: str = name
        self.skip_newlines()
        while self.current().kind != "RBRACE" and self.current().kind != "EOF":
            if self.current().kind != "IDENT":
                self.skip_newlines()
                self.match("COMMA")
                self.skip_newlines()
                continue
            key: str = self.expect("IDENT").value
            self.expect("COLON")
            if self.current().kind != "STRING":
                # Skip to next comma or closing brace
                tok = self.current()
                self.errors.append(ParseError(
                    f"Expected STRING for model property value, got {tok.kind}",
                    tok.line, tok.col, self.source
                ))
                while self.current().kind not in ("COMMA", "RBRACE", "EOF", "NEWLINE"):
                    self.pos += 1
                self.match("COMMA")
                self.skip_newlines()
                continue
            value: str = self.expect("STRING").value
            if key == "provider":
                provider = value
            elif key == "name":
                model_name = value
            else:
                tok = self.current()
                if self.recovery_mode:
                    self.errors.append(ParseError(
                        f"Unknown model property '{key}'",
                        tok.line, tok.col, self.source
                    ))
                else:
                    raise ParseError(
                        f"Unknown model property '{key}'",
                        tok.line, tok.col, self.source
                    )
            self.skip_newlines()
            self.match("COMMA")
            self.skip_newlines()
        self.match("RBRACE")
        return ModelDecl(name, provider, model_name)

    def parse_agent(self) -> AgentDecl:
        self.expect("AGENT")
        name: str = self.expect("IDENT").value
        self.expect("LPAREN")
        model: str = self.expect("IDENT").value
        self.expect("RPAREN")
        self.expect("LBRACE")
        self.skip_newlines()
        instructions: str = ""
        tools: list[str] = []
        body: list[ASTNode] = []
        while self.current().kind != "RBRACE":
            if self.current().kind == "IDENT":
                key: str = self.current().value
                if key == "instructions":
                    self.pos += 1
                    self.expect("COLON")
                    instructions = self.expect("STRING").value
                    self.skip_newlines()
                elif key == "tools":
                    self.pos += 1
                    self.expect("COLON")
                    tools.append(self.expect("IDENT").value)
                    while self.match("COMMA"):
                        tools.append(self.expect("IDENT").value)
                    self.skip_newlines()
                else:
                    body.append(self.parse_statement())
            else:
                body.append(self.parse_statement())
            self.skip_newlines()
        self.expect("RBRACE")
        return AgentDecl(name, model, instructions, tools, body)

    def parse_function(self) -> FunctionDecl:
        self.expect("FN")
        name: str = self.expect("IDENT").value
        self.expect("LPAREN")
        params: list[str] = []
        param_types: list[str | None] = []
        if self.current().kind != "RPAREN":
            params.append(self.expect("IDENT").value)
            if self.match("COLON"):
                param_types.append(self.expect("IDENT").value)
            else:
                param_types.append(None)
            while self.match("COMMA"):
                if self.current().kind == "RPAREN":
                    break
                params.append(self.expect("IDENT").value)
                if self.match("COLON"):
                    param_types.append(self.expect("IDENT").value)
                else:
                    param_types.append(None)
        self.expect("RPAREN")
        return_type: str | None = None
        if self.current().kind == "MINUS_GT":
            self.expect("MINUS_GT")
            return_type = self.expect("IDENT").value
        elif self.current().kind == "COLON" and self.peek().kind == "IDENT":
            # Support old `: type` syntax for return type
            # Only if the IDENT after COLON looks like a type (not a block)
            if self.peek().kind == "IDENT" and self.peek(2).kind != "EQUAL":
                self.expect("COLON")
                return_type = self.expect("IDENT").value
        body: list[ASTNode] = self.parse_block()
        return FunctionDecl(name, params, param_types, return_type, body)

    def parse_import(self) -> ImportDecl:
        self.expect("IMPORT")
        # Support dotted module names: import foo.bar.baz
        module: str = self.expect("IDENT").value
        while self.current().kind == "DOT":
            self.pos += 1
            module += "." + self.expect("IDENT").value
        # Support slash paths: import libs/math_utils (converted to dot notation)
        while self.current().kind == "SLASH":
            self.pos += 1
            module += "/" + self.expect("IDENT").value
        names: list[str] = []
        if self.match("COLON"):
            names.append(self.expect("IDENT").value)
            while self.match("COMMA"):
                names.append(self.expect("IDENT").value)
        else:
            names = ["*"]
        return ImportDecl(module, names)

    # --- Blocks ---

    def parse_block(self) -> list[ASTNode]:
        self.expect("LBRACE")
        body: list[ASTNode] = []
        self.skip_newlines()
        safety = 0
        while self.current().kind != "RBRACE" and self.current().kind != "EOF" and safety < 1000:
            safety += 1
            if self.recovery_mode:
                try:
                    body.append(self.parse_statement())
                except ParseError as e:
                    self.errors.append(e)
                    skip_count = 0
                    while (self.current().kind not in (
                        "RBRACE", "EOF", "FN", "IF", "FOR", "WHILE",
                        "TRY", "PRINT", "RETURN", "BREAK", "CONTINUE",
                        "CONST", "ASK", "NEWLINE"
                    ) and skip_count < 100):
                        self.pos += 1
                        skip_count += 1
            else:
                body.append(self.parse_statement())
            self.skip_newlines()
        if self.current().kind == "RBRACE":
            self.pos += 1  # consume RBRACE
        elif not self.recovery_mode:
            tok = self.current()
            raise ParseError(
                f"Expected RBRACE, got {tok.kind}",
                tok.line, tok.col, self.source
            )
        return body

    # --- Statements ---

    def parse_statement(self) -> ASTNode:
        kind = self.current().kind
        if kind == "PRINT":
            return self.parse_print()
        if kind == "RETURN":
            return self.parse_return()
        if kind == "BREAK":
            self.expect("BREAK")
            return BreakStmt()
        if kind == "CONTINUE":
            self.expect("CONTINUE")
            return ContinueStmt()
        if kind == "CONST":
            return self.parse_const()
        if kind == "IF":
            return self.parse_if()
        if kind == "FOR":
            return self.parse_for()
        if kind == "WHILE":
            return self.parse_while()
        if kind == "TRY":
            return self.parse_try()
        if kind == "ASK":
            return self.parse_ask_stmt(None)
        if kind == "FN":
            return self.parse_function()
        if kind == "IDENT":
            # Check for assignment: IDENT = expr
            if self.peek().kind == "EQUAL":
                name = self.current().value
                self.pos += 2  # skip IDENT and EQUAL
                # Check for ask assignment: x = ask MODEL: "prompt"
                if self.current().kind == "ASK":
                    return self.parse_ask_stmt(name)
                expr = self.parse_expression()
                return Assignment(name, expr)
            # Check for compound assignment: IDENT += expr, IDENT -= expr, etc.
            if self.peek().kind in ("PLUS_EQUAL", "MINUS_EQUAL", "STAR_EQUAL", "SLASH_EQUAL", "PERCENT_EQUAL"):
                name = self.current().value
                op_map = {"PLUS_EQUAL": "+", "MINUS_EQUAL": "-", "STAR_EQUAL": "*", "SLASH_EQUAL": "/", "PERCENT_EQUAL": "%"}
                op = op_map[self.peek().kind]
                self.pos += 2  # skip IDENT and compound op
                expr = self.parse_expression()
                return CompoundAssignment(name, op, expr)
            # Otherwise it's an expression statement
            expr = self.parse_expression()
            # Check for index assignment: expr[key] = value
            if isinstance(expr, IndexAccess) and self.current().kind == "EQUAL":
                self.pos += 1  # skip EQUAL
                value = self.parse_expression()
                return IndexAssignment(expr.obj, expr.index, value)
            return ExprStmt(expr)
        # Fallback: expression statement
        expr = self.parse_expression()
        return ExprStmt(expr)

    def parse_print(self) -> PrintStmt:
        self.expect("PRINT")
        self.expect("LPAREN")
        # Support print with multiple arguments: print(a, b, c)
        # We transpile this as a single tuple or just pass through
        args: list[Expr] = []
        if self.current().kind != "RPAREN":
            args.append(self.parse_expression())
            while self.match("COMMA"):
                args.append(self.parse_expression())
        self.expect("RPAREN")
        if len(args) == 1:
            return PrintStmt(args[0])
        # Multiple args: wrap as a call to print for the transpiler
        from .ast_nodes import CallExpr as CallExprAlias
        from .ast_nodes import Identifier as IdentAlias
        return PrintStmt(CallExprAlias(IdentAlias("print"), args))

    def parse_return(self) -> ReturnStmt:
        self.expect("RETURN")
        expr = self.parse_expression()
        return ReturnStmt(expr)

    def parse_const(self) -> ConstDecl:
        self.expect("CONST")
        name: str = self.expect("IDENT").value
        self.expect("EQUAL")
        expr = self.parse_expression()
        return ConstDecl(name, expr)

    def parse_if(self) -> IfStmt:
        self.expect("IF")
        condition = self.parse_expression()
        then_body: list[ASTNode] = self.parse_block()
        else_body: list[ASTNode] = []
        self.skip_newlines()
        if self.match("ELSE"):
            else_body = self.parse_block()
        return IfStmt(condition, then_body, else_body)

    def parse_for(self) -> ForStmt:
        self.expect("FOR")
        var_name: str = self.expect("IDENT").value
        self.expect("IN")
        iterable = self.parse_expression()
        body: list[ASTNode] = self.parse_block()
        return ForStmt(var_name, iterable, body)

    def parse_while(self) -> WhileStmt:
        self.expect("WHILE")
        condition = self.parse_expression()
        body: list[ASTNode] = self.parse_block()
        return WhileStmt(condition, body)

    def parse_try(self) -> TryStmt:
        self.expect("TRY")
        try_body = self.parse_block()
        self.skip_newlines()
        catch_var = None
        catch_body: list[ASTNode] = []
        if self.match("CATCH"):
            if self.current().kind == "LPAREN":
                self.expect("LPAREN")
                catch_var = self.expect("IDENT").value
                self.expect("RPAREN")
            catch_body = self.parse_block()
        return TryStmt(try_body, catch_var, catch_body)

    def parse_ask_stmt(self, target: str | None) -> AskStmt:
        self.expect("ASK")
        model: str = self.expect("IDENT").value
        self.expect("COLON")
        prompt = self.parse_expression()
        schema: Expr | None = None
        if self.match("PIPE"):
            schema = self.parse_expression()
        return AskStmt(target, model, prompt, schema)

    def parse_schema(self) -> SchemaDecl:
        """Parse: schema Name { field: type, field: type }"""
        self.expect("SCHEMA")
        name = self.expect("IDENT").value
        self.skip_newlines()
        self.expect("LBRACE")
        self.skip_newlines()
        fields: list[tuple[str, str]] = []
        while self.current().kind != "RBRACE" and self.current().kind != "EOF":
            field_name = self.expect("IDENT").value
            self.expect("COLON")
            field_type = self.expect("IDENT").value
            fields.append((field_name, field_type))
            self.skip_newlines()
            if self.current().kind == "COMMA":
                self.pos += 1
            self.skip_newlines()
        self.expect("RBRACE")
        return SchemaDecl(name, fields)

    def parse_async_function(self) -> AsyncFunctionDecl:
        """Parse: async fn name(params) { body }"""
        self.expect("ASYNC")
        self.expect("FN")
        name = self.expect("IDENT").value
        self.expect("LPAREN")
        params: list[str] = []
        param_types: list[str | None] = []
        if self.current().kind != "RPAREN":
            p = self.expect("IDENT").value
            params.append(p)
            if self.match("COLON"):
                param_types.append(self.expect("IDENT").value)
            else:
                param_types.append(None)
            while self.match("COMMA"):
                p = self.expect("IDENT").value
                params.append(p)
                if self.match("COLON"):
                    param_types.append(self.expect("IDENT").value)
                else:
                    param_types.append(None)
        self.expect("RPAREN")
        return_type: str | None = None
        if self.match("COLON"):
            return_type = self.expect("IDENT").value
        body = self.parse_block()
        return AsyncFunctionDecl(name, params, param_types, return_type, body)

    def parse_on_reload(self) -> OnReloadBlock:
        """Parse: on_reload { body }"""
        self.expect("ON_RELOAD")
        body = self.parse_block()
        return OnReloadBlock(body)

    # --- Expression Parser (Pratt / Top-Down Operator Precedence) ---

    def parse_expression(self, min_prec: int = 0) -> Expr:
        self._expr_depth += 1
        if self._expr_depth > self.MAX_EXPR_DEPTH:
            self._expr_depth -= 1
            tok = self.current()
            if self.recovery_mode:
                self.errors.append(ParseError(
                    "Expression too deeply nested", tok.line, tok.col, self.source
                ))
                return Identifier("__expr_depth_exceeded__")
            raise ParseError(
                "Expression too deeply nested", tok.line, tok.col, self.source
            )
        try:
            left = self.parse_prefix()
            while True:
                # Check if current token is a binary operator with sufficient precedence
                op_prec = BINARY_OP_PRECEDENCE.get(self.current().kind, 0)
                if op_prec <= min_prec:
                    break
                left = self.parse_infix(left, op_prec)
            return left
        finally:
            self._expr_depth -= 1

    def parse_prefix(self) -> Expr:
        tok = self.current()

        # Literals
        if tok.kind == "NUMBER":
            self.pos += 1
            val = float(tok.value)
            if val == int(val) and "." not in tok.value:
                return NumberLiteral(int(val))
            return NumberLiteral(val)

        if tok.kind == "STRING":
            self.pos += 1
            return StringLiteral(tok.value)

        if tok.kind == "FSTRING":
            self.pos += 1
            return self._parse_fstring_content(tok.value)

        if tok.kind == "TRUE":
            self.pos += 1
            return BoolLiteral(True)

        if tok.kind == "FALSE":
            self.pos += 1
            return BoolLiteral(False)

        if tok.kind == "NONE":
            self.pos += 1
            return NoneLiteral()

        # Identifier (may be followed by call, member access, etc.)
        if tok.kind == "IDENT":
            self.pos += 1
            return Identifier(tok.value)

        # Unary operators
        if tok.kind == "MINUS":
            self.pos += 1
            operand = self.parse_expression(PREC_UNARY)
            return UnaryOp("-", operand)

        if tok.kind in ("NOT", "BANG"):
            self.pos += 1
            operand = self.parse_expression(PREC_UNARY)
            return UnaryOp("not", operand)

        # Parenthesized expression
        if tok.kind == "LPAREN":
            self.pos += 1
            expr = self.parse_expression()
            self.expect("RPAREN")
            return expr

        # List literal
        if tok.kind == "LBRACKET":
            return self.parse_list_literal()

        # Dict literal
        if tok.kind == "LBRACE":
            return self.parse_dict_literal()

        # Ask expression (standalone, not in assignment context)
        if tok.kind == "ASK":
            self.expect("ASK")
            model: str = self.expect("IDENT").value
            self.expect("COLON")
            prompt = self.parse_expression()
            schema: Expr | None = None
            if self.match("PIPE"):
                schema = self.parse_expression()
            return AskExpr(model, prompt, schema)

        # Await expression: await expr
        if tok.kind == "AWAIT":
            self.pos += 1
            expr = self.parse_expression(PREC_UNARY)
            return AwaitExpr(expr)

        # Stream expression: stream expr
        if tok.kind == "STREAM":
            self.pos += 1
            expr = self.parse_expression(PREC_UNARY)
            return StreamExpr(expr)

        raise ParseError(
            f"Unexpected token in expression: {tok.kind} ('{tok.value}')",
            tok.line, tok.col, self.source
        )

    def parse_infix(self, left: Expr, prec: int) -> Expr:
        tok = self.current()

        # Member access: expr.identifier
        if tok.kind == "DOT":
            self.pos += 1
            member = self.expect("IDENT").value
            return MemberAccess(left, member)

        # Index access: expr[index]
        if tok.kind == "LBRACKET":
            self.pos += 1
            index = self.parse_expression()
            self.expect("RBRACKET")
            return IndexAccess(left, index)

        # Function call: expr(args)
        if tok.kind == "LPAREN":
            self.pos += 1
            args: list[Expr] = []
            if self.current().kind != "RPAREN":
                args.append(self._parse_call_arg())
                while self.match("COMMA"):
                    args.append(self._parse_call_arg())
            self.expect("RPAREN")
            return CallExpr(left, args)

        # Pipe operator: left |> right
        if tok.kind == "PIPE_GT":
            self.pos += 1
            right = self.parse_expression(prec)
            return PipeExpr(left, right)

        # Binary operators
        if tok.kind in BINARY_OP_PRECEDENCE:
            op = self._token_to_binary_op(tok.kind)
            self.pos += 1
            right = self.parse_expression(prec)
            return BinaryOp(op, left, right)

        # This shouldn't happen if precedence table is correct
        raise ParseError(
            f"Unexpected infix token: {tok.kind}",
            tok.line, tok.col, self.source
        )

    @staticmethod
    def _token_to_binary_op(kind: str) -> str:
        mapping = {
            "PLUS": "+",
            "MINUS": "-",
            "STAR": "*",
            "SLASH": "/",
            "PERCENT": "%",
            "GT": ">",
            "LT": "<",
            "GTE": ">=",
            "LTE": "<=",
            "EQ": "==",
            "NEQ": "!=",
            "AND": "and",
            "OR": "or",
        }
        return mapping.get(kind, kind)

    def _parse_call_arg(self) -> Expr:
        """Parse a single call argument, which may be a keyword argument (name=expr)."""
        if self.current().kind == "IDENT" and self.peek().kind == "EQUAL":
            # Keyword argument: name=expr
            name = self.current().value
            self.pos += 2  # skip IDENT and EQUAL
            value = self.parse_expression()
            return KwArg(name, value)
        return self.parse_expression()

    def parse_list_literal(self) -> ListLiteral:
        self.expect("LBRACKET")
        elements: list[Expr] = []
        self.skip_newlines()
        if self.current().kind != "RBRACKET":
            elements.append(self.parse_expression())
            while self.match("COMMA"):
                self.skip_newlines()
                if self.current().kind == "RBRACKET":
                    break
                elements.append(self.parse_expression())
            self.skip_newlines()
        self.expect("RBRACKET")
        return ListLiteral(elements)

    def parse_dict_literal(self) -> DictLiteral:
        self.expect("LBRACE")
        pairs: list[tuple] = []
        self.skip_newlines()
        # Empty dict: {}
        if self.current().kind == "RBRACE":
            self.expect("RBRACE")
            return DictLiteral(pairs)
        # Check that the first token after { can be a key
        # If not, it's an empty dict with stray tokens
        if self.current().kind not in ("STRING", "FSTRING", "NUMBER", "IDENT", "TRUE", "FALSE", "NONE", "LBRACKET", "LPAREN"):
            raise ParseError(
                f"Unexpected token in dict literal: {self.current().kind}",
                self.current().line, self.current().col, self.source
            )
        key = self.parse_expression()
        self.expect("COLON")
        value = self.parse_expression()
        pairs.append((key, value))
        while self.match("COMMA"):
            self.skip_newlines()
            if self.current().kind == "RBRACE":
                break
            key = self.parse_expression()
            self.expect("COLON")
            value = self.parse_expression()
            pairs.append((key, value))
        self.skip_newlines()
        self.expect("RBRACE")
        return DictLiteral(pairs)

    def _parse_fstring_content(self, raw: str) -> FString:
        """Parse the content of an f-string into literal and expression parts.

        The raw string may contain {expr} interpolation markers.
        We split on { } to produce alternating string/expr parts.
        """
        parts: list = []
        i = 0
        current_str = ""
        while i < len(raw):
            if raw[i] == "\\" and i + 1 < len(raw):
                # Handle escape sequences
                esc = raw[i + 1]
                if esc == "n":
                    current_str += "\n"
                elif esc == "t":
                    current_str += "\t"
                elif esc == "\\":
                    current_str += "\\"
                elif esc == '"':
                    current_str += '"'
                elif esc == "'":
                    current_str += "'"
                elif esc == "{":
                    current_str += "{"
                elif esc == "}":
                    current_str += "}"
                else:
                    current_str += raw[i] + raw[i + 1]
                i += 2
            elif raw[i] == "{":
                # Save current string part
                if current_str:
                    parts.append(current_str)
                    current_str = ""
                # Find matching }
                j = i + 1
                depth = 1
                while j < len(raw) and depth > 0:
                    if raw[j] == "{":
                        depth += 1
                    elif raw[j] == "}":
                        depth -= 1
                    j += 1
                expr_str = raw[i + 1:j - 1].strip()
                if expr_str:
                    # Parse the expression inside {}
                    expr_tokens = lex(expr_str)
                    expr_parser = Parser(expr_tokens, expr_str)
                    expr = expr_parser.parse_expression()
                    parts.append(expr)
                i = j
            else:
                current_str += raw[i]
                i += 1
        if current_str:
            parts.append(current_str)
        return FString(parts)


def parse_source(source: str) -> Program:
    return Parser(lex(source), source).parse()


@dataclass
class ParseResult:
    """Result of parsing with error recovery."""
    program: Program
    errors: list[ParseError]


def parse_source_with_recovery(source: str) -> ParseResult:
    """Parse source code with error recovery.

    Instead of stopping at the first error, this collects all parse errors
    and returns both the partial AST and the list of errors.
    """
    tokens = lex(source)
    parser = Parser(tokens, source)
    parser.recovery_mode = True
    program = parser.parse()
    return ParseResult(program=program, errors=parser.errors)
