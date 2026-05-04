"""Composition subcommand. Phase 1 stub: builds composition.json from
upstream artifacts. Phase 6 replaces with full composition-director logic
(style preset judgment, collision resolution, audio mix).

This stub IS schema-valid and IS the contract test for the Python↔Node bridge:
it must produce JSON that round-trips through both Pydantic and Zod.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic


def _resolve_caption(caption: dict[str, Any], events_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve anchored caption (D4) to absolute (start, end) + duck_window.

    Returns None if the anchor cannot be resolved — caller drops the caption
    and records it in dropped_captions. Phase 6's real composition-director
    emits an error.json instead; the stub is more forgiving.
    """
    anchor_id = caption["anchor_event_id"]
    event = events_by_id.get(anchor_id)
    if event is None:
        return None
    offset = caption.get("anchor_offset", 0.0)
    start = max(0.0, float(event["t"]) + float(offset))
    end = start + float(caption["intent_duration"])
    mood = caption["mood"]
    duck = None
    if mood in {"announce", "callout", "punchline", "tagline"}:
        duck = {"start": start - 0.2, "end": end + 0.3}
    return {
        "id": caption["id"],
        "text": caption["text"],
        "mood": mood,
        "start": start,
        "end": end,
        "priority": int(caption.get("priority", 3)),
        "anchor_event_id": anchor_id,
        "duck_window": duck,
    }


def stub_compose(
    *,
    analysis_path: Path,
    captions_path: Path,
    music_path: Path,
    sfx_manifest_path: Path,
    footage_path: Path,
    out_path: Path,
) -> dict[str, Any]:
    """Phase 1 stub: deterministic resolution of anchored captions to
    absolute timing. No collision resolution, no style judgment (picks
    `neutral` preset), default audio mix.
    """
    analysis = json.loads(analysis_path.read_text())
    captions_doc = json.loads(captions_path.read_text())

    duration = float(analysis["duration_seconds"])
    fps = int(analysis.get("fps", 30))
    resolution = analysis.get("resolution", {"width": 1920, "height": 1080})

    events_by_id = {e["id"]: e for e in analysis.get("events", [])}
    rendered: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for cap in captions_doc.get("captions", []):
        resolved = _resolve_caption(cap, events_by_id)
        if resolved is None:
            dropped.append(
                {
                    "id": cap["id"],
                    "reason": "anchor_density",  # use enum value; Phase 6 distinguishes reasons
                    "details": f"anchor_event_id {cap['anchor_event_id']} not found",
                }
            )
            continue
        # Clamp end to duration.
        if resolved["end"] > duration:
            resolved["end"] = duration
        rendered.append(resolved)

    sfx_placements: list[dict[str, Any]] = []
    if sfx_manifest_path.exists():
        sfx_doc = json.loads(sfx_manifest_path.read_text())
        for placement in sfx_doc.get("placements", []):
            sfx_placements.append(
                {
                    "src": placement["clip_path"],
                    "t": float(placement.get("t", 0.0)),
                    "gain_db": float(placement.get("gain_db", 0)),
                    "anchor_event_id": placement.get("event_id"),
                }
            )

    composition = {
        "schema_version": 1,
        "fps": fps,
        "duration_seconds": duration,
        "resolution": resolution,
        "footage": {"src": footage_path.name, "trim_before": 0},
        "audio": {
            "music": {"src": music_path.name, "gain_db": 0},
            "sfx": sfx_placements,
            "mix": {
                "integrated_lufs": -14,
                "true_peak_dbtp": -1,
                "duck_to_lufs": -22,
            },
        },
        "captions": rendered,
        "dropped_captions": dropped,
        "style": {"preset": "neutral"},
    }

    write_json_atomic(out_path, composition)
    return composition
