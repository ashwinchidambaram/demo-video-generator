"""End-to-end walking-skeleton tests.

Phase 1 exit criterion: `dvg run` produces a valid MP4 against a fixture
input via the deterministic driver, and `--from <stage>` correctly cascades
invalidation per `depends_on`.

The render-stage tests are gated by the presence of the Remotion bundle
(slow, requires browser) — CI runs them via `dvg run --skip-render` for the
fast path; a `RUN_RENDER_E2E=1` env var enables the full path locally.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from demo_video_generator import manifest as mf
from demo_video_generator import run as run_mod


def _e2e_skip_render(tmp_path: Path) -> Path:
    """Run the driver end-to-end with --skip-render. Returns the run dir."""
    run_id = run_mod.make_run_id()
    run_dir = run_mod.init_run_dir(tmp_path / "runs", run_id, "url", "http://localhost:0/")
    result = run_mod.dispatch(run_dir, skip_render=True)
    assert result.error is None, f"driver error: {result.error}"
    return run_dir


def test_e2e_skip_render_produces_all_upstream_artifacts(tmp_path: Path) -> None:
    run_dir = _e2e_skip_render(tmp_path)

    # Every pre-render artifact exists and (where applicable) parses as JSON.
    for artifact in [
        "manifest.json",
        "footage.events.json",
        "analysis.json",
        "captions.json",
        "composition.json",
        "sfx/manifest.json",
    ]:
        path = run_dir / artifact
        assert path.exists(), f"missing artifact: {artifact}"
        if artifact.endswith(".json"):
            json.loads(path.read_text())  # asserts well-formed

    # Manifest reflects the per-stage status.
    manifest = json.loads((run_dir / "manifest.json").read_text())
    statuses = {s["name"]: s["status"] for s in manifest["stages"]}
    for s in ["capture", "analyze", "captions", "music", "sfx", "compose"]:
        assert statuses[s] == "complete", f"{s} not complete: {statuses[s]}"
    assert statuses["render"] == "skipped"


def test_e2e_composition_json_matches_d4_caption_resolution(tmp_path: Path) -> None:
    """Anchored captions resolve to absolute timing per D4."""
    run_dir = _e2e_skip_render(tmp_path)

    captions_in = json.loads((run_dir / "captions.json").read_text())
    composition = json.loads((run_dir / "composition.json").read_text())
    analysis = json.loads((run_dir / "analysis.json").read_text())
    events_by_id = {e["id"]: e for e in analysis["events"]}

    for in_cap, out_cap in zip(
        captions_in["captions"], composition["captions"], strict=False
    ):
        # Each output caption must keep id, text, mood, priority.
        assert in_cap["id"] == out_cap["id"]
        assert in_cap["text"] == out_cap["text"]
        assert in_cap["mood"] == out_cap["mood"]
        # And timing is `event.t + anchor_offset` for start, + intent_duration.
        anchor = events_by_id[in_cap["anchor_event_id"]]
        offset = in_cap.get("anchor_offset", 0.0)
        expected_start = max(0.0, anchor["t"] + offset)
        assert abs(out_cap["start"] - expected_start) < 1e-6
        assert (out_cap["end"] - out_cap["start"]) <= in_cap["intent_duration"] + 1e-6


def test_e2e_composition_audio_mix_matches_d9(tmp_path: Path) -> None:
    """Default audio mix targets must match D9 (YouTube-aligned: -14 LUFS / -1 dBTP)."""
    run_dir = _e2e_skip_render(tmp_path)
    composition = json.loads((run_dir / "composition.json").read_text())
    mix = composition["audio"]["mix"]
    assert mix["integrated_lufs"] == -14
    assert mix["true_peak_dbtp"] == -1
    assert mix["duck_to_lufs"] == -22


def test_e2e_dropped_captions_is_present_even_when_empty(tmp_path: Path) -> None:
    """Composition schema includes dropped_captions for elision traceability."""
    run_dir = _e2e_skip_render(tmp_path)
    composition = json.loads((run_dir / "composition.json").read_text())
    assert "dropped_captions" in composition  # may be empty list, but must exist


def test_e2e_artifact_sha256_recorded_per_stage(tmp_path: Path) -> None:
    """D17 content-aware invalidation: every completed stage records artifact_sha256."""
    run_dir = _e2e_skip_render(tmp_path)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    for stage in manifest["stages"]:
        if stage["status"] == "complete":
            # Empty placeholder files (footage.mp4) hash to None per the
            # _sha256_of helper convention; everything else must hash.
            artifact = run_dir / stage["artifact"]
            if artifact.is_file() and artifact.stat().st_size > 0:
                assert stage["artifact_sha256"] is not None, f"{stage['name']} missing sha"


@pytest.mark.skipif(
    os.environ.get("RUN_RENDER_E2E") != "1",
    reason="set RUN_RENDER_E2E=1 to exercise the full render path (slow, requires Chromium)",
)
def test_e2e_full_pipeline_renders_mp4(tmp_path: Path) -> None:
    """Full path: driver walks every stage including render and produces an MP4."""
    run_id = run_mod.make_run_id()
    run_dir = run_mod.init_run_dir(tmp_path / "runs", run_id, "url", "http://localhost:0/")
    result = run_mod.dispatch(run_dir)
    assert result.error is None, result.error
    final = run_dir / "final.mp4"
    assert final.exists()
    assert final.stat().st_size > 1024  # > 1 KB sanity floor


def test_invalidate_directory_artifact_clears_siblings(tmp_path: Path) -> None:
    """Belt-and-braces test of the sfx directory invalidation fix."""
    run_id = run_mod.make_run_id()
    run_dir = run_mod.init_run_dir(tmp_path / "runs", run_id, "url", "http://localhost:0/")

    # Run skip-render so sfx dir is populated with manifest.json
    run_mod.dispatch(run_dir, skip_render=True)
    sfx_dir = run_dir / "sfx"
    # Drop a sibling .wav as if Phase 5 had placed it
    (sfx_dir / "evt-2-0.wav").touch()
    assert (sfx_dir / "manifest.json").exists()
    assert (sfx_dir / "evt-2-0.wav").exists()

    manifest = mf.load(run_dir / "manifest.json")
    mf.invalidate(manifest, "sfx", run_dir)
    # sfx/ directory survives but contents are wiped.
    assert sfx_dir.is_dir()
    assert list(sfx_dir.iterdir()) == []
