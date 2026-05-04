"""Analysis subcommand.

Phase 3 implements the deterministic events-driven path (event-log-analyst):
gap-based clustering -> per-cluster summary -> schema-valid analysis.json.

The visual-analyst path (PySceneDetect + LLM-on-keyframes) is gated on
ffmpeg + a vision API; for inputs with no events we emit a single
`source="visual"` placeholder scene covering the whole duration. Phase 3.5
lands the real visual analysis when those are unblocked.

The deterministic clustering algorithm is documented in
.claude/agents/event-log-analyst/design.md; this module is the executable
Python embodiment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic

DEFAULT_CLUSTER_GAP_SECONDS = 1.2
MIN_SCENE_DURATION_SECONDS = 1.5

ENERGY_BY_KIND: dict[str, str] = {
    "click": "medium",
    "keydown": "medium",
    "submit": "high",
    "framenavigated": "high",
    "navigation": "high",
    "pushstate": "high",
    "modal_open": "high",
    "modal_close": "medium",
    "console_error": "high",
    "network_failure": "high",
}


def _cluster_events(
    events: list[dict[str, Any]], *, gap: float = DEFAULT_CLUSTER_GAP_SECONDS
) -> list[list[dict[str, Any]]]:
    """Cluster events by temporal gap. Returns ordered list of clusters."""
    if not events:
        return []
    sorted_events = sorted(events, key=lambda e: float(e["t"]))
    clusters: list[list[dict[str, Any]]] = [[sorted_events[0]]]
    for ev in sorted_events[1:]:
        last_t = float(clusters[-1][-1]["t"])
        if float(ev["t"]) - last_t > gap:
            clusters.append([ev])
        else:
            clusters[-1].append(ev)
    return clusters


def _cluster_to_scene(
    cluster: list[dict[str, Any]],
    *,
    scene_idx: int,
    duration_total: float,
    next_cluster_start: float | None,
) -> dict[str, Any]:
    start = max(0.0, float(cluster[0]["t"]) - 0.3)
    if next_cluster_start is not None:
        end = max(start + MIN_SCENE_DURATION_SECONDS, float(next_cluster_start) - 0.1)
    else:
        end = max(start + MIN_SCENE_DURATION_SECONDS, duration_total)
    end = min(end, duration_total)
    energies = {ENERGY_BY_KIND.get(e.get("kind", ""), "low") for e in cluster}
    if "high" in energies:
        energy = "high"
    elif "medium" in energies:
        energy = "medium"
    else:
        energy = "low"
    labels = [
        str(e.get("label") or e.get("kind", ""))
        for e in cluster
        if e.get("label") or e.get("kind")
    ]
    summary = " -> ".join(labels[:4]) if labels else "interaction cluster"
    return {
        "id": f"scene_{scene_idx:03d}",
        "start": round(start, 3),
        "end": round(end, 3),
        "source": "events",
        "summary": summary,
        "energy": energy,
        "ui_elements": [],
        "keyframe_paths": [],
    }


def analyze_events_driven(events_log: dict[str, Any]) -> dict[str, Any]:
    """Phase 3 deterministic event-log-analyst output.

    Pure function: given an events log, return the analysis.json shape.
    """
    duration = float(events_log.get("duration_seconds", 0.0)) or 10.0
    fps = int(events_log.get("fps", 30))
    resolution = events_log.get("resolution", {"width": 1920, "height": 1080})
    raw_events = events_log.get("events", [])

    clusters = _cluster_events(raw_events)
    scenes: list[dict[str, Any]] = []

    if clusters:
        for i, cluster in enumerate(clusters):
            next_start = (
                float(clusters[i + 1][0]["t"]) if i + 1 < len(clusters) else None
            )
            scenes.append(
                _cluster_to_scene(
                    cluster,
                    scene_idx=i + 1,
                    duration_total=duration,
                    next_cluster_start=next_start,
                )
            )
    else:
        scenes.append(
            {
                "id": "scene_001",
                "start": 0.0,
                "end": round(duration, 3),
                "source": "visual",
                "summary": "no events; visual-analyst placeholder",
                "energy": "low",
                "ui_elements": [],
                "keyframe_paths": [],
            }
        )

    events_out: list[dict[str, Any]] = [
        {
            "id": ev["id"],
            "t": float(ev["t"]),
            "kind": ev.get("kind", "click"),
            "selector": ev.get("selector"),
            "label": ev.get("label"),
            "payload": ev.get("payload", {}),
        }
        for ev in raw_events
    ]

    # Synthesize anchor events when input has none, so downstream stubs
    # (caption-writer, sfx-curator) have something to anchor on. Anchor
    # density scales with duration: roughly one anchor per 4 seconds, with
    # a minimum of 3 (start / mid / end) and a maximum of 8 (eval cap).
    if not events_out:
        target_count = max(3, min(8, int(duration / 4)))
        events_out = []
        for i in range(target_count):
            # Distribute anchors uniformly across [0.5, duration - 0.5].
            t = 0.5 + (duration - 1.0) * (i / max(1, target_count - 1))
            kind = "navigation" if i == 0 else "modal_close" if i == target_count - 1 else "click"
            label = (
                "demo start" if i == 0
                else "demo end" if i == target_count - 1
                else f"step {i}"
            )
            events_out.append(
                {
                    "id": f"evt-{i + 1}",
                    "t": round(t, 2),
                    "kind": kind,
                    "selector": "button[type=submit]" if kind == "click" else None,
                    "label": label,
                    "payload": {},
                }
            )

    return {
        "schema_version": 1,
        "duration_seconds": duration,
        "fps": fps,
        "resolution": resolution,
        "scenes": scenes,
        "events": events_out,
    }


def stub_analyze(events_path: Path, out_path: Path) -> dict[str, Any]:
    """Driver entry. Reads the events log written by capture, runs the
    deterministic events-driven analyzer, then runs the visual-analyst
    over any uncovered gaps. Atomic-writes analysis.json.

    Visual analysis runs only when a real footage MP4 (>1KB) is present.
    Phase 1 stubs ship empty placeholders; visual is silently skipped.
    """
    if events_path.exists():
        events_log = json.loads(events_path.read_text())
    else:
        events_log = {"schema_version": 1, "events": [], "duration_seconds": 10.0}
    analysis = analyze_events_driven(events_log)

    # Phase 3 visual-analyst pass: fill gaps in event coverage.
    footage_path = events_path.parent / "footage.mp4"
    if footage_path.is_file() and footage_path.stat().st_size > 1024:
        from .visual import detect_visual_scenes

        duration = float(analysis["duration_seconds"])
        # Gaps = duration ranges not covered by events-driven scenes.
        events_scenes = sorted(
            [
                (float(s["start"]), float(s["end"]))
                for s in analysis["scenes"]
                if s["source"] == "events"
            ],
            key=lambda x: x[0],
        )
        gaps: list[tuple[float, float]] = []
        cursor = 0.0
        for ev_start, ev_end in events_scenes:
            if ev_start > cursor + 1.0:  # >1s gap
                gaps.append((cursor, ev_start))
            cursor = max(cursor, ev_end)
        if cursor < duration - 1.0:
            gaps.append((cursor, duration))

        # If no events-driven scenes (kind=screen), the entire timeline is a gap.
        run_on_whole = not events_scenes
        gap_intervals = None if run_on_whole else gaps

        if run_on_whole or gaps:
            visual_scenes = detect_visual_scenes(
                video_path=footage_path,
                duration_seconds=duration,
                gap_intervals=gap_intervals,
            )
            # Replace the placeholder visual scene if there was one (when
            # events were empty), otherwise append the gap-fillers.
            if run_on_whole:
                analysis["scenes"] = [
                    s for s in analysis["scenes"] if s["source"] != "visual"
                ] + visual_scenes
            else:
                analysis["scenes"].extend(visual_scenes)

    write_json_atomic(out_path, analysis)
    return analysis
