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
pip install sacrebleu          # metrics
pip install requests           # only needed for --mode http
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
--out-dir results     # where JSON/CSV land (default ./results)
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

## Files

```
benchmarks/
├── run_benchmark.py        # the harness (http + direct modes)
├── testset_en_ht.json      # ~50 EN<->HT pairs, references need native review
├── README.md               # this file
└── results/                # generated JSON + CSV reports
```
