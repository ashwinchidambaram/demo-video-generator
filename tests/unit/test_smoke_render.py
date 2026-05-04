"""Smoke test: build a composition and render it end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest

from dvg import (
    AudioLayer,
    CaptionLayer,
    Composition,
    Mood,
    TitleLayer,
    VideoLayer,
)
from dvg.models import Anchor

FIXTURE = Path(__file__).parents[1] / "fixtures/video/fixture_12s.mp4"
SOUNDTRACK = Path("/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-edm.mp3")


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture missing")
@pytest.mark.skipif(not SOUNDTRACK.exists(), reason="soundtrack missing")
def test_render_smoke(tmp_path: Path) -> None:
    comp = Composition(
        fps=30,
        width=1920,
        height=1080,
        duration=10.0,
        background="#0a0a0a",
        layers=[
            VideoLayer(src=FIXTURE, time=(0, 10), fit="cover"),
            TitleLayer(
                title="dvg — built lean",
                subtitle="ffmpeg + libass",
                time=(0.0, 2.0),
                align=Anchor.MIDDLE_CENTER,
                fade_in=0.4,
                fade_out=0.4,
            ),
            CaptionLayer(
                text="Captions render via libass",
                mood=Mood.ANNOUNCE,
                time=(2.5, 5.0),
                anchor=Anchor.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="No bundling, no Chromium",
                mood=Mood.PUNCHLINE,
                time=(5.5, 8.0),
                anchor=Anchor.BOTTOM_CENTER,
            ),
            CaptionLayer(
                text="Try it: dvg",
                mood=Mood.CALL_TO_ACTION,
                time=(8.5, 10.0),
                anchor=Anchor.BOTTOM_CENTER,
            ),
        ],
        audio=[
            AudioLayer(
                src=SOUNDTRACK,
                time=(0, 10),
                role="music",
                target_lufs=-22.0,
                duck_under_captions=True,
            ),
        ],
    )

    out = tmp_path / "out.mp4"
    result = comp.render(out, keep_intermediates=False)

    assert out.exists()
    assert out.stat().st_size > 100_000  # at least ~100KB

    # Audio compliance: should be near -14 LUFS, peak ≤ -1
    assert result.audio_lufs is not None, f"could not measure LUFS, stderr={result.stderr_tail}"
    assert -16 <= result.audio_lufs <= -12, f"LUFS out of band: {result.audio_lufs}"
    assert result.audio_peak_dbfs is not None
    assert result.audio_peak_dbfs <= -0.5, f"peak too hot: {result.audio_peak_dbfs}"
