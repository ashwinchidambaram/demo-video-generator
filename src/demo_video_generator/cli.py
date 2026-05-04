"""Typer CLI entry: ``dvg <subcommand>``."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from . import doctor as doctor_mod
from . import run as run_mod
from .errors import DvgError, DvgRuntimeError, die

app = typer.Typer(
    name="dvg",
    help="demo-video-generator: turn a thing you built into a production-quality demo video.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command("doctor")
def doctor_cmd(
    strict_freshness: bool = typer.Option(False, "--strict-freshness"),
) -> None:
    """Verify dev environment and codegen freshness."""
    ok = doctor_mod.run(strict_freshness=strict_freshness)
    if not ok:
        raise typer.Exit(1)


@app.command("run")
def run_cmd(
    input: str = typer.Argument(..., help="URL, video path, or 'screen'"),
    runs_root: Path = typer.Option(Path("runs"), "--runs-root"),
    from_stage: str | None = typer.Option(None, "--from", help="Invalidate this stage and downstream, then re-run."),
) -> None:
    """Deterministic driver: walks manifest, dispatches missing-artifact agents."""
    if input.startswith(("http://", "https://")):
        kind = "url"
    elif input == "screen":
        kind = "screen"
    else:
        kind = "video"

    if from_stage is not None:
        # Resume: pick the most-recent run and rewind from a stage.
        # Run-dir names are ISO-like timestamps starting with "20"; this filter
        # excludes meta dirs like runs/refresh/.
        if not runs_root.exists():
            die(
                DvgError(
                    error="No runs directory; cannot --from.",
                    code="RUN_NO_RESUME",
                    retryable=False,
                    suggestion=f"Run 'dvg run {input}' first.",
                )
            )
        existing = sorted(
            p for p in runs_root.iterdir() if p.is_dir() and p.name.startswith("20")
        )
        if not existing:
            die(
                DvgError(
                    error="No prior runs to resume.",
                    code="RUN_NO_RESUME",
                    retryable=False,
                    suggestion=f"Run 'dvg run {input}' first.",
                )
            )
        run_dir = existing[-1]
    else:
        run_id = run_mod.make_run_id()
        run_dir = run_mod.init_run_dir(runs_root, run_id, kind, input)

    result = run_mod.dispatch(run_dir, from_stage=from_stage, dry_run=True)
    console.print(f"[bold]run dir:[/] {result.run_dir}")
    if result.final_artifact:
        console.print(f"[green]final:[/] {result.final_artifact}")
    else:
        console.print(
            "[yellow]Phase 0 driver: no agents wired yet. "
            "Phase 1 stubs the agent dispatch.[/]"
        )


def main() -> None:
    try:
        app()
    except DvgRuntimeError as e:
        die(e.err, e.exit_code)


if __name__ == "__main__":
    main()
