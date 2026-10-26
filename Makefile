.PHONY: lint test-unit test-integration test up down migrate

COMPOSE = docker compose --env-file .env -f deploy/compose/docker-compose.yml

lint:
	uv run --locked ruff format --check .
	uv run --locked ruff check .
	uv run --locked mypy .

test-unit:
	uv run --locked pytest tests/unit

test-integration:
	uv run --locked pytest tests/integration

test: test-unit test-integration

up:
	$(COMPOSE) up --build -d --wait

down:
	$(COMPOSE) down

migrate:
	$(COMPOSE) run --rm migrate
