"""H1 demo: prove end-to-end render. Output committed to runs/demo_h1/."""

from __future__ import annotations

from pathlib import Path

from dvg import (
    AudioLayer,
    CaptionLayer,
    Composition,
    Mood,
    TitleLayer,
    VideoLayer,
)
from dvg.models import Anchor

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests/fixtures/video/fixture_12s.mp4"
SOUNDTRACK = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-edm.mp3"
)
OUT_DIR = ROOT / "runs/demo_h1"

if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    comp = Composition(
        fps=30,
        width=1920,
        height=1080,
        duration=12.0,
        background="#0a0a0a",
        layers=[
            VideoLayer(src=FIXTURE, time=(0, 12), fit="cover"),
            TitleLayer(
                title="dvg",
                subtitle="lean demo-video generator",
                time=(0.0, 2.5),
                align=Anchor.MIDDLE_CENTER,
                title_size=120,
                subtitle_size=44,
                fade_in=0.5,
                fade_out=0.5,
            ),
            CaptionLayer(
                text="Composition is a Pydantic model",
                mood=Mood.ANNOUNCE,
                time=(3.0, 5.5),
                anchor=Anchor.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="No bundling, no Chromium",
                mood=Mood.PUNCHLINE,
                time=(6.0, 8.5),
                anchor=Anchor.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="ffmpeg + libass = production-grade",
                mood=Mood.EXPLAIN,
                time=(9.0, 11.0),
                anchor=Anchor.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="dvg.dev",
                mood=Mood.CALL_TO_ACTION,
                time=(11.2, 12.0),
                anchor=Anchor.BOTTOM_CENTER,
                font_size=72,
            ),
        ],
        audio=[
            AudioLayer(
                src=SOUNDTRACK,
                time=(0, 12),
                role="music",
                target_lufs=-22.0,
                duck_under_captions=True,
                fade_in=0.5,
                fade_out=0.8,
            ),
        ],
    )
    comp.save(OUT_DIR / "composition.json")
    result = comp.render(OUT_DIR / "final.mp4", keep_intermediates=True)
    print(f"Wrote {result.out}")
    print(f"  duration: {result.duration_s:.2f}s")
    print(f"  LUFS: {result.audio_lufs}")
    print(f"  peak: {result.audio_peak_dbfs} dBFS")
