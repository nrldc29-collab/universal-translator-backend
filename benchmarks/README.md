# EN↔HT Translation Accuracy Benchmark

This benchmark turns "is the translation any good?" into real numbers. It runs a
curated English↔Haitian Creole test set through the Anai pipeline and reports
BLEU and chrF scores, broken down by direction and domain, with the weakest
sentences surfaced so you know exactly where to improve.

## Why this exists

The pipeline (Whisper → MarianMT/NLLB → Piper) is wired end to end, but nothing
in the repo measures *translation quality* on the flagship EN↔HT pair. Because no
direct `Helsinki-NLP/opus-mt-en-ht` model exists, EN↔HT falls back to the
distilled NLLB-200 model — serviceable, but unproven. This gives you a repeatable
score instead of a guess.

## The one thing that matters most: the references

A translation score is only as trustworthy as the "correct answer" it's compared
against. The Haitian Creole strings in `testset_en_ht.json` are **best-effort and
marked `"review_status": "unverified"`**. Before you trust any number:

1. Give `testset_en_ht.json` to a fluent Haitian Creole speaker.
2. For each item, have them confirm or fix the Creole (the HT *reference* in
   `en-ht` items, and the HT *source* in `ht-en` items). English is reliable.
3. Change that item's `review_status` to `"verified"`.

Until then, treat results as a smoke test of "does it produce plausible Creole,"
not as a true accuracy figure. The English-side direction (`ht-en`) is more
trustworthy out of the gate because its references are English.

## Setup

```bash
pip install -r requirements.txt   # includes sacrebleu
pip install requests              # only needed for --mode http
```

## Running it

Direct mode (no server; imports the translator straight from the repo):

```bash
cd benchmarks
python run_benchmark.py --mode direct
```

HTTP mode (tests the real deployed path through the API). Start the backend
first and wait for **LIVE**, then:

```bash
python run_benchmark.py --mode http --base-url http://127.0.0.1:8000
```

If your server has auth enabled (`USERS`/`API_KEYS` set), pass a credential:

```bash
python run_benchmark.py --mode http --base-url https://your-backend --token <JWT>
python run_benchmark.py --mode http --base-url https://your-backend --api-key <key>
```

Locally with no `API_KEYS` set and not in production, the backend treats the
caller as `dev` and no token is needed.

Useful flags:

```bash
--direction en-ht     # or ht-en; run only one side
--limit 10            # quick smoke run on the first 10 items
--verified-only       # only items with review_status=verified (use after native review)
--tier marian         # marian | hybrid | ollama (direct mode or HTTP provider hint)
--quality             # wider beam search (TRANSLATION_QUALITY_NUM_BEAMS, default 4)
--min-chrf 30         # exit 1 if overall chrF2 is below floor (CI gate)
--testset testset_en_ht_extended.json   # 200+ sentence extended set
--out-dir results     # where JSON/CSV land (default ./results)
```

Extended test set (200+ items, still unverified HT):

```bash
python scripts/expand_en_ht_testset.py
python run_benchmark.py --mode direct --testset testset_en_ht_extended.json --limit 20
```

Quality A/B (Phase 2 tuning — compare chrF vs latency):

```bash
# Baseline (600M, beam=1)
python run_benchmark.py --mode direct --direction en-ht

# Wider beams
python run_benchmark.py --mode direct --direction en-ht --quality

# Larger NLLB model (config swap, no code change)
NLLB_MODEL=facebook/nllb-200-1.3B python run_benchmark.py --mode direct --direction en-ht

# LLM path (requires Ollama)
python run_benchmark.py --mode direct --tier ollama --direction en-ht --limit 10
```

## What you get

- A console summary: overall scores, per-direction, per-domain, and the weakest
  10 sentences with source / reference / actual output side by side.
- `results/results_<timestamp>.json` — full machine-readable results.
- `results/results_<timestamp>.csv` — one row per sentence, opens in Excel.

## Reading the scores

Three metrics are reported; for Haitian Creole, **chrF2 is the one to watch**.
chrF compares character n-grams, which is far more reliable than BLEU on small,
low-resource test sets (BLEU punishes single-word swaps harshly and is noisy
below a few thousand sentences). chrF++ adds word-order sensitivity. BLEU is
shown for familiarity only.

chrF2 rough bands:

| chrF2 | Meaning |
|------:|---------|
| 60+   | Strong — usually faithful, minor edits at most |
| 45–60 | Usable — gets the meaning, some errors |
| 30–45 | Gist only — needs human editing before use |
| <30   | Unreliable — frequently wrong |

These bands are guidance, not gospel — anchor them by spot-reading the actual
outputs in the CSV.

## Suggested workflow

1. Run `--mode direct` once now for a baseline (with unverified references).
2. Get the test set verified by a native speaker; re-run for trustworthy numbers.
3. Run `--mode http` to confirm the API path matches direct mode (it should).
4. Read the "weakest 10" — that's your prioritized fix list (often idioms,
   numbers/dosages, or specific domains).
5. Try the LLM-enhanced path (Ollama/AILang) and re-run to measure the lift.
6. Expand the test set toward 200+ verified sentences for stable scores; small
   sets swing a lot per sentence.

## CI quality gate

The `integration-live` CI job runs a smoke benchmark after models are warmed:

```bash
python benchmarks/run_benchmark.py --mode direct --direction en-ht --limit 5 --min-chrf 12
```

Raise `--min-chrf` as verified references improve.

## Phase 5 — field validation (streaming path)

After the backend is LIVE, run the two-person EN↔HT dialogue over WebSocket:

```bash
python scripts/en_ht_field_validation.py --base-url http://127.0.0.1:8000
```

Reports chrF on translations, STT word-error rate, and first-translation / end-to-end latency.

## Files

```
benchmarks/
├── run_benchmark.py              # the harness (http + direct modes)
├── testset_en_ht.json            # ~56 EN<->HT pairs (starter set)
├── testset_en_ht_extended.json    # 200+ pairs (generate via scripts/expand_en_ht_testset.py)
├── README.md                     # this file
└── results/                      # generated JSON + CSV reports
```
