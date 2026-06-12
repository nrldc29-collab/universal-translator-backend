#!/usr/bin/env python3
"""Bounded live API verification for every configured language direction."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import LANGUAGES

LANGS = tuple(LANGUAGES.keys())


class VerificationInfrastructureError(RuntimeError):
    """The verifier could not exercise a translation because its environment failed."""


class RequestPacer:
    def __init__(self, requests_per_minute: float):
        self.interval = 60.0 / requests_per_minute
        self.next_request_at = time.monotonic()
        self.lock = Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next_request_at - now)
            self.next_request_at = max(now, self.next_request_at) + self.interval
        if delay:
            time.sleep(delay)
GREETINGS = {
    "en": "hello", "es": "hola", "ht": "bonjou", "fr": "bonjour", "de": "hallo",
    "it": "ciao", "pt": "ola", "nl": "hallo", "ru": "\u043f\u0440\u0438\u0432\u0435\u0442",
    "zh": "\u4f60\u597d", "ja": "\u3053\u3093\u306b\u3061\u306f", "ko": "\uc548\ub155\ud558\uc138\uc694",
    "ar": "\u0645\u0631\u062d\u0628\u0627", "hi": "\u0928\u092e\u0938\u094d\u0924\u0947",
}
THANKS = {
    "en": "thank you", "es": "gracias", "ht": "m\u00e8si", "fr": "merci", "de": "danke",
    "it": "grazie", "pt": "obrigado", "nl": "dank je", "ru": "\u0441\u043f\u0430\u0441\u0438\u0431\u043e",
    "zh": "\u8c22\u8c22", "ja": "\u3042\u308a\u304c\u3068\u3046", "ko": "\uac10\uc0ac\ud569\ub2c8\ub2e4",
    "ar": "\u0634\u0643\u0631\u0627", "hi": "\u0927\u0928\u094d\u092f\u0935\u093e\u0926",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test every configured source/target direction through POST /translate/text.",
    )
    parser.add_argument("legacy_api_url", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--phrases", choices=("greeting", "both"), default="greeting")
    parser.add_argument("--workers", type=int, default=6, help="Parallel requests (default: 6)")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds")
    parser.add_argument("--retries", type=int, default=1, help="Retries for transient HTTP/network errors")
    parser.add_argument("--requests-per-minute", type=float, default=90.0, help="Request start rate (default: 90)")
    parser.add_argument("--max-seconds", type=float, default=300.0, help="Hard deadline for the matrix")
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "logs" / "live_api_lang_report.txt")
    parser.add_argument("--token", default="", help="Optional bearer token for an isolated test identity")
    args = parser.parse_args()
    if args.legacy_api_url:
        args.api_url = args.legacy_api_url
    parsed = urlparse(args.api_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        parser.error("API URL must be an absolute http:// or https:// URL")
    if args.workers < 1 or args.workers > 32:
        parser.error("--workers must be between 1 and 32")
    if args.timeout <= 0 or args.max_seconds <= 0 or args.requests_per_minute <= 0 or args.retries < 0:
        parser.error("timeouts must be positive and retries cannot be negative")
    return args


def is_bad(text: str, source: str, target: str) -> bool:
    out = str(text or "").strip()
    if not out:
        return True
    if out.startswith(f"[{source}->{target}]"):
        return True
    if out.startswith("[AI_ERROR:"):
        return True
    return out.startswith("[AI:") and len(out) < 20


def read_json(request: urllib.request.Request, timeout: float) -> dict:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def backend_ready(api_url: str, timeout: float, token: str = "") -> tuple[bool, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(api_url.rstrip("/") + "/health", headers=headers)
    try:
        data = read_json(request, min(timeout, 10.0))
        return data.get("status") == "ok", str(data.get("status") or "unknown")
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def post_once(endpoint: str, payload: dict, timeout: float, retries: int, pacer: RequestPacer, token: str = "") -> dict:
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(retries + 1):
        pacer.wait()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers=headers,
        )
        try:
            return read_json(request, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                detail = exc.read().decode("utf-8", errors="replace")[:240]
                raise VerificationInfrastructureError(f"HTTP 429 quota: {detail}") from exc
            transient = 500 <= exc.code < 600
            if transient and attempt < retries:
                retry_after = exc.headers.get("Retry-After")
                time.sleep(min(float(retry_after or attempt + 1), 3.0))
                continue
            detail = exc.read().decode("utf-8", errors="replace")[:240]
            raise VerificationInfrastructureError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt < retries:
                time.sleep(min(attempt + 1, 2))
                continue
            raise VerificationInfrastructureError(f"{type(exc).__name__}: {exc}") from exc
    raise VerificationInfrastructureError("request retry loop exhausted")


def build_tasks(phrases: str) -> list[tuple[str, str, str, str]]:
    task_phrases = (("greet", GREETINGS),) if phrases == "greeting" else (("greet", GREETINGS), ("thanks", THANKS))
    return [
        (label, source, target, phrase_map[source])
        for source in LANGS
        for target in LANGS
        if source != target
        for label, phrase_map in task_phrases
    ]


def write_report(
    path: Path,
    *,
    status: str,
    api_url: str,
    passed: int,
    failed: int,
    misses: list[str],
    infrastructure_errors: list[str],
    elapsed: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"STATUS: {status}",
        f"API: {api_url}",
        f"LANGUAGES: {len(LANGS)}",
        f"PASS: {passed}",
        f"FAIL: {failed}",
        f"INFRASTRUCTURE_ERRORS: {len(infrastructure_errors)}",
        f"ELAPSED_SECONDS: {elapsed:.2f}",
        "FAILURES:",
        *(misses or ["none"]),
        "INFRASTRUCTURE:",
        *(infrastructure_errors or ["none"]),
    ]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    api_url = args.api_url.rstrip("/")
    endpoint = api_url + "/translate/text"
    ready, health_detail = backend_ready(api_url, args.timeout, args.token)
    if not ready:
        message = f"Backend is not ready at {api_url}: {health_detail}"
        print(message, file=sys.stderr)
        write_report(
            args.report,
            status="INFRASTRUCTURE_ERROR",
            api_url=api_url,
            passed=0,
            failed=0,
            misses=[],
            infrastructure_errors=[message],
            elapsed=0.0,
        )
        return 2

    tasks = build_tasks(args.phrases)
    started = time.monotonic()
    deadline = started + args.max_seconds
    passed = 0
    misses: list[str] = []
    infrastructure_errors: list[str] = []
    pacer = RequestPacer(args.requests_per_minute)

    def execute(task: tuple[str, str, str, str]) -> tuple[tuple[str, str, str, str], dict]:
        label, source, target, phrase = task
        payload = {
            "text": phrase,
            "source_language": source,
            "target_language": target,
            "translation_mode": "fast",
            "translation_provider": "lightweight",
            "session_id": f"live-verify-{source}-{target}-{label}",
        }
        return task, post_once(endpoint, payload, args.timeout, args.retries, pacer, args.token)

    executor = ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="lang-verify")
    futures = {executor.submit(execute, task): task for task in tasks}
    completed = 0
    timed_out = False
    try:
        for future in as_completed(futures, timeout=args.max_seconds):
            task = futures[future]
            label, source, target, _ = task
            completed += 1
            try:
                _, data = future.result()
                output = str(data.get("translated_text") or "")
                if is_bad(output, source, target):
                    misses.append(f"{label} {source}->{target}: {output!r} clarify={data.get('clarify')}")
                else:
                    passed += 1
            except VerificationInfrastructureError as exc:
                infrastructure_errors.append(f"{label} {source}->{target}: {exc}")
            except Exception as exc:
                misses.append(f"{label} {source}->{target}: {type(exc).__name__}: {exc}")
            if completed % 26 == 0 or completed == len(tasks):
                print(f"  progress {completed}/{len(tasks)} pass={passed} fail={len(misses)}")
            if time.monotonic() >= deadline:
                timed_out = True
                break
    except TimeoutError:
        timed_out = True
    finally:
        if timed_out:
            for future, task in futures.items():
                if not future.done():
                    future.cancel()
                    label, source, target, _ = task
                    infrastructure_errors.append(f"{label} {source}->{target}: matrix deadline exceeded")
        executor.shutdown(wait=not timed_out, cancel_futures=True)

    elapsed = time.monotonic() - started
    failed = len(misses)
    if infrastructure_errors:
        status = "INFRASTRUCTURE_ERROR"
    else:
        status = "PASS" if not timed_out and failed == 0 and passed == len(tasks) else "FAIL"
    write_report(
        args.report,
        status=status,
        api_url=api_url,
        passed=passed,
        failed=failed,
        misses=misses,
        infrastructure_errors=infrastructure_errors,
        elapsed=elapsed,
    )
    print(f"\nLive API: {passed} pass, {failed} translation fail, {len(infrastructure_errors)} infrastructure error ({elapsed:.1f}s)")
    for miss in misses[:20]:
        print(f"  FAIL {miss}")
    if len(misses) > 20:
        print(f"  ... and {len(misses) - 20} more")
    for error in infrastructure_errors[:10]:
        print(f"  INFRA {error}")
    if len(infrastructure_errors) > 10:
        print(f"  ... and {len(infrastructure_errors) - 10} more infrastructure errors")
    print(f"Report: {args.report}")
    print(status)
    return 0 if status == "PASS" else (2 if status == "INFRASTRUCTURE_ERROR" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
