from dataclasses import dataclass
from typing import Dict, List, Set

from .errors import LexError


@dataclass
class Token:
    kind: str
    value: str
    line: int
    col: int


KEYWORDS: Set[str] = {
    "model", "fn", "print", "return", "if", "else", "for", "in",
    "ask", "try", "catch", "import", "agent", "while", "break",
    "continue", "const", "true", "false", "none", "not", "and", "or",
    "async", "await", "stream", "schema", "on_reload",
}

SINGLE_CHAR: Dict[str, str] = {
    "{": "LBRACE",
    "}": "RBRACE",
    "(": "LPAREN",
    ")": "RPAREN",
    "[": "LBRACKET",
    "]": "RBRACKET",
    ",": "COMMA",
    ":": "COLON",
    ".": "DOT",
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "%": "PERCENT",
    "=": "EQUAL",
    "|": "PIPE",
    "!": "NOT",
    ">": "GT",
    "<": "LT",
}


def _has_interpolation(value: str) -> bool:
    """Check if a string contains {identifier} interpolation patterns."""
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            i += 2  # Skip escaped characters
            continue
        if value[i] == "{":
            # Check if content looks like an identifier (letter/underscore followed by alnum)
            j = i + 1
            if j < len(value) and (value[j].isalpha() or value[j] == "_"):
                while j < len(value) and (value[j].isalnum() or value[j] == "_" or value[j] == "."):
                    j += 1
                if j < len(value) and value[j] == "}":
                    return True
        i += 1
    return False


def lex(source: str) -> List[Token]:
    tokens: List[Token] = []
    i: int = 0
    line: int = 1
    col: int = 1

    def add(kind: str, value: str, start_col: int) -> None:
        tokens.append(Token(kind, value, line, start_col))

    def error(message: str, start_line: int, start_col: int) -> None:
        raise LexError(message, start_line, start_col, source)

    while i < len(source):
        ch = source[i]

        # Skip UTF-8 BOM
        if ch == "\ufeff":
            i += 1
            col += 1
            continue

        # Whitespace
        if ch in " \t\r":
            i += 1
            col += 1
            continue

        # Newlines
        if ch == "\n":
            tokens.append(Token("NEWLINE", "\n", line, col))
            i += 1
            line += 1
            col = 1
            continue

        # Comments
        if ch == "#":
            while i < len(source) and source[i] != "\n":
                i += 1
                col += 1
            continue

        # Strings and f-strings
        if ch == '"' or ch == "'" or (ch == 'f' and i + 1 < len(source) and source[i + 1] in '"\''):
            start_col = col
            is_fstring = (ch == 'f')
            quote_char = source[i + 1] if is_fstring else ch
            if is_fstring:
                i += 2
                col += 2
            else:
                i += 1
                col += 1
            value = ""
            while i < len(source) and source[i] != quote_char:
                if source[i] == "\n":
                    # Unescaped newline in string — report error
                    error("Unterminated string literal (newline in string)", line, start_col)
                if source[i] == "\\" and i + 1 < len(source):
                    value += source[i] + source[i + 1]
                    i += 2
                    col += 2
                else:
                    value += source[i]
                    i += 1
                    col += 1
            if i >= len(source):
                error("Unterminated string literal", line, start_col)
            i += 1
            col += 1
            add("FSTRING" if is_fstring else "STRING", value, start_col)
            continue

        # Numbers
        if ch.isdigit():
            start_col = col
            value = ""
            dot_count = 0
            while i < len(source) and (source[i].isdigit() or source[i] == "."):
                if source[i] == ".":
                    dot_count += 1
                    if dot_count > 1:
                        # Second dot — stop before it (it's a member access like 42.toString)
                        break
                value += source[i]
                i += 1
                col += 1
            # Reject trailing dot like "42." — require "42.0"
            if value.endswith("."):
                value = value[:-1]
                i -= 1
                col -= 1
            add("NUMBER", value, start_col)
            continue

        # Identifiers and keywords
        if ch.isalpha() or ch == "_":
            start_col = col
            value = ""
            while i < len(source) and (source[i].isalnum() or source[i] == "_"):
                value += source[i]
                i += 1
                col += 1
            if value in KEYWORDS:
                kind = value.upper()
            else:
                kind = "IDENT"
            add(kind, value, start_col)
            continue

        # Two-character operators
        start_col = col
        if i + 1 < len(source):
            two = source[i:i + 2]
            if two == "==":
                add("EQ", "==", start_col)
                i += 2
                col += 2
                continue
            if two == "!=":
                add("NEQ", "!=", start_col)
                i += 2
                col += 2
                continue
            if two == ">=":
                add("GTE", ">=", start_col)
                i += 2
                col += 2
                continue
            if two == "<=":
                add("LTE", "<=", start_col)
                i += 2
                col += 2
                continue
            if two == "&&":
                add("AND", "&&", start_col)
                i += 2
                col += 2
                continue
            if two == "||":
                add("OR", "||", start_col)
                i += 2
                col += 2
                continue
            if two == "->":
                add("MINUS_GT", "->", start_col)
                i += 2
                col += 2
                continue
            if two == "|>":
                add("PIPE_GT", "|>", start_col)
                i += 2
                col += 2
                continue
            if two == "+=":
                add("PLUS_EQUAL", "+=", start_col)
                i += 2
                col += 2
                continue
            if two == "-=":
                add("MINUS_EQUAL", "-=", start_col)
                i += 2
                col += 2
                continue
            if two == "*=":
                add("STAR_EQUAL", "*=", start_col)
                i += 2
                col += 2
                continue
            if two == "/=":
                add("SLASH_EQUAL", "/=", start_col)
                i += 2
                col += 2
                continue
            if two == "%=":
                add("PERCENT_EQUAL", "%=", start_col)
                i += 2
                col += 2
                continue

        # Single-character tokens
        if ch in SINGLE_CHAR:
            add(SINGLE_CHAR[ch], ch, start_col)
            i += 1
            col += 1
            continue

        error(f"Unexpected character '{ch}'", line, col)

    tokens.append(Token("EOF", "", line, col))
    return tokens
