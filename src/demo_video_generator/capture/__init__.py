"""Capture subcommand. Phase 1 stub: writes a placeholder footage marker
+ valid empty events log. Phase 2 replaces with real Playwright + ffmpeg."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..atomic import write_atomic, write_json_atomic


def stub_capture(input_kind: str, input_value: str, out_dir: Path) -> dict[str, Any]:
    """Phase 1 stub: produce a tiny placeholder footage.mp4 marker and a
    schema-valid (empty) footage.events.json.

    The "footage" here is an empty file; Phase 1 DemoVideo doesn't render the
    footage layer (Phase 6 wires that up). The events log is structurally
    valid so event-log-analyst's stub can read it.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    footage_path = out_dir / "footage.mp4"
    events_path = out_dir / "footage.events.json"

    # Placeholder footage. Real bytes land in Phase 2.
    write_atomic(footage_path, b"")

    # Schema-valid empty events log.
    write_json_atomic(
        events_path,
        {
            "schema_version": 1,
            "kind": input_kind,
            "input": input_value,
            "events": [],
            "duration_seconds": 10.0,
            "fps": 30,
            "resolution": {"width": 1920, "height": 1080},
        },
    )
    return {
        "footage": str(footage_path),
        "events": str(events_path),
        "duration_seconds": 10.0,
    }


def cli(input_kind: str, input_value: str, out: str) -> str:
    """Entry called by `dvg capture`. Returns JSON to stdout."""
    out_dir = Path(out).parent
    result = stub_capture(input_kind, input_value, out_dir)
    return json.dumps(result, indent=2)
