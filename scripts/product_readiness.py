#!/usr/bin/env python3
"""Score Anai product readiness across five dimensions (target 10/10 each).

Static checks always run. Live checks (--live URL) verify a running backend.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"node_modules", "dist-verify", "dist", ".expo", "__pycache__", ".git"}


@dataclass
class Dimension:
    name: str
    label: str
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    @property
    def score(self) -> int:
        if not self.checks:
            return 0
        passed = sum(1 for _, ok, _ in self.checks if ok)
        return round(10 * passed / len(self.checks))

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def run_script(rel: str, *args: str) -> tuple[bool, str]:
    cmd = [sys.executable, str(ROOT / rel), *args]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
        ok = proc.returncode == 0
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()
        summary = tail[-1] if tail else f"exit {proc.returncode}"
        return ok, summary
    except Exception as exc:
        return False, str(exc)


def fetch_json(url: str, timeout: float = 10) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def grep_files(pattern: str, *roots: str) -> list[Path]:
    rx = re.compile(pattern, re.MULTILINE)
    hits: list[Path] = []
    for root_name in roots:
        root = ROOT / root_name
        if root.is_file():
            if rx.search(read(root)):
                hits.append(root)
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".js", ".jsx", ".ts", ".tsx", ".html", ".py", ".yml", ".ps1"}:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if rx.search(read(path)):
                hits.append(path)
    return hits


def add(dim: Dimension, label: str, ok: bool, detail: str = "") -> None:
    dim.checks.append((label, ok, detail))


def audit_core(live_url: str | None) -> Dimension:
    dim = Dimension("core_product", "Core product (STT -> translate -> TTS)")
    ok, msg = run_script("scripts/audit_continuous_speech.py")
    add(dim, "Continuous speech static audit", ok, msg)

    verify = ROOT / "scripts" / "verify_speech_pipeline.py"
    langs = read(verify)
    add(dim, "14-language speech verify script", len(re.findall(r'"[a-z]{2}"', langs)) >= 14)

    for rel in (
        "backend/pipeline.py",
        "backend/streaming.py",
        "speech/whisper_stt.py",
        "translation/hybrid_translator.py",
        "backend/mobile_interpreter.html",
        "frontend/src/main.jsx",
        "translator-mobile/App.js",
    ):
        add(dim, f"Core path exists: {rel}", (ROOT / rel).is_file())

    if live_url:
        ok, msg = run_script("scripts/verify_speech_pipeline.py", live_url)
        add(dim, f"Live speech pipeline @ {live_url}", ok, msg)
        health = fetch_json(f"{live_url.rstrip('/')}/health")
        add(dim, "Backend health reachable", health is not None)
        add(dim, "Backend reports ready", bool(health and health.get("ready")))
    else:
        add(dim, "Live speech pipeline (skipped — use --live URL)", True, "static-only")

    return dim


def audit_ship(live_url: str | None) -> Dimension:
    dim = Dimension("ship_ready", "Ship-ready polish")
    add(dim, "Start-Translator.ps1 launcher", (ROOT / "Start-Translator.ps1").is_file())
    add(dim, "verify-local.ps1", (ROOT / "verify-local.ps1").is_file())
    add(dim, ".env.example", (ROOT / ".env.example").is_file())
    add(dim, "Ensure-MobileHttps.ps1", (ROOT / "Ensure-MobileHttps.ps1").is_file())
    add(dim, "Fix-ExpoPhone.ps1", (ROOT / "Fix-ExpoPhone.ps1").is_file())

    launcher = read(ROOT / "Start-Translator.ps1")
    add(dim, "QuickStart switch in launcher", "[switch]$QuickStart" in launcher)
    add(dim, "One-click Open-Anai.ps1", (ROOT / "Open-Anai.ps1").is_file())
    add(dim, "Score-Product.ps1 wrapper", (ROOT / "Score-Product.ps1").is_file())

    mount_hook = (ROOT / "translator-mobile" / "hooks" / "useMountForPresence.js").is_file()
    add(dim, "Safe Expo mount hook (update-depth fix)", mount_hook)

    bad_mount_deps = grep_files(
        r"useEffect\(\(\)[\s\S]{0,400}?setMounted[\s\S]{0,120}?\[[^\]]*\bmounted\b",
        "translator-mobile/components",
    )
    bad_mount_deps = [p for p in bad_mount_deps if "useMountForPresence" not in read(p)]
    add(dim, "No mounted-in-deps banner loops", len(bad_mount_deps) == 0,
        ", ".join(str(p.relative_to(ROOT)) for p in bad_mount_deps[:3]))

    mobile_app = read(ROOT / "translator-mobile" / "App.js")
    add(dim, "Guarded confidence/brain setState", "previous === warning ? previous : warning" in mobile_app
        or "(previous ? false : previous)" in mobile_app)

    if live_url:
        health = fetch_json(f"{live_url.rstrip('/')}/health")
        add(dim, "Health ready for open-and-go", bool(health and health.get("ready")))
    else:
        add(dim, "Health ready (skipped — use --live URL)", True)

    return dim


def audit_ops() -> Dimension:
    dim = Dimension("production_ops", "Production ops")
    for rel in (
        ".github/workflows/ci.yml",
        ".github/workflows/production-smoke.yml",
        "scripts/preflight_deploy.sh",
        "scripts/smoke_local.py",
        "backend/api_health.py",
        "Start-Translator.ps1",
    ):
        add(dim, f"Ops asset: {rel}", (ROOT / rel).is_file())

    ci = read(ROOT / ".github" / "workflows" / "ci.yml")
    add(dim, "CI runs pytest", "pytest" in ci)
    add(dim, "CI integration-live job", "integration-live:" in ci)
    add(dim, "CI product readiness gate", "product_readiness" in ci)

    api = read(ROOT / "backend" / "api_health.py")
    add(dim, "/health endpoint module", "/health" in api or "health" in api.lower())
    add(dim, "/diagnostics endpoint", "diagnostics" in api.lower() or (ROOT / "backend" / "api.py").is_file())

    return dim


def audit_ux() -> Dimension:
    dim = Dimension("ux_focus", "UX / product focus")
    readme = read(ROOT / "README.md")
    add(dim, "README design rule documented",
        "main-screen ui elements" in readme.lower()
        or "main screen ui elements" in readme.lower()
        or "language direction, microphone, transcript" in readme.lower())

    mobile_mode = read(ROOT / "translator-mobile" / "constants" / "productMode.js")
    web_mode = read(ROOT / "frontend" / "src" / "constants" / "productMode.js")
    add(dim, "Mobile focused product mode", "FOCUSED_PRODUCT_UI = true" in mobile_mode)
    add(dim, "Web focused product mode", "FOCUSED_PRODUCT_UI = true" in web_mode)

    app = read(ROOT / "translator-mobile" / "App.js")
    add(dim, "Mobile uses focused chrome gate", "showAdvancedInterpreterChrome" in app)
    add(dim, "Mobile hides duplex rail when focused", "showAdvancedInterpreterChrome" in app and "DuplexConversationPanel" in app)

    web_main = read(ROOT / "frontend" / "src" / "main.jsx")
    add(dim, "Web debug panel gated", "showDebugPanel" in web_main and "debugMode" in web_main)

    return dim


def audit_consumer() -> Dimension:
    dim = Dimension("consumer_app", "Consumer App Store readiness")
    app_json_path = ROOT / "translator-mobile" / "app.json"
    add(dim, "Expo app.json", app_json_path.is_file())
    try:
        app_json = json.loads(read(app_json_path) or "{}")
        expo = app_json.get("expo", {})
        ios = expo.get("ios", {})
        android = expo.get("android", {})
        add(dim, "iOS bundleIdentifier", bool(ios.get("bundleIdentifier")))
        add(dim, "Android package", bool(android.get("package")))
        add(dim, "Microphone permission strings", bool(ios.get("infoPlist", {}).get("NSMicrophoneUsageDescription")))
        add(dim, "App version set", bool(expo.get("version")))
        add(dim, "Store description metadata", bool(expo.get("description")))
        add(dim, "EAS project configured", bool(expo.get("extra", {}).get("eas", {}).get("projectId")))
    except json.JSONDecodeError:
        add(dim, "Valid app.json", False)

    add(dim, "Welcome setup modal", (ROOT / "translator-mobile" / "components" / "WelcomeSetupModal.js").is_file())
    add(dim, "Mobile README", (ROOT / "translator-mobile" / "README.md").is_file())
    add(dim, "QUICKSTART guide", (ROOT / "QUICKSTART.md").is_file())

    bootstrap = read(ROOT / "translator-mobile" / "index.js")
    add(dim, "Bootstrap error boundary", "RootErrorBoundary" in bootstrap)
    add(dim, "Auto server discovery", "resolveServerUrl" in bootstrap)

    return dim


def print_report(dims: list[Dimension]) -> int:
    print("\nAnai product readiness\n" + "=" * 40)
    all_pass = True
    for dim in dims:
        status = "PASS" if dim.passed else "FAIL"
        print(f"\n{dim.label}: {dim.score}/10 [{status}]")
        for label, ok, detail in dim.checks:
            mark = "OK" if ok else "FAIL"
            line = f"  [{mark}] {label}"
            if detail and not ok:
                line += f" — {detail}"
            elif detail and ok and "skipped" in detail.lower():
                line += f" — {detail}"
            print(line)
        if not dim.passed:
            all_pass = False

    overall = round(sum(d.score for d in dims) / len(dims))
    print(f"\n{'=' * 40}")
    print(f"Overall: {overall}/10")
    if all_pass:
        print("PRODUCT READINESS: 10/10 ALL DIMENSIONS")
        return 0
    print("PRODUCT READINESS: not yet 10/10 - fix FAIL items above")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Anai product readiness scorecard")
    parser.add_argument("--live", metavar="URL", help="Running backend base URL for live checks")
    parser.add_argument("--static-only", action="store_true", help="Skip live backend checks")
    args = parser.parse_args()
    live = None if args.static_only else args.live

    dims = [
        audit_core(live),
        audit_ship(live),
        audit_ops(),
        audit_ux(),
        audit_consumer(),
    ]
    return print_report(dims)


if __name__ == "__main__":
    sys.exit(main())
