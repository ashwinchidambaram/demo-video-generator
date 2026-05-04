"""dvg run — deterministic driver.

Walks the per-run manifest and dispatches the owning stage handler for the
next missing artifact. Phase 1: real dispatch via in-process Python stubs
(capture/analyze/captions/music/sfx/compose/render/review).

Phase 2+ swaps each stage to its agent-driven implementation. The driver
contract — walk manifest, atomic-write the artifact, validate, advance —
stays identical.

Replaces the v1 plan's LLM-orchestrator (`director`) — see DECISIONS.md D7.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console

from . import manifest as mf
from .analysis import stub_analyze
from .atomic import write_json_atomic
from .captions import stub_captions
from .capture import stub_capture
from .composition import stub_compose
from .music import stub_music
from .render import RenderError
from .render import render as render_mp4
from .review import stub_review
from .sfx import stub_sfx

console = Console()


@dataclass(slots=True)
class RunResult:
    run_dir: Path
    completed: list[str]
    skipped: list[str]
    final_artifact: Path | None
    error: str | None = None


def make_run_id() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H-%M-%S")


def init_run_dir(root: Path, run_id: str, input_kind: str, input_value: str) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "sfx").mkdir(exist_ok=True)
    manifest = mf.new_manifest(run_id, input_kind, input_value)
    write_json_atomic(run_dir / "manifest.json", manifest)
    return run_dir


def _sha256_of(path: Path) -> str | None:
    """Hash file bytes; return None for missing or empty files (the latter is
    common for Phase 1 placeholder artifacts where 'no content' is content-equal)."""
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _record_stage_result(
    manifest: dict[str, Any],
    stage_name: str,
    *,
    started: float,
    finished: float,
    run_dir: Path,
    cost_usd: float = 0.0,
) -> None:
    stage = mf.find_stage(manifest, stage_name)
    if stage is None:
        return
    stage["status"] = "complete"
    stage["started_at"] = dt.datetime.fromtimestamp(started, tz=dt.UTC).isoformat()
    stage["finished_at"] = dt.datetime.fromtimestamp(finished, tz=dt.UTC).isoformat()
    stage["duration_seconds"] = round(finished - started, 3)
    stage["cost_usd"] = cost_usd
    stage["attempts"] = (stage.get("attempts") or 0) + 1
    artifact_path = run_dir / stage["artifact"]
    stage["artifact_sha256"] = _sha256_of(artifact_path)


def _dispatch_capture(run_dir: Path, manifest: dict[str, Any]) -> None:
    inp = manifest["input"]
    stub_capture(inp["kind"], inp["value"], run_dir)


def _dispatch_analyze(run_dir: Path, manifest: dict[str, Any]) -> None:
    stub_analyze(run_dir / "footage.events.json", run_dir / "analysis.json")


def _dispatch_captions(run_dir: Path, manifest: dict[str, Any]) -> None:
    stub_captions(run_dir / "analysis.json", run_dir / "captions.json")


def _dispatch_music(run_dir: Path, manifest: dict[str, Any]) -> None:
    import contextlib
    import json

    duration = 10.0
    analysis = run_dir / "analysis.json"
    if analysis.exists():
        with contextlib.suppress(KeyError, json.JSONDecodeError, ValueError):
            duration = float(json.loads(analysis.read_text())["duration_seconds"])
    stub_music(run_dir / "music.mp3", duration)


def _dispatch_sfx(run_dir: Path, manifest: dict[str, Any]) -> None:
    stub_sfx(run_dir / "sfx")


def _dispatch_compose(run_dir: Path, manifest: dict[str, Any]) -> None:
    stub_compose(
        analysis_path=run_dir / "analysis.json",
        captions_path=run_dir / "captions.json",
        music_path=run_dir / "music.mp3",
        sfx_manifest_path=run_dir / "sfx" / "manifest.json",
        footage_path=run_dir / "footage.mp4",
        out_path=run_dir / "composition.json",
    )


def _dispatch_render(run_dir: Path, manifest: dict[str, Any]) -> None:
    composition = run_dir / "composition.json"
    out = run_dir / "final.mp4"
    bundle_dir = run_dir / ".remotion-bundle"
    render_mp4(composition, out, bundle_dir=bundle_dir)


def _dispatch_review(run_dir: Path, manifest: dict[str, Any]) -> None:
    stub_review(run_dir / "final.mp4", run_dir)


_DISPATCHERS: dict[str, Callable[[Path, dict[str, Any]], None]] = {
    "capture": _dispatch_capture,
    "analyze": _dispatch_analyze,
    "captions": _dispatch_captions,
    "music": _dispatch_music,
    "sfx": _dispatch_sfx,
    "compose": _dispatch_compose,
    "render": _dispatch_render,
    "review": _dispatch_review,
}


def dispatch(
    run_dir: Path,
    *,
    from_stage: str | None = None,
    skip_render: bool = False,
) -> RunResult:
    """Walk the manifest and dispatch the owning handler for each missing artifact.

    `skip_render`: Phase 1 escape hatch — if Remotion isn't available (CI without
    Chromium), skip the render + review stages cleanly and return early.
    """
    manifest_path = run_dir / "manifest.json"
    manifest = mf.load(manifest_path)

    if from_stage is not None:
        invalidated = mf.invalidate(manifest, from_stage, run_dir)
        write_json_atomic(manifest_path, manifest)
        console.print(f"[yellow]--from {from_stage}: invalidated {invalidated}[/]")

    completed: list[str] = []
    skipped: list[str] = []
    error: str | None = None

    while True:
        view = mf.next_pending(manifest, run_dir)
        if view is None:
            break

        if skip_render and view.name in {"render", "review"}:
            console.print(f"[dim]skip-render: skipping {view.name}[/]")
            skipped.append(view.name)
            stage = mf.find_stage(manifest, view.name)
            if stage is not None:
                stage["status"] = "skipped"
            write_json_atomic(manifest_path, manifest)
            break  # nothing else to do; render/review are last

        handler = _DISPATCHERS.get(view.name)
        if handler is None:
            console.print(f"[red]no dispatcher for stage {view.name}[/]")
            error = f"no dispatcher for stage {view.name}"
            break

        console.print(f"[cyan]dispatch[/] {view.owner} → [bold]{view.name}[/] → {view.artifact}")
        started = time.time()
        try:
            handler(run_dir, manifest)
        except RenderError as e:
            console.print(f"[red]render failed:[/] {e}")
            stage = mf.find_stage(manifest, view.name)
            if stage is not None:
                stage["status"] = "failed"
                stage["attempts"] = (stage.get("attempts") or 0) + 1
            write_json_atomic(manifest_path, manifest)
            error = str(e)
            break
        except Exception as e:
            console.print(f"[red]{view.name} failed:[/] {e}")
            stage = mf.find_stage(manifest, view.name)
            if stage is not None:
                stage["status"] = "failed"
                stage["attempts"] = (stage.get("attempts") or 0) + 1
            write_json_atomic(manifest_path, manifest)
            error = str(e)
            break
        finished = time.time()
        _record_stage_result(manifest, view.name, started=started, finished=finished, run_dir=run_dir)
        write_json_atomic(manifest_path, manifest)
        completed.append(view.name)

    final = run_dir / "final.mp4"
    return RunResult(
        run_dir=run_dir,
        completed=completed,
        skipped=skipped,
        final_artifact=final if final.exists() else None,
        error=error,
    )
