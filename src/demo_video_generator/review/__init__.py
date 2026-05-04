"""Review subcommand.

Phase 8: implements the audio QA toolkit subset that's actually deterministic
across ffmpeg versions per ultraplan R3 (canonical scalars, not raw stderr):

- ffprobe metadata: duration, video/audio stream presence, codec
- ffmpeg ebur128: integrated LUFS, true peak (rounded to 0.1 LUFS / 0.1 dB)
- length check vs composition.json's declared duration

The full toolkit (sox spectrogram, aubio tempo, librosa segmentation) lands
in Phase 8.5 alongside the qa-reviewer agent's structured proposed_action
allowlist.

Severity ladder (qa.json schema):
- high: ship-blocker (LUFS off >2, true peak >-1 dBTP, length off >10%, no audio stream)
- medium: noticeable (LUFS off 1-2, length off 5-10%)
- low: nit (LUFS off <1, length off <5%)
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic


def _ffprobe_meta(final_mp4: Path) -> dict[str, Any]:
    """Return canonical ffprobe metadata: duration, codecs, stream presence."""
    if shutil.which("ffprobe") is None:
        return {"available": False}
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration,bit_rate:stream=codec_name,codec_type",
                "-of", "json",
                str(final_mp4),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        data = json.loads(proc.stdout)
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        return {
            "available": True,
            "duration_seconds": float(data["format"].get("duration", 0)),
            "bit_rate": int(data["format"].get("bit_rate", 0)) if data["format"].get("bit_rate") else None,
            "video_codec": video.get("codec_name") if video else None,
            "audio_codec": audio.get("codec_name") if audio else None,
            "has_video": video is not None,
            "has_audio": audio is not None,
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ValueError):
        return {"available": False}


def _ebur128(final_mp4: Path) -> dict[str, Any]:
    """Run ffmpeg ebur128 and parse integrated LUFS + true peak.

    Returns canonical scalars (rounded per R3) — not the raw stderr blob.
    """
    if shutil.which("ffmpeg") is None:
        return {"available": False}
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-i", str(final_mp4),
                "-filter_complex", "ebur128=peak=true",
                "-f", "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {"available": False, "error": "timeout"}

    text = proc.stderr
    integrated = None
    true_peak = None
    # ffmpeg writes a "Summary" block at the end with these lines:
    #   Integrated loudness:
    #       I:         -14.1 LUFS
    #   True peak:
    #       Peak:       -1.0 dBFS
    in_summary = False
    in_integrated = False
    in_true_peak = False
    for raw in text.splitlines():
        line = raw.strip()
        # "Summary:" line is prefixed with [Parsed_ebur128_0 @ 0x...]; match anywhere.
        if "Summary:" in line:
            in_summary = True
            continue
        if not in_summary:
            continue
        if line.startswith("Integrated loudness:"):
            in_integrated = True
            in_true_peak = False
            continue
        if line.startswith("True peak:"):
            in_true_peak = True
            in_integrated = False
            continue
        if in_integrated and line.startswith("I:"):
            with contextlib.suppress(IndexError, ValueError):
                integrated = float(line.split()[1])
            in_integrated = False
        if in_true_peak and line.startswith("Peak:"):
            with contextlib.suppress(IndexError, ValueError):
                true_peak = float(line.split()[1])
            in_true_peak = False

    return {
        "available": True,
        "integrated_lufs": round(integrated, 1) if integrated is not None else None,
        "true_peak_dbtp": round(true_peak, 1) if true_peak is not None else None,
    }


def _aubio_tempo(audio_path: Path) -> dict[str, Any]:
    """Run `aubio tempo` and return canonical scalar BPM (rounded to int).

    aubio writes BPM estimates per-frame to stdout; we take the median.
    Returns {"available": False} if aubio isn't installed or the clip is too
    short (aubio is unstable on <8s clips per qa-reviewer/gotchas.md).
    """
    if shutil.which("aubio") is None:
        return {"available": False}
    try:
        proc = subprocess.run(
            ["aubio", "tempo", "-i", str(audio_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"available": False, "error": "timeout"}
    if proc.returncode != 0:
        return {"available": False, "error": proc.stderr.strip()[:200]}

    bpms: list[float] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # `aubio tempo` prints "<seconds> <bpm>" or sometimes just "<bpm>"
        parts = line.split()
        try:
            bpm = float(parts[-1])
            if 30 < bpm < 240:
                bpms.append(bpm)
        except ValueError:
            continue
    if not bpms:
        return {"available": True, "bpm": None}
    median_bpm = sorted(bpms)[len(bpms) // 2]
    return {"available": True, "bpm": round(median_bpm)}


def _aubio_onset_count(audio_path: Path) -> dict[str, Any]:
    """Run `aubio onset` and return the count of detected onsets.

    Onset density is a useful signal for "busy vs sparse" sections.
    """
    if shutil.which("aubio") is None:
        return {"available": False}
    try:
        proc = subprocess.run(
            ["aubio", "onset", "-i", str(audio_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"available": False, "error": "timeout"}
    if proc.returncode != 0:
        return {"available": False}
    count = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            float(line.split()[0])
            count += 1
        except (ValueError, IndexError):
            continue
    return {"available": True, "onset_count": count}


def _librosa_segments(
    audio_path: Path, *, segment_count: int = 6
) -> dict[str, Any]:
    """Use librosa.segment to compute boundary timestamps where character
    changes (per agent design / audio-qa-toolkit catalog). Returns canonical
    boundary timestamps quantized to 100 ms (per ultraplan R3 to avoid
    cross-platform numpy/scipy boundary jitter).

    Phase 8: agglomerative segmentation on MFCC features. Returns up to
    `segment_count` boundaries.
    """
    try:
        import librosa
    except ImportError:
        return {"available": False, "error": "librosa not installed"}
    try:
        # Load audio (mono, native SR). Limit to first 60s to bound cost.
        y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=60)
    except Exception as e:
        return {"available": False, "error": str(e)[:200]}
    if len(y) == 0:
        return {"available": False, "error": "empty audio"}

    try:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        # agglomerative clustering on MFCC frames
        boundary_frames = librosa.segment.agglomerative(mfcc, segment_count)
        # Convert frame indices to seconds quantized to 100 ms
        times = librosa.frames_to_time(boundary_frames, sr=sr)
        boundaries_100ms = sorted({round(float(t) * 10) / 10 for t in times})
        return {
            "available": True,
            "boundaries_seconds": boundaries_100ms,
            "segment_count_actual": len(boundaries_100ms),
            "duration_loaded": float(len(y) / sr),
        }
    except Exception as e:
        return {"available": False, "error": str(e)[:200]}


def _sox_spectrogram(audio_path: Path, out_path: Path) -> dict[str, Any]:
    """Generate a 1920x1080 spectrogram PNG via sox.

    Returns the path on success. Phase 8: spectrogram is evidence; perceptual
    hash for snapshot tests lands when Phase 8.5 vendors a stable sox/libpng
    pin (per ultraplan R3).
    """
    if shutil.which("sox") is None:
        return {"available": False}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # sox needs WAV; if the input is MP3 we transcode via ffmpeg first.
    src: Path = audio_path
    tmp_wav: Path | None = None
    if audio_path.suffix.lower() != ".wav" and shutil.which("ffmpeg") is not None:
        tmp_wav = audio_path.with_suffix(".tmp_qa.wav")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel", "error",
                    "-i", str(audio_path),
                    str(tmp_wav),
                ],
                capture_output=True,
                check=True,
                timeout=60,
            )
            src = tmp_wav
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            tmp_wav = None
    try:
        subprocess.run(
            [
                "sox", str(src), "-n", "spectrogram",
                "-o", str(out_path),
                "-x", "1920", "-y", "1080",
                "-z", "90",
            ],
            capture_output=True,
            check=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return {"available": False, "error": str(e)[:200]}
    finally:
        if tmp_wav is not None and tmp_wav.exists():
            with contextlib.suppress(OSError):
                tmp_wav.unlink()
    if not out_path.is_file():
        return {"available": False, "error": "sox produced no output"}
    return {
        "available": True,
        "path": str(out_path),
        "size_bytes": out_path.stat().st_size,
    }


def _extract_audio_from_video(video_path: Path, out_path: Path) -> bool:
    """Helper: extract the audio track from a video to a temporary WAV so
    aubio/librosa can analyze it (those tools want audio, not video)."""
    if shutil.which("ffmpeg") is None:
        return False
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel", "error",
                "-i", str(video_path),
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                str(out_path),
            ],
            capture_output=True,
            check=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return out_path.is_file()


def _classify_lufs_severity(actual: float, target: float) -> str | None:
    """Per severity ladder: high if off >2; medium 1-2; low <1."""
    delta = abs(actual - target)
    if delta > 2:
        return "high"
    if delta > 1:
        return "medium"
    if delta >= 0.5:
        return "low"
    return None


def _classify_length_severity(actual: float, declared: float) -> str | None:
    if declared <= 0:
        return None
    pct = abs(actual - declared) / declared * 100
    if pct > 10:
        return "high"
    if pct > 5:
        return "medium"
    if pct > 2:
        return "low"
    return None


def review(final_mp4: Path, run_dir: Path) -> dict[str, Any]:
    """Phase 8 audit. Reads composition.json's targets, runs the toolkit,
    classifies issues against the severity ladder, writes audio_qa.json + qa.json.
    """
    issues: list[dict[str, Any]] = []
    measurements: dict[str, Any] = {}
    evidence_paths: list[str] = []

    composition_path = run_dir / "composition.json"
    composition: dict[str, Any] = {}
    if composition_path.is_file():
        composition = json.loads(composition_path.read_text())

    target_lufs = composition.get("audio", {}).get("mix", {}).get("integrated_lufs", -14)
    target_truepeak = composition.get("audio", {}).get("mix", {}).get("true_peak_dbtp", -1)
    declared_duration = composition.get("duration_seconds", 0.0)

    # 1. final.mp4 must exist.
    if not final_mp4.exists():
        issues.append(
            {
                "code": "FINAL_MP4_MISSING",
                "severity": "high",
                "stage": "render",
                "evidence": {"path": str(final_mp4)},
                "proposed_action": {"kind": "regenerate_stage", "target_stage": "render"},
            }
        )
        signoff = "fail"
        write_json_atomic(run_dir / "audio_qa.json", {"schema_version": 1, "measurements": measurements})
        qa_doc = {
            "schema_version": 1,
            "signoff": signoff,
            "issues": issues,
            "measurements": measurements,
            "evidence_paths": evidence_paths,
        }
        write_json_atomic(run_dir / "qa.json", qa_doc)
        return qa_doc

    # 2. ffprobe metadata.
    meta = _ffprobe_meta(final_mp4)
    measurements["ffprobe"] = meta

    if meta.get("available"):
        actual_duration = meta.get("duration_seconds", 0.0)
        sev = _classify_length_severity(actual_duration, declared_duration)
        if sev:
            issues.append(
                {
                    "code": "LENGTH_OFF_BY_>10PCT" if sev == "high" else "LENGTH_DRIFT",
                    "severity": sev,
                    "stage": "render",
                    "evidence": {
                        "actual_duration_seconds": actual_duration,
                        "declared_duration_seconds": declared_duration,
                    },
                    "proposed_action": {"kind": "escalate"},
                }
            )

        if not meta.get("has_audio"):
            issues.append(
                {
                    "code": "NO_AUDIO_STREAM",
                    "severity": "high",
                    "stage": "render",
                    "evidence": meta,
                    "proposed_action": {"kind": "regenerate_stage", "target_stage": "compose"},
                }
            )

    # 3. ebur128 loudness + true peak.
    loudness = _ebur128(final_mp4)
    measurements["ebur128"] = loudness

    # 4. Extract audio for aubio/librosa toolkit.
    audio_wav = run_dir / ".qa-audio.wav"
    audio_extracted = _extract_audio_from_video(final_mp4, audio_wav)
    if audio_extracted:
        measurements["aubio_tempo"] = _aubio_tempo(audio_wav)
        measurements["aubio_onset"] = _aubio_onset_count(audio_wav)
        measurements["librosa_segments"] = _librosa_segments(audio_wav)
        # 5. Spectrogram as evidence.
        spec_path = run_dir / "spectrogram.png"
        spec_result = _sox_spectrogram(audio_wav, spec_path)
        measurements["sox_spectrogram"] = spec_result
        if spec_result.get("available"):
            evidence_paths.append(str(spec_path))
        # Cleanup tmp wav
        with contextlib.suppress(OSError):
            audio_wav.unlink()

    if loudness.get("available"):
        integrated = loudness.get("integrated_lufs")
        true_peak = loudness.get("true_peak_dbtp")
        if integrated is not None:
            sev = _classify_lufs_severity(integrated, target_lufs)
            if sev:
                issues.append(
                    {
                        "code": "MIX_LUFS_OFF_TARGET",
                        "severity": sev,
                        "stage": "compose",
                        "evidence": {
                            "actual": integrated,
                            "target": target_lufs,
                        },
                        "proposed_action": (
                            {"kind": "regenerate_stage", "target_stage": "compose"}
                            if sev == "high"
                            else {"kind": "accept_with_warning"}
                        ),
                    }
                )
        if true_peak is not None and true_peak > target_truepeak:
            issues.append(
                {
                    "code": "MIX_TRUEPEAK_EXCEEDED",
                    "severity": "high",
                    "stage": "compose",
                    "evidence": {
                        "actual": true_peak,
                        "target": target_truepeak,
                    },
                    "proposed_action": {"kind": "regenerate_stage", "target_stage": "compose"},
                }
            )

    # Determine signoff.
    has_high = any(i["severity"] == "high" for i in issues)
    if has_high:
        signoff = "fail"
    elif issues:
        signoff = "warn"
    else:
        signoff = "pass"

    audio_qa_doc = {
        "schema_version": 1,
        "measurements": measurements,
    }
    qa_doc = {
        "schema_version": 1,
        "signoff": signoff,
        "issues": issues,
        "measurements": measurements,
        "evidence_paths": evidence_paths,
    }
    write_json_atomic(run_dir / "audio_qa.json", audio_qa_doc)
    write_json_atomic(run_dir / "qa.json", qa_doc)
    return qa_doc


def stub_review(final_mp4: Path, run_dir: Path) -> dict[str, Any]:
    """Driver entry. Phase 8 calls the real review() with audio toolkit."""
    return review(final_mp4, run_dir)
