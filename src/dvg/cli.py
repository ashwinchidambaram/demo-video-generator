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
from dvg.analysis import analyze_events
from dvg.capture import capture_url_sync
from dvg.composition.render import plan as plan_composition
from dvg.composition.render import render as render_composition
from dvg.director import DirectorContext
from dvg.director import plan_composition as director_plan
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
def capture(
    url: Annotated[str, typer.Argument(help="URL to capture (file:// or http(s)://)")],
    out_dir: Annotated[
        Path, typer.Option("--out-dir", "-o", help="Run directory")
    ] = Path("runs/capture"),
    duration: Annotated[float, typer.Option("--duration", "-d", help="seconds")] = 12.0,
    width: Annotated[int, typer.Option("--width", help="canvas width")] = 1920,
    height: Annotated[int, typer.Option("--height", help="canvas height")] = 1080,
    fps: Annotated[int, typer.Option("--fps", help="output fps")] = 30,
    scenario: Annotated[
        str, typer.Option("--scenario", help="tour | idle | path/to/scenario.py")
    ] = "tour",
    headless: Annotated[
        bool, typer.Option("--headless", help="run headless instead of headed")
    ] = False,
) -> None:
    """Capture a URL → footage.mp4 + footage.events.json."""
    console.print(f"[dim]Capturing[/dim] {url} → {out_dir}")
    result = capture_url_sync(
        url,
        out_dir=out_dir,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        scenario=scenario,
        headed=not headless,
    )
    table = Table(title="Capture result")
    table.add_column("metric", style="cyan")
    table.add_column("value", style="white")
    table.add_row("video", str(result.video_path))
    table.add_row("events", str(result.events_path))
    table.add_row("events count", str(result.events_count))
    table.add_row("size", f"{result.video_path.stat().st_size / 1024:.0f} KB")
    table.add_row("real time", f"{result.duration_s:.2f}s")
    console.print(table)


@app.command()
def analyze(
    run_dir: Annotated[
        Path, typer.Argument(help="Run dir containing footage.events.json")
    ],
    duration: Annotated[
        float, typer.Option("--duration", help="footage duration in seconds")
    ] = 12.0,
) -> None:
    """Analyze events.json → analysis.json (scenes + anchors)."""
    events_path = run_dir / "footage.events.json"
    if not events_path.exists():
        console.print(f"[red]✗[/red] {events_path} missing")
        raise typer.Exit(1)
    events = json.loads(events_path.read_text())
    analysis = analyze_events(events, duration=duration)
    out = run_dir / "analysis.json"
    out.write_text(analysis.model_dump_json(indent=2))
    table = Table(title=f"Analysis — {run_dir.name}")
    table.add_column("metric", style="cyan")
    table.add_column("value", style="white")
    table.add_row("duration", f"{analysis.duration_s:.2f}s")
    table.add_row("scenes", str(len(analysis.scenes)))
    table.add_row("anchors", str(len(analysis.anchors)))
    table.add_row("source", analysis.source)
    console.print(table)
    console.print()
    for s in analysis.scenes:
        console.print(
            f"  scene [dim]{s.id}[/dim] "
            f"[cyan]{s.time[0]:.2f}s → {s.time[1]:.2f}s[/cyan] "
            f"energy={s.energy:.2f} anchors={len(s.anchors)}"
        )


@app.command()
def direct(
    run_dir: Annotated[Path, typer.Argument(help="Run dir with footage + analysis")],
    url: Annotated[
        str | None, typer.Option("--url", help="Source URL (for title + CTA)")
    ] = None,
    title: Annotated[str | None, typer.Option("--title", help="Override title")] = None,
    tagline: Annotated[str | None, typer.Option("--tagline", help="Subtitle")] = None,
    brand_color: Annotated[
        str | None, typer.Option("--brand-color", help="Accent #RRGGBB")
    ] = None,
) -> None:
    """Heuristic director: footage + analysis → composition.json."""
    video = run_dir / "footage.mp4"
    analysis_path = run_dir / "analysis.json"
    if not video.exists() or not analysis_path.exists():
        console.print(f"[red]✗[/red] {run_dir} missing footage or analysis")
        raise typer.Exit(1)

    from dvg.analysis.events import Analysis as AnalysisModel

    analysis = AnalysisModel.model_validate_json(analysis_path.read_text())
    # probe video dims + duration
    import json as _json

    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=width,height,codec_type:format=duration",
            "-of",
            "json",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    info = _json.loads(proc.stdout)
    v_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    width = int(v_stream["width"])
    height = int(v_stream["height"])
    duration = float(info["format"]["duration"])

    ctx = DirectorContext(
        video_path=video,
        duration_s=duration,
        width=width,
        height=height,
        analysis=analysis,
        source_url=url,
        title=title,
        tagline=tagline,
        brand_color=brand_color,
    )
    comp = director_plan(ctx)
    out = run_dir / "composition.json"
    comp.save(out)
    table = Table(title=f"Director — {run_dir.name}")
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")
    table.add_row("composition", str(out))
    table.add_row("duration", f"{comp.duration:.2f}s")
    table.add_row("layers", str(len(comp.layers)))
    table.add_row("captions", str(sum(1 for layer in comp.layers if layer.kind == "caption")))
    table.add_row("audio", comp.audio[0].src.name if comp.audio else "—")
    console.print(table)


@app.command()
def make_video(
    url: Annotated[str, typer.Argument(help="URL or file:// to demo")],
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("final.mp4"),
    duration: Annotated[float, typer.Option("--duration", "-d")] = 12.0,
    width: Annotated[int, typer.Option("--width")] = 1920,
    height: Annotated[int, typer.Option("--height")] = 1080,
    scenario: Annotated[str, typer.Option("--scenario")] = "tour",
    headless: Annotated[bool, typer.Option("--headless")] = False,
    title: Annotated[str | None, typer.Option("--title")] = None,
    tagline: Annotated[str | None, typer.Option("--tagline")] = None,
    brand_color: Annotated[str | None, typer.Option("--brand-color")] = None,
    narrations: Annotated[
        str | None,
        typer.Option(
            "--narrations",
            help="Pipe-separated list of caption strings, e.g. 'Hello|World|Try it'",
        ),
    ] = None,
    keep_run: Annotated[bool, typer.Option("--keep-run")] = True,
) -> None:
    """End-to-end: capture → analyze → direct → render → MP4."""
    import time as _time
    from datetime import datetime

    run_dir = Path("runs") / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[bold]dvg make-video[/bold] {url} → {out}  ([dim]{run_dir}[/dim])")

    t0 = _time.perf_counter()
    cap = capture_url_sync(
        url,
        out_dir=run_dir,
        duration=duration,
        width=width,
        height=height,
        scenario=scenario,
        headed=not headless,
    )
    console.print(
        f"  [green]✓[/green] capture: {cap.events_count} events, "
        f"{cap.video_path.stat().st_size / 1024:.0f}KB"
    )

    events = json.loads(cap.events_path.read_text())
    analysis = analyze_events(events, duration=duration)
    (run_dir / "analysis.json").write_text(analysis.model_dump_json(indent=2))
    console.print(
        f"  [green]✓[/green] analyze: {len(analysis.scenes)} scenes, "
        f"{len(analysis.anchors)} anchors"
    )

    narration_list = (
        [s.strip() for s in narrations.split("|") if s.strip()]
        if narrations
        else None
    )
    ctx = DirectorContext(
        video_path=cap.video_path,
        duration_s=duration,
        width=width,
        height=height,
        analysis=analysis,
        source_url=url,
        title=title,
        tagline=tagline,
        brand_color=brand_color,
        narrations=narration_list,
    )
    comp = director_plan(ctx)
    comp.save(run_dir / "composition.json")
    n_caps = sum(1 for layer in comp.layers if layer.kind == "caption")
    console.print(
        f"  [green]✓[/green] direct: {n_caps} captions, "
        f"music={comp.audio[0].src.name}"
    )

    result = render_composition(comp, out, keep_intermediates=False)
    elapsed = _time.perf_counter() - t0
    console.print(
        f"  [green]✓[/green] render: {result.duration_s:.1f}s, "
        f"LUFS={result.audio_lufs}, peak={result.audio_peak_dbfs}"
    )

    # Telemetry
    from dvg.review.telemetry import append_row, build_row

    row = build_row(
        run_id=run_dir.name,
        input=url,
        composition=comp,
        output_path=out,
        render_time_s=result.duration_s,
        output_lufs=result.audio_lufs,
        output_peak_dbfs=result.audio_peak_dbfs,
    )
    append_row(row)

    console.print()
    console.print(
        f"[bold green]Done[/bold green] in {elapsed:.1f}s → {out} "
        f"({out.stat().st_size / 1024:.0f}KB)"
    )


@app.command()
def new(
    out: Annotated[
        Path, typer.Argument(help="Path to write a starter composition.json or .py")
    ],
    duration: Annotated[float, typer.Option("--duration", "-d")] = 12.0,
    style: Annotated[
        str, typer.Option("--style", help="json | py")
    ] = "json",
) -> None:
    """Scaffold a starter composition file."""
    if style == "json":
        from dvg.models import (
            AudioLayer,
            CaptionLayer,
            Composition,
            Mood,
            TitleLayer,
            VideoLayer,
        )

        # We can't reference real files; emit a template the user can edit.
        template = Composition(
            fps=30,
            width=1920,
            height=1080,
            duration=duration,
            background="#0a0a0a",
            layers=[
                TitleLayer(
                    title="My demo",
                    subtitle="built with dvg",
                    time=(0.0, 2.5),
                    fade_in=0.4,
                    fade_out=0.4,
                ),
                VideoLayer(
                    src=Path("footage.mp4"),  # replace
                    time=(2.3, duration - 1.5),
                    fit="cover",
                    fade_in=0.4,
                    fade_out=0.4,
                ),
                CaptionLayer(
                    text="Your first caption",
                    mood=Mood.ANNOUNCE,
                    time=(3.0, 5.5),
                ),
                CaptionLayer(
                    text="Your punchline",
                    mood=Mood.PUNCHLINE,
                    time=(6.0, 8.5),
                ),
                TitleLayer(
                    title="install dvg",
                    subtitle="pip install dvg",
                    time=(duration - 1.6, duration),
                    title_size=80,
                    subtitle_size=44,
                    fade_in=0.3,
                    fade_out=0.3,
                ),
            ],
            audio=[
                AudioLayer(
                    src=Path("music.mp3"),  # replace
                    time=(0.0, duration),
                    target_lufs=-22.0,
                    duck_under_captions=True,
                    fade_in=0.4,
                    fade_out=0.8,
                ),
            ],
            title="My demo",
        )
        out.write_text(template.model_dump_json(indent=2))
    elif style == "py":
        out.write_text(_PY_TEMPLATE.format(duration=duration))
    else:
        console.print(f"[red]✗[/red] unknown style: {style}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] {out}")
    console.print(
        "[dim]edit `src` paths to your footage / music, then "
        "[bold]dvg render " + str(out) + "[/bold][/dim]"
    )


_PY_TEMPLATE = """\"\"\"Starter dvg composition. Run via: uv run python this_file.py\"\"\"

from pathlib import Path

from dvg import (
    AudioLayer, CaptionLayer, Composition, Mood, TitleLayer, VideoLayer,
)

DURATION = {duration}

comp = Composition(
    fps=30, width=1920, height=1080, duration=DURATION, background="#0a0a0a",
    layers=[
        TitleLayer(
            title="My demo", subtitle="built with dvg",
            time=(0.0, 2.5), fade_in=0.4, fade_out=0.4,
        ),
        VideoLayer(
            src=Path("footage.mp4"),  # ← replace with your captured footage
            time=(2.3, DURATION - 1.5), fit="cover",
            fade_in=0.4, fade_out=0.4,
        ),
        CaptionLayer(text="Your first caption", mood=Mood.ANNOUNCE, time=(3.0, 5.5)),
        CaptionLayer(text="Your punchline", mood=Mood.PUNCHLINE, time=(6.0, 8.5)),
        TitleLayer(
            title="install dvg", subtitle="pip install dvg",
            time=(DURATION - 1.6, DURATION),
            title_size=80, subtitle_size=44,
            fade_in=0.3, fade_out=0.3,
        ),
    ],
    audio=[
        AudioLayer(
            src=Path("music.mp3"),  # ← replace with your soundtrack
            time=(0.0, DURATION),
            target_lufs=-22.0, duck_under_captions=True,
            fade_in=0.4, fade_out=0.8,
        ),
    ],
)

if __name__ == "__main__":
    result = comp.render("final.mp4")
    print(f"→ {{result.out}}  LUFS={{result.audio_lufs}}  peak={{result.audio_peak_dbfs}}")
"""


@app.command()
def preview(
    composition_path: Annotated[Path, typer.Argument(help="composition.json")],
    port: Annotated[int, typer.Option("--port", "-p")] = 8765,
) -> None:
    """Open a local preview server with a scrubbable timeline."""
    from dvg.preview.server import serve

    serve(composition_path, port=port)


@app.command(name="review")
def review_cmd(
    path: Annotated[Path, typer.Argument(help="Path to MP4")],
    target_lufs: Annotated[float, typer.Option("--target-lufs")] = -14.0,
    json_out: Annotated[
        Path | None, typer.Option("--json-out", help="Write QA report JSON")
    ] = None,
) -> None:
    """Run audio + visual QA on an MP4."""
    from dvg.review import review

    report = review(path, target_lufs=target_lufs)
    if json_out:
        json_out.write_text(report.model_dump_json(indent=2))

    table = Table(title=f"QA — {path.name}")
    table.add_column("metric", style="cyan")
    table.add_column("value", style="white")
    table.add_row("duration", f"{report.duration_s:.2f}s" if report.duration_s else "?")
    table.add_row("dimensions", f"{report.width}×{report.height}")
    table.add_row("fps", f"{report.fps:.2f}" if report.fps else "?")
    table.add_row("video codec", report.video_codec or "?")
    table.add_row("audio codec", report.audio_codec or "?")
    table.add_row(
        "integrated LUFS",
        f"{report.integrated_lufs:.1f}" if report.integrated_lufs is not None else "?",
    )
    table.add_row(
        "true peak",
        f"{report.true_peak_dbfs:.1f} dBFS" if report.true_peak_dbfs is not None else "?",
    )
    table.add_row("LRA", f"{report.lra:.1f}" if report.lra else "?")
    table.add_row("BPM", f"{report.bpm:.0f}" if report.bpm else "?")
    table.add_row("dead air", f"{report.dead_air_total_s:.1f}s in {report.dead_air_count} segs")
    console.print(table)
    console.print()

    if report.findings:
        finding_table = Table(title="Findings")
        finding_table.add_column("sev", style="bold")
        finding_table.add_column("code", style="cyan")
        finding_table.add_column("message")
        finding_table.add_column("action", style="dim")
        for f in report.findings:
            color = {"high": "red", "medium": "yellow", "low": "blue"}[f.severity.value]
            finding_table.add_row(
                f"[{color}]{f.severity.value}[/{color}]",
                f.code,
                f.message,
                f.proposed_action or "",
            )
        console.print(finding_table)
    else:
        console.print("[green]✓[/green] no findings")

    console.print()
    if report.pass_:
        console.print("[bold green]PASS[/bold green]")
    else:
        console.print(f"[bold red]FAIL[/bold red] ({report.severity_high_count} high-severity)")
        raise typer.Exit(1)


@app.command()
def frame(
    composition_path: Annotated[Path, typer.Argument(help="composition.json path")],
    t: Annotated[float, typer.Option("--t", help="time in seconds")] = 1.0,
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("frame.png"),
) -> None:
    """Render a single frame from a composition (for visual debugging)."""
    import tempfile

    comp = Composition.load(composition_path)
    # Render only the first 0.5 s window around t to keep ffmpeg fast.
    # Strategy: render the full composition to a temp MP4 and extract frame.
    with tempfile.TemporaryDirectory() as td:
        tmp_mp4 = Path(td) / "tmp.mp4"
        result = render_composition(comp, tmp_mp4, preset="ultrafast", crf=28)
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(result.out),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            console.print(f"[red]✗[/red] frame extract failed: {proc.stderr}")
            raise typer.Exit(1)
    console.print(f"[green]✓[/green] frame at t={t}s → {out}")


@app.command()
def contact_sheet(
    composition_path: Annotated[Path, typer.Argument()],
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("contact_sheet.png"),
    cols: Annotated[int, typer.Option("--cols")] = 4,
    rows: Annotated[int, typer.Option("--rows")] = 3,
) -> None:
    """Generate an N×M grid of frames sampled across the composition."""
    import tempfile

    comp = Composition.load(composition_path)
    n = cols * rows
    with tempfile.TemporaryDirectory() as td:
        tmp_mp4 = Path(td) / "tmp.mp4"
        render_composition(comp, tmp_mp4, preset="ultrafast", crf=28)
        # Sample n frames evenly. ffmpeg select filter + tile.
        # interval = n+1 evenly spaces between 0 and duration
        tile_w = comp.width // cols
        tile_h = comp.height // rows
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(tmp_mp4),
            "-vf",
            (
                f"select='not(mod(n\\,{int(comp.duration * comp.fps / n)}))',"
                f"scale={tile_w}:{tile_h},"
                f"tile={cols}x{rows}:padding=4:color=#1a1a1a"
            ),
            "-frames:v",
            "1",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            console.print(f"[red]✗[/red] contact sheet failed: {proc.stderr[-1000:]}")
            raise typer.Exit(1)
    console.print(f"[green]✓[/green] {cols}×{rows} contact sheet → {out}")


@app.command()
def telemetry(
    path: Annotated[
        Path, typer.Option("--path", help="Telemetry file")
    ] = Path("runs/_telemetry.jsonl"),
) -> None:
    """Show summary of dvg make-video runs."""
    from dvg.review.telemetry import summary

    s = summary(path)
    table = Table(title="Telemetry summary")
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")
    for k, v in s.items():
        if "ts" in k and isinstance(v, (int, float)):
            from datetime import datetime
            table.add_row(k, datetime.fromtimestamp(v).isoformat(timespec="seconds"))
        elif isinstance(v, float):
            table.add_row(k, f"{v:.2f}")
        else:
            table.add_row(k, str(v))
    console.print(table)


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
