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
from dvg.composition.html_layer import render_static_html_sync
from dvg.keyframes import compile_to_ffmpeg_expr
from dvg.models import (
    Anchor,
    CaptionLayer,
    Composition,
    Fit,
    HTMLLayer,
    ImageLayer,
    ShapeLayer,
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
    # Flatten Sequence layers before rendering.
    comp = comp.flatten()
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

    # 2.5) Pre-render HTML layers to PNGs (treated as ImageLayers downstream)
    html_image_layers: list[ImageLayer] = []
    for idx, layer in enumerate(comp.layers):
        if isinstance(layer, HTMLLayer):
            png_path = work / f"html_layer_{idx}.png"
            bbox = layer.bbox or (0, 0, comp.width, comp.height)
            render_static_html_sync(
                layer,
                png_path,
                width=bbox[2],
                height=bbox[3],
                transparent=layer.transparent,
            )
            intermediates.append(png_path)
            # Synthesize an ImageLayer
            from dvg.models import Anchor as _Anchor

            html_image_layers.append(
                ImageLayer(
                    src=png_path,
                    time=layer.time,
                    z=layer.z,
                    opacity=layer.opacity,
                    fade_in=layer.fade_in,
                    fade_out=layer.fade_out,
                    transform=layer.transform,
                    anchor=_Anchor.TOP_LEFT,
                    offset=(bbox[0], bbox[1]),
                    scale=1.0,
                )
            )

    # 3) Assemble video filter graph
    video_layers = [layer for layer in comp.layers if isinstance(layer, VideoLayer)]
    image_layers = [
        layer for layer in comp.layers if isinstance(layer, ImageLayer)
    ] + html_image_layers

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

    # Image layers — explicit framerate + duration to keep ffmpeg's filter graph
    # in sync with the video stream. Plain `-loop 1` defaults to 25fps which
    # desyncs the overlay graph and causes earlier video overlays to drop.
    img_input_offset = len(video_layers)
    for idx, il in enumerate(image_layers):
        inputs += [
            "-framerate",
            str(comp.fps),
            "-loop",
            "1",
            "-t",
            f"{comp.duration:.3f}",
            "-i",
            str(il.src),
        ]
        ffmpeg_in = img_input_offset + idx
        prepared, out_label = _prepare_image_layer(il, comp, ffmpeg_in)
        filter_parts.append(prepared)
        next_label = f"[v_img_{idx}]"
        x_expr, y_expr = _resolve_position(il, comp)
        enable = f"enable='between(t,{il.time[0]:.3f},{il.time[1]:.3f})'"
        filter_parts.append(
            f"{current_label}{out_label}overlay=x='{x_expr}':y='{y_expr}':{enable}{next_label}"
        )
        current_label = next_label

    # Caption backdrop strips (drawbox behind any CaptionLayer with backdrop=True).
    caption_layers = [layer for layer in comp.layers if isinstance(layer, CaptionLayer)]
    backdrop_idx = 0
    for cl in caption_layers:
        if not cl.backdrop:
            continue
        # bottom strip by default; could derive from anchor in future
        strip_h = cl.backdrop_height_px
        anchor = cl.anchor
        if anchor.value.startswith("bottom"):
            y = comp.height - strip_h
        elif anchor.value.startswith("top"):
            y = 0
        else:
            y = (comp.height - strip_h) // 2
        bg = _strip_hash(cl.backdrop_color)
        next_label = f"[v_capbd_{backdrop_idx}]"
        enable = f"enable='between(t,{cl.time[0]:.3f},{cl.time[1]:.3f})'"
        filter_parts.append(
            f"{current_label}drawbox=x=0:y={y}:w={comp.width}:h={strip_h}:"
            f"color={bg}@{cl.backdrop_opacity:.2f}:t=fill:{enable}{next_label}"
        )
        current_label = next_label
        backdrop_idx += 1

    # Shape layers — drawbox for rect (filled or stroked).
    shape_layers = [layer for layer in comp.layers if isinstance(layer, ShapeLayer)]
    for sl in shape_layers:
        if sl.shape != "rect":
            # Other shapes (circle, line, rounded_rect) require Pillow pre-render.
            # Defer to a future iteration.
            continue
        x, y, w, h = sl.bbox
        fill = sl.fill or "white"
        fill_arg = _strip_hash(fill)
        thickness = "fill" if sl.stroke_width <= 0 else f"{sl.stroke_width}"
        enable = f"enable='between(t,{sl.time[0]:.3f},{sl.time[1]:.3f})'"
        next_label = f"[v_shape_{shape_layers.index(sl)}]"
        filter_parts.append(
            f"{current_label}drawbox=x={x}:y={y}:w={w}:h={h}:"
            f"color={fill_arg}@{sl.opacity:.2f}:t={thickness}:{enable}{next_label}"
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
    # always save filter graph for debugging
    (work / "filter_complex.txt").write_text(filter_complex)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
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

    Order: scale/crop → setpts shift to comp time → fades (now in comp time) →
    optional opacity. Putting setpts BEFORE fades ensures fade `st` is on the
    same clock as the comp's timeline.
    """
    chain = f"[{idx}:v]"
    if vl.speed != 1.0:
        chain += f"setpts={1/vl.speed:.6f}*PTS,"
    if vl.crop is not None:
        x, y, w, h = vl.crop
        chain += f"crop=iw*{w:.6f}:ih*{h:.6f}:iw*{x:.6f}:ih*{y:.6f},"
    if vl.fit == Fit.COVER:
        chain += (
            f"scale={comp.width}:{comp.height}:force_original_aspect_ratio=increase,"
            f"crop={comp.width}:{comp.height},"
        )
        # Ken Burns: simple time-driven zoom (centered) — pre-upscale to a buffer
        # then crop a fixed window. Note: ffmpeg crop's w/h must be even at all
        # frame times. We approximate by sweeping `x,y` only (constant w,h).
        if vl.ken_burns > 0:
            kb = vl.ken_burns
            dur = vl.duration
            t0 = vl.time[0]
            buf_w = int(comp.width * (1 + kb))
            buf_h = int(comp.height * (1 + kb))
            chain += (
                f"scale={buf_w}:{buf_h}:flags=lanczos,"
                f"crop={comp.width}:{comp.height}:"
                f"x='({buf_w - comp.width})/2 + ({buf_w - comp.width})/2 *"
                f"sin((t-{t0:.3f})/{dur:.3f}*PI/2)':"
                f"y='({buf_h - comp.height})/2',"
            )
    elif vl.fit == Fit.CONTAIN:
        chain += (
            f"scale={comp.width}:{comp.height}:force_original_aspect_ratio=decrease,"
            f"pad={comp.width}:{comp.height}:(ow-iw)/2:(oh-ih)/2:"
            f"color={_strip_hash(comp.background)},"
        )
    elif vl.fit == Fit.FILL:
        chain += f"scale={comp.width}:{comp.height},"

    # Shift to comp time FIRST so fade timestamps are in comp time.
    # tpad prepends frozen frames (or transparent if alpha) to fill the gap.
    if vl.time[0] > 0:
        chain += f"setpts=PTS+{vl.time[0]:.6f}/TB,"

    # Fades now in comp/output time
    if vl.fade_in > 0:
        chain += f"fade=t=in:st={vl.time[0]:.3f}:d={vl.fade_in:.3f},"
    if vl.fade_out > 0:
        chain += f"fade=t=out:st={vl.time[1] - vl.fade_out:.3f}:d={vl.fade_out:.3f},"
    if vl.opacity < 1.0:
        chain += f"format=yuva420p,colorchannelmixer=aa={vl.opacity:.3f},"
    chain = chain.rstrip(",")
    chain += f"[v{idx}]"
    return chain, f"[v{idx}]"


def _prepare_image_layer(
    il: ImageLayer, comp: Composition, idx: int
) -> tuple[str, str]:
    """Prepare an image input for overlay. Uses format=rgba to keep alpha.

    Fades use the layer-relative time AFTER setpts has been applied.
    """
    chain = f"[{idx}:v]"
    chain += "format=rgba,"
    if il.scale != 1.0:
        chain += f"scale=iw*{il.scale:.4f}:ih*{il.scale:.4f},"
    if il.opacity < 1.0:
        chain += f"colorchannelmixer=aa={il.opacity:.3f},"
    # Trim to the layer's lifetime so the image is a finite stream — looped images
    # at unmatched fps confuse downstream overlay timing. Then re-base PTS to 0
    # and add a delay equal to the layer's start (so the overlay sees the stream
    # appearing at the right comp time).
    chain += f"trim=duration={il.duration:.3f},setpts=PTS-STARTPTS,"
    if il.fade_in > 0:
        chain += f"fade=t=in:st=0:d={il.fade_in:.3f}:alpha=1,"
    if il.fade_out > 0:
        chain += (
            f"fade=t=out:st={il.duration - il.fade_out:.3f}:d={il.fade_out:.3f}:alpha=1,"
        )
    if il.time[0] > 0:
        chain += f"setpts=PTS+{il.time[0]:.6f}/TB,"
    chain = chain.rstrip(",")
    chain += f"[i{idx}]"
    return chain, f"[i{idx}]"


def _resolve_position(layer: ImageLayer, comp: Composition) -> tuple[str, str]:
    """Return (x_expr, y_expr) for the overlay step.

    Priority: transform.position keyframes > anchor + offset.
    Keyframes are layer-relative time; ffmpeg expressions use comp time, so
    we shift by layer.time[0].
    """
    if layer.transform and layer.transform.position is not None:
        pos = layer.transform.position
        if isinstance(pos, list):
            x_expr = compile_to_ffmpeg_expr(pos, component=0, layer_start=layer.time[0])
            y_expr = compile_to_ffmpeg_expr(pos, component=1, layer_start=layer.time[0])
            return x_expr, y_expr
        # constant tuple
        return f"{pos[0]:.3f}", f"{pos[1]:.3f}"
    return _anchor_to_xy(layer.anchor, comp.width, comp.height, layer.offset)


def _anchor_to_xy(
    anchor: Anchor, w: int, h: int, offset: tuple[int, int]
) -> tuple[str, str]:
    """Map anchor + offset to overlay x/y expressions.

    Offset semantics: positive ox moves the layer INWARD from the anchor edge
    (so for top-right, +ox is leftward; for bottom-left, +oy is upward).
    """
    ox, oy = offset
    horiz = anchor.value.split("-")[1]
    vert = anchor.value.split("-")[0]

    if horiz == "left":
        x = f"{ox}"
    elif horiz == "right":
        x = f"W-w-{ox}"
    else:
        x = f"(W-w)/2+{ox}"

    if vert == "top":
        y = f"{oy}"
    elif vert == "bottom":
        y = f"H-h-{oy}"
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
        "video_layers": len([layer for layer in comp.layers if isinstance(layer, VideoLayer)]),
        "image_layers": len([layer for layer in comp.layers if isinstance(layer, ImageLayer)]),
        "caption_layers": len([layer for layer in comp.layers if isinstance(layer, CaptionLayer)]),
        "title_layers": len([layer for layer in comp.layers if isinstance(layer, TitleLayer)]),
        "audio_layers": len(comp.audio),
        "ducking": any(a.duck_under_captions for a in comp.audio),
        "final_loudness_target": comp.final_loudness,
        "peak_dbfs_target": comp.peak_dbfs,
    }
