"""Sequence-based demo — composes two sub-segments end-to-end via Sequence.

Demonstrates that nested compositions flatten correctly: each Sequence has
its own captions on a relative timeline, and the parent stitches them
into a single 18 s output.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path

from dvg import (
    AudioLayer,
    CaptionLayer,
    Composition,
    Mood,
    Sequence,
    TitleLayer,
    VideoLayer,
)
from dvg.capture import capture_url
from dvg.models import Anchor as A

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests/fixtures/site/index.html"
LOGO = ROOT / "tests/fixtures/logo.png"
SOUNDTRACK = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-edm.mp3"
)
OUT_DIR = ROOT / "runs/sequence_demo"


async def _capture() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    url = f"file://{FIXTURE.resolve()}"
    result = await capture_url(
        url,
        out_dir=OUT_DIR,
        duration=10.0,
        width=1920,
        height=1080,
        fps=30,
        scenario="tour",
        headed=False,
    )
    return result.video_path


def main() -> None:
    print("[1/3] capturing...")
    video_path = asyncio.run(_capture())

    print("[2/3] composing with Sequences...")
    # Sub-comp A: 0-9s, focuses on capture
    seq_a = Sequence(
        time=(0.0, 9.0),
        layers=[
            VideoLayer(
                src=video_path,
                time=(0.0, 9.0),
                fit="cover",
                fade_in=0.4,
                fade_out=0.3,
                ken_burns=0.04,
            ),
            CaptionLayer(text="Step 1: Capture", mood=Mood.ANNOUNCE, time=(0.5, 3.0), anchor=A.BOTTOM_CENTER),
            CaptionLayer(text="Playwright headed Chromium", mood=Mood.EXPLAIN, time=(3.5, 6.0), anchor=A.BOTTOM_CENTER),
            CaptionLayer(text="Real DOM events captured", mood=Mood.PUNCHLINE, time=(6.5, 8.5), anchor=A.BOTTOM_CENTER),
        ],
    )
    # Sub-comp B: 9-18s, focuses on render
    seq_b = Sequence(
        time=(9.0, 18.0),
        layers=[
            VideoLayer(
                src=video_path,
                time=(0.0, 9.0),
                fit="cover",
                fade_in=0.3,
                fade_out=0.4,
                ken_burns=0.04,
            ),
            CaptionLayer(text="Step 2: Render", mood=Mood.ANNOUNCE, time=(0.5, 3.0), anchor=A.BOTTOM_CENTER),
            CaptionLayer(text="ffmpeg + libass, no Chromium", mood=Mood.EXPLAIN, time=(3.5, 6.0), anchor=A.BOTTOM_CENTER),
            CaptionLayer(text="Sub-3-second renders", mood=Mood.PUNCHLINE, time=(6.5, 8.5), anchor=A.BOTTOM_CENTER),
        ],
    )

    comp = Composition(
        fps=30,
        width=1920,
        height=1080,
        duration=18.0,
        background="#0a0a0a",
        layers=[
            TitleLayer(
                title="dvg pipeline",
                subtitle="composed from sub-sequences",
                time=(0.0, 1.0),
                title_size=120,
                subtitle_size=42,
                fade_in=0.0,
                fade_out=0.5,
            ),
            seq_a,
            seq_b,
        ],
        audio=[
            AudioLayer(
                src=SOUNDTRACK,
                time=(0.0, 18.0),
                target_lufs=-22.0,
                duck_under_captions=True,
                fade_in=0.4,
                fade_out=0.8,
            ),
        ],
        title="dvg sequence demo",
    )
    comp.save(OUT_DIR / "composition.json")
    print(f"  ✓ {len(comp.layers)} top-level layers (sequences flatten at render)")
    flat = comp.flatten()
    print(f"  ✓ flattened: {len(flat.layers)} layers + {len(flat.audio)} audio")

    print("[3/3] rendering...")
    t0 = time.perf_counter()
    result = comp.render(OUT_DIR / "final.mp4", crf=18, preset="medium")
    print(f"  ✓ {time.perf_counter() - t0:.1f}s — LUFS={result.audio_lufs}, peak={result.audio_peak_dbfs}")

    shutil.copy(OUT_DIR / "final.mp4", ROOT / "runs/_demos/dvg_sequence_v1.mp4")
    shutil.copy(OUT_DIR / "composition.json", ROOT / "runs/_demos/dvg_sequence_v1_composition.json")
    size_mb = (ROOT / "runs/_demos/dvg_sequence_v1.mp4").stat().st_size / 1024 / 1024
    print(f"  → runs/_demos/dvg_sequence_v1.mp4 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
