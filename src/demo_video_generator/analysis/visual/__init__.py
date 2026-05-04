"""Visual-analyst implementation per agent design.

Phase 3: deterministic PySceneDetect scene detection. Runs only on time
ranges NOT covered by event-driven scenes (gap-filler) AND on the entirety
of `kind=screen` videos.

LLM-on-keyframes (which produces the `summary` + `ui_elements` fields by
asking a vision model to describe each scene's middle frame) is gated on
a vision API key and lands as Phase 3.5. Until then, scenes get a
placeholder summary and an empty ui_elements list.

Detector selection per agent design (event-log-analyst/visual-analyst
gotchas.md):
- ContentDetector(threshold=27) default — film-cut tuned but works for
  most UI footage
- AdaptiveDetector for low-contrast UI (dark mode, soft transitions);
  used as fallback when Content density < 1 scene per 30s on a known-busy gap
- ThresholdDetector for fade-heavy footage; not auto-selected (user
  config required)

Cost guard: keyframe count is capped at 8 per minute of footage (per
ultraplan R2). When PySceneDetect would emit more, scenes are merged in
priority of length.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

KEYFRAMES_PER_MINUTE_CAP = 8
MIN_SCENE_DURATION_SECONDS = 1.0
DEFAULT_CONTENT_THRESHOLD = 27.0
ADAPTIVE_THRESHOLD = 3.0


def _detect_scenes_in_range(
    video_path: Path,
    *,
    start_seconds: float,
    end_seconds: float,
    detector: str = "content",
) -> list[tuple[float, float]]:
    """Run PySceneDetect over `[start_seconds, end_seconds]` and return
    a list of (scene_start, scene_end) tuples in absolute seconds.

    Returns an empty list if the detector finds no scenes — caller emits a
    fallback "no detectable transitions" scene per the agent design.
    """
    try:
        from scenedetect import (  # type: ignore[import-untyped]
            AdaptiveDetector,
            ContentDetector,
            SceneManager,
            open_video,
        )
    except ImportError:
        return []

    try:
        video = open_video(str(video_path))
        scene_manager = SceneManager()
        if detector == "adaptive":
            scene_manager.add_detector(AdaptiveDetector(adaptive_threshold=ADAPTIVE_THRESHOLD))
        else:
            scene_manager.add_detector(ContentDetector(threshold=DEFAULT_CONTENT_THRESHOLD))
        # PySceneDetect uses FrameTimecode; we pass seconds directly.
        scene_manager.detect_scenes(
            video=video,
            duration=video.duration if end_seconds <= 0 else None,
            show_progress=False,
        )
    except Exception:  # noqa: BLE001
        return []

    raw_scenes = scene_manager.get_scene_list()
    out: list[tuple[float, float]] = []
    for s_start, s_end in raw_scenes:
        a = float(s_start.get_seconds())
        b = float(s_end.get_seconds())
        # Clip to the requested window.
        if b <= start_seconds or a >= end_seconds:
            continue
        out.append((max(a, start_seconds), min(b, end_seconds)))
    return out


def _cap_keyframes(
    scenes: list[tuple[float, float]], *, total_minutes: float
) -> list[tuple[float, float]]:
    """Enforce the 8-keyframes-per-minute cap by merging shortest neighbours
    until under cap.
    """
    cap = max(1, int(KEYFRAMES_PER_MINUTE_CAP * total_minutes))
    if len(scenes) <= cap:
        return scenes
    # Merge greedily: find the shortest scene; merge with its smaller
    # neighbour until count <= cap.
    out = list(scenes)
    while len(out) > cap and len(out) > 1:
        # find shortest scene
        idx = min(range(len(out)), key=lambda i: out[i][1] - out[i][0])
        if idx == 0:
            merged = (out[0][0], out[1][1])
            out = [merged] + out[2:]
        elif idx == len(out) - 1:
            merged = (out[-2][0], out[-1][1])
            out = out[:-2] + [merged]
        else:
            left = out[idx - 1]
            right = out[idx + 1]
            # merge with shorter neighbour
            if (left[1] - left[0]) <= (right[1] - right[0]):
                merged = (left[0], out[idx][1])
                out = out[: idx - 1] + [merged] + out[idx + 1 :]
            else:
                merged = (out[idx][0], right[1])
                out = out[:idx] + [merged] + out[idx + 2 :]
    return out


def detect_visual_scenes(
    *,
    video_path: Path,
    duration_seconds: float,
    gap_intervals: list[tuple[float, float]] | None = None,
) -> list[dict[str, Any]]:
    """Phase 3 visual-analyst entry point.

    `gap_intervals`: list of (start, end) intervals in seconds NOT covered
    by event-driven scenes. If None or empty, the detector runs over the
    entire duration (kind=screen recordings).

    Returns a list of visual Scene dicts (source="visual") matching the
    analysis.schema.json shape. LLM-on-keyframes summary + ui_elements
    are placeholders pending Phase 3.5.
    """
    if not video_path.is_file() or video_path.stat().st_size < 1024:
        return []  # placeholder/empty footage; nothing to analyze

    if gap_intervals is None or not gap_intervals:
        gap_intervals = [(0.0, duration_seconds)]

    scene_idx = 1
    out: list[dict[str, Any]] = []
    for gap_start, gap_end in gap_intervals:
        if gap_end - gap_start < MIN_SCENE_DURATION_SECONDS:
            continue
        # Try Content detector first.
        scenes = _detect_scenes_in_range(
            video_path,
            start_seconds=gap_start,
            end_seconds=gap_end,
            detector="content",
        )
        # If density < 1 per 30s, retry with Adaptive (low-contrast UI fallback).
        gap_minutes = max((gap_end - gap_start) / 60.0, 0.001)
        if len(scenes) < int(2 * gap_minutes):
            adaptive_scenes = _detect_scenes_in_range(
                video_path,
                start_seconds=gap_start,
                end_seconds=gap_end,
                detector="adaptive",
            )
            if len(adaptive_scenes) > len(scenes):
                scenes = adaptive_scenes
        # Fallback: emit one "no detectable transitions" scene per the agent design.
        if not scenes:
            scenes = [(gap_start, gap_end)]
        # Cap keyframe density.
        scenes = _cap_keyframes(scenes, total_minutes=gap_minutes)
        for s_start, s_end in scenes:
            if s_end - s_start < MIN_SCENE_DURATION_SECONDS:
                continue
            out.append(
                {
                    "id": f"scene_v{scene_idx:03d}",
                    "start": round(float(s_start), 3),
                    "end": round(float(s_end), 3),
                    "source": "visual",
                    "summary": "visual scene (LLM keyframe summary deferred to Phase 3.5)",
                    "energy": "low",  # default low confidence per design
                    "ui_elements": [],
                    "keyframe_paths": [],
                }
            )
            scene_idx += 1
    return out
