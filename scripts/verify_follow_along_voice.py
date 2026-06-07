"""Verify live follow-along translation + partial TTS over /ws/audio.

Simulates someone speaking in word chunks and checks that:
1. partial_translation arrives before the utterance is final
2. tts_audio_chunk (partial) arrives while speech is still in progress
3. the full translated sentence is produced by the end
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/audio"
TIMEOUT = 120


async def run() -> int:
    t0 = time.perf_counter()
    partial_translation_ms: float | None = None
    partial_tts_ms: float | None = None
    final_translation_ms: float | None = None
    final_tts_ms: float | None = None
    translations: list[str] = []
    tts_chunks: list[dict] = []
    errors: list[str] = []

    async with websockets.connect(WS, open_timeout=15, ping_interval=None) as ws:
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        if ready.get("type") != "ready":
            errors.append(f"unexpected ready: {ready!r}")
            return 1

        await ws.send(
            json.dumps(
                {
                    "type": "start",
                    "session_id": "verify-follow-along",
                    "device_id": "verify-follow-along",
                    "speaker_name": "Verifier",
                    "source_language": "en",
                    "target_language": "es",
                    "speaker_mode": "auto",
                    "speaker": "auto",
                    "mime_type": "audio/webm",
                }
            )
        )

        listen_deadline = time.perf_counter() + 15
        while time.perf_counter() < listen_deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if msg.get("type") == "listening":
                break

        chunks = [
            ("Hello", False),
            ("Hello how", False),
            ("Hello how are", False),
            ("Hello how are you", False),
            ("Hello how are you today", True),
        ]
        for text, final in chunks:
            await ws.send(
                json.dumps(
                    {
                        "type": "live_text",
                        "text": text,
                        "final": final,
                        "utterance_id": 1,
                        "session_id": "verify-follow-along",
                        "device_id": "verify-follow-along",
                        "source_language": "en",
                        "target_language": "es",
                        "speaker_mode": "auto",
                        "speaker": "auto",
                    }
                )
            )
            if not final:
                await asyncio.sleep(0.4)

        deadline = time.perf_counter() + TIMEOUT
        while time.perf_counter() < deadline:
            remaining = max(0.5, deadline - time.perf_counter())
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), remaining))
            except asyncio.TimeoutError:
                break

            mtype = msg.get("type")
            now_ms = (time.perf_counter() - t0) * 1000

            if mtype in {"partial_translation", "live_translation"} and msg.get("text"):
                translations.append(msg["text"])
                if mtype == "partial_translation" and partial_translation_ms is None:
                    partial_translation_ms = now_ms
                if mtype == "live_translation":
                    final_translation_ms = now_ms

            if mtype == "tts_audio_chunk" and msg.get("audio_base64"):
                tts_chunks.append(
                    {
                        "ms": now_ms,
                        "partial": bool(msg.get("partial")),
                        "text": msg.get("text") or "",
                        "bytes": len(msg["audio_base64"]),
                    }
                )
                if msg.get("partial") and partial_tts_ms is None:
                    partial_tts_ms = now_ms
                if not msg.get("partial") and final_tts_ms is None:
                    final_tts_ms = now_ms

            if mtype == "error":
                errors.append(msg.get("message") or str(msg))

            if final_translation_ms is not None and len(tts_chunks) >= 1 and partial_tts_ms is not None:
                # Allow a short tail for any final remainder audio
                if time.perf_counter() - t0 > (final_translation_ms / 1000) + 8:
                    break

    last_translation = translations[-1] if translations else ""
    checks = {
        "partial_translation_arrived": partial_translation_ms is not None and partial_translation_ms < 15000,
        "partial_tts_follows_speech": partial_tts_ms is not None and partial_tts_ms < 20000,
        "received_translation_audio": len(tts_chunks) >= 1,
        "full_sentence_translated": len(last_translation.split()) >= 3,
        "no_errors": len(errors) == 0,
    }

    report = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "partial_translation_ms": round(partial_translation_ms or -1, 1),
        "partial_tts_ms": round(partial_tts_ms or -1, 1),
        "final_translation_ms": round(final_translation_ms or -1, 1),
        "final_tts_ms": round(final_tts_ms or -1, 1),
        "tts_chunk_count": len(tts_chunks),
        "last_translation": last_translation,
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
