"""Music subcommand. Phase 1 stub: emits a placeholder marker file. Phase 4
replaces with real Lyria (or fallback) generator + audio QA verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..atomic import write_atomic


def stub_music(out_path: Path, duration_seconds: float = 10.0) -> dict[str, Any]:
    """Phase 1 stub: write a placeholder marker file. The Phase 1 DemoVideo
    does not consume the audio track yet; Phase 6 wires it up.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        b"# placeholder music.mp3 marker. Phase 4 replaces with real audio.\n"
        + f"# duration={duration_seconds}\n".encode()
    )
    write_atomic(out_path, payload)
    return {"music": str(out_path), "duration_seconds": duration_seconds}
