# GreenFlow developer commands. On Windows use `make` from Git Bash, or copy commands directly.

.PHONY: up down db seed assets api web test baseline install

install:
	pip install -e ".[dev]"
	cd web && npm install
	cd tools && npm install

db:
	docker compose up -d db

up:
	docker compose up -d --build

down:
	docker compose down

# Parse IDF -> normalized JSON + GLB + XKT + metadata + viewer manifest
assets:
	python scripts/build_3d_assets.py

# Seed demo building, zones, devices, telemetry, baseline run (needs db up)
seed:
	python scripts/seed_demo.py

api:
	uvicorn greenflow.api.main:app --app-dir backend --reload --port 8000

web:
	cd web && npm run dev

test:
	pytest backend/tests -q

baseline:
	python scripts/run_baseline.py
