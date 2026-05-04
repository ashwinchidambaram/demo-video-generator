"""Caption moods showcase — every mood preset with example copy.

Useful as a reference card. Not narrative; just a visual catalog.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from dvg import (
    AudioLayer,
    CaptionLayer,
    Composition,
    Mood,
    TitleLayer,
)
from dvg.models import Anchor as A

ROOT = Path(__file__).parent.parent
SOUNDTRACK = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/Vibe B.mp3"
)
OUT_DIR = ROOT / "runs/moods_demo"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    duration = 18.0
    moods_with_copy = [
        (Mood.ANNOUNCE, "ANNOUNCE — bold + outlined"),
        (Mood.EXPLAIN, "EXPLAIN — neutral readable text"),
        (Mood.PUNCHLINE, "PUNCHLINE!"),
        (Mood.ASIDE, "(an italic aside)"),
        (Mood.CALLOUT, "Callout → here"),
        (Mood.TAGLINE, "tagline of the moment"),
        (Mood.CALL_TO_ACTION, "Try it now"),
    ]
    n = len(moods_with_copy)
    cap_dur = 2.0
    gap = 0.4
    start = 1.5
    layers = [
        TitleLayer(
            title="Caption moods",
            subtitle="every preset, in order",
            time=(0.0, 1.4),
            align=A.MIDDLE_CENTER,
            title_size=110,
            subtitle_size=42,
            fade_in=0.3,
            fade_out=0.3,
        ),
    ]
    for i, (mood, copy) in enumerate(moods_with_copy):
        s = start + i * (cap_dur + gap)
        e = s + cap_dur
        if e > duration - 0.3:
            break
        layers.append(
            CaptionLayer(
                text=copy,
                mood=mood,
                time=(s, e),
                anchor=A.MIDDLE_CENTER,
            )
        )

    comp = Composition(
        fps=30,
        width=1920,
        height=1080,
        duration=duration,
        background="#0a0a0a",
        layers=layers,
        audio=[
            AudioLayer(
                src=SOUNDTRACK,
                time=(0.0, duration),
                target_lufs=-22.0,
                duck_under_captions=True,
                fade_in=0.3,
                fade_out=0.8,
            ),
        ],
        title="dvg moods showcase",
    )
    comp.save(OUT_DIR / "composition.json")

    print(f"composing {len(layers)} layers, {duration}s ...")
    t0 = time.perf_counter()
    result = comp.render(OUT_DIR / "final.mp4", crf=20, preset="medium")
    print(f"rendered in {time.perf_counter() - t0:.1f}s — LUFS={result.audio_lufs}, peak={result.audio_peak_dbfs}")
    shutil.copy(OUT_DIR / "final.mp4", ROOT / "runs/_demos/dvg_moods_v1.mp4")
    shutil.copy(OUT_DIR / "composition.json", ROOT / "runs/_demos/dvg_moods_v1_composition.json")
    size_mb = (ROOT / "runs/_demos/dvg_moods_v1.mp4").stat().st_size / 1024 / 1024
    print(f"  → runs/_demos/dvg_moods_v1.mp4 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
