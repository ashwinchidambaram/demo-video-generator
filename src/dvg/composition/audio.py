"""Audio mixer. Builds an ffmpeg pre-mix stem from AudioLayer list.

Pipeline per audio layer:
  input → atrim → asetpts → afade(in/out) → loudnorm(target) → volume → [duck]
Then amix all layers, apply final loudnorm to comp.final_loudness, and an
alimiter at peak_dbfs. Output is a single stereo .m4a or .mp3.

Ducking: if any layer has duck_under_captions=True, we generate a sidechain
control envelope from the union of caption time ranges (silent track gated
to caption windows) and run sidechaincompress. This is deterministic and
ebur128-verifiable before final mux — per main's D12.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from dvg.models import CaptionLayer, Composition


@dataclass
class AudioBuildResult:
    out: Path
    cmd: list[str]
    stderr: str
    duration_s: float


def build_audio_stem(comp: Composition, out_dir: Path) -> AudioBuildResult:
    """Build the pre-mixed audio stem for `comp`. Writes to out_dir/audio.m4a.

    If comp has no audio layers, writes a silent stem of comp.duration.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stem_path = out_dir / "audio.m4a"

    if not comp.audio:
        cmd = _silent_stem_cmd(comp.duration, stem_path)
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return AudioBuildResult(
            out=stem_path, cmd=cmd, stderr=proc.stderr, duration_s=comp.duration
        )

    duck_windows = _caption_duck_windows(comp) if _any_ducking(comp) else []

    inputs: list[str] = []
    filter_parts: list[str] = []
    mix_inputs: list[str] = []

    for idx, layer in enumerate(comp.audio):
        inputs += ["-i", str(layer.src)]
        end = layer.time[1] if layer.time[1] != -1 else comp.duration
        start = layer.time[0]
        layer_dur = end - start

        # 1) trim source to (0, layer_dur), then offset on the timeline via adelay
        # 2) loudnorm to target
        # 3) volume
        # 4) afade in/out
        chain = (
            f"[{idx}:a]"
            f"atrim=0:{layer_dur:.3f},"
            f"asetpts=PTS-STARTPTS,"
            f"loudnorm=I={layer.target_lufs}:TP=-1.5:LRA=11,"
            f"volume={layer.volume}"
        )
        if layer.fade_in > 0:
            chain += f",afade=t=in:st=0:d={layer.fade_in}"
        if layer.fade_out > 0:
            chain += f",afade=t=out:st={layer_dur - layer.fade_out}:d={layer.fade_out}"

        # delay onto comp timeline
        delay_ms = int(start * 1000)
        if delay_ms > 0:
            chain += f",adelay={delay_ms}|{delay_ms}"

        # pad to comp.duration so amix has equal-length inputs
        chain += f",apad=whole_dur={comp.duration:.3f}"
        chain += f"[a{idx}_pre]"
        filter_parts.append(chain)

        if layer.duck_under_captions and duck_windows:
            # build a sidechain envelope: silence except in caption windows
            sc_label = f"[sc{idx}]"
            envelope = _build_envelope_filter(duck_windows, comp.duration, sc_label)
            filter_parts.append(envelope)
            duck_chain = (
                f"[a{idx}_pre]{sc_label}sidechaincompress="
                f"threshold=0.05:ratio=8:attack=20:release=400:"
                f"makeup=1:level_sc=1[a{idx}]"
            )
            filter_parts.append(duck_chain)
        else:
            filter_parts.append(f"[a{idx}_pre]anull[a{idx}]")

        mix_inputs.append(f"[a{idx}]")

    if len(mix_inputs) == 1:
        merged = mix_inputs[0]
        filter_parts.append(f"{merged}aformat=channel_layouts=stereo[mixed]")
    else:
        filter_parts.append(
            f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:dropout_transition=0:"
            f"normalize=0,aformat=channel_layouts=stereo[mixed]"
        )

    # Final loudnorm to comp target + alimiter for peak ceiling.
    # Two-pass loudnorm is more accurate; for now single-pass with the integrated target.
    filter_parts.append(
        f"[mixed]loudnorm=I={comp.final_loudness}:TP={comp.peak_dbfs}:LRA=11,"
        f"alimiter=limit={_db_to_lin(comp.peak_dbfs):.4f}:level=disabled[out]"
    )

    filter_complex = ";".join(filter_parts)
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
        "[out]",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-t",
        f"{comp.duration:.3f}",
        str(stem_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"audio mix failed: {proc.stderr[-2000:]}")
    return AudioBuildResult(
        out=stem_path, cmd=cmd, stderr=proc.stderr, duration_s=comp.duration
    )


# ---- helpers -------------------------------------------------------------


def _silent_stem_cmd(duration: float, out: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r=48000:cl=stereo",
        "-t",
        f"{duration:.3f}",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(out),
    ]


def _any_ducking(comp: Composition) -> bool:
    return any(a.duck_under_captions for a in comp.audio)


def _caption_duck_windows(comp: Composition) -> list[tuple[float, float]]:
    """Union of caption time ranges (with small lead-in/out for smoother duck)."""
    windows: list[tuple[float, float]] = []
    for layer in comp.layers:
        if isinstance(layer, CaptionLayer):
            lead = 0.15
            tail = 0.25
            start = max(0, layer.time[0] - lead)
            end = min(comp.duration, layer.time[1] + tail)
            windows.append((start, end))
    # merge overlapping windows
    if not windows:
        return []
    windows.sort()
    merged = [windows[0]]
    for w in windows[1:]:
        if w[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], w[1]))
        else:
            merged.append(w)
    return merged


def _build_envelope_filter(
    windows: list[tuple[float, float]], total_duration: float, out_label: str
) -> str:
    """Build a sidechain envelope filter: silent stereo except inside windows."""
    # Use lavfi sine source @ low gain, gated by volume expression.
    # Volume expression for sidechain: 1 inside any window, 0 outside.
    expr_parts = []
    for s, e in windows:
        expr_parts.append(f"between(t,{s:.3f},{e:.3f})")
    expr = "+".join(expr_parts) if expr_parts else "0"
    return (
        f"sine=frequency=200:beep_factor=0:duration={total_duration:.3f}:sample_rate=48000,"
        f"aformat=channel_layouts=stereo,volume='{expr}':eval=frame{out_label}"
    )


def _db_to_lin(db: float) -> float:
    return 10 ** (db / 20.0)


# ---- introspection -------------------------------------------------------


def measure_loudness(path: Path) -> dict[str, float]:
    """Run ffmpeg ebur128 and parse integrated LUFS + true peak."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(path),
        "-filter_complex",
        "ebur128=peak=true:framelog=quiet",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = proc.stderr
    return _parse_ebur128(out)


def _parse_ebur128(stderr: str) -> dict[str, float]:
    result: dict[str, float] = {}
    # Look for "I:   -14.0 LUFS" + "Peak:   -1.5 dBFS"
    for line in stderr.splitlines():
        line = line.strip()
        if line.startswith("I:") and "LUFS" in line:
            try:
                value = float(line.split()[1])
                result["integrated_lufs"] = value
            except (ValueError, IndexError):
                pass
        elif "Peak:" in line and "dBFS" in line:
            try:
                # "Peak:   -1.5 dBFS"
                parts = line.split()
                value = float(parts[parts.index("Peak:") + 1])
                result["true_peak_dbfs"] = value
            except (ValueError, IndexError):
                pass
        elif line.startswith("LRA:"):
            try:
                value = float(line.split()[1])
                result["lra"] = value
            except (ValueError, IndexError):
                pass
    return result
