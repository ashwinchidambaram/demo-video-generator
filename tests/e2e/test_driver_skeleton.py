"""E2E: dvg run skeleton against an empty fixture exits cleanly."""

from __future__ import annotations

from pathlib import Path

from demo_video_generator import manifest as mf
from demo_video_generator import run as run_mod


def test_init_run_dir_writes_valid_manifest(tmp_path: Path) -> None:
    run_id = run_mod.make_run_id()
    run_dir = run_mod.init_run_dir(tmp_path / "runs", run_id, "url", "http://localhost:0/")
    assert (run_dir / "manifest.json").exists()
    manifest = mf.load(run_dir / "manifest.json")
    assert manifest["run_id"] == run_id
    assert manifest["input"]["kind"] == "url"


def test_dispatch_dry_run_announces_first_pending(tmp_path: Path) -> None:
    run_id = run_mod.make_run_id()
    run_dir = run_mod.init_run_dir(tmp_path / "runs", run_id, "url", "http://localhost:0/")
    result = run_mod.dispatch(run_dir, dry_run=True)
    # First pending stage is capture (no deps).
    assert "capture" in result.pending


def test_from_stage_invalidates_downstream_only(tmp_path: Path) -> None:
    run_id = run_mod.make_run_id()
    run_dir = run_mod.init_run_dir(tmp_path / "runs", run_id, "url", "http://localhost:0/")

    # Simulate a fully-completed run by creating all artifacts on disk.
    manifest = mf.load(run_dir / "manifest.json")
    for stage in manifest["stages"]:
        artifact = run_dir / stage["artifact"]
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.touch()

    # Rewind from music: captions must survive, music+compose+render+review must drop.
    run_mod.dispatch(run_dir, from_stage="music", dry_run=True)
    assert (run_dir / "captions.json").exists()
    assert not (run_dir / "music.mp3").exists()
    assert not (run_dir / "composition.json").exists()
    assert not (run_dir / "final.mp4").exists()
    assert not (run_dir / "qa.json").exists()
