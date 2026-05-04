"""Tests for the Phase 8 audio QA toolkit.

These hit real shell tools (sox/aubio/ffmpeg/ffprobe). When a tool is missing,
the test is skipped via pytest.skip — the toolkit's own gate should already
return {"available": False} but we belt-and-brace at the test boundary.

Inputs are the synthetic SFX clips from src/.../sfx/pack/, which always
exist (generated programmatically) and have predictable properties.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from demo_video_generator.review import (
    _aubio_onset_count,
    _aubio_tempo,
    _classify_length_severity,
    _classify_lufs_severity,
    _ebur128,
    _extract_audio_from_video,
    _ffprobe_meta,
    _librosa_segments,
    _sox_spectrogram,
)

PACK_DIR = Path(__file__).resolve().parents[2] / "src" / "demo_video_generator" / "sfx" / "pack"
CONFIRM_BLIP = PACK_DIR / "confirm_blip_01.wav"


@pytest.fixture(scope="module")
def confirm_blip() -> Path:
    if not CONFIRM_BLIP.is_file():
        pytest.skip(f"sfx pack not generated: {CONFIRM_BLIP}")
    return CONFIRM_BLIP


# ---------- Severity classifiers (pure logic, no tools) ----------


def test_lufs_severity_classifier() -> None:
    # Within 0.5 LUFS: no issue.
    assert _classify_lufs_severity(-14.0, -14) is None
    assert _classify_lufs_severity(-14.4, -14) is None
    # 0.5-1: low.
    assert _classify_lufs_severity(-14.7, -14) == "low"
    # 1-2: medium.
    assert _classify_lufs_severity(-15.5, -14) == "medium"
    # >2: high.
    assert _classify_lufs_severity(-17.0, -14) == "high"
    # Direction agnostic.
    assert _classify_lufs_severity(-12.0, -14) == "medium"


def test_length_severity_classifier() -> None:
    assert _classify_length_severity(25.0, 25.0) is None
    assert _classify_length_severity(25.5, 25.0) is None  # 2% — under threshold
    assert _classify_length_severity(26.0, 25.0) == "low"  # 4%
    assert _classify_length_severity(27.0, 25.0) == "medium"  # 8%
    assert _classify_length_severity(30.0, 25.0) == "high"  # 20%
    # Edge: declared 0 → no comparison.
    assert _classify_length_severity(5.0, 0.0) is None


# ---------- Real toolkit smoke tests ----------


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not on PATH")
def test_ffprobe_meta_on_wav(confirm_blip: Path) -> None:
    meta = _ffprobe_meta(confirm_blip)
    assert meta["available"] is True
    assert meta["duration_seconds"] > 0.1
    assert meta["has_audio"] is True
    assert meta["has_video"] is False  # WAV — no video


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_ebur128_on_wav(confirm_blip: Path) -> None:
    result = _ebur128(confirm_blip)
    # Some clips may be too short for stable integrated LUFS but the toolkit
    # availability flag should still be True.
    assert result["available"] is True


@pytest.mark.skipif(shutil.which("aubio") is None, reason="aubio not on PATH")
def test_aubio_tempo_returns_canonical_int_bpm(confirm_blip: Path) -> None:
    result = _aubio_tempo(confirm_blip)
    assert result["available"] is True
    # bpm is None for very short clips OR an int when stable.
    if result["bpm"] is not None:
        assert isinstance(result["bpm"], int)
        assert 30 < result["bpm"] < 240


@pytest.mark.skipif(shutil.which("aubio") is None, reason="aubio not on PATH")
def test_aubio_onset_count_returns_int(confirm_blip: Path) -> None:
    result = _aubio_onset_count(confirm_blip)
    assert result["available"] is True
    assert isinstance(result["onset_count"], int)
    assert result["onset_count"] >= 0


def test_librosa_segments_returns_quantized_boundaries(confirm_blip: Path) -> None:
    """Boundaries must be quantized to 100 ms per R3."""
    result = _librosa_segments(confirm_blip, segment_count=2)
    if not result.get("available"):
        pytest.skip(f"librosa segmentation unavailable: {result}")
    boundaries = result["boundaries_seconds"]
    # Each boundary should be a multiple of 0.1 (100 ms quantum).
    for b in boundaries:
        # Rounding through float can drift; assert at the canonical resolution.
        assert abs(b * 10 - round(b * 10)) < 1e-9, f"boundary {b} not quantized to 100ms"


@pytest.mark.skipif(shutil.which("sox") is None, reason="sox not on PATH")
def test_sox_spectrogram_creates_png(confirm_blip: Path, tmp_path: Path) -> None:
    out = tmp_path / "spec.png"
    result = _sox_spectrogram(confirm_blip, out)
    assert result["available"] is True
    assert out.is_file()
    assert out.stat().st_size > 1024  # PNG of 1920x1080 should be substantial


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_extract_audio_from_video_roundtrip(tmp_path: Path) -> None:
    """Extract → ffprobe roundtrip: a synthetic input fed through the
    extraction pipeline must yield a probable WAV.
    """
    # We use confirm_blip as a stand-in "video"; ffmpeg will happily extract
    # the audio stream of a WAV (no-op transcode).
    src = CONFIRM_BLIP
    if not src.is_file():
        pytest.skip("sfx pack not generated")
    out = tmp_path / "out.wav"
    ok = _extract_audio_from_video(src, out)
    assert ok
    assert out.is_file()
    meta = _ffprobe_meta(out)
    assert meta["available"] is True
    assert meta["has_audio"] is True
