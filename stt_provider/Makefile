.PHONY: install run dev compose smoke metrics logs clean

# Install Python dependencies in a virtual environment
install:
	cd server && python3 -m venv .venv
	cd server && . .venv/bin/activate && pip install --upgrade pip
	cd server && . .venv/bin/activate && pip install -r requirements.txt

# Run the STT server locally with uvicorn
run:
	cd server && . .venv/bin/activate && uvicorn stt_server.main:app --host 0.0.0.0 --port 8000

# Run the client development server
dev:
	cd client && python3 -m http.server 5173

# Build and run with docker-compose
compose:
	docker compose up --build

# Run smoke tests to verify server health
smoke:
	cd server && . .venv/bin/activate && python scripts/smoke_test_http.py

# View Prometheus metrics endpoint
metrics:
	curl http://localhost:8000/metrics

# View docker-compose logs
logs:
	docker compose logs -f stt-server

# Clean up build artifacts and virtual environment
clean:
	rm -rf server/.venv
	rm -rf server/stt_server/__pycache__
	rm -rf logs
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
