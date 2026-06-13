#!/usr/bin/env python3
"""Static audit: nothing should block continuous speak-while-talking except user pause or hard gates."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _repo_path(relative: str) -> Path:
    return ROOT / relative.replace("\\", "/")


# Patterns that MUST NOT appear (block continuous speech incorrectly)
FORBIDDEN = [
    (r'clarify:\s*cip_clarify\s+or\s+low_confidence_warn', "backend/streaming.py", "clarify must not include low_confidence_warn"),
    (r'payload\?\.low_confidence\)\s*return\s*true', None, "shouldSkipBrainTts must not block on low_confidence alone"),
    (r'asBool\(message\.clarify\).*suppressTurnAudioRef\.current\s*=\s*true', "translator-mobile/App.js", "mobile final must not suppress on clarify alone"),
    (r'asBool\(data\.clarify\).*suppressTurnAudio\s*=\s*true', "backend/mobile_interpreter.html", "phone web must not suppress on clarify alone"),
]

# Patterns that MUST appear (continuous speech safeguards)
REQUIRED = [
    (r'suppressTurnAudioRef\.current\s*=\s*false', "translator-mobile/App.js", "mobile must reset suppressTurnAudio"),
    (r'suppressTurnAudio\s*=\s*false', "backend/mobile_interpreter.html", "phone web must reset suppressTurnAudio"),
    (r'keepContinuous', "frontend/src/main.jsx", "web must keep continuous stream on final"),
    (r'"clarify":\s*bool\(cip_clarify\)', "backend/streaming.py", "backend clarify must be cip_clarify only"),
    (r'liveSpeechSessionRef\.current', "frontend/src/main.jsx", "web live speech session ref"),
    (r'final_low_confidence', "frontend/src/main.jsx", "web must handle final_low_confidence clarify"),
    (r'final_low_confidence', "translator-mobile/App.js", "mobile must handle final_low_confidence clarify"),
    (r'final_low_confidence', "backend/mobile_interpreter.html", "phone web must handle final_low_confidence clarify"),
    (r'if not cip_clarify and cip_client_hints\.get\("skip_tts"\)', "backend/streaming.py", "backend must clear stale skip_tts hints"),
    (r'already streamed\|browser voice handles\|live voice', "translator-mobile/App.js", "mobile must treat benign tts_skipped"),
    (r'already streamed\|browser voice handles\|live voice', "backend/mobile_interpreter.html", "phone web must treat benign tts_skipped"),
    (r'already streamed\|browser voice handles\|live voice', "frontend/src/main.jsx", "web must treat benign tts_skipped"),
    (r'Never block playback from stale brain hints', "frontend/src/hooks/useBrainState.js", "web must not block TTS from stale hints alone"),
    (r'listening && data\.allowed !== false', "backend/mobile_interpreter.html", "phone web must resume mic after turn complete"),
]

RESUME_HINTS = (
    "frontend/src/main.jsx",
    "translator-mobile/App.js",
    "backend/mobile_interpreter.html",
)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def main() -> int:
    failures: list[str] = []

    for pattern, file_hint, msg in FORBIDDEN:
        if file_hint:
            paths = [_repo_path(file_hint)]
        else:
            paths = [
                ROOT / "frontend" / "src",
                ROOT / "translator-mobile",
                ROOT / "backend" / "mobile_interpreter.html",
                ROOT / "translator-mobile" / "utils" / "brainPlan.js",
            ]
        for path in paths:
            if path.is_file():
                candidates = [path]
            else:
                skip_dirs = {"node_modules", "dist-verify", "dist", ".expo", "__pycache__"}
                candidates = []
                for ext in ("*.js", "*.jsx", "*.html"):
                    for candidate in path.rglob(ext):
                        if any(part in skip_dirs for part in candidate.parts):
                            continue
                        candidates.append(candidate)
            for candidate in candidates:
                text = read(candidate)
                if text and re.search(pattern, text, re.MULTILINE):
                    failures.append(f"FORBIDDEN [{msg}]: {candidate.relative_to(ROOT)}")

    for pattern, file_hint, msg in REQUIRED:
        path = _repo_path(file_hint)
        if not re.search(pattern, read(path), re.MULTILINE):
            failures.append(f"MISSING [{msg}] in {file_hint}")

    resume_pat = re.compile(r"resumeMicAfterVoicePlayback|resumeMicAfterPlayback|resumeAudioUpload")
    if not any(resume_pat.search(read(_repo_path(p))) for p in RESUME_HINTS):
        failures.append("MISSING [mic resume after TTS] in web/mobile clients")

    print("Continuous speech static audit\n")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        print(f"\n{len(failures)} issue(s) found")
        return 1
    print("  All forbidden patterns absent")
    print("  All required safeguards present")
    print("\nCONTINUOUS SPEECH STATIC AUDIT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
