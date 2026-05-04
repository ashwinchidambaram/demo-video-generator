"""Music subcommand.

Phase 4 implements the soundtrack-from-folder path: ingest one MP3 from a
configured directory of pre-existing tracks. Lyria preview generation
remains the v1 target (D1) but is gated on `GEMINI_API_KEY` and an
empirical smoke test; until then the soundtrack-folder mode lets a real
demo run end-to-end with the user's own audio.

The agent design (`.claude/agents/music-prompt-engineer/design.md`)
covers Lyria-prompt authoring + audio-QA verification for the generated
path; this module supplies the deterministic ingest path that doesn't
need an LLM in the loop.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path
from typing import Any

from ..atomic import write_atomic, write_json_atomic


def _list_soundtracks(soundtrack_dir: Path) -> list[Path]:
    """List `.mp3` files in soundtrack_dir, sorted by name for determinism."""
    if not soundtrack_dir.is_dir():
        return []
    return sorted(p for p in soundtrack_dir.glob("*.mp3") if p.is_file())


def _pick_track(tracks: list[Path], *, hint: str | None = None, run_id_seed: str = "") -> Path:
    """Choose one track. Hint is a substring to prefer (e.g. 'flow', 'edm');
    otherwise picks deterministically from `run_id_seed`.

    Deterministic so re-runs of the same input produce the same music
    selection (caption authoring + QA depend on this).
    """
    if not tracks:
        raise FileNotFoundError("no soundtracks available")
    if hint:
        matches = [t for t in tracks if hint.lower() in t.name.lower()]
        if matches:
            return matches[0]
    seed_int = int(hashlib.sha256(run_id_seed.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed_int)
    return rng.choice(tracks)


def ingest_soundtrack(
    *,
    soundtrack_dir: Path,
    out_path: Path,
    duration_seconds: float = 10.0,
    hint: str | None = None,
    run_id_seed: str = "",
) -> dict[str, Any]:
    """Phase 4 ingest path: pick a track from `soundtrack_dir`, copy to `out_path`.

    Writes a `music_meta.json` sidecar (per agent design) recording which
    source track was chosen and the verification readout (Phase 4 stub: just
    file size + duration hint; Phase 4.5 wires the audio-QA toolkit).
    """
    tracks = _list_soundtracks(soundtrack_dir)
    if not tracks:
        raise FileNotFoundError(f"no .mp3 files in {soundtrack_dir}")
    chosen = _pick_track(tracks, hint=hint, run_id_seed=run_id_seed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(out_path, chosen.read_bytes())

    meta_path = out_path.with_name("music_meta.json")
    write_json_atomic(
        meta_path,
        {
            "schema_version": 1,
            "mode": "ingest",
            "source": str(chosen),
            "source_name": chosen.name,
            "intended_duration_seconds": duration_seconds,
            "hint": hint,
            "verification": {
                "stub": True,
                "size_bytes": chosen.stat().st_size,
            },
        },
    )
    return {
        "music": str(out_path),
        "source": str(chosen),
        "duration_seconds": duration_seconds,
    }


def stub_music(out_path: Path, duration_seconds: float = 10.0) -> dict[str, Any]:
    """Driver entry. Looks at the run dir's manifest config for a
    `soundtrack_dir` setting; if present, ingests. Otherwise falls back to
    the Phase 1 placeholder so the walking skeleton still completes.

    Soundtrack dir can be set via:
    - `DVG_SOUNDTRACK_DIR` env var (preferred for ad-hoc runs)
    - `manifest.config.soundtrack_dir` (preferred for tracked runs)
    """
    soundtrack_dir = os.environ.get("DVG_SOUNDTRACK_DIR")
    run_dir = out_path.parent
    if not soundtrack_dir:
        manifest_path = run_dir / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text())
                soundtrack_dir = (manifest.get("config") or {}).get("soundtrack_dir")
            except (json.JSONDecodeError, KeyError):
                soundtrack_dir = None

    hint = os.environ.get("DVG_MUSIC_HINT")
    run_id_seed = run_dir.name

    if soundtrack_dir:
        try:
            return ingest_soundtrack(
                soundtrack_dir=Path(soundtrack_dir),
                out_path=out_path,
                duration_seconds=duration_seconds,
                hint=hint,
                run_id_seed=run_id_seed,
            )
        except FileNotFoundError:
            # Fall through to placeholder if the dir is bad.
            pass

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        b"# placeholder music.mp3 marker. Set DVG_SOUNDTRACK_DIR or "
        b"manifest.config.soundtrack_dir to ingest a real track.\n"
        + f"# duration={duration_seconds}\n".encode()
    )
    write_atomic(out_path, payload)
    return {"music": str(out_path), "duration_seconds": duration_seconds, "mode": "placeholder"}
