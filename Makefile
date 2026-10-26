.PHONY: lint test-unit test

lint:
	uv run --locked ruff format --check .
	uv run --locked ruff check .
	uv run --locked mypy .

test-unit:
	uv run --locked pytest tests/unit

# Part 1a has only a unit suite.
test: test-unit
