"""SFX subcommand.

Phase 5: maps events from `analysis.json` to clips in the synthetic CC0 pack
(`pack/index.json`). Aesthetic anchor per agent design: tasteful UI feedback
("Linear notification, not Mario coin").

Density rule: Phase 5 places SFX for ~30-50% of events — each event consults
the kind->clip mapping table; events whose kinds aren't in the table get
silently skipped. (Phase 5.5 will use the real Kenney curated subset and
the sfx-curator agent's judgment for tasteful selection.)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic

PACK_DIR = Path(__file__).resolve().parent / "pack"
PACK_INDEX = PACK_DIR / "index.json"


def _load_pack() -> dict[str, Any]:
    if not PACK_INDEX.is_file():
        return {"clips": [], "kind_to_clip": {}}
    pack: dict[str, Any] = json.loads(PACK_INDEX.read_text())
    return pack


def place_sfx_from_analysis(
    *,
    analysis: dict[str, Any],
    sfx_dir: Path,
) -> dict[str, Any]:
    """Phase 5 placement: read events, look up clips, copy to sfx_dir."""
    sfx_dir.mkdir(parents=True, exist_ok=True)
    pack = _load_pack()
    kind_to_clip: dict[str, str] = pack.get("kind_to_clip", {})
    clips_by_id: dict[str, dict[str, Any]] = {c["id"]: c for c in pack.get("clips", [])}

    placements: list[dict[str, Any]] = []
    for ev in analysis.get("events", []):
        kind = ev.get("kind", "")
        clip_id = kind_to_clip.get(kind)
        if clip_id is None:
            continue
        clip = clips_by_id.get(clip_id)
        if clip is None:
            continue
        src = PACK_DIR / clip["filename"]
        if not src.is_file():
            continue
        dst_name = f"{ev['id']}-0.wav"
        dst = sfx_dir / dst_name
        shutil.copy2(src, dst)
        placements.append(
            {
                "event_id": ev["id"],
                "clip_path": f"sfx/{dst_name}",
                "source_clip_id": clip_id,
                "t": float(ev["t"]),
                "gain_db": -3.0,
                "rationale": clip.get("description", ""),
            }
        )

    manifest_path = sfx_dir / "manifest.json"
    write_json_atomic(
        manifest_path,
        {
            "schema_version": 1,
            "placements": placements,
        },
    )
    return {
        "manifest": str(manifest_path),
        "placement_count": len(placements),
    }


def stub_sfx(sfx_dir: Path) -> dict[str, Any]:
    """Driver entry. Reads sibling analysis.json for events, places SFX.

    Falls back to empty placements if analysis.json is missing.
    """
    run_dir = sfx_dir.parent
    analysis_path = run_dir / "analysis.json"
    if not analysis_path.is_file():
        sfx_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            sfx_dir / "manifest.json",
            {"schema_version": 1, "placements": []},
        )
        return {"manifest": str(sfx_dir / "manifest.json"), "placement_count": 0}
    analysis = json.loads(analysis_path.read_text())
    return place_sfx_from_analysis(analysis=analysis, sfx_dir=sfx_dir)
