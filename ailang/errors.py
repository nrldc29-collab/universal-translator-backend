"""Custom error classes for AILang with improved error reporting."""
from typing import List


class AILangError(Exception):
    """Base exception for all AILang errors."""

    def __init__(self, message: str, line: int = 0, col: int = 0, source: str = ""):
        self.message = message
        self.line = line
        self.col = col
        self.source = source
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = []

        # Add location
        if self.line > 0:
            loc = f"Line {self.line}"
            if self.col > 0:
                loc += f", Column {self.col}"
            parts.append(loc)

        # Add message
        parts.append(self.message)

        # Add source context if available
        if self.source and self.line > 0:
            lines = self.source.split("\n")
            if 0 < self.line <= len(lines):
                error_line = lines[self.line - 1]
                parts.append("\n")
                parts.append(error_line)
                if self.col > 0:
                    # Add caret pointer
                    pointer = " " * (self.col - 1) + "^"
                    parts.append(pointer)

        # Add suggestions if available
        if hasattr(self, 'suggestions') and self.suggestions:
            parts.append("\n")
            parts.append("Suggestions:")
            for suggestion in self.suggestions:
                parts.append(f"  - {suggestion}")

        return "\n".join(parts)


class LexError(AILangError):
    """Raised when the lexer encounters an invalid token."""

    def __init__(self, message: str, line: int = 0, col: int = 0, source: str = ""):
        suggestions = self._get_suggestions(message)
        super().__init__(message, line, col, source)
        if suggestions:
            self.suggestions = suggestions

    def _get_suggestions(self, message: str) -> List[str]:
        """Provide helpful suggestions based on the error message."""
        suggestions = []
        msg_lower = message.lower()

        if "unterminated" in msg_lower:
            if "string" in msg_lower:
                suggestions.append("Make sure all strings are closed with matching quotes")
            elif "comment" in msg_lower:
                suggestions.append("Make sure all comments are closed with #")
        elif "unexpected" in msg_lower:
            suggestions.append("Check for typos or invalid characters")
        elif "identifier" in msg_lower:
            suggestions.append("Identifiers must start with a letter or underscore")

        return suggestions


class ParseError(AILangError):
    """Raised when the parser encounters invalid syntax."""

    def __init__(self, message: str, line: int = 0, col: int = 0, source: str = ""):
        suggestions = self._get_suggestions(message)
        super().__init__(message, line, col, source)
        if suggestions:
            self.suggestions = suggestions

    def _get_suggestions(self, message: str) -> List[str]:
        """Provide helpful suggestions based on the error message."""
        suggestions = []
        msg_lower = message.lower()

        if "expected" in msg_lower:
            if "lbrace" in msg_lower:
                suggestions.append("Missing opening brace {")
            elif "rbrace" in msg_lower:
                suggestions.append("Missing closing brace }")
            elif "lparen" in msg_lower:
                suggestions.append("Missing opening parenthesis (")
            elif "rparen" in msg_lower:
                suggestions.append("Missing closing parenthesis )")
        elif "unexpected" in msg_lower:
            if "eof" in msg_lower:
                suggestions.append("Unexpected end of file - check for missing closing braces or parentheses")
            else:
                suggestions.append("Check for syntax errors in the statement")
        elif "ident" in msg_lower and "expected" in msg_lower:
            suggestions.append("Check that variable names are valid identifiers")

        return suggestions


class AILangRuntimeError(AILangError):
    """Raised when runtime execution fails."""

    def __init__(self, message: str, line: int = 0, col: int = 0, source: str = ""):
        suggestions = self._get_suggestions(message)
        super().__init__(message, line, col, source)
        if suggestions:
            self.suggestions = suggestions

    def _get_suggestions(self, message: str) -> List[str]:
        """Provide helpful suggestions based on the error message."""
        suggestions = []
        msg_lower = message.lower()

        if "not found" in msg_lower:
            if "model" in msg_lower:
                suggestions.append("Make sure the model is defined before use")
            elif "agent" in msg_lower:
                suggestions.append("Make sure the agent is defined before use")
            elif "function" in msg_lower or "tool" in msg_lower:
                suggestions.append("Make sure the function is defined before calling it")
        elif "api key" in msg_lower:
            suggestions.append("Set the required API key in your environment variables")
        elif "attribute" in msg_lower:
            suggestions.append("Check that the object has the expected attribute")

        return suggestions
