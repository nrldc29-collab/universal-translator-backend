# Release Checklist

## Code quality

- [ ] Backend tests pass with `make validate` or `python -m pytest`.
- [ ] Frontend builds with `npm run build`.
- [ ] Mobile lints and builds with `npm run lint && npm run build`.
- [ ] `git diff --check` has no whitespace errors.

## Product

- [ ] Web mic flow works.
- [ ] Mobile live voice flow works.
- [ ] Text translation works.
- [ ] Audio upload translation works.
- [ ] TTS playback works.

## Operations

- [ ] `.env.example` covers new env vars.
- [ ] `/health`, `/ready`, and `/diagnostics` are clean.
- [ ] No secrets, generated audio, uploads, profiles, or model binaries are staged.
- [ ] Changelog updated.
