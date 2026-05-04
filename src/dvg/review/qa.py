"""Audio + visual QA for rendered MP4.

Audit signals:
- ffprobe: duration, dimensions, codec, bitrate, fps
- ebur128: integrated LUFS, true peak, LRA
- aubio: BPM (best-effort)
- ffmpeg astats: dead-air detection (RMS below threshold for >2s)

Findings are categorized by severity (high / medium / low) with proposed
actions on a hard-allowlist (per main D-decisions).
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QAFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str  # stable id e.g. "audio.lufs.too_high"
    severity: Severity
    message: str
    measured: float | str | None = None
    expected: float | str | None = None
    proposed_action: str | None = None  # e.g. "regenerate_audio_mix"


class QAReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    path: str
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    bitrate_video: int | None = None
    bitrate_audio: int | None = None

    integrated_lufs: float | None = None
    true_peak_dbfs: float | None = None
    lra: float | None = None
    bpm: float | None = None
    dead_air_count: int = 0
    dead_air_total_s: float = 0.0

    findings: list[QAFinding] = Field(default_factory=list)
    pass_: bool = Field(default=False, alias="pass")

    @property
    def severity_high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)


# ---- main ---------------------------------------------------------------


def review(
    path: Path,
    *,
    target_lufs: float = -14.0,
    lufs_tolerance: float = 1.0,
    peak_dbfs_ceiling: float = -1.0,
    min_duration_s: float = 5.0,
    max_duration_s: float = 180.0,
    min_width: int = 1080,
    target_fps_min: float = 24.0,
) -> QAReport:
    """Run full QA on path. Returns a QAReport with findings + pass flag."""
    info = _ffprobe(path)
    measurements = _ebur128(path)
    bpm = _aubio_bpm(path)
    dead_air = _detect_dead_air(path)

    report = QAReport(
        path=str(path),
        duration_s=info.get("duration_s"),
        width=info.get("width"),
        height=info.get("height"),
        fps=info.get("fps"),
        video_codec=info.get("video_codec"),
        audio_codec=info.get("audio_codec"),
        bitrate_video=info.get("bitrate_video"),
        bitrate_audio=info.get("bitrate_audio"),
        integrated_lufs=measurements.get("integrated_lufs"),
        true_peak_dbfs=measurements.get("true_peak_dbfs"),
        lra=measurements.get("lra"),
        bpm=bpm,
        dead_air_count=dead_air["count"],
        dead_air_total_s=dead_air["total_s"],
    )

    # findings
    findings: list[QAFinding] = []
    if report.duration_s is not None:
        if report.duration_s < min_duration_s:
            findings.append(
                QAFinding(
                    code="length.too_short",
                    severity=Severity.HIGH,
                    message=f"video {report.duration_s:.1f}s < {min_duration_s}s",
                    measured=report.duration_s,
                    expected=f">= {min_duration_s}",
                )
            )
        if report.duration_s > max_duration_s:
            findings.append(
                QAFinding(
                    code="length.too_long",
                    severity=Severity.MEDIUM,
                    message=f"video {report.duration_s:.1f}s > {max_duration_s}s",
                    measured=report.duration_s,
                    expected=f"<= {max_duration_s}",
                )
            )
    if report.width is not None and report.width < min_width:
        findings.append(
            QAFinding(
                code="resolution.too_small",
                severity=Severity.HIGH,
                message=f"width {report.width} < {min_width}",
                measured=report.width,
                expected=f">= {min_width}",
            )
        )
    if report.fps is not None and report.fps < target_fps_min:
        findings.append(
            QAFinding(
                code="fps.too_low",
                severity=Severity.MEDIUM,
                message=f"fps {report.fps:.1f} < {target_fps_min}",
                measured=report.fps,
                expected=f">= {target_fps_min}",
            )
        )
    if report.integrated_lufs is None:
        findings.append(
            QAFinding(
                code="audio.lufs.unmeasurable",
                severity=Severity.HIGH,
                message="could not measure integrated LUFS",
            )
        )
    else:
        if abs(report.integrated_lufs - target_lufs) > lufs_tolerance:
            sev = (
                Severity.HIGH
                if abs(report.integrated_lufs - target_lufs) > lufs_tolerance * 2
                else Severity.MEDIUM
            )
            findings.append(
                QAFinding(
                    code="audio.lufs.out_of_band",
                    severity=sev,
                    message=f"integrated LUFS {report.integrated_lufs:.1f} "
                    f"deviates from target {target_lufs} by "
                    f"{abs(report.integrated_lufs - target_lufs):.1f}dB",
                    measured=report.integrated_lufs,
                    expected=f"{target_lufs} ± {lufs_tolerance}",
                    proposed_action="regenerate_audio_mix",
                )
            )
    if report.true_peak_dbfs is not None and report.true_peak_dbfs > peak_dbfs_ceiling:
        findings.append(
            QAFinding(
                code="audio.peak.too_hot",
                severity=Severity.HIGH,
                message=f"true peak {report.true_peak_dbfs:.1f} dBFS exceeds {peak_dbfs_ceiling}",
                measured=report.true_peak_dbfs,
                expected=f"<= {peak_dbfs_ceiling}",
                proposed_action="regenerate_audio_mix",
            )
        )
    if report.dead_air_total_s > 2.0:
        findings.append(
            QAFinding(
                code="audio.dead_air",
                severity=Severity.MEDIUM,
                message=f"{report.dead_air_total_s:.1f}s of dead air "
                f"across {report.dead_air_count} segments",
                measured=report.dead_air_total_s,
                expected="<= 2.0",
            )
        )

    report.findings = findings
    report.pass_ = report.severity_high_count == 0
    return report


# ---- introspection helpers -----------------------------------------------


def measure(path: Path) -> dict[str, float | int | str | None]:
    """Lightweight wrapper for telemetry (no findings)."""
    info = _ffprobe(path)
    measurements = _ebur128(path)
    return {**info, **measurements}


def _ffprobe(path: Path) -> dict[str, float | int | str | None]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {}
    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}
    out: dict[str, float | int | str | None] = {}
    fmt = info.get("format", {})
    out["duration_s"] = float(fmt.get("duration", 0)) or None
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v:
        out["width"] = int(v.get("width", 0)) or None
        out["height"] = int(v.get("height", 0)) or None
        out["video_codec"] = v.get("codec_name")
        out["bitrate_video"] = int(v.get("bit_rate", 0)) or None
        # parse fps from r_frame_rate "30/1"
        fr = v.get("r_frame_rate", "")
        if "/" in fr:
            num, den = fr.split("/")
            try:
                out["fps"] = float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                pass
    if a:
        out["audio_codec"] = a.get("codec_name")
        out["bitrate_audio"] = int(a.get("bit_rate", 0)) or None
    return out


def _ebur128(path: Path) -> dict[str, float | None]:
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
    out: dict[str, float | None] = {
        "integrated_lufs": None,
        "true_peak_dbfs": None,
        "lra": None,
    }
    for line in proc.stderr.splitlines():
        line = line.strip()
        if line.startswith("I:") and "LUFS" in line:
            try:
                out["integrated_lufs"] = float(line.split()[1])
            except (ValueError, IndexError):
                pass
        elif "Peak:" in line and "dBFS" in line:
            m = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", line)
            if m:
                out["true_peak_dbfs"] = float(m.group(1))
        elif line.startswith("LRA:"):
            try:
                out["lra"] = float(line.split()[1])
            except (ValueError, IndexError):
                pass
    return out


def _aubio_bpm(path: Path) -> float | None:
    cmd = ["aubio", "tempo", "-i", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None
    # last printed BPM line
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return float(line.split()[0])
        except (ValueError, IndexError):
            continue
    return None


def _detect_dead_air(path: Path, threshold_db: float = -50.0, min_seconds: float = 2.0) -> dict[str, float | int]:
    """Use ffmpeg silencedetect to find dead-air segments."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(path),
        "-af",
        f"silencedetect=noise={threshold_db}dB:d={min_seconds}",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    count = 0
    total = 0.0
    for line in proc.stderr.splitlines():
        m = re.search(r"silence_duration:\s*(-?\d+(?:\.\d+)?)", line)
        if m:
            count += 1
            total += float(m.group(1))
    return {"count": count, "total_s": total}
