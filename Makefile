.PHONY: help schemas schemas-check agents test lint format typecheck doctor clean install

PY_SCHEMA_DIR := src/demo_video_generator/schemas
TS_SCHEMA_DIR := remotion/src/schemas
SCHEMA_SRC := schemas
CHECKSUM_FILE := schemas/.checksums

help:
	@echo "Targets:"
	@echo "  install        - uv sync + remotion deps"
	@echo "  schemas        - codegen Pydantic + Zod from schemas/*.schema.json"
	@echo "  schemas-check  - verify codegen is up to date with sources"
	@echo "  agents         - compile .claude/agents/<x>/agent.md from section-loader markers"
	@echo "  test           - pytest"
	@echo "  lint           - ruff check"
	@echo "  format         - ruff format + prettier write"
	@echo "  typecheck      - mypy --strict src/"
	@echo "  doctor         - run dvg doctor"
	@echo "  clean          - remove generated files"

install:
	uv sync --all-extras
	cd remotion && npm install

schemas:
	@mkdir -p $(PY_SCHEMA_DIR) $(TS_SCHEMA_DIR)
	uv run datamodel-codegen \
		--input $(SCHEMA_SRC) \
		--input-file-type jsonschema \
		--output $(PY_SCHEMA_DIR) \
		--output-model-type pydantic_v2.BaseModel \
		--target-python-version 3.12 \
		--use-schema-description \
		--use-double-quotes \
		--disable-timestamp \
		--use-standard-collections \
		--use-union-operator
	@touch $(PY_SCHEMA_DIR)/__init__.py
	cd remotion && npm run gen-schemas
	@shasum -a 256 $(SCHEMA_SRC)/*.schema.json > $(CHECKSUM_FILE)
	@echo "Codegen complete. Checksums recorded in $(CHECKSUM_FILE)."

schemas-check:
	@if [ ! -f $(CHECKSUM_FILE) ]; then \
		echo "ERROR: $(CHECKSUM_FILE) missing. Run 'make schemas'."; exit 1; \
	fi
	@shasum -a 256 -c $(CHECKSUM_FILE) > /dev/null || ( \
		echo "ERROR: schemas/*.schema.json changed without re-running 'make schemas'."; \
		exit 1; \
	)

agents:
	uv run python -m demo_video_generator.tools.compile_agents

test:
	uv run pytest

lint:
	uv run ruff check src tests
	cd remotion && npx prettier --check "src/**/*.{ts,tsx}"

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests
	cd remotion && npx prettier --write "src/**/*.{ts,tsx}"

typecheck:
	uv run mypy src

doctor:
	uv run dvg doctor

clean:
	rm -rf $(PY_SCHEMA_DIR)/*.py $(TS_SCHEMA_DIR)/*.ts $(CHECKSUM_FILE)
	rm -rf .pytest_cache .ruff_cache .mypy_cache
