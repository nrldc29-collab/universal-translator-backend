# Tests

Backend and safety tests for Anai Translator.

Run:

```bash
pytest
```

If pytest is unavailable in a constrained environment, use:

```bash
python -m compileall backend translation speech tts llm tests -q
```

Do not add new test frameworks unless the project intentionally adopts them.
