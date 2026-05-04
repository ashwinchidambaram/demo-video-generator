"""Smoke test: ShapeLayer rect renders end-to-end via ffmpeg drawbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from dvg import (
    AudioLayer,
    CaptionLayer,
    Composition,
    Mood,
    ShapeLayer,
    VideoLayer,
)
from dvg.models import Anchor as A

FIXTURE = Path(__file__).parents[1] / "fixtures/video/fixture_12s.mp4"
SOUNDTRACK = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-edm.mp3"
)


@pytest.mark.skipif(
    not FIXTURE.exists() or not SOUNDTRACK.exists(),
    reason="fixture missing",
)
def test_shape_layer_renders(tmp_path: Path) -> None:
    """A composition with a ShapeLayer rect renders successfully."""
    comp = Composition(
        fps=30, width=1280, height=720, duration=4.0,
        layers=[
            VideoLayer(src=FIXTURE, time=(0, 4), fit="cover"),
            ShapeLayer(
                shape="rect",
                bbox=(60, 580, 1160, 80),  # bottom strip
                fill="#3b82f6",
                opacity=0.65,
                time=(0.5, 3.5),
            ),
            CaptionLayer(
                text="On the strip",
                mood=Mood.EXPLAIN,
                time=(0.7, 3.3),
                anchor=A.BOTTOM_CENTER,
            ),
        ],
        audio=[AudioLayer(src=SOUNDTRACK, time=(0, 4))],
    )
    out = tmp_path / "shape.mp4"
    result = comp.render(out, preset="ultrafast", crf=28)
    assert out.exists()
    assert result.audio_lufs is not None
    assert -16 <= result.audio_lufs <= -12
