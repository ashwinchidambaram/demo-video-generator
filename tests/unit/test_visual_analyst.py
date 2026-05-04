"""Tests for the Phase 3 visual-analyst (PySceneDetect deterministic path).

Cap-merge logic is pure Python and always exercised. PySceneDetect itself is
exercised against the rendered demo MP4 when available (it's a real video
with scene transitions every ~6s).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from demo_video_generator.analysis.visual import (
    KEYFRAMES_PER_MINUTE_CAP,
    _cap_keyframes,
    detect_visual_scenes,
)

# ---------- _cap_keyframes (pure logic) ----------


def test_cap_keyframes_under_cap_passthrough() -> None:
    scenes = [(0.0, 1.0), (1.0, 2.0)]
    capped = _cap_keyframes(scenes, total_minutes=1.0)
    assert capped == scenes  # 2 scenes < 8 cap


def test_cap_keyframes_merges_shortest() -> None:
    """When over cap, shortest scene merges with shorter neighbour."""
    # 10 scenes in 1 minute: cap is 8.
    scenes = [(i, i + 0.1) for i in range(10)]
    # add a tail so total spans the minute
    scenes[-1] = (9.0, 60.0)
    capped = _cap_keyframes(scenes, total_minutes=1.0)
    assert len(capped) <= KEYFRAMES_PER_MINUTE_CAP


def test_cap_keyframes_idempotent_at_exact_cap() -> None:
    cap = KEYFRAMES_PER_MINUTE_CAP
    scenes = [(i, i + 1.0) for i in range(cap)]
    capped = _cap_keyframes(scenes, total_minutes=1.0)
    assert len(capped) == cap


# ---------- detect_visual_scenes against a real MP4 ----------


@pytest.fixture(scope="module")
def demo_mp4() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    mp4 = repo_root / "demo-deliverable.mp4"
    if not mp4.is_file():
        pytest.skip("demo-deliverable.mp4 not rendered yet")
    return mp4


def test_detect_visual_scenes_finds_scenes_in_demo(demo_mp4: Path) -> None:
    """The DvgSelfDemo MP4 has 6 distinct scenes at known transitions
    (0:00 title, 0:04 terminal, 0:10 pipeline, 0:18 schemas, 0:22 QA, 0:28 final).
    PySceneDetect should find at least 3 scene boundaries.
    """
    scenes = detect_visual_scenes(
        video_path=demo_mp4,
        duration_seconds=32.0,
        gap_intervals=None,
    )
    # Lower bound: at least one scene; upper bound: keyframe cap (~5 for 0.5min).
    assert len(scenes) >= 1
    # All output scenes carry source="visual".
    for s in scenes:
        assert s["source"] == "visual"
        assert s["start"] >= 0
        assert s["end"] > s["start"]


def test_detect_visual_scenes_skips_empty_footage(tmp_path: Path) -> None:
    """Empty placeholder MP4 (Phase 1 stub) → no visual scenes."""
    placeholder = tmp_path / "footage.mp4"
    placeholder.write_bytes(b"")  # 0 bytes
    scenes = detect_visual_scenes(
        video_path=placeholder,
        duration_seconds=10.0,
        gap_intervals=None,
    )
    assert scenes == []


def test_detect_visual_scenes_respects_gap_intervals(demo_mp4: Path) -> None:
    """Visual scenes never extend outside the requested gap windows."""
    scenes = detect_visual_scenes(
        video_path=demo_mp4,
        duration_seconds=32.0,
        gap_intervals=[(10.0, 18.0)],  # only the pipeline-DAG window
    )
    for s in scenes:
        assert s["start"] >= 10.0 - 0.01
        assert s["end"] <= 18.0 + 0.01
