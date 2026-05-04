"""Tests for libass file emitter."""

from __future__ import annotations

from dvg.composition.captions.ass import _hex_to_ass_color, compile_ass
from dvg.models import Anchor, CaptionLayer, Composition, Mood, TitleLayer


def test_hex_to_ass_color_rgb() -> None:
    """RRGGBB → ASS &H00BBGGRR& format."""
    assert _hex_to_ass_color("#ffffff") == "&H00FFFFFF&"
    assert _hex_to_ass_color("#000000") == "&H00000000&"
    assert _hex_to_ass_color("#3b82f6") == "&H00F6823B&"  # blue → BGR swap


def test_hex_to_ass_color_with_alpha() -> None:
    """RRGGBBAA → ASS &HAABBGGRR& with inverted alpha."""
    # opaque
    assert _hex_to_ass_color("#000000ff") == "&H00000000&"
    # half-transparent
    half = _hex_to_ass_color("#000000aa")
    assert half.startswith("&H55")  # 255-170=85 → 0x55


def test_compile_ass_minimal() -> None:
    """A composition with one caption emits valid ASS."""
    comp = Composition(
        fps=30, width=1920, height=1080, duration=10.0,
        layers=[CaptionLayer(text="hello", mood=Mood.EXPLAIN, time=(1, 3))],
    )
    out = compile_ass(comp)
    assert "[Script Info]" in out
    assert "[V4+ Styles]" in out
    assert "[Events]" in out
    assert "PlayResX: 1920" in out
    assert "PlayResY: 1080" in out
    assert "WrapStyle: 2" in out
    assert "hello" in out


def test_compile_ass_title_with_subtitle() -> None:
    comp = Composition(
        fps=30, width=1920, height=1080, duration=5.0,
        layers=[
            TitleLayer(
                title="dvg", subtitle="lean",
                time=(0, 2.5), align=Anchor.MIDDLE_CENTER,
                title_size=80, subtitle_size=40,
            ),
        ],
    )
    out = compile_ass(comp)
    # both lines present
    assert "dvg" in out
    assert "lean" in out
    # \N separates them in the same dialogue line
    assert "dvg\\N" in out
    # \pos for absolute centering
    assert "\\pos(960," in out


def test_compile_ass_mood_styles_unique() -> None:
    """Different moods produce different style names."""
    comp = Composition(
        fps=30, width=1920, height=1080, duration=10.0,
        layers=[
            CaptionLayer(text="a", mood=Mood.ANNOUNCE, time=(1, 2)),
            CaptionLayer(text="b", mood=Mood.PUNCHLINE, time=(3, 4)),
        ],
    )
    out = compile_ass(comp)
    assert "cap_announce_" in out
    assert "cap_punchline_" in out


def test_compile_ass_escapes_braces() -> None:
    """Curly braces in caption text don't break the override syntax."""
    comp = Composition(
        fps=30, width=1920, height=1080, duration=10.0,
        layers=[CaptionLayer(text="like {this}", mood=Mood.EXPLAIN, time=(1, 3))],
    )
    out = compile_ass(comp)
    # curly braces should be escaped
    assert "like \\{this\\}" in out
