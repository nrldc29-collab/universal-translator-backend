PYTHON ?= python3

.PHONY: backend-test backend-compile frontend-build mobile-lint mobile-build validate setup setup-deps setup-models verify-local verify-local-live verify-bundled-live verify-all preflight-deploy preflight-deploy-live release-ready smoke-production run-backend run-frontend start-local test-translator

setup-deps:
	$(PYTHON) -m pip install -r requirements.txt
	cd frontend && npm ci

setup: setup-deps setup-models

backend-test:
	$(PYTHON) -m pytest -q

backend-compile:
	$(PYTHON) -m compileall backend translation speech tts llm tests scripts -q

setup-models:
	$(PYTHON) scripts/setup_models.py

verify-local:
	$(PYTHON) scripts/smoke_local.py

verify-local-live:
	$(PYTHON) scripts/smoke_local.py http://127.0.0.1:8000

run-backend:
	$(PYTHON) -m backend.app

run-frontend:
	cd frontend && npm run dev

start-local:
	bash scripts/start_local.sh

test-translator:
	bash scripts/test_translator.sh http://127.0.0.1:8000

verify-bundled-live: frontend-build
	@echo "Starting bundled backend (SERVE_FRONTEND_DIST=1) on port 8001..."
	@env -u ALLOWED_ORIGIN_REGEX SERVE_FRONTEND_DIST=1 BACKEND_PORT=8001 PARTIAL_TTS_MODE=1 REQUESTS_PER_MINUTE=120 QUOTA_REQUESTS_PER_HOUR=500 MAX_ACTIVE_STREAMS_PER_USER=5 $(PYTHON) -m uvicorn backend.api:app --host 127.0.0.1 --port 8001 >logs/bundled-backend.log 2>&1 & echo $$! >logs/bundled-backend.pid
	@for i in $$(seq 1 60); do curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1 && break; sleep 2; done
	$(PYTHON) scripts/smoke_local.py http://127.0.0.1:8001 || (kill $$(cat logs/bundled-backend.pid) 2>/dev/null; exit 1)
	@kill $$(cat logs/bundled-backend.pid) 2>/dev/null || true
	@rm -f logs/bundled-backend.pid

frontend-build:
	cd frontend && npm run build

mobile-lint:
	cd translator-mobile && npm run lint

mobile-build:
	cd translator-mobile && npm run build

validate: backend-compile backend-test frontend-build mobile-lint

verify-all: verify-local verify-bundled-live

preflight-deploy:
	bash scripts/preflight_deploy.sh

preflight-deploy-live:
	bash scripts/preflight_deploy.sh --smoke http://127.0.0.1:8000

release-ready: validate verify-all preflight-deploy
	@echo "Release-ready: all local and production preflight checks passed."

smoke-production:
	@test -n "$(URL)" || (echo "Usage: make smoke-production URL=https://YOUR-SERVICE.up.railway.app [USERS=user:pass]" >&2; exit 1)
	USERS="$(USERS)" $(PYTHON) scripts/smoke_local.py "$(URL)"
