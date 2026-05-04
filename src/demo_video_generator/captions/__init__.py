"""Captions subcommand. Phase 1 stub: writes a small valid captions.json
anchored to the analysis stub's events. Phase 7 replaces with caption-writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic


def stub_captions(analysis_path: Path, out_path: Path) -> dict[str, Any]:
    """Phase 1 stub: produce a few captions anchored to whatever events
    analysis stub produced. Composition-director's stub turns these into
    rendered captions with absolute timing.
    """
    analysis = json.loads(analysis_path.read_text())
    events = analysis.get("events", [])

    captions: list[dict[str, Any]] = []
    if events:
        # Anchor announce → first event, explain → middle, tagline → last
        first = events[0]
        captions.append(
            {
                "id": "c1",
                "text": "demo-video-generator",
                "mood": "announce",
                "anchor_event_id": first["id"],
                "intent_duration": 2.5,
                "anchor_offset": 0.0,
                "priority": 5,
            }
        )
        if len(events) >= 2:
            mid = events[len(events) // 2]
            captions.append(
                {
                    "id": "c2",
                    "text": "Walks the manifest.",
                    "mood": "explain",
                    "anchor_event_id": mid["id"],
                    "intent_duration": 2.5,
                    "anchor_offset": 0.0,
                    "priority": 4,
                }
            )
        last = events[-1]
        captions.append(
            {
                "id": "c3",
                "text": "Deterministic by design.",
                "mood": "tagline",
                "anchor_event_id": last["id"],
                "intent_duration": 3.0,
                "anchor_offset": -0.5,
                "priority": 5,
            }
        )

    payload = {"schema_version": 1, "captions": captions}
    write_json_atomic(out_path, payload)
    return payload
