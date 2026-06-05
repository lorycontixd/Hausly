.PHONY: start-api start-mobile test-api lint migrate format

# Backend
start-api:
	cd apps/api && uvicorn hausly.main:app --reload --host 0.0.0.0 --port 8000

test-api:
	cd apps/api && pytest -v

lint:
	cd apps/api && ruff check .
	cd apps/api && mypy hausly/

format:
	cd apps/api && ruff format .

migrate:
	cd apps/api && alembic upgrade head

migrate-new:
	cd apps/api && alembic revision --autogenerate -m "$(name)"

# Mobile
start-mobile:
	cd apps/mobile && npx expo start

# All
install:
	cd apps/api && pip install -e ".[dev]"
	cd apps/mobile && npm install
