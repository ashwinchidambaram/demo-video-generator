"""Analysis subcommand. Phase 1 stub: writes a hardcoded valid analysis.json
with one fixture scene + three fixture events for downstream stubs to anchor on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic


def stub_analyze(events_path: Path, out_path: Path) -> dict[str, Any]:
    """Phase 1 stub: produce a schema-valid analysis.json so caption-writer,
    sfx-curator, composition-director have anchors to point at.

    Phase 3 replaces with real event-log-analyst + visual-analyst output.
    """
    duration = 10.0
    fps = 30
    if events_path.exists():
        try:
            events_log = json.loads(events_path.read_text())
            duration = float(events_log.get("duration_seconds", duration))
            fps = int(events_log.get("fps", fps))
        except (json.JSONDecodeError, ValueError):
            pass

    analysis = {
        "schema_version": 1,
        "duration_seconds": duration,
        "fps": fps,
        "resolution": {"width": 1920, "height": 1080},
        "scenes": [
            {
                "id": "scene_001",
                "start": 0.0,
                "end": duration,
                "source": "events",
                "summary": "demo overview",
                "energy": "medium",
                "ui_elements": [],
                "keyframe_paths": [],
            }
        ],
        "events": [
            {
                "id": "evt-1",
                "t": 1.0,
                "kind": "navigation",
                "selector": None,
                "label": "demo start",
                "payload": {},
            },
            {
                "id": "evt-2",
                "t": duration / 2,
                "kind": "click",
                "selector": "button[type=submit]",
                "label": "primary action",
                "payload": {},
            },
            {
                "id": "evt-3",
                "t": max(duration - 1.0, duration / 2 + 1.0),
                "kind": "modal_close",
                "selector": None,
                "label": "demo end",
                "payload": {},
            },
        ],
    }

    write_json_atomic(out_path, analysis)
    return analysis
