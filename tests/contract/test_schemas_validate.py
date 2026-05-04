"""Contract tests: every schema is valid JSON Schema and has schema_version=1."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMAS = ["error", "manifest", "analysis", "captions", "composition"]


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_is_valid_json_schema(name: str) -> None:
    schemas_dir = Path(__file__).resolve().parents[2] / "schemas"
    schema = json.loads((schemas_dir / f"{name}.schema.json").read_text())
    # Will raise if the schema itself is malformed.
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_pins_schema_version_const_1(name: str) -> None:
    schemas_dir = Path(__file__).resolve().parents[2] / "schemas"
    schema = json.loads((schemas_dir / f"{name}.schema.json").read_text())
    sv = schema.get("properties", {}).get("schema_version", {})
    assert sv.get("const") == 1, f"{name} schema_version must be const: 1"
