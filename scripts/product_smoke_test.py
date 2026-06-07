"""Product smoke test for the Anai Translator phone URL.

Checks the public app URL, backend health/diagnostics, and the live WebSocket
translated-audio path. This is intentionally small so the launcher can run it
after startup and fail fast when the phone path would be silent.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import socket
import sys
import wave
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

import requests
import websockets


DEFAULT_EXPECTED = ""
DEFAULT_DOH_URL = "https://cloudflare-dns.com/dns-query"
INTERNAL_ARTIFACT_MARKERS = (
    "[AI:",
    "[AI_ERROR:",
    "[plugin-ai:",
    "Ensure this",
    "Keep meaning:",
    "->None",
)


def _ws_url(base_url: str) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunsplit((scheme, parts.netloc, "/ws/audio", "", ""))


def _resolve_with_doh(hostname: str, doh_url: str, timeout: int) -> list[str]:
    response = requests.get(
        doh_url,
        params={"name": hostname, "type": "A"},
        headers={"Accept": "application/dns-json"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    answers = payload.get("Answer") or []
    addresses = [item.get("data") for item in answers if item.get("type") == 1 and item.get("data")]
    if not addresses:
        raise AssertionError(f"DNS-over-HTTPS returned no A records for {hostname}.")
    return addresses


@contextmanager
def _public_dns_override(base_url: str, doh_url: str | None, timeout: int):
    if not doh_url:
        yield
        return

    hostname = urlsplit(base_url.rstrip("/")).hostname
    if not hostname:
        yield
        return

    try:
        socket.getaddrinfo(hostname, 443)
        resolved_with_system_dns = True
    except OSError:
        resolved_with_system_dns = False

    if resolved_with_system_dns:
        yield
        return

    addresses = _resolve_with_doh(hostname, doh_url, timeout)
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
        if host == hostname:
            return [
                (
                    socket.AF_INET,
                    socktype or socket.SOCK_STREAM,
                    proto or socket.IPPROTO_TCP,
                    "",
                    (address, port),
                )
                for address in addresses
            ]
        return original_getaddrinfo(host, port, family, socktype, proto, flags)

    socket.getaddrinfo = patched_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo


def _check_http(base_url: str, require_embedded: bool, timeout: int) -> dict:
    base = base_url.rstrip("/")
    app = requests.get(f"{base}/", timeout=timeout)
    app.raise_for_status()
    if "text/html" not in app.headers.get("content-type", ""):
        raise AssertionError("App root did not return HTML.")

    health = requests.get(f"{base}/health", timeout=timeout)
    health.raise_for_status()
    health_json = health.json()
    if health_json.get("ready") is not True:
        raise AssertionError(f"Backend is not ready: {health_json!r}")

    diagnostics = requests.get(f"{base}/diagnostics", timeout=timeout)
    diagnostics.raise_for_status()
    diagnostics_json = diagnostics.json()
    if diagnostics_json.get("ready") is not True:
        raise AssertionError(f"Diagnostics not ready: {diagnostics_json!r}")
    frontend = diagnostics_json.get("frontend") or {}
    if require_embedded and frontend.get("mode") != "embedded_dist":
        raise AssertionError(f"Frontend is not embedded_dist: {frontend!r}")

    return {
        "app_status": app.status_code,
        "health_ready": health_json.get("ready"),
        "frontend_mode": frontend.get("mode"),
    }


def _expected_values(expected: str) -> set[str]:
    return {value.strip() for value in expected.split("|") if value.strip()}


def _assert_translation_is_product_text(translated: str, expected: str) -> None:
    if not translated:
        raise AssertionError("No translated text received before audio.")
    if any(marker in translated for marker in INTERNAL_ARTIFACT_MARKERS):
        raise AssertionError(f"Internal AI artifact leaked into translation: {translated!r}")
    allowed = _expected_values(expected)
    if allowed and translated not in allowed:
        raise AssertionError(f"Unexpected translation: {translated!r}, expected one of {sorted(allowed)!r}")


async def _check_websocket_audio(
    base_url: str,
    source: str,
    target: str,
    phrase: str,
    expected: str,
    timeout: int,
) -> dict:
    ws_url = _ws_url(base_url)
    async with websockets.connect(ws_url, open_timeout=timeout, ping_interval=None) as websocket:
        ready = json.loads(await asyncio.wait_for(websocket.recv(), timeout))
        if ready.get("type") != "ready":
            raise AssertionError(f"Unexpected WebSocket ready payload: {ready!r}")

        await websocket.send(
            json.dumps(
                {
                    "type": "start",
                    "session_id": "launcher-product-smoke",
                    "device_id": "launcher-smoke",
                    "speaker_name": "Launcher Smoke",
                    "source_language": source,
                    "target_language": target,
                    "speaker_mode": "auto",
                    "speaker": "auto",
                    "mime_type": "audio/webm",
                }
            )
        )
        await websocket.send(
            json.dumps(
                {
                    "type": "live_text",
                    "text": phrase,
                    "final": True,
                    "utterance_id": 1,
                    "session_id": "launcher-product-smoke",
                    "device_id": "launcher-smoke",
                    "source_language": source,
                    "target_language": target,
                    "speaker_mode": "auto",
                    "speaker": "auto",
                }
            )
        )

        translated = ""
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            remaining = max(1, min(20, deadline - asyncio.get_running_loop().time()))
            message = json.loads(await asyncio.wait_for(websocket.recv(), remaining))
            message_type = message.get("type")
            if message_type in {"live_translation", "partial_translation"} and message.get("text"):
                translated = message["text"]
            if message_type == "tts_audio_chunk" and message.get("audio_base64"):
                audio = base64.b64decode(message["audio_base64"])
                with wave.open(io.BytesIO(audio), "rb") as wav_file:
                    duration = wav_file.getnframes() / float(wav_file.getframerate())
                _assert_translation_is_product_text(translated, expected)
                if len(audio) <= 1000 or duration <= 0.2:
                    raise AssertionError(f"Audio too small: bytes={len(audio)} duration={duration:.2f}s")
                return {
                    "translation": translated,
                    "spoken": message.get("text"),
                    "audio_bytes": len(audio),
                    "duration_seconds": round(duration, 2),
                }

    raise AssertionError(f"No translated audio received. Last translation: {translated!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--source", default="ht")
    parser.add_argument("--target", default="ru")
    parser.add_argument("--phrase", default="Mesi anpil")
    parser.add_argument("--expected", default=DEFAULT_EXPECTED)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--require-embedded", action="store_true")
    parser.add_argument("--doh-url", default=DEFAULT_DOH_URL)
    parser.add_argument("--no-doh", action="store_true")
    args = parser.parse_args()

    try:
        doh_url = None if args.no_doh else args.doh_url
        with _public_dns_override(args.base_url, doh_url, args.timeout):
            http_result = _check_http(args.base_url, args.require_embedded, args.timeout)
            ws_result = asyncio.run(
                _check_websocket_audio(
                    args.base_url,
                    args.source,
                    args.target,
                    args.phrase,
                    args.expected,
                    args.timeout,
                )
            )
    except Exception as exc:
        message = str(exc).strip() or f"{type(exc).__name__}: {exc!r}"
        print(json.dumps({"status": "fail", "error": message}, ensure_ascii=True))
        return 1

    print(json.dumps({"status": "pass", "http": http_result, "websocket": ws_result}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
