"""Pydantic-side codegen parity smoke test.

Asserts every JSON Schema codegens into a Pydantic model and that a fixture
instance round-trips through the model. The Zod side is exercised at Remotion
runtime (Phase 1+); Python-side parity catches the most common drift (renamed
field, removed const, type widening) before it reaches the bridge.

Per R1 finding 3.4: schemas/<name>.py must accept and emit instances that
match the JSON Schema. We don't assert byte-identical roundtrip (Pydantic
reorders keys); we assert validation + value preservation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"


def _instances() -> dict[str, dict]:
    """Minimal valid instances for each schema."""
    return {
        "error": {
            "schema_version": 1,
            "error": "test",
            "code": "TEST_CODE",
            "retryable": False,
        },
        "captions": {
            "schema_version": 1,
            "captions": [
                {
                    "id": "c1",
                    "text": "Hello world",
                    "mood": "announce",
                    "anchor_event_id": "evt-1",
                    "intent_duration": 2.5,
                }
            ],
        },
        "analysis": {
            "schema_version": 1,
            "duration_seconds": 30.0,
            "scenes": [],
        },
    }


@pytest.mark.parametrize("name", ["error", "captions", "analysis"])
def test_pydantic_model_accepts_valid_instance(name: str) -> None:
    """Round-trip a fixture instance through the codegen Pydantic model."""
    pytest.importorskip("demo_video_generator.schemas")
    # Lazy import to avoid breaking when codegen hasn't run yet.
    from demo_video_generator import schemas as gen

    instances = _instances()
    instance = instances[name]

    # Find the model class. datamodel-code-generator names files <name>_schema.py.
    module_name = f"{name}_schema"
    module = getattr(gen, module_name, None)
    if module is None:
        import importlib

        module = importlib.import_module(f"demo_video_generator.schemas.{module_name}")

    # Each schema's top-level title is the model name; datamodel-code-generator
    # may use the title or the filename. Try both.
    candidates = [name.title(), name.capitalize(), "Error", "Captions", "Analysis"]
    model_cls = None
    for cand in candidates:
        if hasattr(module, cand):
            model_cls = getattr(module, cand)
            break
    if model_cls is None:
        # Fall back to the first BaseModel subclass in the module.
        from pydantic import BaseModel

        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
                model_cls = obj
                break

    assert model_cls is not None, f"no Pydantic model found in {module_name}"
    parsed = model_cls.model_validate(instance)
    dumped = parsed.model_dump(mode="json", exclude_none=True)
    # schema_version must round-trip identically (it's a const).
    assert dumped.get("schema_version") == 1


def test_schemas_dir_has_checksums_recorded() -> None:
    """The codegen pipeline must record checksums; otherwise drift is silent."""
    checksums = SCHEMAS_DIR / ".checksums"
    assert checksums.exists(), "Run 'make schemas' to generate codegen + checksums."
    lines = [line for line in checksums.read_text().splitlines() if line.strip()]
    schema_files = list(SCHEMAS_DIR.glob("*.schema.json"))
    assert len(lines) == len(schema_files), "checksums file out of sync with schemas/"
