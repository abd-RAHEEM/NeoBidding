.PHONY: up down test test-backend test-frontend seed simulate lint build

up:
	docker compose up --build

down:
	docker compose down -v

test: test-backend test-frontend

test-backend:
	PYTHONPATH=backend pytest backend/tests

test-frontend:
	cd frontend && pnpm test

seed:
	PYTHONPATH=backend python scripts/seed.py --live

simulate:
	PYTHONPATH=backend python scripts/simulate_bidding.py

lint:
	ruff check backend/
	cd frontend && pnpm lint

build:
	cd frontend && pnpm build

