"""Capture subcommand.

Phase 2 implements the file-ingest path (`kind=video`): copy/normalize an
existing video file. The URL (Playwright headed-Chromium) and screen
(ffmpeg avfoundation) paths are gated on ffmpeg availability and macOS
TCC permission — they fall through to a structured synthetic placeholder
when not viable locally, deferring full implementation to Phase 2.5 once
those are unblocked.

Phase 2 is enough to drive a real demo render through Phases 4-11 with a
pre-recorded video as input.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..atomic import write_atomic, write_json_atomic


def _ffprobe_duration(path: Path) -> float | None:
    """Return video duration in seconds via ffprobe, or None if unavailable."""
    if shutil.which("ffprobe") is None:
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        meta = json.loads(proc.stdout)
        return float(meta["format"]["duration"])
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, KeyError, ValueError):
        return None


def capture_file(
    src: Path,
    out_dir: Path,
    *,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Phase 2 file-ingest path: copy the source video to footage.mp4.

    (Phase 2.5 will normalize via ffmpeg if installed.) Writes a valid
    empty footage.events.json since pre-recorded files have no DOM events.
    """
    if not src.is_file():
        raise FileNotFoundError(f"capture source not found: {src}")

    out_dir.mkdir(parents=True, exist_ok=True)
    footage_path = out_dir / "footage.mp4"
    events_path = out_dir / "footage.events.json"

    data = src.read_bytes()
    write_atomic(footage_path, data)

    probed = _ffprobe_duration(footage_path)
    if probed is not None:
        duration = probed
    elif duration_seconds is not None:
        duration = duration_seconds
    else:
        duration = 10.0

    write_json_atomic(
        events_path,
        {
            "schema_version": 1,
            "kind": "video",
            "input": str(src),
            "events": [],
            "duration_seconds": duration,
            "fps": 30,
            "resolution": {"width": 1920, "height": 1080},
        },
    )
    return {
        "footage": str(footage_path),
        "events": str(events_path),
        "duration_seconds": duration,
        "source": str(src),
    }


def capture_synthetic(out_dir: Path, *, duration_seconds: float = 10.0) -> dict[str, Any]:
    """Synthetic placeholder for URL/screen inputs when ffmpeg/Playwright/TCC
    aren't available. Phase 1 DemoVideo composes captions over a gradient
    background so a placeholder footage file works for the walking skeleton.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    footage_path = out_dir / "footage.mp4"
    events_path = out_dir / "footage.events.json"
    write_atomic(footage_path, b"")
    write_json_atomic(
        events_path,
        {
            "schema_version": 1,
            "kind": "synthetic",
            "events": [],
            "duration_seconds": duration_seconds,
            "fps": 30,
            "resolution": {"width": 1920, "height": 1080},
        },
    )
    return {
        "footage": str(footage_path),
        "events": str(events_path),
        "duration_seconds": duration_seconds,
        "source": "synthetic",
    }


def stub_capture(input_kind: str, input_value: str, out_dir: Path) -> dict[str, Any]:
    """Driver dispatch entry. Routes by `input_kind`:

    - `video` → Phase 2 file-ingest path.
    - `url` / `screen` → synthetic placeholder (Phase 2.5 gated on ffmpeg + TCC).
    """
    if input_kind == "video":
        return capture_file(Path(input_value), out_dir)
    return capture_synthetic(out_dir, duration_seconds=10.0)


def cli(input_kind: str, input_value: str, out: str) -> str:
    """Entry called by `dvg capture`. Returns JSON to stdout."""
    out_dir = Path(out).parent
    result = stub_capture(input_kind, input_value, out_dir)
    return json.dumps(result, indent=2)
