#!/usr/bin/env python3
"""
Anai Translator EN<->HT accuracy benchmark.

Runs a curated test set through the translation pipeline and reports
BLEU and chrF / chrF++ scores, broken down by direction and domain.

Two modes:
  --mode http     Calls a running backend at /translate/text (the real
                  deployed path). Needs the server up and LIVE.
  --mode direct   Imports translation.marian_translator.MarianTranslator
                  directly. No server needed; skips the API/streaming layer.

Metrics (via sacrebleu):
  - chrF2   : character n-gram F-score. PRIMARY metric for Haitian Creole,
              which is low-resource; chrF correlates with human judgment
              far better than BLEU on small/low-resource test sets.
  - chrF++  : chrF plus word unigrams/bigrams (rewards word order too).
  - BLEU    : reported for familiarity, but treat as secondary here.

Usage examples:
  python run_benchmark.py --mode direct
  python run_benchmark.py --mode http --base-url http://127.0.0.1:8000
  python run_benchmark.py --mode http --base-url https://my-backend --token <JWT>
  python run_benchmark.py --mode direct --direction en-ht --limit 10

Outputs (written to --out-dir, default ./results):
  results_<timestamp>.json   full machine-readable results
  results_<timestamp>.csv    per-sentence rows (open in Excel)
  console summary table
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


# --------------------------------------------------------------------------
# Metric helpers
# --------------------------------------------------------------------------
def load_sacrebleu():
    try:
        import sacrebleu  # noqa: F401
        from sacrebleu.metrics import BLEU, CHRF
        return BLEU, CHRF
    except ImportError:
        sys.exit(
            "ERROR: sacrebleu is not installed.\n"
            "Install it with:\n"
            "    pip install sacrebleu\n"
        )


def corpus_scores(hyps, refs, BLEU, CHRF):
    """Return dict of corpus-level BLEU, chrF2, chrF++ for parallel lists."""
    if not hyps:
        return {"bleu": 0.0, "chrf2": 0.0, "chrfpp": 0.0, "n": 0}
    refs_wrapped = [refs]  # sacrebleu wants list-of-reference-streams
    bleu = BLEU(effective_order=True).corpus_score(hyps, refs_wrapped).score
    chrf2 = CHRF(word_order=0).corpus_score(hyps, refs_wrapped).score
    chrfpp = CHRF(word_order=2).corpus_score(hyps, refs_wrapped).score
    return {"bleu": round(bleu, 2), "chrf2": round(chrf2, 2),
            "chrfpp": round(chrfpp, 2), "n": len(hyps)}


def sentence_chrf(hyp, ref, CHRF):
    return round(CHRF(word_order=2).sentence_score(hyp, [ref]).score, 2)


# --------------------------------------------------------------------------
# Translation backends
# --------------------------------------------------------------------------
def make_http_translator(base_url, token, api_key, timeout, *, quality=False, tier="marian"):
    try:
        import requests
    except ImportError:
        sys.exit("ERROR: 'requests' is required for --mode http. Run: pip install requests")

    base_url = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["x-api-key"] = api_key

    def translate(text, src, tgt):
        payload = {
            "text": text,
            "source_language": src,
            "target_language": tgt,
            "synthesize_audio": False,
        }
        if quality:
            payload["translation_quality"] = "quality"
        if tier == "hybrid":
            payload["translation_provider"] = "hybrid"
        elif tier == "ollama":
            payload["translation_provider"] = "hybrid"
            payload["translation_mode"] = "balanced"
            os.environ["TRANSLATION_TIER"] = "ollama"
        resp = requests.post(
            f"{base_url}/translate/text",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # /translate/text returns the pipeline result dict; translated text
        # lives in "translated_text" (see backend/api.py translate_text).
        return (data.get("translated_text")
                or data.get("improved_text")
                or "").strip()

    return translate


def make_direct_translator(*, tier="marian", quality=False):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    tier = (tier or "marian").lower()
    if tier in {"hybrid", "ollama", "auto"}:
        try:
            from translation.hybrid_translator import HybridTranslator
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"ERROR: could not import HybridTranslator: {exc}")
        if tier == "ollama":
            os.environ["TRANSLATION_TIER"] = "ollama"
        elif tier == "hybrid":
            os.environ.setdefault("TRANSLATION_TIER", "auto")
        hybrid = HybridTranslator()

        def translate(text, src, tgt):
            return (hybrid.translate(text, src, tgt, quality=quality) or "").strip()

        return translate

    try:
        from translation.marian_translator import MarianTranslator
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            f"ERROR: could not import the translator for --mode direct: {exc}\n"
            "Run this from the repo (so 'translation' is importable) and make "
            "sure backend deps are installed (pip install -r requirements.txt)."
        )
    translator = MarianTranslator()

    def translate(text, src, tgt):
        return (translator.translate(text, src, tgt, quality=quality) or "").strip()

    return translate


# --------------------------------------------------------------------------
# Core run
# --------------------------------------------------------------------------
def run(args):
    BLEU, CHRF = load_sacrebleu()

    testset_path = Path(args.testset)
    if not testset_path.is_absolute():
        testset_path = HERE / testset_path
    data = json.loads(testset_path.read_text(encoding="utf-8"))
    items = data["items"]

    if args.direction:
        items = [it for it in items if it["direction"] == args.direction]
    if args.verified_only:
        items = [it for it in items if str(it.get("review_status", "")).lower() == "verified"]
    if args.limit:
        items = items[: args.limit]
    if not items:
        sys.exit("No test items matched the filters.")

    tier = args.tier or "marian"
    if args.mode == "http":
        translate = make_http_translator(
            args.base_url, args.token, args.api_key, args.timeout,
            quality=args.quality, tier=tier,
        )
    else:
        translate = make_direct_translator(tier=tier, quality=args.quality)

    rows = []
    print(f"\nRunning {len(items)} items in {args.mode} mode...\n")
    for i, it in enumerate(items, 1):
        src_lang, tgt_lang = it["direction"].split("-")
        t0 = time.time()
        error = ""
        try:
            hyp = translate(it["source"], src_lang, tgt_lang)
        except Exception as exc:  # noqa: BLE001
            hyp = ""
            error = str(exc)[:300]
        latency_ms = round((time.time() - t0) * 1000)

        s_chrf = sentence_chrf(hyp, it["reference"], CHRF) if hyp else 0.0
        rows.append({
            "id": it["id"],
            "domain": it["domain"],
            "direction": it["direction"],
            "source": it["source"],
            "reference": it["reference"],
            "hypothesis": hyp,
            "sentence_chrfpp": s_chrf,
            "latency_ms": latency_ms,
            "review_status": it.get("review_status", "unverified"),
            "error": error,
        })
        flag = "  ERR" if error else ""
        print(f"[{i:>3}/{len(items)}] {it['id']:<6} {it['direction']}  "
              f"chrF++={s_chrf:>5}  {latency_ms:>5}ms{flag}")

    # ---- aggregate ----
    def agg(subset):
        hyps = [r["hypothesis"] for r in subset]
        refs = [r["reference"] for r in subset]
        scores = corpus_scores(hyps, refs, BLEU, CHRF)
        lats = [r["latency_ms"] for r in subset if not r["error"]]
        scores["avg_latency_ms"] = round(sum(lats) / len(lats)) if lats else 0
        scores["errors"] = sum(1 for r in subset if r["error"])
        return scores

    overall = agg(rows)
    by_direction = {}
    for d in sorted({r["direction"] for r in rows}):
        by_direction[d] = agg([r for r in rows if r["direction"] == d])
    by_domain = {}
    for dom in sorted({r["domain"] for r in rows}):
        by_domain[dom] = agg([r for r in rows if r["domain"] == dom])

    worst = sorted([r for r in rows if not r["error"]],
                   key=lambda r: r["sentence_chrfpp"])[:10]

    verified_count = sum(
        1 for it in data.get("items", [])
        if str(it.get("review_status", "")).lower() == "verified"
    )
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "tier": tier,
        "quality_beams": args.quality,
        "base_url": args.base_url if args.mode == "http" else None,
        "testset": str(testset_path),
        "verified_items_in_testset": verified_count,
        "review_warning": data.get("meta", {}).get("review_note", ""),
        "overall": overall,
        "by_direction": by_direction,
        "by_domain": by_domain,
        "worst_sentences": [
            {k: r[k] for k in ("id", "direction", "domain", "source",
                               "reference", "hypothesis", "sentence_chrfpp")}
            for r in worst
        ],
        "rows": rows,
    }

    # ---- write outputs ----
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = HERE / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"results_{stamp}.json"
    csv_path = out_dir / f"results_{stamp}.csv"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print_summary(result, json_path, csv_path)

    if args.min_chrf is not None:
        score = result["overall"]["chrf2"]
        if score < args.min_chrf:
            print(f"FAIL: overall chrF2 {score} < floor {args.min_chrf}", file=sys.stderr)
            sys.exit(1)
        print(f"PASS: overall chrF2 {score} >= floor {args.min_chrf}")

    return result


def _fmt(scores):
    return (f"BLEU {scores['bleu']:>5}  chrF2 {scores['chrf2']:>5}  "
            f"chrF++ {scores['chrfpp']:>5}  n={scores['n']:>3}  "
            f"err={scores['errors']:>2}  ~{scores['avg_latency_ms']}ms")


def print_summary(result, json_path, csv_path):
    line = "=" * 72
    tier = result.get("tier", "marian")
    quality = "on" if result.get("quality_beams") else "off"
    print(f"\n{line}\nANAI TRANSLATOR  EN<->HT  ACCURACY  —  {result['generated_at']}"
          f"\nmode: {result['mode']}   tier: {tier}   quality-beams: {quality}" +
          (f"   base_url: {result['base_url']}" if result["base_url"] else "") +
          f"\nverified refs in testset: {result.get('verified_items_in_testset', 0)}" +
          f"\n{line}")
    print(f"OVERALL    {_fmt(result['overall'])}")
    print("\nBY DIRECTION")
    for d, s in result["by_direction"].items():
        print(f"  {d:<8} {_fmt(s)}")
    print("\nBY DOMAIN")
    for dom, s in result["by_domain"].items():
        print(f"  {dom:<10} {_fmt(s)}")
    print("\nWEAKEST 10 SENTENCES (by chrF++)")
    for r in result["worst_sentences"]:
        print(f"  [{r['sentence_chrfpp']:>5}] {r['id']:<6} {r['direction']}")
        print(f"          src: {r['source']}")
        print(f"          ref: {r['reference']}")
        print(f"          out: {r['hypothesis']}")
    print(f"\n{line}")
    print("INTERPRETATION (chrF2, the primary metric for Haitian Creole):")
    print("  60+  strong, usually faithful   45-60  usable, some errors")
    print("  30-45 gist only, edit needed    <30   unreliable")
    print("NOTE: scores are only as trustworthy as the Creole references.")
    print("      Have a native speaker verify the test set first (see README).")
    print(f"{line}")
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}\n")


def build_parser():
    p = argparse.ArgumentParser(description="EN<->HT translation accuracy benchmark")
    p.add_argument("--mode", choices=["http", "direct"], default="direct",
                   help="how to call the pipeline (default: direct)")
    p.add_argument("--base-url", default=os.getenv("ANAI_BASE_URL", "http://127.0.0.1:8000"),
                   help="backend URL for --mode http")
    p.add_argument("--token", default=os.getenv("ANAI_TOKEN"),
                   help="JWT bearer token (only if the server requires auth)")
    p.add_argument("--api-key", default=os.getenv("ANAI_API_KEY"),
                   help="x-api-key (only if the server requires auth)")
    p.add_argument("--testset", default="testset_en_ht.json")
    p.add_argument("--direction", choices=["en-ht", "ht-en"],
                   help="run only one direction")
    p.add_argument("--verified-only", action="store_true",
                   help="only items with review_status=verified")
    p.add_argument("--tier", choices=["marian", "hybrid", "ollama"], default="marian",
                   help="translation backend for --mode direct (or http provider hint)")
    p.add_argument("--quality", action="store_true",
                   help="use wider beam search (TRANSLATION_QUALITY_NUM_BEAMS)")
    p.add_argument("--min-chrf", type=float, default=None,
                   help="exit 1 if overall chrF2 is below this floor (CI gate)")
    p.add_argument("--limit", type=int, help="run only the first N items")
    p.add_argument("--timeout", type=float, default=60.0,
                   help="per-request HTTP timeout seconds")
    p.add_argument("--out-dir", default="results")
    return p


if __name__ == "__main__":
    run(build_parser().parse_args())
