"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_video_generator import manifest as mf
from demo_video_generator.atomic import write_json_atomic


@pytest.fixture
def runs_root(tmp_path: Path) -> Path:
    return tmp_path / "runs"


@pytest.fixture
def empty_run(runs_root: Path) -> Path:
    """A bare run dir with a fresh manifest, no artifacts."""
    run_dir = runs_root / "fixture-run"
    run_dir.mkdir(parents=True)
    manifest = mf.new_manifest("fixture-run", "url", "http://localhost:0/fixture.html")
    write_json_atomic(run_dir / "manifest.json", manifest)
    return run_dir


@pytest.fixture
def schemas_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas"


def load_schema(schemas_dir: Path, name: str) -> dict:
    return json.loads((schemas_dir / f"{name}.schema.json").read_text())
