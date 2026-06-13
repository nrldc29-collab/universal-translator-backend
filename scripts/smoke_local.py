#!/usr/bin/env python3
"""Quick local stack verification after setup_models (no server required)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _post_json(url: str, payload: dict, headers: dict | None = None) -> tuple[int, dict | str]:
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw


def _post_json_with_retry(
    url: str,
    payload: dict,
    headers: dict | None = None,
    *,
    retries: int = 4,
) -> tuple[int, dict | str]:
    status = 0
    response: dict | str = {}
    for attempt in range(retries):
        status, response = _post_json(url, payload, headers)
        if status != 429:
            return status, response
        time.sleep(min(8, 1 + attempt * 2))
    return status, response


def _get_json(url: str, headers: dict | None = None, timeout: int = 10) -> tuple[int, dict | str]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


def _get_text(url: str, headers: dict | None = None, timeout: int = 10) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


def check_imports() -> list[str]:
    errors: list[str] = []
    for module in ("fastapi", "faster_whisper", "transformers", "torch", "sacremoses"):
        try:
            __import__(module)
        except ImportError:
            errors.append(f"missing python package: {module}")
    try:
        __import__("piper")
    except ImportError:
        try:
            from tts.tts_readiness import is_neural_tts_ready

            if not is_neural_tts_ready():
                errors.append("missing python package: piper (install edge-tts + ffmpeg for neural voice)")
        except ImportError:
            errors.append("missing python package: piper")
    return errors


def check_model_files() -> list[str]:
    errors: list[str] = []
    required = [
        ROOT / "models" / "tts" / "en_US-lessac-medium.onnx",
        ROOT / "models" / "tts" / "en_US-lessac-medium.onnx.json",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing file: {path.relative_to(ROOT)}")
    return errors


def _smoke_login_credentials(base_url: str) -> tuple[str, str]:
    user = os.getenv("SMOKE_USERNAME", "").strip()
    password = os.getenv("SMOKE_PASSWORD", "").strip()
    if user and password:
        return user, password
    use_users_env = (
        os.getenv("SMOKE_REMOTE", "").strip().lower() in {"1", "true", "yes", "on"}
        or not _is_local_smoke_url(base_url)
    )
    if use_users_env:
        raw_users = os.getenv("USERS", "demo:demo").strip()
        if ":" in raw_users:
            username, user_password = raw_users.split(":", 1)
            return username.strip(), user_password.strip()
    return "demo", "demo"


def check_health(base_url: str) -> list[str]:
    errors: list[str] = []
    url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"health check failed ({url}): {exc}")
        return errors
    if not payload.get("ready"):
        blockers = payload.get("blockers") or []
        errors.append(f"backend not ready: {blockers or payload.get('status')}")
    return errors


def check_translate(base_url: str, auth: dict[str, str]) -> list[str]:
    errors: list[str] = []
    root = base_url.rstrip("/")

    status, payload = _post_json_with_retry(
        f"{root}/translate/text",
        {
            "text": "hello",
            "source_language": "en",
            "target_language": "es",
            "session_id": "smoke-es",
        },
        auth,
    )
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"translate en->es failed ({status}): {payload}")
    else:
        translated = str(payload.get("translated_text") or "")
        if "hola" not in translated.lower():
            errors.append(f"translate en->es unexpected result: {translated!r}")
        if translated.startswith("[") and "->" in translated[:12]:
            errors.append(f"translate en->es returned placeholder output: {translated!r}")

    status, payload = _post_json_with_retry(
        f"{root}/translate/text",
        {
            "text": "I need help",
            "source_language": "en",
            "target_language": "ht",
            "session_id": "smoke-ht",
        },
        auth,
    )
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"translate en->ht failed ({status}): {payload}")
    else:
        translated = str(payload.get("translated_text") or "")
        if "èd" not in translated.lower() and "ed" not in translated.lower():
            errors.append(f"translate en->ht glossary miss: {translated!r}")

    status, payload = _post_json_with_retry(
        f"{root}/translate/text",
        {
            "text": "M ap byen",
            "source_language": "ht",
            "target_language": "en",
            "session_id": "smoke-ht-en",
        },
        auth,
    )
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"translate ht->en failed ({status}): {payload}")
    else:
        translated = str(payload.get("translated_text") or "")
        if not translated.strip():
            errors.append(f"translate ht->en returned empty text: {payload}")
        elif translated.startswith("[") and "->" in translated[:12]:
            errors.append(f"translate ht->en returned placeholder output: {translated!r}")

    status, payload = _post_json_with_retry(
        f"{root}/translate/text",
        {
            "text": "I need help",
            "source_language": "en",
            "target_language": "ht",
            "session_id": f"smoke-ht-flip-{uuid4()}",
        },
        auth,
    )
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"translate en->ht failed ({status}): {payload}")
    else:
        translated = str(payload.get("translated_text") or "").lower()
        if payload.get("clarify"):
            errors.append(f"translate en->ht returned clarification instead of translation: {payload.get('clarify_message')}")
        elif not translated.strip():
            errors.append(f"translate en->ht returned empty text: {payload}")
        elif translated.startswith("[") and "->" in translated[:12]:
            errors.append(f"translate en->ht returned placeholder output: {translated!r}")

    status, payload = _post_json_with_retry(
        f"{root}/translate/text",
        {
            "text": "hello",
            "source_language": "en",
            "target_language": "es",
            "session_id": "smoke-tts",
            "synthesize_audio": True,
            "audio_response_format": "url",
        },
        auth,
    )
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"translate with audio failed ({status}): {payload}")
    elif not (payload.get("audio_url") or payload.get("audio_base64")):
        errors.append("translate with audio returned no playable payload")

    return errors


def check_languages(base_url: str) -> list[str]:
    errors: list[str] = []
    url = f"{base_url.rstrip('/')}/languages"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"languages check failed ({url}): {exc}")
        return errors
    languages = payload.get("languages")
    if isinstance(languages, dict):
        if not languages:
            errors.append(f"languages endpoint returned empty map: {payload}")
    elif isinstance(languages, list):
        if not languages:
            errors.append(f"languages endpoint returned empty list: {payload}")
    else:
        errors.append(f"languages endpoint invalid payload: {payload}")
    return errors


def check_diagnostics(base_url: str) -> list[str]:
    errors: list[str] = []
    status, payload = _get_json(f"{base_url.rstrip('/')}/diagnostics")
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"diagnostics check failed ({status}): {payload}")
        return errors
    if not payload.get("ready"):
        errors.append(f"diagnostics reports not ready: {payload.get('status')}")
    frontend = payload.get("frontend") or {}
    if frontend.get("mode") == "embedded_dist" and not frontend.get("reachable"):
        errors.append(f"embedded frontend not reachable: {frontend}")
    return errors


def _frontend_asset_root(base_url: str) -> tuple[str, str | None]:
    status, payload = _get_json(f"{base_url.rstrip('/')}/diagnostics")
    if status != 200 or not isinstance(payload, dict):
        return base_url.rstrip("/"), None
    frontend = payload.get("frontend") or {}
    mode = frontend.get("mode")
    if mode == "embedded_dist":
        return base_url.rstrip("/"), mode
    if mode == "dev_proxy" and frontend.get("reachable"):
        target = str(frontend.get("target") or "").rstrip("/")
        if target:
            return target, mode
    return base_url.rstrip("/"), mode


def check_pwa_assets(base_url: str) -> list[str]:
    errors: list[str] = []
    root, mode = _frontend_asset_root(base_url)
    if mode == "dev_proxy" and root == base_url.rstrip("/"):
        return errors
    status, raw_payload = _get_json(f"{root}/manifest.json")
    if status != 200 or not isinstance(raw_payload, dict):
        errors.append(f"manifest fetch failed ({status}): {raw_payload}")
        return errors
    if raw_payload.get("name") != "Anai Translator":
        errors.append(f"manifest app name is not Anai Translator: {raw_payload.get('name')!r}")
        return errors
    payload = raw_payload
    if payload.get("display") != "standalone":
        errors.append(f"manifest display is not standalone: {payload.get('display')!r}")
    icons = payload.get("icons") or []
    if not any(icon.get("src") == "/icons/icon-512.png" for icon in icons if isinstance(icon, dict)):
        errors.append("manifest is missing the 512px app icon")
    icon_status, _ = _get_text(f"{root}/icons/icon-512.png")
    if icon_status != 200:
        errors.append(f"app icon fetch failed ({icon_status})")

    sw_status, sw_body = _get_text(f"{root}/sw.js")
    if sw_status != 200:
        errors.append(f"service worker fetch failed ({sw_status})")
        return errors
    if "anai-translator-shell-" not in sw_body:
        errors.append("service worker is not using the Anai Translator cache")
    if "cacheDiscoveredShellAssets" not in sw_body or "/offline.html" not in sw_body:
        errors.append("service worker is missing offline shell caching")
    return errors


def check_app_shell(base_url: str) -> list[str]:
    errors: list[str] = []
    root, mode = _frontend_asset_root(base_url)
    if mode == "dev_proxy" and root == base_url.rstrip("/"):
        return errors
    url = root.rstrip("/") + "/"
    try:
        request = urllib.request.Request(url, headers={"Accept": "text/html"})
        with urllib.request.urlopen(request, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"app shell check failed ({url}): {exc}")
        return errors
    lowered = body.lower()
    if "anai translator" not in lowered and 'id="root"' not in lowered:
        errors.append("root URL did not return the Anai Translator app shell")
    return errors


def check_self_test_bundle(base_url: str) -> list[str]:
    errors: list[str] = []
    root, mode = _frontend_asset_root(base_url)
    if mode == "dev_proxy" and root == base_url.rstrip("/"):
        return errors
    url = root.rstrip("/") + "/"
    try:
        request = urllib.request.Request(url, headers={"Accept": "text/html"})
        with urllib.request.urlopen(request, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"self-test bundle check failed ({url}): {exc}")
        return errors

    import re

    script_paths = re.findall(r'<script[^>]+src="([^"]+)"', body)
    if not script_paths:
        errors.append("app shell did not include a JS bundle for self-test verification")
        return errors

    bundle_body = ""
    css_bodies: list[str] = []
    for script_path in script_paths:
        script_url = script_path if script_path.startswith("http") else f"{root.rstrip('/')}/{script_path.lstrip('/')}"
        status, bundle_body = _get_text(script_url)
        if status != 200:
            continue
        if re.search(r"Run Self Test|Self Test|runSelfTest", bundle_body):
            css_paths = re.findall(r'<link[^>]+href="([^"]+\.css)"', body)
            for css_path in css_paths:
                css_url = css_path if css_path.startswith("http") else f"{root.rstrip('/')}/{css_path.lstrip('/')}"
                css_status, css_body = _get_text(css_url)
                if css_status == 200:
                    css_bodies.append(css_body)
            combined = bundle_body + "\n".join(css_bodies)
            if not re.search(r"conv-waveform|neo-mode-btn|has-conversation", combined):
                errors.append("frontend bundle is missing conversation mode UI")
            return errors
    errors.append("frontend bundle is missing the browser self-test UI")
    return errors


def check_ready_details(base_url: str) -> list[str]:
    errors: list[str] = []
    url = f"{base_url.rstrip('/')}/ready"
    deadline = time.time() + 120
    payload: dict | str = {}
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"ready check failed ({url}): {exc}")
            return errors
        if payload.get("ready"):
            break
        time.sleep(2)
    else:
        blockers = payload.get("blockers") or payload.get("readiness", {}).get("blockers") or []
        errors.append(f"/ready not ready after 120s: {blockers or payload.get('status')}")
        return errors
    models = payload.get("models") or {}
    if models.get("translation_backend") not in {"marian", "hybrid", "lightweight"}:
        errors.append(f"/ready missing translation backend metadata: {models}")
    readiness = payload.get("readiness") or {}
    neural_ready = readiness.get("neural_tts_ready")
    if neural_ready is None:
        try:
            from tts.tts_readiness import is_neural_tts_ready

            neural_ready = is_neural_tts_ready()
        except ImportError:
            neural_ready = False
    if readiness.get("espeak_available") is False and not neural_ready:
        errors.append("/ready reports espeak unavailable — Haitian Creole TTS will not work")
    blockers = payload.get("blockers") or readiness.get("blockers") or []
    for blocker in blockers:
        if "espeak" in str(blocker).lower() and not neural_ready:
            errors.append(f"/ready espeak blocker: {blocker}")
    return errors


async def _ws_translate_roundtrip(base_url: str, token: str) -> list[str]:
    import websockets

    ws_base = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/translate?access_token={quote(token)}"
    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if ready.get("type") != "ready":
                return [f"ws/translate bad ready frame: {ready}"]
            await ws.send(json.dumps({"text": "hello", "source_language": "en", "target_language": "es"}))
            reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            if reply.get("type") != "translation":
                return [f"ws/translate unexpected reply: {reply}"]
            translated = str(reply.get("translated_text") or "")
            if "hola" not in translated.lower():
                return [f"ws/translate en->es unexpected: {translated!r}"]
    except (TimeoutError, OSError, ConnectionError, json.JSONDecodeError) as exc:
        return [f"ws/translate failed: {exc}"]
    except Exception as exc:
        return [f"ws/translate failed: {exc}"]
    return []


def check_websocket_translate(base_url: str, token: str) -> list[str]:
    return asyncio.run(_ws_translate_roundtrip(base_url, token))


async def _expect_speaker(ws, expected_speaker: str, expected_label: str) -> dict:
    speaker_message: dict | None = None
    for _ in range(20):
        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        if message.get("type") == "error":
            raise RuntimeError(f"WebSocket error while waiting for speaker detection: {message}")
        if message.get("type") == "speaker_detected":
            if message.get("speaker") != expected_speaker:
                raise RuntimeError(f"Expected {expected_speaker}, got {message}")
            if message.get("speaker_label") != expected_label:
                raise RuntimeError(f"Expected {expected_label}, got {message}")
            if message.get("detection") != "device_source":
                raise RuntimeError(f"Expected device_source detection, got {message}")
            speaker_message = message
            continue
        if speaker_message and message.get("type") in {"turn", "session_restored", "listening", "config_ack"}:
            if message.get("type") == "listening":
                return speaker_message
            continue
    if speaker_message:
        return speaker_message
    raise RuntimeError("Timed out waiting for speaker_detected")


async def _ws_audio_speaker_session(base_url: str, token: str) -> list[str]:
    import websockets

    ws_base = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/audio?access_token={quote(token)}"
    session_id = f"smoke-{uuid4()}"
    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if ready.get("type") != "ready":
                return [f"ws/audio bad ready frame: {ready}"]
            await ws.send(json.dumps({"type": "ping"}))
            pong = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if pong.get("type") != "pong":
                return [f"ws/audio unexpected ping reply: {pong}"]

            async def start_device(device_id: str, expected_speaker: str, expected_label: str) -> dict:
                await ws.send(
                    json.dumps(
                        {
                            "type": "start",
                            "session_id": session_id,
                            "device_id": device_id,
                            "speaker_mode": "auto",
                            "source_language": "en",
                            "target_language": "es",
                            "mime_type": "audio/webm;codecs=opus",
                        }
                    )
                )
                return await _expect_speaker(ws, expected_speaker, expected_label)

            first = await start_device("smoke-device-1", "person-1", "Person 1")
            same = await start_device("smoke-device-1", "person-1", "Person 1")
            second = await start_device("smoke-device-2", "person-2", "Person 2")
            if first.get("speaker_label") != "Person 1" or same.get("speaker_label") != "Person 1":
                return [f"ws/audio auto speaker labels unstable: {first}, {same}"]
            if second.get("speaker_label") != "Person 2":
                return [f"ws/audio auto speaker device-2 failed: {second}"]
    except (TimeoutError, OSError, ConnectionError, json.JSONDecodeError, RuntimeError) as exc:
        return [f"ws/audio speaker session failed: {exc}"]
    except Exception as exc:
        return [f"ws/audio speaker session failed: {exc}"]
    return []


def check_websocket_speaker_session(base_url: str, token: str) -> list[str]:
    return asyncio.run(_ws_audio_speaker_session(base_url, token))


async def _ws_audio_ping(base_url: str, token: str) -> list[str]:
    import websockets

    ws_base = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/audio?access_token={quote(token)}"
    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if ready.get("type") != "ready":
                return [f"ws/audio bad ready frame: {ready}"]
            await ws.send(json.dumps({"type": "ping"}))
            reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if reply.get("type") != "pong":
                return [f"ws/audio unexpected reply: {reply}"]
    except (TimeoutError, OSError, ConnectionError, json.JSONDecodeError) as exc:
        return [f"ws/audio failed: {exc}"]
    except Exception as exc:
        return [f"ws/audio failed: {exc}"]
    return []


def check_websocket_audio(base_url: str, token: str) -> list[str]:
    return asyncio.run(_ws_audio_ping(base_url, token))


async def _ws_stt_only_start(base_url: str, token: str) -> list[str]:
    import websockets

    ws_base = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/audio?access_token={quote(token)}"
    try:
        async with websockets.connect(ws_url, open_timeout=15) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if ready.get("type") != "ready":
                return [f"ws/stt_only bad ready frame: {ready}"]
            await ws.send(json.dumps({
                "type": "start",
                "source_language": "en",
                "target_language": "ht",
                "speaker_mode": "auto",
                "speaker": "auto",
                "device_id": "smoke-stt-only",
                "stt_only": True,
                "mime_type": "audio/webm;codecs=opus",
            }))
            saw_listening = False
            for _ in range(20):
                message = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if message.get("type") == "error":
                    return [f"ws/stt_only error: {message}"]
                if message.get("type") == "listening":
                    saw_listening = True
                    break
            if not saw_listening:
                return ["ws/stt_only missing listening ack"]
    except (TimeoutError, OSError, ConnectionError, json.JSONDecodeError) as exc:
        return [f"ws/stt_only failed: {exc!r}"]
    except Exception as exc:
        return [f"ws/stt_only failed: {exc!r}"]
    return []


def check_websocket_stt_only(base_url: str, token: str) -> list[str]:
    return asyncio.run(_ws_stt_only_start(base_url, token))


async def _ws_conversation_triple(base_url: str, token: str) -> list[str]:
    import websockets

    ws_base = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/audio?access_token={quote(token)}"
    session_id = f"smoke-conv-{uuid4()}"

    async def await_ready(ws) -> None:
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        if ready.get("type") != "ready":
            raise RuntimeError(f"bad ready frame: {ready}")

    async def start_stream(
        ws,
        *,
        device_id: str,
        source_language: str,
        target_language: str,
        speaker: str,
        stt_only: bool = False,
    ) -> None:
        await ws.send(
            json.dumps(
                {
                    "type": "start",
                    "session_id": session_id,
                    "device_id": device_id,
                    "source_language": source_language,
                    "target_language": target_language,
                    "speaker_mode": "manual",
                    "speaker": speaker,
                    "speaker_label": f"Person {speaker}",
                    "stt_only": stt_only,
                    "mime_type": "audio/webm;codecs=opus",
                }
            )
        )
        saw_listening = False
        for _ in range(25):
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if message.get("type") == "error":
                raise RuntimeError(f"start error on {device_id}: {message}")
            if message.get("type") == "listening":
                saw_listening = True
                break
        if not saw_listening:
            raise RuntimeError(f"no listening ack on {device_id}")

    try:
        async with (
            websockets.connect(ws_url, open_timeout=15) as ws_ab,
            websockets.connect(ws_url, open_timeout=15) as ws_ba,
            websockets.connect(ws_url, open_timeout=15) as ws_stt,
        ):
            await await_ready(ws_ab)
            await await_ready(ws_ba)
            await await_ready(ws_stt)

            await start_stream(
                ws_ab,
                device_id="smoke-conv-ab",
                source_language="en",
                target_language="ht",
                speaker="A",
            )
            await start_stream(
                ws_ba,
                device_id="smoke-conv-ba",
                source_language="ht",
                target_language="en",
                speaker="B",
            )
            await start_stream(
                ws_stt,
                device_id="smoke-conv-stt",
                source_language="en",
                target_language="ht",
                speaker="auto",
                stt_only=True,
            )

            await ws_ab.send(
                json.dumps(
                    {
                        "type": "live_text",
                        "text": "Mwen bezwen èd",
                        "final": True,
                        "session_id": session_id,
                        "device_id": "smoke-conv-ab",
                        "source_language": "en",
                        "target_language": "ht",
                        "speaker_mode": "manual",
                        "speaker": "A",
                    }
                )
            )

            saw_english = False
            saw_final = False
            for _ in range(40):
                recv_tasks = {asyncio.create_task(ws.recv()): ws for ws in (ws_ab, ws_ba)}
                done, still_pending = await asyncio.wait(
                    recv_tasks.keys(),
                    timeout=30,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in still_pending:
                    task.cancel()
                if not done:
                    break
                raw = next(iter(done)).result()
                message = json.loads(raw)
                if message.get("type") == "error":
                    return [f"ws/conversation live_text error: {message}"]
                if message.get("type") in ("live_translation", "partial_translation"):
                    text = str(message.get("text") or "").lower()
                    if "help" in text or "need" in text:
                        saw_english = True
                if message.get("type") == "final" and message.get("source") == "browser_live_text":
                    saw_final = True
                if saw_english and saw_final:
                    break

            if not saw_english:
                return ["ws/conversation ht->en auto-flip returned no English translation"]
            if not saw_final:
                return ["ws/conversation ht->en missing final turn frame"]
    except (TimeoutError, OSError, ConnectionError, json.JSONDecodeError, RuntimeError) as exc:
        return [f"ws/conversation triple failed: {exc!r}"]
    except Exception as exc:
        return [f"ws/conversation triple failed: {exc!r}"]
    return []


def check_websocket_conversation_triple(base_url: str, token: str) -> list[str]:
    return asyncio.run(_ws_conversation_triple(base_url, token))


async def _ws_live_text_ht(base_url: str, token: str) -> list[str]:
    import websockets

    ws_base = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/audio?access_token={quote(token)}"
    try:
        async with websockets.connect(ws_url, open_timeout=15) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if ready.get("type") != "ready":
                return [f"ws/live_text bad ready frame: {ready}"]
            await ws.send(json.dumps({
                "type": "start",
                "source_language": "en",
                "target_language": "ht",
                "speaker_mode": "manual",
                "speaker": "A",
                "mime_type": "audio/webm;codecs=opus",
            }))
            await ws.send(json.dumps({
                "type": "live_text",
                "text": "I need help",
                "final": True,
                "source_language": "en",
                "target_language": "ht",
                "speaker_mode": "manual",
                "speaker": "A",
            }))
            saw_translation = False
            saw_final_tts = False
            saw_final = False
            for _ in range(60):
                message = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                if message.get("type") == "error":
                    return [f"ws/live_text error: {message}"]
                if message.get("type") in ("live_translation", "partial_translation", "partial_transcription"):
                    text = str(message.get("text") or "").lower()
                    if "èd" in text or "ed" in text or "bezwen" in text or "mwen" in text:
                        saw_translation = True
                if message.get("type") == "final" and message.get("source") == "browser_live_text":
                    saw_final = True
                if message.get("type") == "tts_end" and not message.get("partial"):
                    saw_final_tts = True
                if saw_translation and saw_final and saw_final_tts:
                    break
            if not saw_translation:
                return ["ws/live_text en->ht returned no Creole translation"]
            if not saw_final:
                return ["ws/live_text en->ht missing final turn frame"]
            if not saw_final_tts:
                return ["ws/live_text en->ht missing final tts_end"]
    except (TimeoutError, OSError, ConnectionError, json.JSONDecodeError) as exc:
        return [f"ws/live_text en->ht failed: {exc!r}"]
    except Exception as exc:
        return [f"ws/live_text en->ht failed: {exc!r}"]
    return []


def check_websocket_live_text_ht(base_url: str, token: str) -> list[str]:
    return asyncio.run(_ws_live_text_ht(base_url, token))


def check_tts(base_url: str, auth: dict[str, str]) -> list[str]:
    errors: list[str] = []
    root = base_url.rstrip("/")
    for language, text, label in (
        ("en", "hello", "en"),
        ("ht", "Mwen bezwen èd", "ht"),
    ):
        status, payload = _post_json_with_retry(
            f"{root}/tts",
            {"text": text, "language": language},
            auth,
        )
        if status != 200 or not isinstance(payload, dict):
            errors.append(f"tts {label} failed ({status}): {payload}")
            continue
        if not (payload.get("audio_base64") or payload.get("audio_url")):
            errors.append(f"tts {label} returned no audio")
    return errors


def _is_local_smoke_url(base_url: str) -> bool:
    if os.getenv("SMOKE_REMOTE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    from urllib.parse import urlparse

    host = (urlparse(base_url).hostname or "").lower()
    if host in {"127.0.0.1", "localhost"}:
        return True
    return host.startswith("192.168.") or host.startswith("10.") or host.startswith("172.")


def check_remote_runtime() -> list[str]:
    errors: list[str] = []
    try:
        import websockets  # noqa: F401
    except ImportError:
        errors.append("missing python package: websockets (pip install websockets)")
    return errors


def main() -> int:
    errors: list[str] = []
    base_url = sys.argv[1] if len(sys.argv) > 1 else ""

    if not base_url:
        errors.extend(check_imports())
        errors.extend(check_model_files())
    elif _is_local_smoke_url(base_url):
        errors.extend(check_imports())
        errors.extend(check_model_files())
    else:
        errors.extend(check_remote_runtime())

    if base_url:
        errors.extend(check_health(base_url))
        errors.extend(check_ready_details(base_url))
        errors.extend(check_languages(base_url))
        errors.extend(check_app_shell(base_url))
        errors.extend(check_self_test_bundle(base_url))
        errors.extend(check_diagnostics(base_url))
        errors.extend(check_pwa_assets(base_url))
        username, password = _smoke_login_credentials(base_url)
        login_status, login_payload = _post_json_with_retry(
            f"{base_url.rstrip('/')}/auth/login",
            {"username": username, "password": password},
        )
        if login_status != 200 or not isinstance(login_payload, dict) or not login_payload.get("access_token"):
            errors.append(f"auth login failed ({login_status}): {login_payload}")
        else:
            token = login_payload["access_token"]
            auth = {"Authorization": f"Bearer {token}"}
            errors.extend(check_translate(base_url, auth))
            errors.extend(check_tts(base_url, auth))
            errors.extend(check_websocket_translate(base_url, token))
            errors.extend(check_websocket_audio(base_url, token))
            errors.extend(check_websocket_live_text_ht(base_url, token))
            errors.extend(check_websocket_stt_only(base_url, token))
            errors.extend(check_websocket_conversation_triple(base_url, token))
            errors.extend(check_websocket_speaker_session(base_url, token))

    if errors:
        label = "Smoke check" if base_url and not _is_local_smoke_url(base_url) else "Local smoke check"
        print(f"{label} failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    label = "Smoke check" if base_url and not _is_local_smoke_url(base_url) else "Local smoke check"
    print(f"{label} passed.")
    if not base_url:
        print("Tip: run `python scripts/smoke_local.py http://127.0.0.1:8000` with backend up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
