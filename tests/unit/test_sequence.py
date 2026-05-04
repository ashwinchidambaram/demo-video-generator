"""Tests for Sequence (composability) flattening."""

from __future__ import annotations

from pathlib import Path

from dvg import (
    AudioLayer,
    CaptionLayer,
    Composition,
    Mood,
    Sequence,
    VideoLayer,
)

FIXTURE = Path(__file__).parents[1] / "fixtures/video/fixture_12s.mp4"


def test_flatten_no_sequences_is_passthrough() -> None:
    comp = Composition(
        fps=30, width=1920, height=1080, duration=10.0,
        layers=[
            CaptionLayer(text="hi", mood=Mood.EXPLAIN, time=(1, 3)),
        ],
    )
    flat = comp.flatten()
    assert len(flat.layers) == 1
    assert flat.layers[0].time == (1.0, 3.0)


def test_flatten_simple_sequence() -> None:
    comp = Composition(
        fps=30, width=1920, height=1080, duration=10.0,
        layers=[
            Sequence(
                time=(2.0, 8.0),
                layers=[
                    CaptionLayer(text="seq cap", mood=Mood.EXPLAIN, time=(0, 2)),
                    CaptionLayer(text="seq cap 2", mood=Mood.EXPLAIN, time=(2, 4)),
                ],
            ),
        ],
    )
    flat = comp.flatten()
    # Two child captions shifted by sequence start (2.0)
    caption_layers = [layer for layer in flat.layers if layer.kind == "caption"]
    assert len(caption_layers) == 2
    assert caption_layers[0].time == (2.0, 4.0)
    assert caption_layers[1].time == (4.0, 6.0)


def test_flatten_sequence_clamps_overflow() -> None:
    """Children whose time exceeds the sequence window get clamped/dropped."""
    comp = Composition(
        fps=30, width=1920, height=1080, duration=10.0,
        layers=[
            Sequence(
                time=(2.0, 5.0),  # 3-sec window
                layers=[
                    # this child wants to be 0..4s relative, but seq only allows 3s
                    CaptionLayer(text="overflow", mood=Mood.EXPLAIN, time=(0, 4)),
                ],
            ),
        ],
    )
    flat = comp.flatten()
    caps = [layer for layer in flat.layers if layer.kind == "caption"]
    assert len(caps) == 1
    # clamped to [2.0, 5.0]
    assert caps[0].time == (2.0, 5.0)


def test_flatten_sequence_audio_shifted() -> None:
    sound = "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/vibe-edm.mp3"
    comp = Composition(
        fps=30, width=1920, height=1080, duration=10.0,
        layers=[
            Sequence(
                time=(2.0, 8.0),
                layers=[],
                audio=[AudioLayer(src=Path(sound), time=(0, 6))],
            ),
        ],
    )
    flat = comp.flatten()
    assert len(flat.audio) == 1
    assert flat.audio[0].time == (2.0, 8.0)


def test_nested_sequences_flatten() -> None:
    comp = Composition(
        fps=30, width=1920, height=1080, duration=20.0,
        layers=[
            Sequence(
                time=(2.0, 18.0),
                layers=[
                    Sequence(
                        time=(0.0, 6.0),  # relative to outer; absolute: 2..8
                        layers=[
                            CaptionLayer(text="deep", mood=Mood.EXPLAIN, time=(1, 3)),
                        ],
                    ),
                ],
            ),
        ],
    )
    flat = comp.flatten()
    caps = [layer for layer in flat.layers if layer.kind == "caption"]
    assert len(caps) == 1
    # absolute time: outer offset (2.0) + inner offset (0.0) + child (1.0..3.0)
    assert caps[0].time == (3.0, 5.0)
