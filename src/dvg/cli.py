"""dvg — typer CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from dvg import __version__
from dvg.composition.render import plan as plan_composition
from dvg.composition.render import render as render_composition
from dvg.models import Composition

app = typer.Typer(
    name="dvg",
    help="Lean demo-video generator. Capture → analyze → compose → render.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
console = Console()


@app.command()
def version() -> None:
    """Print the dvg version."""
    console.print(f"dvg v{__version__}")


@app.command()
def render(
    composition_path: Annotated[Path, typer.Argument(help="Path to composition.json")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output MP4 path")] = Path(
        "final.mp4"
    ),
    keep: Annotated[
        bool, typer.Option("--keep-intermediates", help="Keep audio stem and ASS file")
    ] = False,
    crf: Annotated[int, typer.Option("--crf", help="x264 quality (lower=better)")] = 18,
    preset: Annotated[
        str, typer.Option("--preset", help="x264 preset (faster|medium|slow)")
    ] = "medium",
) -> None:
    """Render a composition.json to MP4."""
    comp = Composition.load(composition_path)
    console.print(f"[dim]Rendering[/dim] {composition_path} → {out}")
    result = render_composition(
        comp,
        out,
        crf=crf,
        preset=preset,
        keep_intermediates=keep,
    )
    table = Table(title="Render result")
    table.add_column("metric", style="cyan")
    table.add_column("value", style="white")
    table.add_row("output", str(result.out))
    table.add_row("render time", f"{result.duration_s:.2f}s")
    table.add_row("integrated LUFS", f"{result.audio_lufs}")
    table.add_row("true peak", f"{result.audio_peak_dbfs} dBFS")
    table.add_row("size", f"{result.out.stat().st_size / 1024:.0f} KB")
    console.print(table)


@app.command()
def plan(
    composition_path: Annotated[Path, typer.Argument(help="Path to composition.json")],
) -> None:
    """Show what would be rendered without rendering."""
    comp = Composition.load(composition_path)
    info = plan_composition(comp)
    table = Table(title=f"Render plan — {composition_path.name}")
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")
    for k, v in info.items():
        table.add_row(k, str(v))
    console.print(table)


@app.command()
def validate(
    composition_path: Annotated[Path, typer.Argument(help="Path to composition.json")],
) -> None:
    """Validate a composition.json against the schema."""
    try:
        Composition.load(composition_path)
        console.print(f"[green]✓[/green] {composition_path} is valid")
    except Exception as e:
        console.print(f"[red]✗[/red] {composition_path}: {e}")
        raise typer.Exit(1) from e


@app.command()
def schema(
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Write JSON schema to this path")
    ] = Path("composition.schema.json"),
) -> None:
    """Export the Composition JSON Schema."""
    schema_dict = Composition.model_json_schema()
    out.write_text(json.dumps(schema_dict, indent=2))
    console.print(f"[green]✓[/green] schema → {out}")


@app.command()
def doctor() -> None:
    """Verify the dvg toolchain is installed and ready."""
    rows: list[tuple[str, bool, str]] = []
    rows.append(_check_cmd("ffmpeg", ["ffmpeg", "-version"]))
    rows.append(_check_cmd("ffprobe", ["ffprobe", "-version"]))
    rows.append(_check_cmd("aubio", ["aubio", "-h"]))
    rows.append(_check_cmd("sox", ["sox", "--version"]))
    rows.append(_check_libass())

    table = Table(title="dvg doctor")
    table.add_column("dep", style="cyan")
    table.add_column("status")
    table.add_column("info", style="dim")
    any_fail = False
    for name, ok, info in rows:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, status, info)
        if not ok:
            any_fail = True
    console.print(table)
    if any_fail:
        console.print()
        console.print(
            "[yellow]Hint:[/yellow] for libass-enabled ffmpeg, "
            "`brew install homebrew-ffmpeg/ffmpeg/ffmpeg` (the default brew formula lacks libass)."
        )
        raise typer.Exit(1)


def _check_cmd(name: str, cmd: list[str]) -> tuple[str, bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0 or "version" in proc.stdout.lower() + proc.stderr.lower():
            first_line = (proc.stdout + proc.stderr).strip().splitlines()[0]
            return name, True, first_line[:80]
        return name, False, f"exit={proc.returncode}"
    except FileNotFoundError:
        return name, False, "not found in PATH"


def _check_libass() -> tuple[str, bool, str]:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=False
        )
        ok = "subtitles" in proc.stdout
        return "ffmpeg+libass", ok, "subtitles filter present" if ok else "subtitles filter missing"
    except FileNotFoundError:
        return "ffmpeg+libass", False, "ffmpeg not found"


if __name__ == "__main__":
    app()
