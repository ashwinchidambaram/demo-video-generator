"""dvg run — deterministic driver.

Walks the per-run manifest and dispatches the owning agent for the next missing
artifact. Phase 0 ships the skeleton: it can construct a manifest, walk it, and
report what *would* be dispatched. Actual agent dispatch wires up in Phase 1
(stub agents) and onward.

Replaces the v1 plan's LLM-orchestrator (``director``) — see DECISIONS.md D7.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from . import manifest as mf
from .atomic import write_json_atomic

console = Console()


@dataclass(slots=True)
class RunResult:
    run_dir: Path
    completed: list[str]
    pending: list[str]
    final_artifact: Path | None


def make_run_id() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H-%M-%S")


def init_run_dir(root: Path, run_id: str, input_kind: str, input_value: str) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "sfx").mkdir(exist_ok=True)
    manifest = mf.new_manifest(run_id, input_kind, input_value)
    write_json_atomic(run_dir / "manifest.json", manifest)
    return run_dir


def dispatch(run_dir: Path, *, from_stage: str | None = None, dry_run: bool = True) -> RunResult:
    """Walk the manifest, dispatching the owning agent for each missing artifact.

    In Phase 0, dispatch is *announce-only* (dry_run forced True). Phase 1 wires
    up real ``claude -p`` invocations for stub agents and removes the dry_run
    default.
    """
    manifest_path = run_dir / "manifest.json"
    manifest = mf.load(manifest_path)

    if from_stage is not None:
        invalidated = mf.invalidate(manifest, from_stage, run_dir)
        write_json_atomic(manifest_path, manifest)
        console.print(f"[yellow]--from {from_stage}: invalidated {invalidated}[/]")

    completed: list[str] = []
    pending: list[str] = []
    while True:
        view = mf.next_pending(manifest, run_dir)
        if view is None:
            break
        if dry_run:
            console.print(
                f"[cyan]would dispatch[/] [bold]{view.owner}[/] for stage "
                f"[bold]{view.name}[/] → {view.artifact}"
            )
            pending.append(view.name)
            # Phase 0: bail after announcing; no agents wired yet.
            break
        # Phase 1+: real dispatch goes here.
        raise NotImplementedError("Real agent dispatch wires up in Phase 1.")

    final = run_dir / "final.mp4"
    return RunResult(
        run_dir=run_dir,
        completed=completed,
        pending=pending,
        final_artifact=final if final.exists() else None,
    )
