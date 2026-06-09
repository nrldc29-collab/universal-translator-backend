#!/usr/bin/env python3
"""
Phase 5 — EN<->HT field validation against a running backend.

Measures the three things that decide whether the barrier is actually broken,
end to end, on real audio:

  - translation chrF++  : is the translation faithful? (vs known references)
  - STT word-error-rate : does speech-to-text hear the sentence correctly?
  - latency             : how long does audio -> translation take?

How it works (all over verified HTTP endpoints, no fragile WS framing):
  1. POST /tts            synthesize each source sentence into real speech audio
                          in its own language (so STT has real words to hear).
  2. POST /translate/audio send that audio through STT -> translation.
  3. Compare the returned STT transcript to the original sentence (WER) and the
     translation to the known reference (chrF); time the /translate/audio call.

If TTS is unavailable, the script degrades to a text-only check over
/translate/text (chrF + latency, no WER) so it still produces a signal.

Usage:
    python scripts/en_ht_field_validation.py --base-url http://127.0.0.1:8000
    python scripts/en_ht_field_validation.py --base-url https://your-deploy --token <JWT>
    python scripts/en_ht_field_validation.py --text-only      # skip audio/WER
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]

# Two-person dialogue: alternating EN and HT speakers (the barrier-acceptance case).
DIALOGUE = (
    ("en", "ht", "Hello, how are you?", "Bonjou, kijan ou ye?"),
    ("ht", "en", "Mèsi anpil pou èd ou.", "Thank you very much for your help."),
    ("en", "ht", "Where is the nearest hospital?", "Kote lopital ki pi pre a ye?"),
    ("ht", "en", "Mwen bezwen yon doktè.", "I need a doctor."),
    ("en", "ht", "Please speak slowly.", "Tanpri pale dousman."),
    ("ht", "en", "Mwen pa konprann.", "I do not understand."),
)

MAX_E2E_MS = 8000
MIN_CHRF = 25.0  # smoke floor on unverified refs; raise after native verification


def _normalize_words(text: str) -> list[str]:
    text = re.sub(r"[^\w\s'-]", " ", (text or "").lower())
    return [w for w in text.split() if w]


def word_error_rate(hypothesis: str, reference: str) -> float:
    """Levenshtein word-error-rate (0 = perfect transcription)."""
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
        sys.exit("ERROR: sacrebleu is required. Run: pip install sacrebleu")
    if not hypothesis or not reference:
        return 0.0
    return round(CHRF(word_order=2).sentence_score(hypothesis, [reference]).score, 2)


@dataclass
class TurnResult:
    source_lang: str
    target_lang: str
    source_text: str
    reference_translation: str
    stt_text: str = ""
    translated_text: str = ""
    e2e_ms: float = 0.0
    chrf: float = 0.0
    wer: float | None = None
    errors: list[str] = field(default_factory=list)


class Backend:
    def __init__(self, base_url: str, token: str | None, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def wait_for_ready(self, timeout_s: float = 120) -> None:
        deadline = time.time() + timeout_s
        last = ""
        while time.time() < deadline:
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=5)
                if resp.ok:
                    data = resp.json()
                    if data.get("ready") or data.get("status") == "ok":
                        return
                    last = f"health={data}"
            except requests.RequestException as exc:
                last = str(exc)
            time.sleep(2)
        sys.exit(f"Backend not ready at {self.base_url} ({last})")

    def tts(self, text: str, language: str) -> bytes | None:
        """Synthesize speech audio for `text` in `language`; None if unavailable."""
        try:
            resp = requests.post(
                f"{self.base_url}/tts",
                json={"text": text, "language": language, "response_format": "base64"},
                headers={**self.headers, "Content-Type": "application/json"},
                timeout=self.timeout,
            )
            if resp.status_code == 503:
                return None
            resp.raise_for_status()
            b64 = resp.json().get("audio_base64")
            return base64.b64decode(b64) if b64 else None
        except (requests.RequestException, ValueError):
            return None

    def translate_audio(self, wav: bytes, src: str, tgt: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/translate/audio",
            files={"audio": ("speech.wav", wav, "audio/wav")},
            data={"source_language": src, "target_language": tgt, "synthesize_audio": "false"},
            headers=self.headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def translate_text(self, text: str, src: str, tgt: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/translate/text",
            json={"text": text, "source_language": src, "target_language": tgt,
                  "synthesize_audio": False},
            headers={**self.headers, "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


def run_turn(backend: Backend, src: str, tgt: str, source_text: str,
             reference: str, *, text_only: bool) -> TurnResult:
    result = TurnResult(src, tgt, source_text, reference)

    audio = None if text_only else backend.tts(source_text, src)
    started = time.perf_counter()
    try:
        if audio:
            data = backend.translate_audio(audio, src, tgt)
            result.stt_text = str(data.get("source_text") or "").strip()
            result.wer = round(word_error_rate(result.stt_text, source_text), 3)
        else:
            data = backend.translate_text(source_text, src, tgt)
            result.stt_text = source_text  # no STT stage in text path
        result.translated_text = str(data.get("translated_text") or "").strip()
    except requests.RequestException as exc:
        result.errors.append(str(exc)[:200])
    result.e2e_ms = round((time.perf_counter() - started) * 1000, 1)
    result.chrf = sentence_chrf(result.translated_text, reference)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="EN<->HT field validation (Phase 5)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default=None)
    parser.add_argument("--min-chrf", type=float, default=MIN_CHRF)
    parser.add_argument("--text-only", action="store_true",
                        help="skip TTS+STT; measure translation chrF/latency only")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    backend = Backend(args.base_url, args.token, args.timeout)
    backend.wait_for_ready()

    mode = "text-only" if args.text_only else "audio (TTS->STT->translate)"
    print(f"EN<->HT field validation — {args.base_url}   mode: {mode}\n")

    results: list[TurnResult] = []
    audio_used = False
    for src, tgt, text, ref in DIALOGUE:
        turn = run_turn(backend, src, tgt, text, ref, text_only=args.text_only)
        if turn.wer is not None:
            audio_used = True
        results.append(turn)
        status = "OK" if not turn.errors else "ERR"
        wer_str = f"WER={turn.wer:.2f}" if turn.wer is not None else "WER=  n/a"
        print(f"  [{status}] {src}->{tgt}  chrF++={turn.chrf:>5}  {wer_str}  e2e={turn.e2e_ms:.0f}ms")
        print(f"        src: {text}")
        if turn.stt_text and turn.wer is not None:
            print(f"        stt: {turn.stt_text}")
        print(f"        out: {turn.translated_text or '(none)'}")
        for err in turn.errors:
            print(f"        ! {err}")

    ok_turns = [r for r in results if not r.errors]
    avg_chrf = sum(r.chrf for r in ok_turns) / max(1, len(ok_turns))
    avg_e2e = sum(r.e2e_ms for r in ok_turns) / max(1, len(ok_turns))
    wer_vals = [r.wer for r in results if r.wer is not None]
    avg_wer = sum(wer_vals) / len(wer_vals) if wer_vals else None

    failures: list[str] = []
    if avg_chrf < args.min_chrf:
        failures.append(f"avg chrF++ {avg_chrf:.1f} < floor {args.min_chrf}")
    for r in results:
        if r.errors:
            failures.append(f"{r.source_lang}->{r.target_lang} request error")
        elif r.e2e_ms > MAX_E2E_MS:
            failures.append(f"{r.source_lang}->{r.target_lang} e2e {r.e2e_ms:.0f}ms > {MAX_E2E_MS}ms")

    report = {
        "base_url": args.base_url,
        "mode": mode,
        "audio_path_used": audio_used,
        "turns": len(results),
        "avg_chrfpp": round(avg_chrf, 2),
        "avg_wer": round(avg_wer, 3) if avg_wer is not None else None,
        "avg_e2e_ms": round(avg_e2e, 1),
        "results": [vars(r) for r in results],
        "failures": failures,
    }
    out_dir = REPO_ROOT / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"field_validation_{int(time.time())}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nAvg chrF++: {avg_chrf:.1f}" +
          (f"   Avg WER: {avg_wer:.2f}" if avg_wer is not None else "   WER: n/a (text-only / no TTS)") +
          f"   Avg e2e: {avg_e2e:.0f}ms")
    print(f"Report: {out_path}")
    if not audio_used and not args.text_only:
        print("NOTE: TTS unavailable, fell back to text-only — STT word-error-rate not measured.")
    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("PASS: EN<->HT field validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
