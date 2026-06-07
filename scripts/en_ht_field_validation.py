#!/usr/bin/env python3
"""
Phase 5 — EN↔HT field validation on the live streaming path.

Measures end-to-end latency, translation chrF against known references, and
STT word-error rate when synthetic speech audio is sent over the WebSocket.

Usage:
    python scripts/en_ht_field_validation.py --base-url http://127.0.0.1:8000
    python scripts/en_ht_field_validation.py --base-url https://your-deploy --token <JWT>
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import sys
import time
import wave
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import requests
import websockets

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Two-person dialogue: EN speaker then HT speaker (mirrors barrier acceptance).
DIALOGUE = (
    ("en", "ht", "Hello, how are you?", "Bonjou, kijan ou ye?"),
    ("ht", "en", "Mèsi anpil pou èd ou.", "Thank you very much for your help."),
    ("en", "ht", "Where is the nearest hospital?", "Kote lopital ki pi pre a ye?"),
    ("ht", "en", "Mwen bezwen yon doktè.", "I need a doctor."),
)

MAX_FIRST_TRANSLATION_MS = 4000
MAX_E2E_MS = 8000
MIN_CHRF = 25.0  # smoke floor on unverified refs; raise after native verification


def _ws_url(base_url: str) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunsplit((scheme, parts.netloc, "/ws/translate", "", ""))


def _normalize_words(text: str) -> list[str]:
    text = re.sub(r"[^\w\s'-]", " ", (text or "").lower())
    return [w for w in text.split() if w]


def word_error_rate(hypothesis: str, reference: str) -> float:
    """Levenshtein WER on word tokens (0 = perfect)."""
    ref = _normalize_words(reference)
    hyp = _normalize_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[n][m] / n


def sentence_chrf(hypothesis: str, reference: str) -> float:
    try:
        from sacrebleu.metrics import CHRF
    except ImportError:
        return 0.0
    if not hypothesis or not reference:
        return 0.0
    return round(CHRF(word_order=2).sentence_score(hypothesis, [reference]).score, 2)


def make_speech_wav(text: str, duration: float = 2.5, sample_rate: int = 16000) -> bytes:
    """Synthetic speech-like audio for STT smoke (not broadcast quality)."""
    n = int(sample_rate * duration)
    t = np.linspace(0, duration, n)
    waveform = (
        0.45 * np.sin(2 * np.pi * 180 * t)
        + 0.25 * np.sin(2 * np.pi * 360 * t)
        + 0.15 * np.sin(2 * np.pi * 720 * t)
    )
    envelope = np.sin(np.pi * t / duration) ** 0.6
    waveform = np.clip(waveform * envelope, -1, 1)
    pcm = (waveform * 32767).astype(np.int16)
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


@dataclass
class TurnResult:
    source_lang: str
    target_lang: str
    source_text: str
    reference_translation: str
    stt_text: str = ""
    translated_text: str = ""
    first_translation_ms: float = 0.0
    e2e_ms: float = 0.0
    chrf: float = 0.0
    wer: float = 0.0
    errors: list[str] = field(default_factory=list)


async def run_turn(
    ws_url: str,
    headers: dict,
    source_lang: str,
    target_lang: str,
    source_text: str,
    reference: str,
) -> TurnResult:
    result = TurnResult(source_lang, target_lang, source_text, reference)
    audio = make_speech_wav(source_text)
    started = time.perf_counter()
    first_translation_at: float | None = None

    async with websockets.connect(ws_url, additional_headers=headers, open_timeout=30) as ws:
        await ws.send(json.dumps({
            "type": "config",
            "source_language": source_lang,
            "target_language": target_lang,
            "partial_tts": False,
        }))
        await ws.send(json.dumps({
            "type": "audio",
            "data": base64.b64encode(audio).decode("ascii"),
            "final": True,
        }))
        deadline = time.perf_counter() + 45
        while time.perf_counter() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=12)
            except asyncio.TimeoutError:
                result.errors.append("timeout waiting for server message")
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type", "")
            if mtype in {"partial_stt", "stt"} and msg.get("text"):
                result.stt_text = str(msg["text"]).strip()
            if mtype in {"partial_translation", "translation"} and msg.get("text"):
                if first_translation_at is None:
                    first_translation_at = time.perf_counter()
                    result.translated_text = str(msg["text"]).strip()
            if mtype == "translation" and msg.get("text"):
                result.translated_text = str(msg["text"]).strip()
                break
            if mtype == "error":
                result.errors.append(str(msg.get("message", msg)))
                break

    result.e2e_ms = round((time.perf_counter() - started) * 1000, 1)
    if first_translation_at is not None:
        result.first_translation_ms = round((first_translation_at - started) * 1000, 1)
    result.chrf = sentence_chrf(result.translated_text, reference)
    result.wer = round(word_error_rate(result.stt_text, source_text), 3)
    return result


def wait_for_health(base_url: str, timeout_s: float = 90) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base_url.rstrip('/')}/health", timeout=5)
            if resp.ok:
                data = resp.json()
                if data.get("ready") or data.get("status") == "ok":
                    return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise SystemExit(f"Backend not ready at {base_url}")


async def main_async(args) -> int:
    wait_for_health(args.base_url)
    ws_url = _ws_url(args.base_url)
    headers = {}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    print(f"EN↔HT field validation — {ws_url}\n")
    results: list[TurnResult] = []
    for src, tgt, text, ref in DIALOGUE:
        print(f"  {src}→{tgt}: {text[:50]}...")
        turn = await run_turn(ws_url, headers, src, tgt, text, ref)
        results.append(turn)
        status = "OK" if not turn.errors else "ERR"
        print(
            f"    [{status}] chrF++={turn.chrf:>5}  WER={turn.wer:.2f}  "
            f"1st={turn.first_translation_ms:.0f}ms  e2e={turn.e2e_ms:.0f}ms"
        )
        if turn.translated_text:
            print(f"    out: {turn.translated_text[:120]}")
        for err in turn.errors:
            print(f"    ! {err}")

    avg_chrf = sum(r.chrf for r in results) / max(1, len(results))
    avg_lat = sum(r.first_translation_ms for r in results if r.first_translation_ms) / max(
        1, sum(1 for r in results if r.first_translation_ms)
    )
    failures = []
    if avg_chrf < args.min_chrf:
        failures.append(f"avg chrF++ {avg_chrf:.1f} < {args.min_chrf}")
    for r in results:
        if r.first_translation_ms and r.first_translation_ms > MAX_FIRST_TRANSLATION_MS:
            failures.append(f"{r.source_lang}→{r.target_lang} first translation {r.first_translation_ms}ms slow")
        if r.e2e_ms > MAX_E2E_MS:
            failures.append(f"{r.source_lang}→{r.target_lang} e2e {r.e2e_ms}ms slow")

    report = {
        "base_url": args.base_url,
        "dialogue_turns": len(results),
        "avg_chrfpp": round(avg_chrf, 2),
        "avg_first_translation_ms": round(avg_lat, 1),
        "turns": [
            {
                "direction": f"{r.source_lang}-{r.target_lang}",
                "source": r.source_text,
                "reference": r.reference_translation,
                "stt": r.stt_text,
                "translation": r.translated_text,
                "chrfpp": r.chrf,
                "wer": r.wer,
                "first_translation_ms": r.first_translation_ms,
                "e2e_ms": r.e2e_ms,
                "errors": r.errors,
            }
            for r in results
        ],
        "failures": failures,
    }
    out_dir = REPO_ROOT / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"field_validation_{int(time.time())}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nAvg chrF++: {avg_chrf:.1f}   Avg first translation: {avg_lat:.0f}ms")
    print(f"Report: {out_path}")
    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("PASS: EN↔HT streaming field validation")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EN↔HT streaming field validation (Phase 5)")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--token", default=None)
    p.add_argument("--min-chrf", type=float, default=MIN_CHRF)
    return p


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async(build_parser().parse_args())))
