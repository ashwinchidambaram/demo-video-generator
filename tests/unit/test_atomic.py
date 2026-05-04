"""Tests for atomic-write helpers."""

from __future__ import annotations

import json
from pathlib import Path

from demo_video_generator.atomic import write_atomic, write_json_atomic


def test_write_atomic_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "subdir" / "file.bin"
    write_atomic(target, b"hello")
    assert target.read_bytes() == b"hello"


def test_write_atomic_no_partial_on_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    write_atomic(target, b"v1")
    write_atomic(target, b"v2-much-longer-content")
    assert target.read_bytes() == b"v2-much-longer-content"


def test_write_json_atomic_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    payload = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
    write_json_atomic(target, payload)
    assert json.loads(target.read_text()) == payload


def test_write_atomic_does_not_leave_tmp_files(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    write_atomic(target, b"data")
    siblings = list(tmp_path.iterdir())
    assert siblings == [target]
