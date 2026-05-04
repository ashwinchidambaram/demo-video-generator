"""Compositor — Composition → ffmpeg invocation → final.mp4.

Strategy:
  1. Pre-render audio stem (composition.audio.build_audio_stem)
  2. Compile caption + title layers to a single .ass file
  3. Build a complex filter graph for video layers + ass subtitles
  4. Single ffmpeg invocation muxes video + audio → out

Backends per layer kind:
  - VideoLayer  : ffmpeg input + filters (scale, crop, fade)
  - ImageLayer  : ffmpeg input as still + overlay
  - CaptionLayer: ass file (libass via subtitles filter)
  - TitleLayer  : ass file
  - ShapeLayer  : ffmpeg drawbox/drawtext (h2: skia backend)
  - HTMLLayer   : Playwright pre-render to PNG sequence (h2)
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from dvg.composition.audio import build_audio_stem, measure_loudness
from dvg.composition.captions.ass import compile_ass
from dvg.models import (
    Anchor,
    CaptionLayer,
    Composition,
    Fit,
    ImageLayer,
    TitleLayer,
    VideoLayer,
)


@dataclass
class RenderResult:
    out: Path
    cmd: list[str]
    duration_s: float
    audio_lufs: float | None
    audio_peak_dbfs: float | None
    intermediates: list[Path] = field(default_factory=list)
    stderr_tail: str = ""


def render(
    comp: Composition,
    out: str | Path,
    *,
    work_dir: Path | None = None,
    encoder: str = "libx264",
    preset: str = "medium",
    crf: int = 18,
    keep_intermediates: bool = False,
) -> RenderResult:
    """Render composition to MP4. Returns a RenderResult with measurements."""
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = work_dir or out_path.parent / f".{out_path.stem}_work"
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    # 1) Audio stem
    audio = build_audio_stem(comp, work)

    # 2) Captions + titles → ASS
    ass_path = work / "captions.ass"
    ass_text = compile_ass(comp)
    ass_path.write_text(ass_text)
    intermediates = [audio.out, ass_path]

    # 3) Assemble video filter graph
    video_layers = [layer for layer in comp.layers if isinstance(layer, VideoLayer)]
    image_layers = [layer for layer in comp.layers if isinstance(layer, ImageLayer)]

    inputs: list[str] = []
    filter_parts: list[str] = []

    # Background canvas — color source matching comp.background, full duration.
    filter_parts.append(
        f"color=c={_strip_hash(comp.background)}:s={comp.width}x{comp.height}:"
        f"r={comp.fps}:d={comp.duration:.3f}[bg]"
    )

    current_label = "[bg]"

    # Video layers
    for idx, vl in enumerate(video_layers):
        inputs += ["-i", str(vl.src)]
        prepared, out_label = _prepare_video_layer(vl, comp, idx)
        filter_parts.append(prepared)  # own chain ending in out_label
        next_label = f"[v_after_{idx}]"
        enable = f"enable='between(t,{vl.time[0]:.3f},{vl.time[1]:.3f})'"
        filter_parts.append(
            f"{current_label}{out_label}overlay=x=0:y=0:{enable}{next_label}"
        )
        current_label = next_label

    # Image layers
    img_input_offset = len(video_layers)
    for idx, il in enumerate(image_layers):
        inputs += ["-loop", "1", "-i", str(il.src)]
        ffmpeg_in = img_input_offset + idx
        prepared, out_label = _prepare_image_layer(il, comp, ffmpeg_in)
        filter_parts.append(prepared)
        next_label = f"[v_img_{idx}]"
        x_expr, y_expr = _anchor_to_xy(il.anchor, comp.width, comp.height, il.offset)
        enable = f"enable='between(t,{il.time[0]:.3f},{il.time[1]:.3f})'"
        filter_parts.append(
            f"{current_label}{out_label}overlay=x={x_expr}:y={y_expr}:{enable}{next_label}"
        )
        current_label = next_label

    # Subtitles last so they sit on top.
    has_captions = any(
        isinstance(layer, (CaptionLayer, TitleLayer)) for layer in comp.layers
    )
    if has_captions:
        # subtitles filter expects the file path. Escape ":" and "'" for ffmpeg.
        ass_arg = _escape_ffmpeg_path(ass_path)
        filter_parts.append(f"{current_label}subtitles=filename={ass_arg}[final]")
        current_label = "[final]"

    filter_complex = ";".join(filter_parts)

    # Audio input
    inputs += ["-i", str(audio.out)]
    audio_input_idx = len(video_layers) + len(image_layers)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "info",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        current_label,
        "-map",
        f"{audio_input_idx}:a",
        "-c:v",
        encoder,
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-t",
        f"{comp.duration:.3f}",
        "-r",
        str(comp.fps),
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        # Save filter graph for debugging.
        (work / "filter_complex.txt").write_text(filter_complex)
        raise RuntimeError(
            f"render failed (rc={proc.returncode}). "
            f"filter_complex saved to {work / 'filter_complex.txt'}\n"
            f"--- stderr tail ---\n{proc.stderr[-3000:]}"
        )

    elapsed = time.perf_counter() - t0
    measurements = measure_loudness(out_path)

    if not keep_intermediates:
        for p in intermediates:
            try:
                p.unlink()
            except OSError:
                pass
        try:
            work.rmdir()
        except OSError:
            pass

    return RenderResult(
        out=out_path,
        cmd=cmd,
        duration_s=elapsed,
        audio_lufs=measurements.get("integrated_lufs"),
        audio_peak_dbfs=measurements.get("true_peak_dbfs"),
        intermediates=intermediates,
        stderr_tail=proc.stderr[-1500:],
    )


# ---- per-layer compilers -------------------------------------------------


def _prepare_video_layer(
    vl: VideoLayer, comp: Composition, idx: int
) -> tuple[str, str]:
    """Return (chain, out_label) for this video layer's own filter chain.

    Crops/scales to fit the canvas, applies fades, retimes via setpts.
    """
    chain = f"[{idx}:v]"
    # speed
    if vl.speed != 1.0:
        chain += f"setpts={1/vl.speed:.6f}*PTS,"
    # crop in 0..1 source-relative coords
    if vl.crop is not None:
        x, y, w, h = vl.crop
        chain += (
            f"crop=iw*{w:.6f}:ih*{h:.6f}:iw*{x:.6f}:ih*{y:.6f},"
        )
    # scale to canvas based on fit
    if vl.fit == Fit.COVER:
        chain += (
            f"scale={comp.width}:{comp.height}:force_original_aspect_ratio=increase,"
            f"crop={comp.width}:{comp.height},"
        )
    elif vl.fit == Fit.CONTAIN:
        chain += (
            f"scale={comp.width}:{comp.height}:force_original_aspect_ratio=decrease,"
            f"pad={comp.width}:{comp.height}:(ow-iw)/2:(oh-ih)/2:color={_strip_hash(comp.background)},"
        )
    elif vl.fit == Fit.FILL:
        chain += f"scale={comp.width}:{comp.height},"
    # fade
    if vl.fade_in > 0:
        chain += f"fade=t=in:st={vl.time[0]:.3f}:d={vl.fade_in:.3f},"
    if vl.fade_out > 0:
        chain += f"fade=t=out:st={vl.time[1] - vl.fade_out:.3f}:d={vl.fade_out:.3f},"
    # opacity via colorchannelmixer doesn't exist for alpha — use format+colorchannelmixer
    if vl.opacity < 1.0:
        chain += f"format=yuva420p,colorchannelmixer=aa={vl.opacity:.3f},"
    # tag with timing offset on the layer's own timeline
    # adelay for video doesn't exist; we use overlay's enable= for time gating.
    chain += f"setpts=PTS+{vl.time[0]:.6f}/TB[v{idx}]"
    return chain, f"[v{idx}]"


def _prepare_image_layer(
    il: ImageLayer, comp: Composition, idx: int
) -> tuple[str, str]:
    chain = f"[{idx}:v]"
    if il.scale != 1.0:
        chain += f"scale=iw*{il.scale:.4f}:ih*{il.scale:.4f},"
    if il.opacity < 1.0:
        chain += f"format=yuva420p,colorchannelmixer=aa={il.opacity:.3f},"
    if il.fade_in > 0 or il.fade_out > 0:
        if il.fade_in > 0:
            chain += f"fade=t=in:st={il.time[0]:.3f}:d={il.fade_in:.3f}:alpha=1,"
        if il.fade_out > 0:
            chain += (
                f"fade=t=out:st={il.time[1] - il.fade_out:.3f}:d={il.fade_out:.3f}:alpha=1,"
            )
    chain += f"setpts=PTS-STARTPTS[i{idx}]"
    return chain, f"[i{idx}]"


def _anchor_to_xy(
    anchor: Anchor, w: int, h: int, offset: tuple[int, int]
) -> tuple[str, str]:
    """Map anchor + offset to overlay x/y expressions referencing W,H,w,h."""
    ox, oy = offset
    horiz = anchor.value.split("-")[1]
    vert = anchor.value.split("-")[0]

    if horiz == "left":
        x = f"{ox}"
    elif horiz == "right":
        x = f"W-w-{-ox}"
    else:
        x = f"(W-w)/2+{ox}"

    if vert == "top":
        y = f"{oy}"
    elif vert == "bottom":
        y = f"H-h-{-oy}"
    else:
        y = f"(H-h)/2+{oy}"

    return x, y


def _strip_hash(color: str) -> str:
    """ffmpeg color expressions accept 0xRRGGBB or color names; strip leading #."""
    if color.startswith("#"):
        return f"0x{color[1:]}"
    return color


def _escape_ffmpeg_path(p: Path) -> str:
    """Escape a path for use in a filter argument."""
    s = str(p.resolve())
    # backslash, colon, single quote
    return s.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


# ---- introspection -------------------------------------------------------


def plan(comp: Composition) -> dict[str, object]:
    """Return a dict describing what would be rendered. Pure (no side effects)."""
    return {
        "canvas": f"{comp.width}x{comp.height}@{comp.fps}fps",
        "duration_s": comp.duration,
        "video_layers": len([l for l in comp.layers if isinstance(l, VideoLayer)]),
        "image_layers": len([l for l in comp.layers if isinstance(l, ImageLayer)]),
        "caption_layers": len([l for l in comp.layers if isinstance(l, CaptionLayer)]),
        "title_layers": len([l for l in comp.layers if isinstance(l, TitleLayer)]),
        "audio_layers": len(comp.audio),
        "ducking": any(a.duck_under_captions for a in comp.audio),
        "final_loudness_target": comp.final_loudness,
        "peak_dbfs_target": comp.peak_dbfs,
    }
