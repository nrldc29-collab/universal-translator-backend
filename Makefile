PYTHON ?= python3

.PHONY: backend-test backend-compile frontend-build mobile-lint mobile-build validate setup-models verify-local

backend-test:
	pytest

backend-compile:
	$(PYTHON) -m compileall backend translation speech tts llm tests scripts -q

setup-models:
	$(PYTHON) scripts/setup_models.py

verify-local:
	$(PYTHON) scripts/smoke_local.py

frontend-build:
	cd frontend && npm run build

mobile-lint:
	cd translator-mobile && npm run lint

mobile-build:
	cd translator-mobile && npm run build

validate: backend-compile frontend-build mobile-lint
