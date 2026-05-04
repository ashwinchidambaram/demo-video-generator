"""Tests for D17 content-aware cascading invalidation."""

from __future__ import annotations

from pathlib import Path

from demo_video_generator import manifest as mf
from demo_video_generator.atomic import write_json_atomic


def _populated_run(tmp_path: Path) -> tuple[dict, Path]:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    m = mf.new_manifest("run-1", "url", "http://example.test/")
    # Pre-populate every artifact with deterministic bytes so we can hash.
    for stage in m["stages"]:
        artifact = run_dir / stage["artifact"]
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(stage["name"].encode())
        # Pretend the prior run hashed this stage.
        import hashlib

        stage["artifact_sha256"] = hashlib.sha256(stage["name"].encode()).hexdigest()
        stage["status"] = "complete"
    write_json_atomic(run_dir / "manifest.json", m)
    return m, run_dir


def test_invalidate_target_only_clears_only_target(tmp_path: Path) -> None:
    m, run_dir = _populated_run(tmp_path)
    captions_artifact = run_dir / "captions.json"
    assert captions_artifact.exists()  # pre-condition

    prior = mf.invalidate_target_only(m, "captions", run_dir)
    # Target cleared.
    assert not captions_artifact.exists()
    # Downstream artifacts UNTOUCHED at this point — that's the contract.
    assert (run_dir / "composition.json").exists()
    assert (run_dir / "final.mp4").exists()
    # Prior hash is returned for the cascade decision.
    assert prior is not None


def test_cascade_if_changed_skips_when_hash_matches(tmp_path: Path) -> None:
    """Re-run produced byte-identical output → downstream preserved."""
    m, run_dir = _populated_run(tmp_path)
    mf.invalidate_target_only(m, "captions", run_dir)

    # Simulate the re-run producing identical bytes -> identical hash.
    captions_artifact = run_dir / "captions.json"
    captions_artifact.write_bytes(b"captions")
    import hashlib

    target_stage = mf.find_stage(m, "captions")
    assert target_stage is not None
    target_stage["artifact_sha256"] = hashlib.sha256(b"captions").hexdigest()

    # Hash hadn't been recorded as 'captions' originally; let's set prior to
    # match the new hash to exercise the unchanged path.
    cascaded = mf.cascade_if_changed(
        m, "captions", run_dir, prior_hash=target_stage["artifact_sha256"]
    )
    assert cascaded == []  # no downstream invalidated
    # Downstream artifacts still on disk.
    assert (run_dir / "composition.json").exists()
    assert (run_dir / "final.mp4").exists()
    # And not_my_prior with explicit different prior should cascade:
    cascaded2 = mf.cascade_if_changed(
        m, "captions", run_dir, prior_hash="different-prior-hash"
    )
    assert "compose" in cascaded2
    assert "render" in cascaded2
    assert "review" in cascaded2
    # Now downstream artifacts gone.
    assert not (run_dir / "composition.json").exists()
    assert not (run_dir / "final.mp4").exists()


def test_cascade_if_changed_invalidates_when_hash_differs(tmp_path: Path) -> None:
    m, run_dir = _populated_run(tmp_path)
    prior = mf.invalidate_target_only(m, "captions", run_dir)

    # Simulate the re-run producing DIFFERENT bytes.
    captions_artifact = run_dir / "captions.json"
    captions_artifact.write_bytes(b"captions-new-content")
    import hashlib

    target_stage = mf.find_stage(m, "captions")
    assert target_stage is not None
    target_stage["artifact_sha256"] = hashlib.sha256(
        b"captions-new-content"
    ).hexdigest()
    assert target_stage["artifact_sha256"] != prior

    cascaded = mf.cascade_if_changed(m, "captions", run_dir, prior_hash=prior)
    assert "compose" in cascaded
    assert "render" in cascaded
    assert "review" in cascaded
    # Downstream artifacts removed.
    assert not (run_dir / "composition.json").exists()
    assert not (run_dir / "final.mp4").exists()
