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


def test_dispatch_walks_stub_stages_with_skip_render(tmp_path: Path) -> None:
    """End-to-end smoke: --skip-render walks the manifest through every
    pre-render stage and produces all upstream artifacts for inspection."""
    run_id = run_mod.make_run_id()
    run_dir = run_mod.init_run_dir(tmp_path / "runs", run_id, "url", "http://localhost:0/")

    result = run_mod.dispatch(run_dir, skip_render=True)
    assert result.error is None
    # All stages up through compose should run; render+review are skipped.
    expected_run = ["capture", "analyze", "captions", "music", "sfx", "compose"]
    for stage in expected_run:
        assert stage in result.completed, f"{stage} should have run"
    assert "render" in result.skipped
    # All upstream artifacts exist and are non-empty (or at least exist).
    assert (run_dir / "footage.mp4").exists()
    assert (run_dir / "footage.events.json").exists()
    assert (run_dir / "analysis.json").exists()
    assert (run_dir / "captions.json").exists()
    assert (run_dir / "music.mp3").exists()
    assert (run_dir / "sfx" / "manifest.json").exists()
    assert (run_dir / "composition.json").exists()


def test_from_stage_invalidates_downstream_only(tmp_path: Path) -> None:
    """--from invalidates the target stage and its declared downstream per
    depends_on, but preserves siblings outside the cone."""
    run_id = run_mod.make_run_id()
    run_dir = run_mod.init_run_dir(tmp_path / "runs", run_id, "url", "http://localhost:0/")

    # Simulate a fully-completed run by creating all artifacts on disk.
    manifest = mf.load(run_dir / "manifest.json")
    for stage in manifest["stages"]:
        artifact = run_dir / stage["artifact"]
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.touch()

    invalidated = mf.invalidate(manifest, "music", run_dir)
    # captions does not depend on music — must survive
    assert "captions" not in invalidated
    assert "music" in invalidated
    assert "compose" in invalidated
    assert (run_dir / "captions.json").exists()
    assert not (run_dir / "music.mp3").exists()
    assert not (run_dir / "composition.json").exists()
    assert not (run_dir / "final.mp4").exists()
    assert not (run_dir / "qa.json").exists()
