"""SFX subcommand. Phase 1 stub: writes an empty sfx/manifest.json (no
placements). Phase 5 replaces with Kenney CC0 lookup + curation logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic


def stub_sfx(sfx_dir: Path) -> dict[str, Any]:
    """Phase 1 stub: empty placement manifest. Schema-valid; downstream stubs
    can read it and produce a composition with `audio.sfx: []`.
    """
    sfx_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = sfx_dir / "manifest.json"
    write_json_atomic(
        manifest_path,
        {
            "schema_version": 1,
            "placements": [],
        },
    )
    return {"manifest": str(manifest_path), "placement_count": 0}
