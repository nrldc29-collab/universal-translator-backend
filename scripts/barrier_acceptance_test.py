"""Acceptance test for the public Anai phone URL.

This verifies the product-level promise: selected-language text enters the live
WebSocket, translated text comes back in the selected target language, playable
voice audio is produced, and no internal prompt/AI artifacts leak to the user.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import io
import json
import os
import re
import socket
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import requests
import websockets


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "ht": "Haitian Creole",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
}

EXPECTED_FRONTEND_BUILD_ID = "continuous-interpreter-v32-soothing-voice"
EXPECTED_FRONTEND_ASSET_MARKER = "v32-soothing-voice"
MAX_FIRST_TRANSLATION_MS = 2000
MAX_FIRST_AUDIO_MS = 3500
MAX_HIGH_FREQUENCY_RATIO = 0.06

INTERNAL_ARTIFACT_MARKERS = (
    "[AI:",
    "[AI_ERROR:",
    "[plugin-ai:",
    "Ensure this",
    "Keep meaning:",
    "->None",
)

SCRIPT_PATTERNS = {
    "en": re.compile(r"[A-Za-z]"),
    "es": re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]"),
    "ht": re.compile(r"[A-Za-zÀ-ÿ]"),
    "fr": re.compile(r"[A-Za-zÀ-ÿ]"),
    "de": re.compile(r"[A-Za-zÄÖÜßäöü]"),
    "it": re.compile(r"[A-Za-zÀ-ÿ]"),
    "pt": re.compile(r"[A-Za-zÀ-ÿ]"),
    "nl": re.compile(r"[A-Za-zÀ-ÿ]"),
    "ru": re.compile(r"[\u0400-\u04ff]"),
    "zh": re.compile(r"[\u3400-\u9fff]"),
    "ja": re.compile(r"[\u3040-\u30ff\u3400-\u9fff]"),
    "ko": re.compile(r"[\uac00-\ud7af]"),
    "ar": re.compile(r"[\u0600-\u06ff]"),
    "hi": re.compile(r"[\u0900-\u097f]"),
}

EXPECTED_SUBSTRINGS = {
    ("en", "es"): ("hola",),
    ("en", "fr"): ("bonjour",),
    ("en", "de"): ("hallo",),
    ("en", "it"): ("ciao",),
    ("en", "pt"): ("ola", "olá"),
    ("en", "nl"): ("hallo",),
    ("en", "ru"): ("привет", "здрав"),
    ("en", "zh"): ("你好",),
    ("en", "ja"): ("こんにちは",),
    ("en", "ko"): ("안녕",),
    ("en", "ar"): ("مرح", "أهل", "اهل"),
    ("en", "hi"): ("नम",),
}

PHRASES = {
    "en": "Hello",
    "es": "Hola",
    "ht": "Mesi anpil",
    "fr": "Bonjour",
    "de": "Hallo",
    "it": "Ciao",
    "pt": "Ola",
    "nl": "Hallo",
    "ru": "Привет",
    "zh": "你好",
    "ja": "こんにちは",
    "ko": "안녕하세요",
    "ar": "مرحبا",
    "hi": "नमस्ते",
}


CONTINUOUS_DIALOGUE_CASES = (
    ("en", "fr", "Hello"),
    ("en", "ja", "Hello"),
    ("ht", "ru", "Mesi anpil"),
    ("es", "en", "Hola"),
)


@dataclass
class CaseResult:
    source: str
    target: str
    phrase: str
    translation: str
    spoken: str
    audio_bytes: int
    duration_seconds: float
    first_translation_ms: int | None
    first_audio_ms: int
    rms: float
    peak: float
    high_frequency_ratio: float


@dataclass
class TextCaseResult:
    source: str
    target: str
    phrase: str
    translation: str
    latency_ms: int


@dataclass
class ContinuousTurnResult:
    turn_index: int
    source: str
    target: str
    phrase: str
    translation: str
    spoken: str
    audio_bytes: int
    duration_seconds: float
    first_audio_ms: int
    rms: float
    peak: float
    high_frequency_ratio: float


def _ws_url(base_url: str) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunsplit((scheme, parts.netloc, "/ws/audio", "", ""))


def _system_dns_ready(base_url: str) -> None:
    host = urlsplit(base_url.rstrip("/")).hostname
    if not host:
        raise AssertionError("Base URL has no host.")
    socket.getaddrinfo(host, 443)


def _audio_metrics(audio: bytes) -> dict:
    with contextlib.closing(wave.open(io.BytesIO(audio), "rb")) as wav_file:
        sample_rate = wav_file.getframerate()
        frames = wav_file.getnframes()
        channels = wav_file.getnchannels()
        raw = wav_file.readframes(frames)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    duration = frames / float(sample_rate)
    rms = float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if samples.size:
        freqs = np.fft.rfftfreq(samples.size, 1.0 / sample_rate)
        power = np.abs(np.fft.rfft(samples)) ** 2
        high_ratio = float(power[freqs >= 6500].sum() / (power.sum() or 1.0))
    else:
        high_ratio = 1.0
    return {
        "duration_seconds": round(duration, 2),
        "rms": round(rms, 4),
        "peak": round(peak, 4),
        "high_frequency_ratio": round(high_ratio, 5),
    }


def _assert_translation(source: str, target: str, phrase: str, translated: str, *, allow_identical: bool = False) -> None:
    value = str(translated or "").strip()
    if not value:
        raise AssertionError("No translated text received.")
    if not allow_identical and value.strip().lower() == phrase.strip().lower() and source != target:
        raise AssertionError(f"Translation stayed identical to source: {value!r}")
    if any(marker in value for marker in INTERNAL_ARTIFACT_MARKERS):
        raise AssertionError(f"Internal AI artifact leaked into translation: {value!r}")
    expected = EXPECTED_SUBSTRINGS.get((source, target))
    lowered = value.casefold()
    if expected and not any(token.casefold() in lowered for token in expected):
        raise AssertionError(f"Unexpected {source}->{target} translation: {value!r}; expected one of {expected!r}")
    pattern = SCRIPT_PATTERNS.get(target)
    if pattern and not pattern.search(value):
        raise AssertionError(f"Translation does not appear to use {target} script/text: {value!r}")


def _assert_audio_payload(audio: bytes) -> dict:
    if len(audio) <= 1000:
        raise AssertionError(f"Audio too small: {len(audio)} bytes")
    metrics = _audio_metrics(audio)
    if metrics["duration_seconds"] <= 0.2:
        raise AssertionError(f"Audio too short: {metrics['duration_seconds']}s")
    if metrics["peak"] > 0.99:
        raise AssertionError(f"Audio is clipping: peak={metrics['peak']}")
    if metrics["rms"] < 0.01:
        raise AssertionError(f"Audio is too quiet/silent: rms={metrics['rms']}")
    if metrics["high_frequency_ratio"] > MAX_HIGH_FREQUENCY_RATIO:
        raise AssertionError(
            f"Audio still sounds too harsh: high_frequency_ratio={metrics['high_frequency_ratio']}"
        )
    return metrics


def _run_text_case(base_url: str, source: str, target: str, phrase: str, timeout: int) -> TextCaseResult:
    started = time.perf_counter()
    response = requests.post(
        base_url.rstrip("/") + "/translate/text",
        json={
            "text": phrase,
            "source_language": source,
            "target_language": target,
            "synthesize_audio": False,
            "session_id": "barrier-text-matrix",
            "device_id": "barrier-test",
            "speaker_name": "Barrier Test",
            "speaker_mode": "auto",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("clarify"):
        raise AssertionError(f"Unexpected clarification for {source}->{target}: {payload!r}")
    translation = str(payload.get("translated_text") or "").strip()
    _assert_translation(source, target, phrase, translation)
    latency_ms = int((time.perf_counter() - started) * 1000)
    if latency_ms > 5000:
        raise AssertionError(f"Text translation too slow: latency_ms={latency_ms}")
    return TextCaseResult(
        source=source,
        target=target,
        phrase=phrase,
        translation=translation,
        latency_ms=latency_ms,
    )


def _build_internal_text_translator(tier: str):
    os.environ["TRANSLATION_TIER"] = tier
    os.environ.setdefault("OLLAMA_ENABLED", "false")
    from translation.hybrid_translator import HybridTranslator

    return HybridTranslator()


def _run_internal_text_case(translator, source: str, target: str, phrase: str) -> TextCaseResult:
    started = time.perf_counter()
    translation = str(translator.translate(phrase, source, target) or "").strip()
    _assert_translation(source, target, phrase, translation, allow_identical=True)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return TextCaseResult(
        source=source,
        target=target,
        phrase=phrase,
        translation=translation,
        latency_ms=latency_ms,
    )


async def _run_ws_case(base_url: str, source: str, target: str, phrase: str, timeout: int) -> CaseResult:
    started = time.perf_counter()
    first_translation_ms = None
    translation = ""
    ws_url = _ws_url(base_url)
    async with websockets.connect(ws_url, open_timeout=timeout, ping_interval=None) as websocket:
        ready = json.loads(await asyncio.wait_for(websocket.recv(), timeout))
        if ready.get("type") != "ready":
            raise AssertionError(f"Unexpected ready payload: {ready!r}")
        payload_base = {
            "session_id": "barrier-acceptance",
            "device_id": "barrier-test",
            "speaker_name": "Barrier Test",
            "source_language": source,
            "target_language": target,
            "speaker_mode": "auto",
            "speaker": "auto",
        }
        await websocket.send(json.dumps({"type": "start", "mime_type": "audio/webm", **payload_base}))
        await websocket.send(json.dumps({"type": "live_text", "text": phrase, "final": True, "utterance_id": int(time.time() * 1000), **payload_base}))

        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            remaining = max(1, min(20, deadline - time.perf_counter()))
            message = json.loads(await asyncio.wait_for(websocket.recv(), remaining))
            message_type = message.get("type")
            if message_type in {"live_translation", "partial_translation"} and message.get("text"):
                translation = message["text"]
                if first_translation_ms is None:
                    first_translation_ms = int((time.perf_counter() - started) * 1000)
            if message_type == "tts_audio_chunk" and message.get("audio_base64"):
                if not translation:
                    translation = str(message.get("text") or "")
                _assert_translation(source, target, phrase, translation)
                audio = base64.b64decode(message["audio_base64"])
                metrics = _assert_audio_payload(audio)
                audio_ms = int((time.perf_counter() - started) * 1000)
                if first_translation_ms is not None and first_translation_ms > MAX_FIRST_TRANSLATION_MS:
                    raise AssertionError(
                        f"Translation too slow: first_translation_ms={first_translation_ms} threshold={MAX_FIRST_TRANSLATION_MS}"
                    )
                if audio_ms > MAX_FIRST_AUDIO_MS:
                    raise AssertionError(f"Audio too slow: first_audio_ms={audio_ms} threshold={MAX_FIRST_AUDIO_MS}")
                return CaseResult(
                    source=source,
                    target=target,
                    phrase=phrase,
                    translation=translation,
                    spoken=str(message.get("text") or ""),
                    audio_bytes=len(audio),
                    duration_seconds=metrics["duration_seconds"],
                    first_translation_ms=first_translation_ms,
                    first_audio_ms=audio_ms,
                    rms=metrics["rms"],
                    peak=metrics["peak"],
                    high_frequency_ratio=metrics["high_frequency_ratio"],
                )
    raise AssertionError(f"No translated audio received for {source}->{target}. Last translation={translation!r}")


async def _run_continuous_dialogue_case(base_url: str, timeout: int) -> list[ContinuousTurnResult]:
    ws_url = _ws_url(base_url)
    results: list[ContinuousTurnResult] = []
    async with websockets.connect(ws_url, open_timeout=timeout, ping_interval=None) as websocket:
        ready = json.loads(await asyncio.wait_for(websocket.recv(), timeout))
        if ready.get("type") != "ready":
            raise AssertionError(f"Unexpected ready payload: {ready!r}")

        session_id = "barrier-continuous-dialogue"
        device_id = "barrier-continuous-test"
        await websocket.send(json.dumps({
            "type": "start",
            "mime_type": "audio/webm",
            "session_id": session_id,
            "device_id": device_id,
            "speaker_name": "Continuous Barrier Test",
            "source_language": CONTINUOUS_DIALOGUE_CASES[0][0],
            "target_language": CONTINUOUS_DIALOGUE_CASES[0][1],
            "speaker_mode": "auto",
            "speaker": "auto",
        }))

        for index, (source, target, phrase) in enumerate(CONTINUOUS_DIALOGUE_CASES, start=1):
            print(f"[continuous {index}/{len(CONTINUOUS_DIALOGUE_CASES)}] {source}->{target}", file=sys.stderr, flush=True)
            await websocket.send(json.dumps({
                "type": "config",
                "session_id": session_id,
                "device_id": device_id,
                "speaker_name": "Continuous Barrier Test",
                "source_language": source,
                "target_language": target,
                "speaker_mode": "auto",
                "speaker": "auto",
            }))
            config_deadline = time.perf_counter() + timeout
            while time.perf_counter() < config_deadline:
                message = json.loads(await asyncio.wait_for(websocket.recv(), max(1, min(10, config_deadline - time.perf_counter()))))
                if message.get("type") != "config_ack":
                    continue
                if message.get("source_language") != source or message.get("target_language") != target:
                    raise AssertionError(f"Config ack language mismatch for {source}->{target}: {message!r}")
                break
            else:
                raise AssertionError(f"No config_ack received for {source}->{target}.")

            started = time.perf_counter()
            translation = ""
            utterance_id = f"continuous-{index}-{int(started * 1000)}"
            await websocket.send(json.dumps({
                "type": "live_text",
                "text": phrase,
                "final": True,
                "utterance_id": utterance_id,
                "session_id": session_id,
                "device_id": device_id,
                "speaker_name": "Continuous Barrier Test",
                "source_language": source,
                "target_language": target,
                "speaker_mode": "auto",
                "speaker": "auto",
            }))

            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                message = json.loads(await asyncio.wait_for(websocket.recv(), max(1, min(20, deadline - time.perf_counter()))))
                if message.get("utterance_id") not in {None, utterance_id}:
                    continue
                message_type = message.get("type")
                if message_type in {"live_translation", "partial_translation"} and message.get("text"):
                    if message.get("source_language") != source or message.get("target_language") != target:
                        raise AssertionError(f"Live translation language mismatch for {source}->{target}: {message!r}")
                    translation = str(message["text"])
                    _assert_translation(source, target, phrase, translation)
                if message_type == "tts_audio_chunk" and message.get("audio_base64"):
                    if message.get("source_language") != source or message.get("target_language") != target:
                        raise AssertionError(f"TTS chunk language mismatch for {source}->{target}: {message!r}")
                    if not translation:
                        translation = str(message.get("live_translation_text") or message.get("text") or "")
                    _assert_translation(source, target, phrase, translation)
                    audio = base64.b64decode(message["audio_base64"])
                    metrics = _assert_audio_payload(audio)
                    audio_ms = int((time.perf_counter() - started) * 1000)
                    if audio_ms > MAX_FIRST_AUDIO_MS:
                        raise AssertionError(f"Continuous turn audio too slow: first_audio_ms={audio_ms} threshold={MAX_FIRST_AUDIO_MS}")
                    results.append(ContinuousTurnResult(
                        turn_index=index,
                        source=source,
                        target=target,
                        phrase=phrase,
                        translation=translation,
                        spoken=str(message.get("text") or ""),
                        audio_bytes=len(audio),
                        duration_seconds=metrics["duration_seconds"],
                        first_audio_ms=audio_ms,
                        rms=metrics["rms"],
                        peak=metrics["peak"],
                        high_frequency_ratio=metrics["high_frequency_ratio"],
                    ))
                    break
            else:
                raise AssertionError(f"No continuous translated audio received for turn {index} {source}->{target}.")
    return results


async def _run_partial_case(base_url: str, timeout: int) -> dict:
    ws_url = _ws_url(base_url)
    started = time.perf_counter()
    translations: list[str] = []
    audio_seen = False
    async with websockets.connect(ws_url, open_timeout=timeout, ping_interval=None) as websocket:
        ready = json.loads(await asyncio.wait_for(websocket.recv(), timeout))
        if ready.get("type") != "ready":
            raise AssertionError(f"Unexpected ready payload: {ready!r}")
        payload_base = {
            "session_id": "barrier-partial",
            "device_id": "barrier-test",
            "speaker_name": "Barrier Test",
            "source_language": "en",
            "target_language": "fr",
            "speaker_mode": "auto",
            "speaker": "auto",
        }
        await websocket.send(json.dumps({"type": "start", "mime_type": "audio/webm", **payload_base}))
        await websocket.send(json.dumps({"type": "live_text", "text": "Hello", "final": False, "utterance_id": 4242, **payload_base}))
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            message = json.loads(await asyncio.wait_for(websocket.recv(), max(1, min(10, deadline - time.perf_counter()))))
            message_type = message.get("type")
            if message_type in {"live_translation", "partial_translation"} and message.get("text"):
                translations.append(message["text"])
            if message_type == "tts_audio_chunk" and message.get("audio_base64"):
                audio_seen = True
                audio = base64.b64decode(message["audio_base64"])
                metrics = _audio_metrics(audio)
                audio_ms = int((time.perf_counter() - started) * 1000)
                if audio_ms > MAX_FIRST_AUDIO_MS:
                    raise AssertionError(f"Partial audio too slow: first_audio_ms={audio_ms} threshold={MAX_FIRST_AUDIO_MS}")
                return {
                    "status": "pass",
                    "translation": translations[-1] if translations else message.get("text"),
                    "audio_bytes": len(audio),
                    "duration_seconds": metrics["duration_seconds"],
                    "first_audio_ms": audio_ms,
                }
        raise AssertionError(f"No partial live translated audio received. translations={translations!r} audio_seen={audio_seen}")


def _check_http(base_url: str, timeout: int) -> dict:
    root = requests.get(base_url.rstrip("/") + "/", timeout=timeout)
    root.raise_for_status()
    if "text/html" not in root.headers.get("content-type", ""):
        raise AssertionError("Root did not return HTML.")
    asset_paths = re.findall(r"""(?:src|href)=["']([^"']+\.(?:js|css))["']""", root.text)
    build_id_found = False
    for asset_path in asset_paths:
        asset_url = asset_path if asset_path.startswith("http") else base_url.rstrip("/") + "/" + asset_path.lstrip("/")
        asset_response = requests.get(asset_url, timeout=timeout)
        asset_response.raise_for_status()
        if EXPECTED_FRONTEND_ASSET_MARKER in asset_response.text:
            build_id_found = True
    if not build_id_found:
        raise AssertionError(f"Frontend build marker {EXPECTED_FRONTEND_ASSET_MARKER!r} was not found in served assets.")
    health = requests.get(base_url.rstrip("/") + "/health", timeout=timeout)
    health.raise_for_status()
    health_json = health.json()
    if health_json.get("ready") is not True:
        raise AssertionError(f"Health not ready: {health_json!r}")
    diagnostics = requests.get(base_url.rstrip("/") + "/diagnostics", timeout=timeout)
    diagnostics.raise_for_status()
    diag = diagnostics.json()
    if diag.get("ready") is not True:
        raise AssertionError(f"Diagnostics not ready: {diag!r}")
    frontend = diag.get("frontend") or {}
    if frontend.get("mode") != "embedded_dist":
        raise AssertionError(f"Frontend not embedded_dist: {frontend!r}")
    translation = diag.get("translation") or {}
    warmup_items = ((diag.get("voice_warmup") or {}).get("items") or [])
    if translation.get("remote_translator_reachable") is not True:
        raise AssertionError(f"Remote translator is not reachable: {translation!r}")
    if len(warmup_items) < len(LANGUAGES):
        raise AssertionError(f"Voice warmup did not cover all languages: {len(warmup_items)}/{len(LANGUAGES)}")
    return {
        "root_status": root.status_code,
        "health_ready": health_json.get("ready"),
        "frontend_mode": frontend.get("mode"),
        "translator_reachable": translation.get("remote_translator_reachable"),
        "voice_warmup_languages": len(warmup_items),
        "frontend_build_id": EXPECTED_FRONTEND_BUILD_ID,
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--pause", type=float, default=2.0)
    parser.add_argument("--all-pairs-text", action="store_true")
    parser.add_argument("--text-base-url", default="")
    parser.add_argument("--text-mode", choices=("http", "internal"), default="http")
    parser.add_argument("--internal-text-tier", choices=("auto", "remote", "local", "ollama"), default="remote")
    args = parser.parse_args()
    text_base_url = (args.text_base_url or args.base_url).rstrip("/")
    internal_translator = None
    if args.all_pairs_text and args.text_mode == "internal":
        internal_translator = _build_internal_text_translator(args.internal_text_tier)
        text_base_url = f"internal:hybrid:{args.internal_text_tier}"

    checks: dict = {}
    results: list[CaseResult] = []
    text_results: list[TextCaseResult] = []
    continuous_results: list[ContinuousTurnResult] = []
    errors: list[str] = []

    try:
        _system_dns_ready(args.base_url)
        checks["dns"] = "pass"
        checks["http"] = _check_http(args.base_url, args.timeout)
    except Exception as exc:
        print(json.dumps({"status": "fail", "stage": "readiness", "error": str(exc)}, ensure_ascii=False))
        return 1

    cases: list[tuple[str, str, str]] = []
    for target in LANGUAGES:
        if target != "en":
            cases.append(("en", target, PHRASES["en"]))
    cases.extend(
        [
            ("es", "en", PHRASES["es"]),
            ("fr", "en", PHRASES["fr"]),
            ("ht", "ru", PHRASES["ht"]),
            ("ja", "en", PHRASES["ja"]),
            ("ar", "en", PHRASES["ar"]),
            ("hi", "en", PHRASES["hi"]),
        ]
    )

    for source, target, phrase in cases:
        try:
            print(f"[voice] {source}->{target}", file=sys.stderr, flush=True)
            results.append(asyncio.run(_run_ws_case(args.base_url, source, target, phrase, args.timeout)))
        except Exception as exc:
            errors.append(f"{source}->{target}: {exc}")
        time.sleep(args.pause)

    if args.all_pairs_text:
        total_text_cases = len(LANGUAGES) * (len(LANGUAGES) - 1)
        completed_text_cases = 0
        for source in LANGUAGES:
            for target in LANGUAGES:
                if source == target:
                    continue
                try:
                    completed_text_cases += 1
                    print(f"[text {completed_text_cases}/{total_text_cases}] {source}->{target}", file=sys.stderr, flush=True)
                    if internal_translator is not None:
                        text_results.append(_run_internal_text_case(internal_translator, source, target, PHRASES[source]))
                    else:
                        text_results.append(_run_text_case(text_base_url, source, target, PHRASES[source], args.timeout))
                except Exception as exc:
                    errors.append(f"text {source}->{target}: {exc}")
                time.sleep(min(args.pause, 0.25))

    try:
        checks["continuous_dialogue"] = "running"
        continuous_results = asyncio.run(_run_continuous_dialogue_case(args.base_url, args.timeout))
        checks["continuous_dialogue"] = {
            "status": "pass",
            "turns": len(continuous_results),
            "avg_first_audio_ms": round(sum(turn.first_audio_ms for turn in continuous_results) / len(continuous_results)),
            "max_first_audio_ms": max(turn.first_audio_ms for turn in continuous_results),
        }
    except Exception as exc:
        errors.append(f"continuous_dialogue: {exc}")

    try:
        checks["partial_live_audio"] = asyncio.run(_run_partial_case(args.base_url, args.timeout))
    except Exception as exc:
        errors.append(f"partial_live_audio: {exc}")

    if errors:
        print(json.dumps({
            "status": "fail",
            "checks": checks,
            "passed_cases": [case.__dict__ for case in results],
            "passed_text_cases": [case.__dict__ for case in text_results],
            "passed_continuous_turns": [turn.__dict__ for turn in continuous_results],
            "errors": errors,
        }, ensure_ascii=False, indent=2))
        return 1

    summary = {
        "status": "pass",
        "thresholds": {
            "max_first_translation_ms": MAX_FIRST_TRANSLATION_MS,
            "max_first_audio_ms": MAX_FIRST_AUDIO_MS,
            "max_high_frequency_ratio": MAX_HIGH_FREQUENCY_RATIO,
        },
        "checks": checks,
        "case_count": len(results),
        "text_case_count": len(text_results),
        "continuous_turn_count": len(continuous_results),
        "text_matrix_base_url": text_base_url,
        "languages_exposed": len(LANGUAGES),
        "avg_first_audio_ms": round(sum(case.first_audio_ms for case in results) / len(results)),
        "max_first_audio_ms": max(case.first_audio_ms for case in results),
        "avg_peak": round(sum(case.peak for case in results) / len(results), 4),
        "max_peak": max(case.peak for case in results),
        "avg_high_frequency_ratio": round(sum(case.high_frequency_ratio for case in results) / len(results), 5),
        "cases": [case.__dict__ for case in results],
        "text_cases": [case.__dict__ for case in text_results],
        "continuous_turns": [turn.__dict__ for turn in continuous_results],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
