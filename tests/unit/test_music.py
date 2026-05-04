"""Tests for music ingest path (Phase 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from demo_video_generator.music import _pick_track, ingest_soundtrack


def _make_track(dir: Path, name: str, content: bytes = b"FAKE_MP3") -> Path:
    p = dir / name
    p.write_bytes(content)
    return p


def test_pick_track_prefers_hint(tmp_path: Path) -> None:
    a = _make_track(tmp_path, "vibe-edm.mp3")
    b = _make_track(tmp_path, "vibe-flow.mp3")
    chosen = _pick_track([a, b], hint="flow", run_id_seed="any-seed")
    assert chosen.name == "vibe-flow.mp3"


def test_pick_track_deterministic_from_seed(tmp_path: Path) -> None:
    a = _make_track(tmp_path, "vibe-edm.mp3")
    b = _make_track(tmp_path, "vibe-flow.mp3")
    c = _make_track(tmp_path, "vibe-c.mp3")
    seed = "run-2026-05-04T05-37-13"
    chosen1 = _pick_track([a, b, c], run_id_seed=seed)
    chosen2 = _pick_track([a, b, c], run_id_seed=seed)
    assert chosen1 == chosen2  # determinism


def test_pick_track_empty_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _pick_track([], run_id_seed="any")


def test_ingest_soundtrack_copies_track_and_writes_meta(tmp_path: Path) -> None:
    src_dir = tmp_path / "soundtracks"
    src_dir.mkdir()
    track = _make_track(src_dir, "Vibe A.mp3", content=b"REAL_MP3_BYTES")

    out_dir = tmp_path / "run"
    out_path = out_dir / "music.mp3"
    result = ingest_soundtrack(
        soundtrack_dir=src_dir,
        out_path=out_path,
        duration_seconds=15.0,
        hint=None,
        run_id_seed="run-1",
    )
    assert out_path.exists()
    assert out_path.read_bytes() == b"REAL_MP3_BYTES"
    assert (out_dir / "music_meta.json").exists()
    assert result["source"] == str(track)


def test_ingest_soundtrack_no_files_raises(tmp_path: Path) -> None:
    src_dir = tmp_path / "soundtracks"
    src_dir.mkdir()
    out_path = tmp_path / "run" / "music.mp3"
    with pytest.raises(FileNotFoundError):
        ingest_soundtrack(
            soundtrack_dir=src_dir,
            out_path=out_path,
        )
