"""Short-form (10s) variant of the dvg demo. Different soundtrack, tighter pacing."""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path

from dvg import (
    AudioLayer,
    CaptionLayer,
    Composition,
    ImageLayer,
    Mood,
    TitleLayer,
    VideoLayer,
)
from dvg.capture import capture_url
from dvg.models import Anchor as A

LOGO = Path(__file__).parent.parent / "tests/fixtures/logo.png"

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests/fixtures/site/index.html"
SOUNDTRACK = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-flow.mp3"
)
OUT_DIR = ROOT / "runs/short_demo"


async def _capture() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    url = f"file://{FIXTURE.resolve()}"
    result = await capture_url(
        url,
        out_dir=OUT_DIR,
        duration=7.0,
        width=1920,
        height=1080,
        fps=30,
        scenario="tour",
        headed=False,
    )
    return result.video_path


def main() -> None:
    print("[1/3] capturing...")
    t0 = time.perf_counter()
    video_path = asyncio.run(_capture())
    print(f"  ✓ ({time.perf_counter() - t0:.1f}s)")

    print("[2/3] composing...")
    comp = Composition(
        fps=30,
        width=1920,
        height=1080,
        duration=10.0,
        background="#0a0a0a",
        layers=[
            TitleLayer(
                title="dvg",
                subtitle="demo videos in one command",
                time=(0.0, 1.6),
                align=A.MIDDLE_CENTER,
                title_size=180,
                subtitle_size=42,
                fade_in=0.3,
                fade_out=0.3,
            ),
            VideoLayer(
                src=video_path,
                time=(1.4, 8.5),
                fit="cover",
                fade_in=0.3,
                fade_out=0.3,
                ken_burns=0.04,
            ),
            ImageLayer(
                src=LOGO,
                time=(2.0, 8.0),
                anchor=A.TOP_RIGHT,
                offset=(40, 40),
                scale=0.4,
                opacity=0.65,
                fade_in=0.4,
                fade_out=0.3,
                z=5,
            ),
            CaptionLayer(
                text="Capture any URL",
                mood=Mood.ANNOUNCE,
                time=(2.0, 4.0),
                anchor=A.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="libass + ffmpeg",
                mood=Mood.PUNCHLINE,
                time=(4.5, 6.5),
                anchor=A.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="Faster than a webpack bundle",
                mood=Mood.TAGLINE,
                time=(7.0, 8.4),
                anchor=A.BOTTOM_CENTER,
            ),
            TitleLayer(
                title="pip install dvg",
                time=(8.5, 10.0),
                align=A.MIDDLE_CENTER,
                title_size=88,
                title_color="#3b82f6",
                fade_in=0.3,
                fade_out=0.3,
            ),
        ],
        audio=[
            AudioLayer(
                src=SOUNDTRACK,
                time=(0.0, 10.0),
                role="music",
                target_lufs=-22.0,
                duck_under_captions=True,
                fade_in=0.3,
                fade_out=0.8,
            ),
        ],
        title="dvg short",
    )
    comp.save(OUT_DIR / "composition.json")

    print("[3/3] rendering...")
    t1 = time.perf_counter()
    result = comp.render(OUT_DIR / "final.mp4", crf=18, preset="medium")
    print(f"  ✓ {time.perf_counter() - t1:.1f}s — LUFS={result.audio_lufs}, peak={result.audio_peak_dbfs}")

    shutil.copy(OUT_DIR / "final.mp4", ROOT / "runs/_demos/dvg_short_v1.mp4")
    shutil.copy(OUT_DIR / "composition.json", ROOT / "runs/_demos/dvg_short_v1_composition.json")
    size_mb = (ROOT / "runs/_demos/dvg_short_v1.mp4").stat().st_size / 1024 / 1024
    print(f"  → runs/_demos/dvg_short_v1.mp4 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
