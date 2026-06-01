"""AILang Web API — Flask backend for the web IDE."""

from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from .errors import AILangError, LexError, ParseError
from .parser import parse_source_with_recovery
from .transpiler import transpile_source

app = Flask(__name__)
CORS(app)

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@app.route("/api/run", methods=["POST"])
def run_code():
    """Execute AILang code and return the output."""
    data = request.get_json()
    source = data.get("source", "")

    try:
        python_code = transpile_source(source)
    except (LexError, ParseError) as e:
        return jsonify({"success": False, "error": str(e), "output": "", "python": ""})
    except AILangError as e:
        return jsonify({"success": False, "error": str(e), "output": "", "python": ""})

    # Capture stdout/stderr from execution
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    output = ""
    exec_error = ""

    try:
        import runpy
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(python_code)
            tmp_path = tmp.name

        try:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            try:
                runpy.run_path(tmp_path, run_name="__main__")
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        output = stdout_capture.getvalue()
        stderr_out = stderr_capture.getvalue()
        if stderr_out:
            output += stderr_out

    except Exception:
        exec_error = traceback.format_exc()

    return jsonify({
        "success": not exec_error,
        "error": exec_error,
        "output": output,
        "python": python_code,
    })


@app.route("/api/check", methods=["POST"])
def check_code():
    """Type-check AILang code and return errors/warnings."""
    data = request.get_json()
    source = data.get("source", "")

    try:
        from .typechecker import check_source
        errors = check_source(source)
        return jsonify({"success": True, "errors": errors})
    except (LexError, ParseError) as e:
        return jsonify({"success": False, "errors": [{"message": str(e), "level": "error"}]})
    except Exception as e:
        return jsonify({"success": False, "errors": [{"message": str(e), "level": "error"}]})


@app.route("/api/transpile", methods=["POST"])
def transpile_code():
    """Transpile AILang code to Python."""
    data = request.get_json()
    source = data.get("source", "")

    try:
        python_code = transpile_source(source)
        return jsonify({"success": True, "python": python_code, "error": ""})
    except (LexError, ParseError) as e:
        return jsonify({"success": False, "python": "", "error": str(e)})
    except AILangError as e:
        return jsonify({"success": False, "python": "", "error": str(e)})


@app.route("/api/parse", methods=["POST"])
def parse_code():
    """Parse AILang code with error recovery and return all errors."""
    data = request.get_json()
    source = data.get("source", "")

    result = parse_source_with_recovery(source)
    errors = [str(e) for e in result.errors]
    return jsonify({"success": len(errors) == 0, "errors": errors})


@app.route("/api/examples", methods=["GET"])
def list_examples():
    """List all example .ai files."""
    examples = []
    if EXAMPLES_DIR.exists():
        for f in sorted(EXAMPLES_DIR.glob("*.ai")):
            try:
                content = f.read_text(encoding="utf-8")
                # Get first line as description
                first_line = content.strip().split("\n")[0] if content.strip() else ""
                desc = first_line.lstrip("# ").strip() if first_line.startswith("#") else f.stem
                examples.append({
                    "name": f.stem,
                    "filename": f.name,
                    "description": desc,
                    "content": content,
                })
            except Exception:
                continue
    return jsonify(examples)


@app.route("/api/examples/<name>", methods=["GET"])
def get_example(name):
    """Get a specific example file."""
    # Sanitize name
    safe_name = Path(name).stem + ".ai"
    filepath = EXAMPLES_DIR / safe_name
    if not filepath.exists():
        return jsonify({"error": "Example not found"}), 404
    try:
        content = filepath.read_text(encoding="utf-8")
        return jsonify({"name": Path(name).stem, "content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def main():
    """Run the API server."""
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
