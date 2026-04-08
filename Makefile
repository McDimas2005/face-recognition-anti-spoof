SHELL := /bin/bash

.PHONY: api-install web-install api-dev web-dev test lint format compose-up compose-down

api-install:
	cd apps/api && python3 -m venv .venv && source .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

web-install:
	npm install

api-dev:
	cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web-dev:
	npm run dev:web

test:
	cd apps/api && pytest

lint:
	cd apps/api && python3 -m compileall app

format:
	@echo "Formatting is deferred to project tooling installation."

compose-up:
	docker compose up --build

compose-down:
	docker compose down -v
