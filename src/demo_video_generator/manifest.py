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
        "artifact": "sfx/.placeholder",  # directory artifact; presence of marker = done
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


def invalidate(manifest: dict[str, Any], target: str, run_dir: Path) -> list[str]:
    """Mark ``target`` and all downstream stages pending; remove their artifacts.

    Returns the list of stage names invalidated (target + cascading downstream).
    """
    cascading = downstream_of(manifest, target)
    invalidated = [target, *cascading]
    for name in invalidated:
        stage = find_stage(manifest, name)
        if stage is None:
            continue
        artifact_path = run_dir / stage["artifact"]
        if artifact_path.is_file():
            artifact_path.unlink()
        stage["status"] = "pending"
        stage["started_at"] = None
        stage["finished_at"] = None
        stage["duration_seconds"] = None
        stage["error"] = None
    return invalidated
