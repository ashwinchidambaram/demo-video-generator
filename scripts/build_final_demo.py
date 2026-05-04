"""Build the final dvg-of-dvg demo video.

Captures the polished landing-page fixture, then composes:
  - libass title card (0..2.8s)
  - captured footage (2.5..19.5s)
  - 6 narration captions over footage
  - libass end card with install command (19.5..22s)
  - vibe-edm soundtrack with sidechain ducking under captions
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
    TitleLayer,
    VideoLayer,
)
from dvg.capture import capture_url
from dvg.models import Anchor as A
from dvg.models import Theme

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests/fixtures/site/index.html"
SOUNDTRACK = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-edm.mp3"
)
OUT_DIR = ROOT / "runs/final_demo"


async def _capture() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    url = f"file://{FIXTURE.resolve()}"
    result = await capture_url(
        url,
        out_dir=OUT_DIR,
        duration=14.0,
        width=1920,
        height=1080,
        fps=30,
        scenario="tour",
        headed=False,
    )
    return result.video_path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/4] capturing fixture site...")
    t0 = time.perf_counter()
    video_path = asyncio.run(_capture())
    print(f"  ✓ {video_path} ({time.perf_counter() - t0:.1f}s)")

    print("[2/4] building hand-crafted composition...")
    theme = Theme(color_accent="#3b82f6")
    comp = Composition(
        fps=30,
        width=1920,
        height=1080,
        duration=22.0,
        background="#0a0a0a",
        theme=theme,
        layers=[
            # Big title card 0..2.8s — libass for clean typography
            TitleLayer(
                title="dvg",
                subtitle="production demo videos in one command",
                time=(0.0, 2.8),
                align=A.MIDDLE_CENTER,
                title_size=200,
                subtitle_size=42,
                title_color="#ffffff",
                subtitle_color="#9ca3af",
                fade_in=0.5,
                fade_out=0.5,
            ),
            # Captured footage 2.5..19.5s (overlaps title fadeout); ken burns
            VideoLayer(
                src=video_path,
                time=(2.5, 19.5),
                fit="cover",
                fade_in=0.5,
                fade_out=0.4,
                ken_burns=0.04,
            ),
            # Narration captions over footage
            CaptionLayer(
                text="Capture any URL with Playwright",
                mood=Mood.ANNOUNCE,
                time=(3.4, 5.6),
                anchor=A.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="DOM events become scenes and anchors",
                mood=Mood.EXPLAIN,
                time=(6.0, 8.5),
                anchor=A.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="One brain picks the music and captions",
                mood=Mood.EXPLAIN,
                time=(9.0, 11.5),
                anchor=A.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="libass + ffmpeg",
                mood=Mood.PUNCHLINE,
                time=(12.0, 14.0),
                anchor=A.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="Zero Chromium per render",
                mood=Mood.PUNCHLINE,
                time=(14.5, 16.5),
                anchor=A.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="Faster than a webpack bundle",
                mood=Mood.TAGLINE,
                time=(17.0, 19.2),
                anchor=A.BOTTOM_CENTER,
            ),
            # End card 19.5..22s
            TitleLayer(
                title="dvg make-video <url>",
                subtitle="pip install dvg",
                time=(19.6, 22.0),
                align=A.MIDDLE_CENTER,
                title_size=80,
                subtitle_size=44,
                title_color="#ffffff",
                subtitle_color="#9ca3af",
                fade_in=0.4,
                fade_out=0.4,
            ),
        ],
        audio=[
            AudioLayer(
                src=SOUNDTRACK,
                time=(0.0, 22.0),
                role="music",
                target_lufs=-22.0,
                duck_under_captions=True,
                fade_in=0.5,
                fade_out=1.5,
            ),
        ],
        title="dvg",
        description="production demo videos in one command",
    )
    comp.save(OUT_DIR / "composition.json")
    print(f"  ✓ composition saved ({len(comp.layers)} layers)")

    print("[3/4] rendering...")
    t1 = time.perf_counter()
    result = comp.render(OUT_DIR / "final.mp4", crf=18, preset="medium")
    print(f"  ✓ rendered in {time.perf_counter() - t1:.1f}s ({result.duration_s:.1f}s ffmpeg)")
    print(f"     LUFS={result.audio_lufs}, peak={result.audio_peak_dbfs} dBFS")

    print("[4/4] copying to _demos/")
    shutil.copy(OUT_DIR / "final.mp4", ROOT / "runs/_demos/dvg_demo_v1.mp4")
    shutil.copy(OUT_DIR / "composition.json", ROOT / "runs/_demos/dvg_demo_v1_composition.json")
    size_mb = (ROOT / "runs/_demos/dvg_demo_v1.mp4").stat().st_size / 1024 / 1024
    print(f"  ✓ runs/_demos/dvg_demo_v1.mp4 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
