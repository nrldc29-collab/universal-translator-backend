"""Setup script for AILang integration.

Run this once to:
1. Install ailang from the local .n directory
2. Verify the integration works
3. Register API routes (prints instructions)
"""

import subprocess
import sys
from pathlib import Path


def find_ailang_dir() -> Path:
    """Find the .n/ailang directory."""
    # Check common locations
    candidates = [
        Path.home() / "OneDrive" / "Desktop" / ".n",
        Path.home() / "Desktop" / ".n",
        Path(__file__).parent.parent.parent / ".n",
        Path("../.n"),
    ]
    for candidate in candidates:
        if (candidate / "ailang").exists():
            return candidate
    return Path("")


def install_ailang():
    """Install ailang package from local source."""
    ailang_dir = find_ailang_dir()
    if not ailang_dir.exists():
        print(f"ERROR: Could not find .n directory. Searched:")
        print(f"  - ~/OneDrive/Desktop/.n")
        print(f"  - ~/Desktop/.n")
        print(f"\nPlease provide the path:")
        path = input("Path to .n directory: ").strip()
        ailang_dir = Path(path)

    if not (ailang_dir / "ailang").exists():
        print(f"ERROR: {ailang_dir} does not contain an 'ailang' package")
        return False

    print(f"Installing ailang from: {ailang_dir}")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(ailang_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: pip install failed:\n{result.stderr}")
        return False

    print("✓ ailang installed successfully")
    return True


def verify_integration():
    """Verify that the integration works."""
    print("\nVerifying integration...")

    # Test 1: Can import ailang
    try:
        import ailang
        print(f"  ✓ ailang package importable (v{getattr(ailang, '__version__', 'unknown')})")
    except ImportError as e:
        print(f"  ✗ ailang not importable: {e}")
        return False

    # Test 2: Can parse .ai files
    try:
        from ailang.parser import parse_source
        source = 'fn hello() { return "world" }'
        program = parse_source(source)
        print(f"  ✓ Parser works ({len(program.body)} nodes)")
    except Exception as e:
        print(f"  ✗ Parser failed: {e}")
        return False

    # Test 3: Can transpile
    try:
        from ailang.transpiler import Transpiler
        transpiler = Transpiler()
        python_code = transpiler.transpile(program)
        print(f"  ✓ Transpiler works ({len(python_code)} chars)")
    except Exception as e:
        print(f"  ✗ Transpiler failed: {e}")
        return False

    # Test 4: Can load the bridge
    try:
        from ailang_integration.runtime.bridge import AILangBridge
        bridge = AILangBridge()
        agents = bridge.list_agents()
        functions = bridge.list_functions()
        print(f"  ✓ Bridge loaded ({len(agents)} agents, {len(functions)} functions)")
    except Exception as e:
        print(f"  ✗ Bridge failed: {e}")
        return False

    # Test 5: Can load plugins
    try:
        from ailang_integration.runtime.plugin_loader import PluginLoader
        loader = PluginLoader()
        plugins = loader.list_plugins()
        print(f"  ✓ Plugin loader works ({len(plugins)} plugins)")
    except Exception as e:
        print(f"  ✗ Plugin loader failed: {e}")
        return False

    # Test 6: Can run pipeline
    try:
        from ailang_integration.runtime.pipeline_runner import PipelineRunner
        runner = PipelineRunner()
        pipelines = runner.list_pipelines()
        print(f"  ✓ Pipeline runner works ({len(pipelines)} pipelines)")
    except Exception as e:
        print(f"  ✗ Pipeline runner failed: {e}")
        return False

    print("\n✓ All integration checks passed!")
    return True


def print_integration_instructions():
    """Print instructions for wiring into the backend."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║           AILang Integration — Setup Complete                 ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  To wire into your backend, add to backend/app.py:            ║
║                                                               ║
║    from ailang_integration.runtime.api_routes import (        ║
║        register_ailang_routes                                 ║
║    )                                                          ║
║    register_ailang_routes(app)                                ║
║                                                               ║
║  To use enhanced translation in streaming.py:                 ║
║                                                               ║
║    from ailang_integration.runtime.backend_hook import (      ║
║        enhance_translation                                    ║
║    )                                                          ║
║    result = enhance_translation(text, src, tgt, context)      ║
║                                                               ║
║  API Endpoints:                                               ║
║    GET  /api/ailang/status    — System status                 ║
║    POST /api/ailang/reload    — Hot-reload .ai files          ║
║    GET  /api/ailang/pipelines — List pipelines                ║
║    GET  /api/ailang/plugins   — List plugins                  ║
║    POST /api/ailang/translate — Direct translation            ║
║                                                               ║
║  To add a plugin:                                             ║
║    1. Create a .ai file in ailang_integration/plugins/        ║
║    2. Define PLUGIN_NAME, PLUGIN_HOOKS, and hook functions    ║
║    3. POST /api/ailang/reload (or restart server)             ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    print("=" * 60)
    print("  AILang × Universal Translator — Integration Setup")
    print("=" * 60)

    if not install_ailang():
        print("\nSetup failed. Please install ailang manually:")
        print("  pip install -e /path/to/.n")
        sys.exit(1)

    if verify_integration():
        print_integration_instructions()
    else:
        print("\nSome checks failed. The integration will work in fallback mode.")
        print("Fix the issues above for full AILang-powered translation.")
