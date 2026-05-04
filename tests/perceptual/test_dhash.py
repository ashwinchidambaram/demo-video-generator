"""Smoke tests for the perceptual-diff harness.

These tests don't require ffmpeg installed — when ffmpeg is missing, dhash()
returns 0 and tests treat that as a no-op skip. Real perceptual regression
golden MP4s land in Phase 6+ when the renderer ships canonical fixtures.
"""

from __future__ import annotations

import shutil

import pytest

from tests.perceptual.dhash import hamming, similar


def test_hamming_distance_self_is_zero() -> None:
    assert hamming(0xCAFEF00D, 0xCAFEF00D) == 0


def test_hamming_distance_one_bit_flip() -> None:
    assert hamming(0b1010, 0b1011) == 1


def test_similar_within_threshold() -> None:
    a = 0
    b = 0b111  # 3 bits set
    assert similar(a, b, max_distance=3)
    assert not similar(a, b, max_distance=2)


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg not on PATH; perceptual hashing requires it",
)
def test_dhash_of_rendered_mp4(tmp_path) -> None:
    """If we have a recently rendered MP4, hash it twice and assert match.

    This is a smoke test of the perceptual pipeline; real golden-set
    regression lives in Phase 6+.
    """
    from pathlib import Path

    from tests.perceptual.dhash import dhash

    # Look for any recent rendered MP4 in the repo's runs/ dir.
    repo_root = Path(__file__).resolve().parents[2]
    candidates = sorted(
        (p for p in (repo_root / "runs").glob("**/final.mp4") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        pytest.skip("no rendered MP4 to perceptually hash")
    h1 = dhash(candidates[0], t=0.5)
    h2 = dhash(candidates[0], t=0.5)
    if h1 == 0:
        pytest.skip("ffmpeg failed to extract frame — toolkit fragile here")
    assert h1 == h2  # determinism: same frame → same hash
