import sys
from pathlib import Path
from typing import List, Optional

from .config import get_config
from .transpiler import transpile_source

# Try to import readline for history and autocomplete
try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False


class REPL:
    def __init__(self) -> None:
        self.buffer: list[str] = []
        self.config = get_config()
        self.multiline_mode = False
        self.brace_depth = 0
        self.history_file = Path.home() / ".ailang_history"

        # Setup readline for history and tab completion if available
        if HAS_READLINE:
            try:
                readline.read_history_file(str(self.history_file))
                readline.set_completer(self._readline_completer)
                readline.parse_and_bind("tab: complete")
                readline.set_completer_delims(" \t\n")
            except:
                pass

        # Auto-completion keywords
        self.keywords = [
            "model", "agent", "fn", "const", "ask", "if", "else", "for", "while",
            "try", "catch", "break", "continue", "return", "print", "import"
        ]
        self.stdlib_functions = [
            "split", "join", "lower", "upper", "trim", "length", "contains",
            "parse_json", "to_json", "read_file", "write_file", "append_file",
            "make_list", "make_dict", "list_get", "list_append", "list_length",
            "dict_get", "dict_set", "dict_keys", "dict_values", "dict_items",
            "create_context", "add_to_context", "get_context_history", "create_memory",
            "add_to_memory", "search_memory", "get_env", "set_env", "has_env",
            "http_get", "http_post", "http_put", "http_delete", "get_current_time",
            "get_current_timestamp", "format_timestamp", "sleep", "format_string",
            "map_list", "filter_list", "reduce_list", "find_item", "unique_list", "sort_list"
        ]

    def _readline_completer(self, text: str, state: int) -> Optional[str]:
        """Readline completer for tab completion."""
        if state == 0:
            self._completions = self._get_completions(text)
        if state < len(self._completions):
            return self._completions[state]
        return None

    def _get_completions(self, prefix: str) -> List[str]:
        """Get auto-completion suggestions."""
        completions = []
        for keyword in self.keywords:
            if keyword.startswith(prefix):
                completions.append(keyword)
        for func in self.stdlib_functions:
            if func.startswith(prefix):
                completions.append(func)
        return completions

    def prompt(self) -> str:
        if self.multiline_mode:
            return "... "
        return ">>> "

    def should_continue(self, line: str) -> bool:
        """Check if input is incomplete (multi-line)."""
        stripped = line.strip()

        # Track brace depth for blocks
        self.brace_depth += stripped.count("{") - stripped.count("}")

        # If we have unclosed braces, continue
        if self.brace_depth > 0:
            return True

        # If we're in multiline mode and just closed braces, exit multiline
        if self.multiline_mode and self.brace_depth == 0:
            return False

        # Check for incomplete statements
        if stripped.endswith(("=", "+", "-", "*", "/", ":", "|")):
            return True

        # Keywords that start blocks
        if stripped.startswith(("fn ", "model ", "agent ", "if ", "for ", "try ", "else")):
            return not stripped.endswith("{")

        return False

    def transpile_and_execute(self, source: str) -> Optional[str]:
        """Transpile ailang source to Python and execute it."""
        try:
            python_code = transpile_source(source)

            # Add runtime imports if not present
            if "from ailang.runtime import" not in python_code:
                python_code = "from ailang.runtime import define_model, define_agent, ask_model\n" + python_code

            # Execute in a clean namespace
            namespace = {"__name__": "__main__"}

            # Capture stdout
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()

            try:
                exec(python_code, namespace)
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            return output if output else None

        except Exception as e:
            return f"Error: {e}"

    def run(self) -> None:
        """Run the REPL loop."""
        print(f"AILang REPL {self._get_version()}")
        print("Type 'exit' or 'quit' to exit, 'help' for help")
        print("Use arrow keys (up/down) for history, TAB for autocomplete")
        print()

        try:
            while True:
                try:
                    line = input(self.prompt())

                    # Handle commands
                    if line.strip().lower() in ("exit", "quit"):
                        print("Goodbye!")
                        break

                    if line.strip().lower() == "help":
                        self._print_help()
                        continue

                    if line.strip() == "":
                        if self.multiline_mode:
                            # Empty line ends multiline input
                            self.multiline_mode = False
                            self.brace_depth = 0
                            source = "\n".join(self.buffer)
                            self.buffer = []

                            if source.strip():
                                try:
                                    readline.add_history(source)
                                except:
                                    pass
                                result = self.transpile_and_execute(source)
                                if result:
                                    print(result)
                        continue

                    # Add to buffer
                    self.buffer.append(line)

                    # Check if we should continue in multiline mode
                    if not self.multiline_mode:
                        if self.should_continue(line):
                            self.multiline_mode = True
                    else:
                        if not self.should_continue(line):
                            self.multiline_mode = False
                            self.brace_depth = 0
                            source = "\n".join(self.buffer)
                            self.buffer = []

                            if source.strip():
                                try:
                                    readline.add_history(source)
                                except:
                                    pass
                                result = self.transpile_and_execute(source)
                                if result:
                                    print(result)

                except KeyboardInterrupt:
                    print("\nKeyboardInterrupt")
                    self.buffer = []
                    self.multiline_mode = False
                    self.brace_depth = 0
                except EOFError:
                    print("\nGoodbye!")
                    break
        finally:
            try:
                readline.write_history_file(str(self.history_file))
            except:
                pass

    def _get_version(self) -> str:
        """Get the version string."""
        try:
            from . import __version__
            return __version__
        except ImportError:
            return "0.1.0"

    def _print_help(self) -> None:
        """Print help information."""
        print("""
AILang REPL Help
==============

Commands:
  exit, quit  - Exit the REPL
  help        - Show this help message

Language Features:
  model <name> { ... }      - Define an AI model
  agent <name>(model) { ... } - Define an AI agent
  fn <name>(params) { ... } - Define a function
  const <name> = <expr>    - Define a constant
  ask <model>: "prompt"     - Query an AI model
  if <condition> { ... }    - Conditional statement
  for <var> in <iter> { ... } - Loop statement
  while <condition> { ... } - While loop
  break                    - Exit loop
  continue                 - Continue to next iteration
  try { ... } catch (e) { ... } - Error handling
  import <module>           - Import Python modules
  print(<expr>)             - Print output
  <var> = <expr>            - Assignment
  &&, ||, !                - Boolean operators

Example:
  >>> model gpt4 { provider: "mock" name: "test" }
  >>> result = ask gpt4: "What is 2+2?"
  >>> print(result)
""")


def main(argv: Optional[list[str]] = None) -> None:
    """Main entry point for the REPL."""
    repl = REPL()
    repl.run()


if __name__ == "__main__":
    main()
