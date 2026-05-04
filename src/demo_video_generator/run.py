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


# Auto-retry allowlist: imported from the codegen module (make qa-codes)
# which parses .claude/agents/qa-reviewer/knowledge/core.md as source of
# truth. Single registry — no manual sync between run.py and the agent
# prompt. Falls back to an empty frozenset if codegen hasn't run yet.
try:
    from .review.codes import AUTO_RETRY_ALLOWLIST
except ImportError:
    AUTO_RETRY_ALLOWLIST: frozenset[str] = frozenset()  # type: ignore[no-redef]


@dataclass(slots=True)
class RunResult:
    run_dir: Path
    completed: list[str]
    skipped: list[str]
    final_artifact: Path | None
    error: str | None = None
    auto_retried: list[str] | None = None


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

    # D17 content-aware --from: clear ONLY the target; downstream cascading
    # decision happens after the target re-runs (depending on whether the new
    # artifact_sha256 matches the prior).
    pending_cascade_target: str | None = None
    pending_cascade_prior_hash: str | None = None
    if from_stage is not None:
        pending_cascade_prior_hash = mf.invalidate_target_only(
            manifest, from_stage, run_dir
        )
        pending_cascade_target = from_stage
        write_json_atomic(manifest_path, manifest)
        console.print(
            f"[yellow]--from {from_stage}: cleared target; downstream cascade decided post-run by hash[/]"
        )

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
        # D17 cascade-if-changed: if this stage was the --from target and its
        # new artifact hash matches the prior, downstream artifacts are kept.
        if pending_cascade_target is not None and view.name == pending_cascade_target:
            cascaded = mf.cascade_if_changed(
                manifest,
                pending_cascade_target,
                run_dir,
                prior_hash=pending_cascade_prior_hash,
            )
            if cascaded:
                console.print(
                    f"[yellow]content changed: cascade invalidated {cascaded}[/]"
                )
            else:
                console.print(
                    "[green]content unchanged: downstream artifacts preserved[/]"
                )
            pending_cascade_target = None
            pending_cascade_prior_hash = None
        write_json_atomic(manifest_path, manifest)
        completed.append(view.name)

    # Phase 8 auto-retry per allowlist: if review just landed and qa.json has
    # a high-severity allowlisted issue proposing regenerate_stage, re-dispatch
    # that stage exactly once.
    auto_retried: list[str] = []
    qa_path = run_dir / "qa.json"
    if (
        not error
        and "review" in completed
        and qa_path.is_file()
    ):
        try:
            qa_doc = __import__("json").loads(qa_path.read_text())
        except Exception:
            qa_doc = {}
        for issue in qa_doc.get("issues", []):
            if issue.get("severity") != "high":
                continue
            code = issue.get("code", "")
            if code not in AUTO_RETRY_ALLOWLIST:
                continue
            action = issue.get("proposed_action", {})
            if action.get("kind") != "regenerate_stage":
                continue
            target = action.get("target_stage")
            if not target or target in auto_retried:
                continue
            target_stage = mf.find_stage(manifest, target)
            attempts = (target_stage or {}).get("attempts", 0) or 0
            if attempts >= 2:  # one retry budget per stage per run
                continue
            console.print(
                f"[yellow]auto-retry[/] qa flagged {code} → re-dispatching {target}"
            )
            # Invalidate the target + its downstream so the re-run flows.
            mf.invalidate(manifest, target, run_dir)
            write_json_atomic(manifest_path, manifest)
            auto_retried.append(target)
            # Walk forward from the invalidated target through to review again.
            while True:
                view = mf.next_pending(manifest, run_dir)
                if view is None:
                    break
                handler = _DISPATCHERS.get(view.name)
                if handler is None:
                    break
                console.print(
                    f"[cyan]dispatch[/] {view.owner} → [bold]{view.name}[/] (retry)"
                )
                started = time.time()
                try:
                    handler(run_dir, manifest)
                except Exception as e:
                    console.print(f"[red]{view.name} retry failed:[/] {e}")
                    error = str(e)
                    break
                finished = time.time()
                _record_stage_result(
                    manifest, view.name, started=started, finished=finished, run_dir=run_dir
                )
                write_json_atomic(manifest_path, manifest)
                completed.append(view.name)
            break  # one auto-retry per run

    # Aggregate cost / duration summary into manifest (Phase 9 polish).
    total_cost = 0.0
    total_duration = 0.0
    for stage in manifest["stages"]:
        if stage.get("cost_usd"):
            total_cost += float(stage["cost_usd"])
        if stage.get("duration_seconds"):
            total_duration += float(stage["duration_seconds"])
    manifest["summary"] = {
        "total_cost_usd": round(total_cost, 4),
        "total_duration_seconds": round(total_duration, 3),
        "stages_completed": len(completed),
        "stages_skipped": len(skipped),
    }
    write_json_atomic(manifest_path, manifest)

    final = run_dir / "final.mp4"
    return RunResult(
        run_dir=run_dir,
        completed=completed,
        skipped=skipped,
        final_artifact=final if final.exists() else None,
        error=error,
        auto_retried=auto_retried or None,
    )


def _qa_has_high_severity(run_dir: Path) -> bool:
    """Check if the run's qa.json contains any severity: high issue."""
    qa_path = run_dir / "qa.json"
    if not qa_path.is_file():
        return False
    try:
        import json as _json

        qa = _json.loads(qa_path.read_text())
    except Exception:
        return False
    return any(issue.get("severity") == "high" for issue in qa.get("issues", []))


def cleanup_runs(runs_root: Path, *, keep: int = 20) -> list[Path]:
    """Delete oldest runs beyond the `keep` most recent. Per ultraplan R3:
    never delete a run with severity:high in qa.json (preserved for debugging).

    Returns the list of run dirs that were removed.
    """
    if not runs_root.is_dir():
        return []
    # Run dirs are timestamp-named; refresh/ etc are excluded by prefix.
    run_dirs = sorted(
        (p for p in runs_root.iterdir() if p.is_dir() and p.name.startswith("20")),
        key=lambda p: p.name,
    )
    if len(run_dirs) <= keep:
        return []

    candidates = run_dirs[:-keep]
    removed: list[Path] = []
    for d in candidates:
        if _qa_has_high_severity(d):
            continue  # preserve for debugging
        try:
            import shutil

            shutil.rmtree(d)
            removed.append(d)
        except OSError:
            pass
    return removed
