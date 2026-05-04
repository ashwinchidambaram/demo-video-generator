"""Tests for the manifest DAG and cascading invalidation."""

from __future__ import annotations

from pathlib import Path

from demo_video_generator import manifest as mf


def test_default_pipeline_topologically_ordered() -> None:
    pipeline = mf.DEFAULT_PIPELINE
    seen: set[str] = set()
    for stage in pipeline:
        for dep in stage["depends_on"]:
            assert dep in seen, f"{stage['name']} depends on {dep} not yet seen"
        seen.add(stage["name"])


def test_new_manifest_initializes_all_stages_pending() -> None:
    m = mf.new_manifest("r1", "url", "http://example.test/")
    assert m["schema_version"] == 1
    for stage in m["stages"]:
        assert stage["status"] == "pending"
        assert stage["attempts"] == 0


def test_downstream_of_capture_is_everything() -> None:
    m = mf.new_manifest("r1", "url", "http://example.test/")
    downstream = mf.downstream_of(m, "capture")
    assert "analyze" in downstream
    assert "compose" in downstream
    assert "render" in downstream
    assert "review" in downstream
    assert "capture" not in downstream  # excluded by definition


def test_downstream_of_music_is_only_compose_and_after() -> None:
    m = mf.new_manifest("r1", "url", "http://example.test/")
    downstream = mf.downstream_of(m, "music")
    # captions does NOT depend on music, so it must NOT be invalidated
    assert "captions" not in downstream
    # compose, render, review depend on music transitively
    assert "compose" in downstream
    assert "render" in downstream
    assert "review" in downstream


def test_invalidate_deletes_artifacts_and_marks_pending(tmp_path: Path) -> None:
    m = mf.new_manifest("r1", "url", "http://example.test/")
    run_dir = tmp_path
    # simulate a fully completed run
    for stage in m["stages"]:
        stage["status"] = "complete"
        artifact = run_dir / stage["artifact"]
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.touch()

    invalidated = mf.invalidate(m, "music", run_dir)
    assert "music" in invalidated
    assert "compose" in invalidated
    assert "captions" not in invalidated  # not downstream of music

    # music + compose + render + review artifacts are gone; captions remain
    assert not (run_dir / "music.mp3").exists()
    assert not (run_dir / "composition.json").exists()
    assert not (run_dir / "final.mp4").exists()
    assert not (run_dir / "qa.json").exists()
    assert (run_dir / "captions.json").exists()

    # invalidated stages back to pending
    for name in invalidated:
        stage = mf.find_stage(m, name)
        assert stage is not None
        assert stage["status"] == "pending"


def test_next_pending_walks_in_order(empty_run: Path) -> None:
    manifest = mf.load(empty_run / "manifest.json")
    view = mf.next_pending(manifest, empty_run)
    assert view is not None
    # capture has no deps so it must be first
    assert view.name == "capture"
