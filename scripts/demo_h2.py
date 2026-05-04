"""H2 demo: animated transforms — logo slides in from offscreen, then settles."""

from __future__ import annotations

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
from dvg.easing import Easing
from dvg.keyframes import Keyframe
from dvg.models import Anchor, Transform

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests/fixtures/video/fixture_12s.mp4"
LOGO = ROOT / "tests/fixtures/logo.png"
SOUNDTRACK = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-flow.mp3"
)
OUT_DIR = ROOT / "runs/demo_h2"

if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Logo slides in from the right edge to top-right corner with ease_out, then
    # settles. Position is in canvas pixels, top-left of the logo image.
    logo_kf = [
        Keyframe(t=0.0, v=(2000.0, 80.0)),  # offscreen right
        Keyframe(t=1.0, v=(1500.0, 80.0), e=Easing.EASE_OUT),  # slide in
    ]

    comp = Composition(
        fps=30,
        width=1920,
        height=1080,
        duration=10.0,
        background="#0a0a0a",
        layers=[
            VideoLayer(src=FIXTURE, time=(0, 10), fit="cover"),
            TitleLayer(
                title="Animated transforms",
                subtitle="Position keyframes via ffmpeg expressions",
                time=(0.5, 3.0),
                align=Anchor.MIDDLE_CENTER,
                title_size=88,
                subtitle_size=36,
                fade_in=0.4,
                fade_out=0.4,
            ),
            ImageLayer(
                src=LOGO,
                time=(0.0, 10.0),
                anchor=Anchor.TOP_LEFT,  # ignored when transform.position is set
                transform=Transform(position=logo_kf),
                fade_in=0.0,
                fade_out=0.4,
            ),
            CaptionLayer(
                text="Each layer can declare keyframed transforms",
                mood=Mood.EXPLAIN,
                time=(3.5, 6.0),
                anchor=Anchor.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="Compiled to ffmpeg expressions — no Chromium",
                mood=Mood.PUNCHLINE,
                time=(6.5, 9.0),
                anchor=Anchor.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="dvg",
                mood=Mood.CALL_TO_ACTION,
                time=(9.2, 10.0),
                anchor=Anchor.BOTTOM_CENTER,
                font_size=72,
            ),
        ],
        audio=[
            AudioLayer(
                src=SOUNDTRACK,
                time=(0, 10),
                role="music",
                target_lufs=-22.0,
                duck_under_captions=True,
                fade_in=0.4,
                fade_out=0.6,
            ),
        ],
    )
    comp.save(OUT_DIR / "composition.json")
    result = comp.render(OUT_DIR / "final.mp4", keep_intermediates=False)
    print(f"Wrote {result.out}")
    print(f"  duration: {result.duration_s:.2f}s")
    print(f"  LUFS: {result.audio_lufs}")
    print(f"  peak: {result.audio_peak_dbfs} dBFS")
