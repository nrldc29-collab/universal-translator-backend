"""AILang lexer — tokenises .ai source files."""
import re
from typing import Any, List, Optional
from dataclasses import dataclass
from typing import List, Optional

TT = type("TT", (), {
    # literals
    "INT": "INT", "FLOAT": "FLOAT", "STRING": "STRING", "FSTRING": "FSTRING",
    "TRUE": "TRUE", "FALSE": "FALSE", "NULL": "NULL",
    # identifiers / keywords
    "IDENT": "IDENT",
    "FN": "FN", "AGENT": "AGENT", "MODEL": "MODEL", "CONST": "CONST",
    "RETURN": "RETURN", "IF": "IF", "ELSE": "ELSE", "FOR": "FOR", "IN": "IN",
    "BREAK": "BREAK", "ASK": "ASK", "INSTRUCTIONS": "INSTRUCTIONS", "TOOLS": "TOOLS",
    # operators
    "PLUS": "PLUS", "MINUS": "MINUS", "STAR": "STAR", "SLASH": "SLASH",
    "EQ": "EQ", "NEQ": "NEQ", "LT": "LT", "GT": "GT", "LTE": "LTE", "GTE": "GTE",
    "AND": "AND", "OR": "OR", "NOT": "NOT",
    "ASSIGN": "ASSIGN", "PLUS_ASSIGN": "PLUS_ASSIGN",
    # punctuation
    "LPAREN": "LPAREN", "RPAREN": "RPAREN",
    "LBRACE": "LBRACE", "RBRACE": "RBRACE",
    "LBRACKET": "LBRACKET", "RBRACKET": "RBRACKET",
    "COMMA": "COMMA", "COLON": "COLON", "DOT": "DOT",
    "ARROW": "ARROW",
    # misc
    "NEWLINE": "NEWLINE", "EOF": "EOF",
})()

KEYWORDS = {
    "fn": TT.FN, "agent": TT.AGENT, "model": TT.MODEL, "const": TT.CONST,
    "return": TT.RETURN, "if": TT.IF, "else": TT.ELSE, "for": TT.FOR, "in": TT.IN,
    "break": TT.BREAK, "ask": TT.ASK,
    "true": TT.TRUE, "false": TT.FALSE, "null": TT.NULL,
    "and": TT.AND, "or": TT.OR, "not": TT.NOT,
    "instructions": TT.INSTRUCTIONS, "tools": TT.TOOLS,
}

SINGLE_CHAR = {
    "+": TT.PLUS, "-": TT.MINUS, "*": TT.STAR, "/": TT.SLASH,
    "(": TT.LPAREN, ")": TT.RPAREN,
    "{": TT.LBRACE, "}": TT.RBRACE,
    "[": TT.LBRACKET, "]": TT.RBRACKET,
    ",": TT.COMMA, ":": TT.COLON, ".": TT.DOT,
}

@dataclass
class Token:
    type: str
    value: Any
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"


class LexerError(Exception):
    pass


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    def error(self, msg: str):
        raise LexerError(f"Lexer error at {self.line}:{self.col}: {msg}")

    def peek(self, offset=0) -> Optional[str]:
        i = self.pos + offset
        return self.source[i] if i < len(self.source) else None

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def add(self, ttype: str, value, line: int, col: int):
        self.tokens.append(Token(ttype, value, line, col))

    def skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self.peek()
            if ch in (" ", "\t", "\r"):
                self.advance()
            elif ch == "#":
                while self.pos < len(self.source) and self.peek() != "\n":
                    self.advance()
            else:
                break

    def read_string(self, quote_char: str) -> str:
        """Read a quoted string, handling escape sequences."""
        result = []
        self.advance()  # consume opening quote
        while self.pos < len(self.source):
            ch = self.peek()
            if ch is None:
                self.error("Unterminated string literal")
            if ch == "\\":
                self.advance()
                esc = self.advance()
                result.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "'": "'", "\\": "\\"}.get(esc, esc))
            elif ch == quote_char:
                self.advance()  # consume closing quote
                break
            else:
                result.append(self.advance())
        return "".join(result)

    def read_fstring(self, quote_char: str) -> str:
        """Read an f-string, returning raw content including {expr} parts."""
        result = []
        self.advance()  # consume opening quote
        while self.pos < len(self.source):
            ch = self.peek()
            if ch is None:
                self.error("Unterminated f-string")
            if ch == quote_char:
                self.advance()
                break
            elif ch == "\\":
                self.advance()
                esc = self.advance()
                result.append({"n": "\n", "t": "\t"}.get(esc, esc))
            else:
                result.append(self.advance())
        return "".join(result)

    def read_number(self) -> Token:
        start_col = self.col
        digits = []
        is_float = False
        while self.pos < len(self.source) and (self.peek().isdigit() or self.peek() == "."):
            ch = self.peek()
            if ch == ".":
                if is_float:
                    break
                # look ahead: next char must be digit
                if self.peek(1) is None or not self.peek(1).isdigit():
                    break
                is_float = True
            digits.append(self.advance())
        raw = "".join(digits)
        if is_float:
            return Token(TT.FLOAT, float(raw), self.line, start_col)
        return Token(TT.INT, int(raw), self.line, start_col)

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break

            start_line = self.line
            start_col = self.col
            ch = self.peek()

            # newlines
            if ch == "\n":
                self.advance()
                self.add(TT.NEWLINE, "\n", start_line, start_col)
                continue

            # f-strings
            if ch == "f" and self.peek(1) in ('"', "'"):
                self.advance()  # consume 'f'
                q = self.peek()
                raw = self.read_fstring(q)
                self.add(TT.FSTRING, raw, start_line, start_col)
                continue

            # strings
            if ch in ('"', "'"):
                raw = self.read_string(ch)
                self.add(TT.STRING, raw, start_line, start_col)
                continue

            # numbers
            if ch.isdigit():
                tok = self.read_number()
                tok.line = start_line
                tok.col = start_col
                self.tokens.append(tok)
                continue

            # identifiers / keywords
            if ch.isalpha() or ch == "_":
                buf = []
                while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == "_"):
                    buf.append(self.advance())
                word = "".join(buf)
                ttype = KEYWORDS.get(word, TT.IDENT)
                self.add(ttype, word, start_line, start_col)
                continue

            # two-char operators
            if ch == "=" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.add(TT.EQ, "==", start_line, start_col); continue
            if ch == "!" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.add(TT.NEQ, "!=", start_line, start_col); continue
            if ch == "<" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.add(TT.LTE, "<=", start_line, start_col); continue
            if ch == ">" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.add(TT.GTE, ">=", start_line, start_col); continue
            if ch == "-" and self.peek(1) == ">":
                self.advance(); self.advance()
                self.add(TT.ARROW, "->", start_line, start_col); continue
            if ch == "+" and self.peek(1) == "=":
                self.advance(); self.advance()
                self.add(TT.PLUS_ASSIGN, "+=", start_line, start_col); continue
            if ch == "|" and self.peek(1) == "|": 
                self.advance(); self.advance()
                self.add(TT.OR, "or", start_line, start_col); continue
            if ch == "&" and self.peek(1) == "&":
                self.advance(); self.advance()
                self.add(TT.AND, "and", start_line, start_col); continue

            # single-char operators
            if ch == "<":
                self.advance(); self.add(TT.LT, "<", start_line, start_col); continue
            if ch == ">":
                self.advance(); self.add(TT.GT, ">", start_line, start_col); continue
            if ch == "=":
                self.advance(); self.add(TT.ASSIGN, "=", start_line, start_col); continue

            if ch in SINGLE_CHAR:
                self.advance()
                self.add(SINGLE_CHAR[ch], ch, start_line, start_col)
                continue

            self.error(f"Unexpected character: {ch!r}")

        self.add(TT.EOF, None, self.line, self.col)
        return self.tokens


def tokenize(source: str) -> List[Token]:
    return Lexer(source).tokenize()
