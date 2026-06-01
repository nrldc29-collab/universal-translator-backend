import argparse
import os
import runpy
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from . import __version__
from .config import get_config
from .parser import parse_source_with_recovery
from .repl import main as repl_main
from .transpiler import transpile_source
from .typechecker import check_source


def build_file(input_path: Path, output_path: Path) -> None:
    try:
        source = input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"Error: File {input_path} is not valid UTF-8 text", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied reading {input_path}", file=sys.stderr)
        sys.exit(1)
    python_code = transpile_source(source, source_path=str(input_path.resolve()))
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(python_code, encoding="utf-8")
    except PermissionError:
        print(f"Error: Permission denied writing to {output_path}", file=sys.stderr)
        sys.exit(1)


def run_file(input_path: Path) -> None:
    try:
        source = input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"Error: File {input_path} is not valid UTF-8 text", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied reading {input_path}", file=sys.stderr)
        sys.exit(1)
    python_code = transpile_source(source, source_path=str(input_path.resolve()))
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as temp:
            temp.write(python_code)
            temp_path = temp.name
        # Execute with the .ai file's directory as the working directory
        # so relative imports and file operations resolve correctly
        original_dir = os.getcwd()
        try:
            os.chdir(input_path.parent.resolve())
            runpy.run_path(temp_path, run_name="__main__")
        finally:
            os.chdir(original_dir)
    finally:
        # Always clean up the temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def watch_file(input_path: Path, interval: float = 1.0) -> None:
    """Watch a file and auto-run on changes.

    Args:
        input_path: Path to the .ai file to watch
        interval: Polling interval in seconds
    """
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    last_modified = input_path.stat().st_mtime
    print(f"Watching {input_path} (Ctrl+C to stop)")
    print("Initial run:")
    run_file(input_path)

    try:
        while True:
            time.sleep(interval)
            current_modified = input_path.stat().st_mtime
            if current_modified != last_modified:
                last_modified = current_modified
                print(f"\n[{time.strftime('%H:%M:%S')}] File changed, re-running...")
                try:
                    run_file(input_path)
                except Exception as e:
                    print(f"Error: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nStopped watching.")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ailang",
        description="AILang compiler and runner - An AI-native programming language"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")
    parser.add_argument("--profile", "-p", action="store_true", help="Enable profiling")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Transpile and run an .ai file")
    run_cmd.add_argument("file", help="Path to the .ai file to run")
    run_cmd.add_argument("--watch", "-w", action="store_true", help="Watch file and auto-run on changes")
    run_cmd.add_argument("--interval", type=float, default=1.0, help="Watch polling interval in seconds")

    build_cmd = sub.add_parser("build", help="Transpile an .ai file to Python")
    build_cmd.add_argument("file", help="Path to the .ai file to transpile")
    build_cmd.add_argument("-o", "--output", required=True, help="Output Python file path")

    sub.add_parser("repl", help="Start interactive REPL")

    check_cmd = sub.add_parser("check", help="Type-check an .ai file")
    check_cmd.add_argument("file", help="Path to the .ai file to check")
    check_cmd.add_argument("--warnings", "-W", action="store_true", help="Show warnings")
    check_cmd.add_argument("--strict", "-s", action="store_true", help="Treat warnings as errors")

    config_cmd = sub.add_parser("config", help="Show or set configuration")
    config_cmd.add_argument("--get", metavar="KEY", help="Get a configuration value")
    config_cmd.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set a configuration value")
    config_cmd.add_argument("--show", action="store_true", help="Show all configuration")

    serve_cmd = sub.add_parser("serve", help="Start the web IDE server")
    serve_cmd.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    serve_cmd.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    serve_cmd.add_argument("--no-open", action="store_true", help="Don't open browser automatically")

    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            input_path = Path(args.file)
            if input_path.is_dir():
                print(f"Error: {args.file} is a directory, not a file", file=sys.stderr)
                sys.exit(1)
            if not input_path.exists():
                print(f"Error: File not found: {args.file}", file=sys.stderr)
                sys.exit(1)
            if args.watch:
                watch_file(input_path, args.interval)
            else:
                if args.debug:
                    import time
                    print(f"[DEBUG] Running {args.file}")
                    start_time = time.time()
                if args.verbose:
                    print(f"[VERBOSE] Transpiling {args.file}...")
                if args.profile:
                    import cProfile
                    import pstats
                    from io import StringIO
                    pr = cProfile.Profile()
                    pr.enable()
                    run_file(input_path)
                    pr.disable()
                    s = StringIO()
                    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
                    ps.print_stats(10)
                    print(s.getvalue())
                else:
                    run_file(input_path)
                if args.debug:
                    elapsed = time.time() - start_time
                    print(f"[DEBUG] Execution completed in {elapsed:.2f}s")
        elif args.command == "build":
            input_path = Path(args.file)
            if input_path.is_dir():
                print(f"Error: {args.file} is a directory, not a file", file=sys.stderr)
                sys.exit(1)
            if not input_path.exists():
                print(f"Error: File not found: {args.file}", file=sys.stderr)
                sys.exit(1)
            if args.verbose:
                print(f"[VERBOSE] Transpiling {args.file} to {args.output}...")
            build_file(input_path, Path(args.output))
            if args.verbose:
                print("[VERBOSE] Build complete")
        elif args.command == "repl":
            if args.verbose:
                print("[VERBOSE] Starting REPL...")
            repl_main()
        elif args.command == "check":
            input_path = Path(args.file)
            if input_path.is_dir():
                print(f"Error: {args.file} is a directory, not a file", file=sys.stderr)
                sys.exit(1)
            if not input_path.exists():
                print(f"Error: File not found: {args.file}", file=sys.stderr)
                sys.exit(1)
            try:
                source = input_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                print(f"Error: File {input_path} is not valid UTF-8 text", file=sys.stderr)
                sys.exit(1)
            except PermissionError:
                print(f"Error: Permission denied reading {input_path}", file=sys.stderr)
                sys.exit(1)
            try:
                # First, parse with recovery to find all parse errors
                parse_result = parse_source_with_recovery(source)
                for parse_error in parse_result.errors:
                    loc = f"Line {parse_error.line}" if parse_error.line else ""
                    print(f"  \u274c Parse error: {parse_error.message} {loc}".strip(), file=sys.stderr)
                # Then, type-check if parsing succeeded
                issues = check_source(source) if not parse_result.errors else []
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            errors = [i for i in issues if i.severity == "error"]
            warnings = [i for i in issues if i.severity == "warning"]
            if args.strict:
                errors.extend(warnings)
                warnings = []
            for issue in errors:
                loc = f"Line {issue.line}" if issue.line else ""
                print(f"  \u274c {issue.message} {loc}".strip(), file=sys.stderr)
            if args.warnings:
                for issue in warnings:
                    loc = f"Line {issue.line}" if issue.line else ""
                    print(f"  \u26a0 {issue.message} {loc}".strip(), file=sys.stderr)
            if errors:
                print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
                sys.exit(1)
            elif warnings:
                print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
            else:
                print("No type issues found.")
        elif args.command == "config":
            cfg = get_config()
            if args.show:
                import json
                print(json.dumps(cfg.config, indent=2))
            elif args.get:
                value = cfg.get(args.get)
                if value is None:
                    print(f"Key '{args.get}' not found in configuration", file=sys.stderr)
                    sys.exit(1)
                print(value)
            elif args.set:
                key, value = args.set
                # Convert value to appropriate type
                if key in ["timeout", "max_retries"]:
                    try:
                        value = int(value)
                    except ValueError:
                        print(f"Error: {key} must be an integer", file=sys.stderr)
                        sys.exit(1)
                cfg.set(key, value)
                cfg.save()
                print(f"Set {key} = {value}")
            else:
                import json
                print(json.dumps(cfg.config, indent=2))
        elif args.command == "serve":
            import webbrowser

            from .api import app

            web_dir = Path(__file__).parent.parent / "web" / "dist"
            if web_dir.exists():
                from flask import send_from_directory

                @app.route("/")
                def serve_index():
                    return send_from_directory(str(web_dir), "index.html")

                @app.route("/<path:path>")
                def serve_static(path):
                    file_path = web_dir / path
                    if file_path.exists():
                        return send_from_directory(str(web_dir), path)
                    return send_from_directory(str(web_dir), "index.html")

            host = args.host
            port = args.port
            if not args.no_open:
                url = f"http://localhost:{port}"
                print(f"Starting AILang IDE at {url}")
                webbrowser.open(url)
            app.run(host=host, port=port, debug=False)
    except SyntaxError as e:
        print(f"Syntax Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.debug or args.verbose:
            import traceback
            traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
