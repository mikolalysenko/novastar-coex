.PHONY: sync test test-ha lint fmt typecheck validate check build clean cli

HA_REQUIREMENTS ?= requirements/ha-latest.txt

sync:            ## create/refresh the dev venv
	uv sync --extra dev

test: sync       ## run the unit tests against the fake controller
	uv run pytest -q

test-ha:         ## exercise the actual Home Assistant integration (Python 3.14)
	uv venv --python 3.14 --allow-existing .venv-ha
	uv pip install --python .venv-ha/bin/python -e '.[dev]' -r $(HA_REQUIREMENTS)
	.venv-ha/bin/python -m pytest -q

lint: sync
	uv run ruff check .
	uv run ruff format --check .

fmt: sync
	uv run ruff format .
	uv run ruff check --fix .

typecheck: sync
	uv run mypy custom_components/novastar_coex/coex

validate:
	uv run python scripts/validate_release.py

check: lint typecheck test validate

build: sync      ## build sdist + wheel (wheel exports the library as `novastar_coex`)
	uv build
	uv run python scripts/build_release.py

cli: sync        ## e.g. make cli ARGS="--host 192.0.2.10 status"
	uv run coex $(ARGS)

clean:
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
