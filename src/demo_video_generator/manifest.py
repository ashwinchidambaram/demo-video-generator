"""Run-manifest helpers.

The manifest is the driver's only state. depends_on per stage encodes the DAG
that --from <step> walks to invalidate downstream artifacts. This file is a
hand-written wrapper around the codegen Pydantic models that exposes the DAG
operations the driver needs.

Codegen output lives in ``schemas/`` (after ``make schemas``) and is the
authoritative type for serialization. We keep this file lightweight on purpose —
the schema is the source of truth, not these helpers.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = 1


# The canonical v1 pipeline. Names match agent owners; depends_on encodes the DAG.
# Listed in topological order so the driver's "next missing" walk is also order-correct.
DEFAULT_PIPELINE: list[dict[str, Any]] = [
    {
        "name": "capture",
        "artifact": "footage.mp4",
        "owner": "footage-capture",
        "depends_on": [],
    },
    {
        "name": "analyze",
        "artifact": "analysis.json",
        "owner": "event-log-analyst",  # visual-analyst contributes to same artifact
        "depends_on": ["capture"],
    },
    {
        "name": "captions",
        "artifact": "captions.json",
        "owner": "caption-writer",
        "depends_on": ["analyze"],
    },
    {
        "name": "music",
        "artifact": "music.mp3",
        "owner": "music-prompt-engineer",
        "depends_on": ["analyze"],
    },
    {
        "name": "sfx",
        "artifact": "sfx/manifest.json",  # sfx-curator writes a manifest of placements; .wav files are siblings
        "owner": "sfx-curator",
        "depends_on": ["analyze"],
    },
    {
        "name": "compose",
        "artifact": "composition.json",
        "owner": "composition-director",
        "depends_on": ["analyze", "captions", "music", "sfx"],
    },
    {
        "name": "render",
        "artifact": "final.mp4",
        "owner": "_cli:render",  # not an agent; CLI primitive only (render-engineer was demoted)
        "depends_on": ["compose"],
    },
    {
        "name": "review",
        "artifact": "qa.json",
        "owner": "qa-reviewer",
        "depends_on": ["render"],
    },
]


@dataclass(slots=True)
class StageView:
    name: str
    artifact: str
    owner: str
    depends_on: tuple[str, ...]
    status: str
    raw: dict[str, Any]


def new_manifest(run_id: str, input_kind: str, input_value: str) -> dict[str, Any]:
    """Construct a fresh manifest with the default pipeline."""
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "input": {"kind": input_kind, "value": input_value},
        "config": {},
        "stages": [
            {
                **stage,
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "duration_seconds": None,
                "artifact_sha256": None,
                "cost_usd": None,
                "tokens": None,
                "attempts": 0,
            }
            for stage in DEFAULT_PIPELINE
        ],
    }


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


def stages(manifest: dict[str, Any]) -> list[StageView]:
    return [
        StageView(
            name=s["name"],
            artifact=s["artifact"],
            owner=s["owner"],
            depends_on=tuple(s["depends_on"]),
            status=s["status"],
            raw=s,
        )
        for s in manifest["stages"]
    ]


def find_stage(manifest: dict[str, Any], name: str) -> dict[str, Any] | None:
    for s in manifest["stages"]:
        if s["name"] == name:
            stage: dict[str, Any] = s
            return stage
    return None


def downstream_of(manifest: dict[str, Any], target: str) -> list[str]:
    """Return all stage names that transitively depend on ``target`` (excluding target itself).

    Used by --from <step> to compute the cascading invalidation set: when the
    user says "redo from analyze", we must invalidate captions/music/sfx/compose/...
    because each declares analyze (transitively) in depends_on.
    """
    by_name = {s["name"]: s for s in manifest["stages"]}
    if target not in by_name:
        raise KeyError(f"Unknown stage: {target}")

    invalidated: set[str] = set()
    queue: deque[str] = deque([target])
    while queue:
        current = queue.popleft()
        for s in manifest["stages"]:
            if current in s["depends_on"] and s["name"] not in invalidated:
                invalidated.add(s["name"])
                queue.append(s["name"])
    return [s["name"] for s in manifest["stages"] if s["name"] in invalidated]


def next_pending(manifest: dict[str, Any], run_dir: Path) -> StageView | None:
    """Return the next stage whose artifact is missing (driver dispatch order)."""
    for view in stages(manifest):
        artifact_path = run_dir / view.artifact
        if not artifact_path.exists():
            return view
    return None


def _clear_stage_artifact(stage: dict[str, Any], run_dir: Path) -> None:
    """Remove a stage's artifact (and sibling files for directory-artifact
    stages like sfx)."""
    artifact_path = run_dir / stage["artifact"]
    if artifact_path.is_file():
        artifact_path.unlink()
    if "/" in stage["artifact"]:
        stage_dir = (run_dir / stage["artifact"]).parent
        if stage_dir.is_dir():
            for child in stage_dir.iterdir():
                if child.is_file():
                    child.unlink()


def _reset_stage(stage: dict[str, Any]) -> None:
    """Reset a stage's run-state fields (preserves attempts counter)."""
    stage["status"] = "pending"
    stage["started_at"] = None
    stage["finished_at"] = None
    stage["duration_seconds"] = None
    stage["error"] = None
    stage["artifact_sha256"] = None


def invalidate(manifest: dict[str, Any], target: str, run_dir: Path) -> list[str]:
    """Mark ``target`` and all downstream stages pending; remove their artifacts.

    Returns the list of stage names invalidated (target + cascading downstream).

    NB: this is the "structural" invalidation that conservatively clears the
    full downstream cone. The driver's content-aware re-run path (D17)
    uses ``invalidate_target_only`` + ``cascade_if_changed`` for the
    skip-when-unchanged case.
    """
    cascading = downstream_of(manifest, target)
    invalidated = [target, *cascading]
    for name in invalidated:
        stage = find_stage(manifest, name)
        if stage is None:
            continue
        _clear_stage_artifact(stage, run_dir)
        _reset_stage(stage)
    return invalidated


def invalidate_target_only(manifest: dict[str, Any], target: str, run_dir: Path) -> str | None:
    """D17 step 1: clear ONLY the target stage so the driver can re-run it.

    Captures the target's prior `artifact_sha256` so the post-run cascade
    decision can compare. Returns the prior hash (or None if the stage
    hadn't run).
    """
    stage = find_stage(manifest, target)
    if stage is None:
        return None
    prior_hash = stage.get("artifact_sha256")
    _clear_stage_artifact(stage, run_dir)
    _reset_stage(stage)
    return prior_hash


def cascade_if_changed(
    manifest: dict[str, Any],
    target: str,
    run_dir: Path,
    *,
    prior_hash: str | None,
) -> list[str]:
    """D17 step 2: invoked AFTER the target stage has been re-run. If the
    new artifact hash matches the prior hash, downstream stages are
    preserved (their artifacts remain valid). Otherwise downstream is
    structurally invalidated.

    Returns the list of downstream stages that ended up invalidated
    (empty when the hashes matched and the cone was preserved).
    """
    stage = find_stage(manifest, target)
    if stage is None:
        return []
    new_hash = stage.get("artifact_sha256")
    if prior_hash is not None and new_hash is not None and prior_hash == new_hash:
        return []
    cascading = downstream_of(manifest, target)
    for name in cascading:
        s = find_stage(manifest, name)
        if s is None:
            continue
        _clear_stage_artifact(s, run_dir)
        _reset_stage(s)
    return cascading
