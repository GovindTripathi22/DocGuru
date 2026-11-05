.PHONY: setup dev test lint typecheck build docker-up docker-down check

setup:
	npm run setup

dev:
	npm run dev:all

test:
	python -m pytest backend/tests -q --cov=backend/app --cov-report=term --cov-fail-under=80
	npm run test:frontend

lint:
	npm run lint
	ruff check backend/app backend/tests scripts
	ruff format --check backend/app backend/tests scripts

typecheck:
	python -m mypy backend/app
	npx tsc --noEmit

build:
	npm run build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

check: test lint typecheck build
