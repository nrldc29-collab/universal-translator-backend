# Translation

Translation adapters for Anai Translator.

- `hybrid_translator.py` — primary translation router.
- `lightweight_translator.py` — fast phrase/fallback translation.
- `marian_translator.py` — MarianMT-backed local model translation.
- `remote_translator.py` — optional remote fallback support.

Downloaded model data belongs in `models/translation/` or package caches, not in git.
