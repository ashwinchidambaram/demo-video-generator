"""Benchmark dvg's render performance.

Renders the same composition at varying complexity and reports:
- composition build time
- ffmpeg render time
- total wall-clock
- output size, LUFS, peak

Prints a markdown table to stdout. Useful for the README and for
regression checks across versions.
"""

from __future__ import annotations

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
from dvg.models import Anchor as A

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests/fixtures/video/fixture_12s.mp4"
LOGO = ROOT / "tests/fixtures/logo.png"
SOUNDTRACK = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-edm.mp3"
)
OUT = ROOT / "runs/_bench"


def build_minimal(duration: float = 12.0) -> Composition:
    return Composition(
        fps=30, width=1920, height=1080, duration=duration,
        layers=[VideoLayer(src=FIXTURE, time=(0, duration), fit="cover")],
        audio=[AudioLayer(src=SOUNDTRACK, time=(0, duration))],
    )


def build_typical(duration: float = 12.0) -> Composition:
    return Composition(
        fps=30, width=1920, height=1080, duration=duration,
        layers=[
            VideoLayer(src=FIXTURE, time=(0, duration), fit="cover", ken_burns=0.04),
            TitleLayer(
                title="Benchmark", subtitle="typical composition",
                time=(0, 2.5), fade_in=0.4, fade_out=0.4,
            ),
            CaptionLayer(text="Caption A", mood=Mood.ANNOUNCE, time=(3, 5)),
            CaptionLayer(text="Caption B", mood=Mood.EXPLAIN, time=(5.5, 7.5)),
            CaptionLayer(text="Caption C", mood=Mood.PUNCHLINE, time=(8, 10)),
            ImageLayer(
                src=LOGO, time=(2, duration - 1),
                anchor=A.TOP_RIGHT, offset=(40, 40), scale=0.4, opacity=0.6,
            ),
        ],
        audio=[AudioLayer(src=SOUNDTRACK, time=(0, duration), duck_under_captions=True)],
    )


def build_heavy(duration: float = 22.0) -> Composition:
    layers: list = [
        VideoLayer(src=FIXTURE, time=(0, duration), fit="cover", ken_burns=0.05),
        TitleLayer(title="Heavy", subtitle="many captions", time=(0, 2.5),
                   fade_in=0.4, fade_out=0.4),
        ImageLayer(src=LOGO, time=(2, duration - 1), anchor=A.TOP_RIGHT,
                   offset=(40, 40), scale=0.4, opacity=0.6),
    ]
    moods = list(Mood)
    for i in range(10):
        s = 3 + i * 1.7
        layers.append(
            CaptionLayer(
                text=f"Caption {i+1}",
                mood=moods[i % len(moods)],
                time=(s, s + 1.4),
            )
        )
    return Composition(
        fps=30, width=1920, height=1080, duration=duration,
        layers=layers,
        audio=[AudioLayer(src=SOUNDTRACK, time=(0, duration), duck_under_captions=True)],
    )


def time_render(comp: Composition, label: str) -> dict[str, float | str | int]:
    OUT.mkdir(parents=True, exist_ok=True)
    out_mp4 = OUT / f"{label}.mp4"
    t0 = time.perf_counter()
    result = comp.render(out_mp4, preset="medium", crf=18, keep_intermediates=False)
    elapsed = time.perf_counter() - t0
    return {
        "label": label,
        "duration_s": comp.duration,
        "layers": len(comp.layers),
        "render_s": result.duration_s,
        "wall_s": elapsed,
        "size_kb": int(out_mp4.stat().st_size / 1024),
        "lufs": float(result.audio_lufs) if result.audio_lufs is not None else 0.0,
        "peak_dbfs": float(result.audio_peak_dbfs) if result.audio_peak_dbfs is not None else 0.0,
    }


def main() -> None:
    if not FIXTURE.exists():
        print(f"[skip] fixture missing: {FIXTURE}")
        return

    print("running 3 benchmark scenarios — minimal / typical / heavy")
    print()
    rows = [
        time_render(build_minimal(), "minimal"),
        time_render(build_typical(), "typical"),
        time_render(build_heavy(), "heavy"),
    ]
    print()
    print("| scenario | layers | output | render | size | LUFS | peak (dBFS) |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        print(
            f"| {r['label']} | {r['layers']} | {r['duration_s']}s | "
            f"{r['render_s']:.2f}s | {int(r['size_kb']) // 1024}.{int(r['size_kb']) % 1024 // 100} MB | "
            f"{r['lufs']:.1f} | {r['peak_dbfs']:.1f} |"
        )


if __name__ == "__main__":
    main()
