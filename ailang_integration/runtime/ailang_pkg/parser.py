"""AILang parser — builds an AST from a token stream."""
from typing import List, Any, Optional
from .lexer import tokenize, Token, TT, LexerError
from .ast_nodes import *


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = [t for t in tokens if t.type != TT.NEWLINE]
        self.pos = 0

    def peek(self, offset=0) -> Token:
        i = self.pos + offset
        if i < len(self.tokens):
            return self.tokens[i]
        return self.tokens[-1]  # EOF

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def check(self, *types) -> bool:
        return self.peek().type in types

    def match(self, *types) -> Optional[Token]:
        if self.check(*types):
            return self.advance()
        return None

    def expect(self, ttype: str, msg: str = "") -> Token:
        if self.check(ttype):
            return self.advance()
        tok = self.peek()
        raise ParseError(f"Expected {ttype}{' ' + msg if msg else ''}, got {tok.type!r} ({tok.value!r}) at {tok.line}:{tok.col}")

    # ------------------------------------------------------------------ #
    #  Top-level                                                           #
    # ------------------------------------------------------------------ #

    def parse(self) -> Program:
        body = []
        while not self.check(TT.EOF):
            node = self.parse_top_level()
            if node is not None:
                body.append(node)
        return Program(body=body)

    def parse_top_level(self):
        tok = self.peek()
        if tok.type == TT.MODEL:
            return self.parse_model_decl()
        if tok.type == TT.CONST:
            return self.parse_const_decl()
        if tok.type == TT.FN:
            return self.parse_fn_decl()
        if tok.type == TT.AGENT:
            return self.parse_agent_decl()
        # skip stray tokens
        self.advance()
        return None

    # ------------------------------------------------------------------ #
    #  Declarations                                                        #
    # ------------------------------------------------------------------ #

    def parse_model_decl(self) -> ModelDecl:
        self.expect(TT.MODEL)
        name = self.expect(TT.IDENT).value
        self.expect(TT.LBRACE)
        props = {}
        while not self.check(TT.RBRACE, TT.EOF):
            key = self.expect(TT.IDENT).value
            self.expect(TT.COLON)
            val = self.expect(TT.STRING).value
            props[key] = val
        self.expect(TT.RBRACE)
        return ModelDecl(
            name=name,
            provider=props.get("provider", "anthropic"),
            model_name=props.get("name", props.get("model", "claude-haiku-4-5-20251001")),
        )

    def parse_const_decl(self) -> ConstDecl:
        self.expect(TT.CONST)
        name = self.expect(TT.IDENT).value
        self.expect(TT.ASSIGN)
        value = self.parse_expr()
        return ConstDecl(name=name, value=value)

    def parse_fn_decl(self, inside_agent=False) -> FnDecl:
        self.expect(TT.FN)
        name = self.expect(TT.IDENT).value
        self.expect(TT.LPAREN)
        params = self.parse_param_list()
        self.expect(TT.RPAREN)
        # optional return type annotation: ): string or -> string
        if self.check(TT.ARROW):
            self.advance()  # consume ->
            self.advance()  # consume type ident
        elif self.check(TT.COLON):
            self.advance()  # consume :
            self.advance()  # consume type ident
        body = self.parse_block()
        return FnDecl(name=name, params=params, body=body)

    def parse_param_list(self) -> List[str]:
        params = []
        while not self.check(TT.RPAREN, TT.EOF):
            name = self.expect(TT.IDENT).value
            if self.match(TT.COLON):
                self.advance()  # consume type annotation
            params.append(name)
            if not self.match(TT.COMMA):
                break
        return params

    def parse_agent_decl(self) -> AgentDecl:
        self.expect(TT.AGENT)
        name = self.expect(TT.IDENT).value
        # optional (ModelRef)
        model_ref = "claude"
        if self.match(TT.LPAREN):
            model_ref = self.expect(TT.IDENT).value
            self.expect(TT.RPAREN)
        self.expect(TT.LBRACE)
        instructions = None
        tools: List[str] = []
        methods: List[FnDecl] = []
        while not self.check(TT.RBRACE, TT.EOF):
            tok = self.peek()
            if tok.type == TT.INSTRUCTIONS:
                self.advance()
                self.expect(TT.COLON)
                instructions = self.expect(TT.STRING).value
            elif tok.type == TT.TOOLS:
                self.advance()
                self.expect(TT.COLON)
                tools = self.parse_tools_list()
            elif tok.type == TT.FN:
                methods.append(self.parse_fn_decl(inside_agent=True))
            else:
                self.advance()
        self.expect(TT.RBRACE)
        return AgentDecl(name=name, model_ref=model_ref, instructions=instructions, tools=tools, methods=methods)

    def parse_tools_list(self) -> List[str]:
        tools = []
        while not self.check(TT.NEWLINE, TT.FN, TT.INSTRUCTIONS, TT.RBRACE, TT.EOF):
            if self.check(TT.IDENT):
                tools.append(self.advance().value)
            if not self.match(TT.COMMA):
                break
        return tools

    # ------------------------------------------------------------------ #
    #  Statements                                                          #
    # ------------------------------------------------------------------ #

    def parse_block(self) -> List[Any]:
        self.expect(TT.LBRACE)
        stmts = []
        while not self.check(TT.RBRACE, TT.EOF):
            stmt = self.parse_stmt()
            if stmt is not None:
                stmts.append(stmt)
        self.expect(TT.RBRACE)
        return stmts

    def parse_stmt(self):
        tok = self.peek()

        if tok.type == TT.RETURN:
            self.advance()
            value = self.parse_expr()
            return ReturnStmt(value=value)

        if tok.type == TT.IF:
            return self.parse_if_stmt()

        if tok.type == TT.FOR:
            return self.parse_for_stmt()

        if tok.type == TT.BREAK:
            self.advance()
            return BreakStmt()

        # assignment or expr-stmt
        if tok.type in (TT.IDENT, TT.INSTRUCTIONS, TT.TOOLS):
            # lookahead: IDENT ASSIGN or IDENT PLUS_ASSIGN
            nxt = self.peek(1)
            if nxt.type == TT.ASSIGN:
                name = self.advance().value
                self.advance()  # consume =
                value = self.parse_expr()
                return AssignStmt(name=name, value=value)
            if nxt.type == TT.PLUS_ASSIGN:
                name = self.advance().value
                self.advance()  # consume +=
                rhs = self.parse_expr()
                # desugar to name = name + rhs
                return AssignStmt(name=name, value=BinOp(op="+", left=Identifier(name=name), right=rhs))

        expr = self.parse_expr()
        return ExprStmt(expr=expr)

    def parse_if_stmt(self) -> IfStmt:
        self.expect(TT.IF)
        condition = self.parse_expr()
        then_body = self.parse_block()
        else_body = []
        if self.match(TT.ELSE):
            if self.check(TT.IF):
                else_body = [self.parse_if_stmt()]
            else:
                else_body = self.parse_block()
        return IfStmt(condition=condition, then_body=then_body, else_body=else_body)

    def parse_for_stmt(self) -> ForStmt:
        self.expect(TT.FOR)
        var = self.expect(TT.IDENT).value
        self.expect(TT.IN)
        iterable = self.parse_expr()
        body = self.parse_block()
        return ForStmt(var=var, iterable=iterable, body=body)

    # ------------------------------------------------------------------ #
    #  Expressions                                                         #
    # ------------------------------------------------------------------ #

    def parse_expr(self) -> Any:
        return self.parse_or()

    def parse_or(self) -> Any:
        left = self.parse_and()
        while self.check(TT.OR):
            self.advance()
            right = self.parse_and()
            left = BinOp(op="or", left=left, right=right)
        return left

    def parse_and(self) -> Any:
        left = self.parse_not()
        while self.check(TT.AND):
            self.advance()
            right = self.parse_not()
            left = BinOp(op="and", left=left, right=right)
        return left

    def parse_not(self) -> Any:
        if self.match(TT.NOT):
            return UnaryOp(op="not", operand=self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> Any:
        left = self.parse_addition()
        cmp_ops = {TT.EQ: "==", TT.NEQ: "!=", TT.LT: "<", TT.GT: ">", TT.LTE: "<=", TT.GTE: ">="}
        while self.peek().type in cmp_ops:
            op = cmp_ops[self.advance().type]
            right = self.parse_addition()
            left = BinOp(op=op, left=left, right=right)
        return left

    def parse_addition(self) -> Any:
        left = self.parse_multiplication()
        while self.check(TT.PLUS, TT.MINUS):
            op = self.advance().value
            right = self.parse_multiplication()
            left = BinOp(op=op, left=left, right=right)
        return left

    def parse_multiplication(self) -> Any:
        left = self.parse_unary()
        while self.check(TT.STAR, TT.SLASH):
            op = self.advance().value
            right = self.parse_unary()
            left = BinOp(op=op, left=left, right=right)
        return left

    def parse_unary(self) -> Any:
        if self.match(TT.MINUS):
            return UnaryOp(op="-", operand=self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self) -> Any:
        """Handle dot-access, method calls, indexing."""
        expr = self.parse_primary()
        while True:
            if self.check(TT.DOT):
                self.advance()
                method = self.expect(TT.IDENT).value
                if self.check(TT.LPAREN):
                    self.advance()
                    args = self.parse_arg_list()
                    self.expect(TT.RPAREN)
                    obj = expr.name if isinstance(expr, Identifier) else str(expr)
                    expr = MethodCallExpr(obj=obj, method=method, args=args)
                else:
                    # attribute access — treat as method call with no args for simplicity
                    obj = expr.name if isinstance(expr, Identifier) else str(expr)
                    expr = MethodCallExpr(obj=obj, method=method, args=[])
            elif self.check(TT.LBRACKET):
                self.advance()
                idx = self.parse_expr()
                self.expect(TT.RBRACKET)
                expr = IndexExpr(obj=expr, index=idx)
            else:
                break
        return expr

    def parse_primary(self) -> Any:
        tok = self.peek()

        # ask <model>: <expr>
        if tok.type == TT.ASK:
            self.advance()
            model_ref = self.expect(TT.IDENT).value
            self.expect(TT.COLON)
            prompt = self.parse_expr()
            return AskExpr(model_ref=model_ref, prompt=prompt)

        # literals
        if tok.type == TT.INT:
            self.advance()
            return Literal(value=tok.value)
        if tok.type == TT.FLOAT:
            self.advance()
            return Literal(value=tok.value)
        if tok.type == TT.STRING:
            self.advance()
            return Literal(value=tok.value)
        if tok.type == TT.FSTRING:
            self.advance()
            return self.build_fstring(tok.value)
        if tok.type == TT.TRUE:
            self.advance()
            return Literal(value=True)
        if tok.type == TT.FALSE:
            self.advance()
            return Literal(value=False)
        if tok.type == TT.NULL:
            self.advance()
            return Literal(value=None)

        # list literal
        if tok.type == TT.LBRACKET:
            self.advance()
            elements = []
            while not self.check(TT.RBRACKET, TT.EOF):
                elements.append(self.parse_expr())
                if not self.match(TT.COMMA):
                    break
            self.expect(TT.RBRACKET)
            return ListLiteral(elements=elements)

        # dict literal
        if tok.type == TT.LBRACE:
            self.advance()
            pairs = []
            while not self.check(TT.RBRACE, TT.EOF):
                key = self.parse_expr()
                self.expect(TT.COLON)
                val = self.parse_expr()
                pairs.append((key, val))
                if not self.match(TT.COMMA):
                    break
            self.expect(TT.RBRACE)
            return DictLiteral(pairs=pairs)

        # grouped expr or call
        if tok.type == TT.LPAREN:
            self.advance()
            expr = self.parse_expr()
            self.expect(TT.RPAREN)
            return expr

        # identifier or function call
        if tok.type == TT.IDENT:
            name = self.advance().value
            if self.check(TT.LPAREN):
                self.advance()
                args = self.parse_arg_list()
                self.expect(TT.RPAREN)
                return CallExpr(func=name, args=args)
            return Identifier(name=name)

        # treat keyword-like tokens as identifiers when used as variable names
        if tok.type in (TT.INSTRUCTIONS, TT.TOOLS, TT.IN, TT.MODEL):
            name = self.advance().value
            if self.check(TT.LPAREN):
                self.advance()
                args = self.parse_arg_list()
                self.expect(TT.RPAREN)
                return CallExpr(func=name, args=args)
            return Identifier(name=name)
        raise ParseError(f"Unexpected token {tok.type!r} ({tok.value!r}) at {tok.line}:{tok.col}")

    def parse_arg_list(self) -> List[Any]:
        args = []
        while not self.check(TT.RPAREN, TT.EOF):
            args.append(self.parse_expr())
            if not self.match(TT.COMMA):
                break
        return args

    def build_fstring(self, raw: str) -> FStringExpr:
        """Parse f-string content into parts (strings and expressions)."""
        parts = []
        i = 0
        buf = []
        while i < len(raw):
            if raw[i] == "{" and i + 1 < len(raw) and raw[i+1] != "{":
                if buf:
                    parts.append(Literal(value="".join(buf)))
                    buf = []
                # find closing }
                depth = 1
                j = i + 1
                while j < len(raw) and depth > 0:
                    if raw[j] == "{": depth += 1
                    elif raw[j] == "}": depth -= 1
                    j += 1
                expr_src = raw[i+1:j-1]
                try:
                    sub_tokens = tokenize(expr_src + "\n")
                    sub_parser = Parser(sub_tokens)
                    expr = sub_parser.parse_expr()
                    parts.append(expr)
                except Exception:
                    parts.append(Literal(value="{" + expr_src + "}"))
                i = j
            elif raw[i:i+2] == "{{":
                buf.append("{")
                i += 2
            elif raw[i:i+2] == "}}":
                buf.append("}")
                i += 2
            else:
                buf.append(raw[i])
                i += 1
        if buf:
            parts.append(Literal(value="".join(buf)))
        return FStringExpr(parts=parts)


def parse_source(source: str) -> Program:
    """Parse AILang source code and return a Program AST."""
    tokens = tokenize(source + "\n")
    return Parser(tokens).parse()
