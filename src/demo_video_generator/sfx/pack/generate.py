"""Generate the Phase 5 synthetic SFX pack.

Run via `python -m demo_video_generator.sfx.pack.generate` to (re)materialize
the four .wav clips. The pack/index.json describes the catalog.

Phase 5.5 replaces this with the vendored Kenney CC0 subset.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent
SAMPLE_RATE = 44100


def _write_wav(path: Path, samples: list[int]) -> None:
    """Write 16-bit mono PCM at SAMPLE_RATE."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(struct.pack("<h", max(-32768, min(32767, s))) for s in samples))


def _envelope(n: int, attack_n: int, release_n: int) -> list[float]:
    env = []
    for i in range(n):
        if i < attack_n:
            env.append(i / attack_n)
        elif i > n - release_n:
            env.append((n - i) / release_n)
        else:
            env.append(1.0)
    return env


def gen_click_soft() -> None:
    """Soft UI click: short noise burst with quick fade."""
    duration = 0.08
    n = int(duration * SAMPLE_RATE)
    env = _envelope(n, attack_n=int(0.002 * SAMPLE_RATE), release_n=int(0.06 * SAMPLE_RATE))
    # Filtered noise: low-pass random walk
    samples: list[int] = []
    prev = 0.0
    for i in range(n):
        target = math.sin(2 * math.pi * 1200 * i / SAMPLE_RATE) * 0.35
        prev = 0.85 * prev + 0.15 * target
        samples.append(int(prev * env[i] * 18000))
    _write_wav(PACK_DIR / "click_soft_01.wav", samples)


def gen_confirm_blip() -> None:
    """Two-tone positive blip: 880 Hz then 1320 Hz (perfect fifth, rising)."""
    seg_dur = 0.1
    n_seg = int(seg_dur * SAMPLE_RATE)
    env_seg = _envelope(n_seg, attack_n=int(0.005 * SAMPLE_RATE), release_n=int(0.05 * SAMPLE_RATE))
    samples: list[int] = []
    for freq in (880.0, 1320.0):
        for i in range(n_seg):
            sample = math.sin(2 * math.pi * freq * i / SAMPLE_RATE) * env_seg[i] * 18000
            samples.append(int(sample))
    _write_wav(PACK_DIR / "confirm_blip_01.wav", samples)


def gen_modal_whoosh() -> None:
    """Subtle whoosh: noise sweeping through a moving low-pass."""
    duration = 0.18
    n = int(duration * SAMPLE_RATE)
    env = _envelope(n, attack_n=int(0.04 * SAMPLE_RATE), release_n=int(0.08 * SAMPLE_RATE))
    # Pseudo-random noise via a deterministic LFSR-like seed.
    samples: list[int] = []
    prev = 0.0
    seed = 0xACE1
    for i in range(n):
        # 16-bit LFSR
        bit = ((seed >> 0) ^ (seed >> 2) ^ (seed >> 3) ^ (seed >> 5)) & 1
        seed = (seed >> 1) | (bit << 15)
        noise = (seed / 32768.0) - 1.0
        # Sweep low-pass alpha from 0.05 -> 0.35 across the clip
        alpha = 0.05 + 0.30 * (i / n)
        prev = (1 - alpha) * prev + alpha * noise
        samples.append(int(prev * env[i] * 12000))
    _write_wav(PACK_DIR / "modal_whoosh_01.wav", samples)


def gen_error_thump() -> None:
    """Muted thump: low sine + soft click."""
    duration = 0.15
    n = int(duration * SAMPLE_RATE)
    env = _envelope(n, attack_n=int(0.005 * SAMPLE_RATE), release_n=int(0.10 * SAMPLE_RATE))
    samples: list[int] = []
    for i in range(n):
        s = math.sin(2 * math.pi * 110.0 * i / SAMPLE_RATE) * env[i]
        # Subtle higher harmonic
        s += 0.2 * math.sin(2 * math.pi * 220.0 * i / SAMPLE_RATE) * env[i]
        samples.append(int(s * 19000))
    _write_wav(PACK_DIR / "error_thump_01.wav", samples)


def main() -> None:
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    gen_click_soft()
    gen_confirm_blip()
    gen_modal_whoosh()
    gen_error_thump()
    print(f"Generated 4 synthetic SFX clips in {PACK_DIR}")


if __name__ == "__main__":
    main()
