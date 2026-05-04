"""Contract test: a fresh manifest validates against manifest.schema.json."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from demo_video_generator import manifest as mf


def test_fresh_manifest_validates() -> None:
    schemas_dir = Path(__file__).resolve().parents[2] / "schemas"
    manifest_schema = json.loads((schemas_dir / "manifest.schema.json").read_text())
    error_schema = json.loads((schemas_dir / "error.schema.json").read_text())

    registry: Registry = Registry().with_resources(
        [
            ("error.schema.json", Resource.from_contents(error_schema)),
        ]
    )
    validator = jsonschema.Draft202012Validator(manifest_schema, registry=registry)
    instance = mf.new_manifest("test-run", "url", "http://example.test/")
    validator.validate(instance)
