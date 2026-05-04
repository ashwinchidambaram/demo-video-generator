"""Tests for the heuristic director."""

from __future__ import annotations

from pathlib import Path

import pytest

from dvg.analysis.events import Analysis, Scene
from dvg.analysis.events import Anchor as EventAnchor
from dvg.director.heuristic import DirectorContext, plan_composition
from dvg.models import CaptionLayer, TitleLayer, VideoLayer

FIXTURE = Path(__file__).parents[1] / "fixtures/video/fixture_12s.mp4"
SOUNDTRACK_DIR = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/"
)


@pytest.mark.skipif(
    not FIXTURE.exists() or not SOUNDTRACK_DIR.exists(),
    reason="fixture or soundtrack dir missing",
)
def test_plan_composition_basic_url() -> None:
    """A URL + minimal analysis should produce a valid composition."""
    analysis = Analysis(
        duration_s=12.0,
        scenes=[Scene(id="s0", time=(0, 12), energy=0.5)],
        anchors=[EventAnchor(id="page_load", t=0.1, kind="page_load", label="loaded")],
    )
    ctx = DirectorContext(
        video_path=FIXTURE,
        duration_s=12.0,
        width=1920,
        height=1080,
        analysis=analysis,
        source_url="https://example.com",
        title="example",
        tagline="a tagline",
    )
    comp = plan_composition(ctx)
    assert comp.duration == 12.0
    assert comp.width == 1920
    assert any(isinstance(layer, VideoLayer) for layer in comp.layers)
    assert any(isinstance(layer, TitleLayer) for layer in comp.layers)
    assert len(comp.audio) == 1


@pytest.mark.skipif(
    not FIXTURE.exists() or not SOUNDTRACK_DIR.exists(),
    reason="fixture or soundtrack dir missing",
)
def test_custom_narrations_used() -> None:
    """Caller-supplied narrations override the heuristic defaults."""
    analysis = Analysis(
        duration_s=10.0,
        scenes=[Scene(id="s0", time=(0, 10), energy=0.5)],
        anchors=[EventAnchor(id="page_load", t=0.1, kind="page_load", label="loaded")],
    )
    custom = ["First", "Second", "Third"]
    ctx = DirectorContext(
        video_path=FIXTURE,
        duration_s=10.0,
        width=1920,
        height=1080,
        analysis=analysis,
        source_url="https://example.com",
        title="example",
        narrations=custom,
    )
    comp = plan_composition(ctx)
    captions = [
        layer for layer in comp.layers if isinstance(layer, CaptionLayer)
    ]
    caption_texts = [c.text for c in captions]
    # at least one of the custom narrations should appear
    assert any(text in caption_texts for text in custom), (
        f"none of {custom!r} in {caption_texts!r}"
    )
