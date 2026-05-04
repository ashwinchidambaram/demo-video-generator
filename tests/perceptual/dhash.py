"""Difference-hash (dHash) for perceptual frame comparison.

Phase 1: zero-dep implementation that doesn't require Pillow/numpy. Reads PPM
output from `ffmpeg -frames:v 1 -f image2pipe -vcodec ppm` and computes a 64-bit
dHash. Real Pillow-based hashing arrives in Phase 6 alongside the full visual
regression suite.

dHash algorithm (Neal Krawetz):
1. Resize to 9x8 grayscale (we read 9x8 PPM directly via ffmpeg scale filter).
2. For each row, hash bit i = (pixel[i] > pixel[i+1]).
3. Concatenate to a 64-bit integer.

Two dHashes are considered "matching" when their Hamming distance ≤ threshold
(default 6 → similarity ≥ 0.91). v2.1 plan calls for dHash similarity ≥ 0.95
default; that maps to Hamming distance ≤ 3 here. Caller picks the threshold.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path


def _ffmpeg_grayscale_9x8(video_path: Path, t: float) -> bytes:
    """Extract one frame at time `t` as 9x8 grayscale PPM, return its 72 byte
    pixel payload. Returns an empty bytes object if ffmpeg is unavailable."""
    if shutil.which("ffmpeg") is None:
        return b""

    proc = subprocess.run(
        [
            "ffmpeg",
            "-loglevel", "error",
            "-ss", str(t),
            "-i", str(video_path),
            "-frames:v", "1",
            "-vf", "scale=9:8,format=gray",
            "-f", "image2pipe",
            "-vcodec", "pgm",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return b""
    # PGM format: header lines, then raw bytes (one per pixel for 8-bit).
    data = proc.stdout
    # Strip the PGM header — three whitespace-separated tokens after magic
    # number "P5", then a single newline, then 9*8 = 72 bytes.
    # Safer parse: locate fourth whitespace.
    head_end = 0
    seen = 0
    for idx, byte in enumerate(data):
        if byte in (0x20, 0x0A):  # space or newline
            seen += 1
            if seen == 4:
                head_end = idx + 1
                break
    return data[head_end : head_end + 72]


def dhash(video_path: Path, t: float = 0.0) -> int:
    """Compute 64-bit dHash of a video frame at time `t` (seconds).

    Returns 0 if the frame can't be extracted (caller should treat 0 as
    "unhashable" and skip comparison).
    """
    pixels = _ffmpeg_grayscale_9x8(video_path, t)
    if len(pixels) != 72:
        return 0
    bits = 0
    bit_idx = 0
    for row in range(8):
        row_start = row * 9
        for col in range(8):
            left = pixels[row_start + col]
            right = pixels[row_start + col + 1]
            if left > right:
                bits |= 1 << bit_idx
            bit_idx += 1
    return bits


def hamming(a: int, b: int) -> int:
    """Number of differing bits in two 64-bit hashes."""
    return bin(a ^ b).count("1")


def similar(a: int, b: int, *, max_distance: int = 3) -> bool:
    """Return True if two dHashes are within `max_distance` Hamming bits.

    Default 3 ≈ 95% similarity (per v2.1 plan dHash ≥ 0.95 default).
    """
    return hamming(a, b) <= max_distance


__all__ = ["dhash", "hamming", "similar"]
# Reference _struct so the import isn't unused — keeps the file at zero deps.
_ = struct
