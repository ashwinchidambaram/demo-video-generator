"""Tests for event-log analysis (events → scenes + anchors)."""

from __future__ import annotations

from dvg.analysis.events import analyze_events


def test_empty_events() -> None:
    a = analyze_events([], duration=10.0)
    assert a.duration_s == 10.0
    assert len(a.scenes) == 1
    assert a.scenes[0].time == (0.0, 10.0)
    assert len(a.anchors) == 0
    assert a.source == "events"


def test_single_click_anchor() -> None:
    events = [
        {"t": 1.0, "type": "page_load", "detail": {}},
        {"t": 3.5, "type": "click", "detail": {"text": "Get started"}},
    ]
    a = analyze_events(events, duration=10.0)
    kinds = sorted({anchor.kind for anchor in a.anchors})
    assert "click" in kinds
    assert "page_load" in kinds
    click = next(anchor for anchor in a.anchors if anchor.kind == "click")
    assert click.label == "Get started"


def test_input_burst_collapses_to_one_anchor() -> None:
    events = [
        {"t": 1.0, "type": "input", "detail": {"len": 1}},
        {"t": 1.2, "type": "input", "detail": {"len": 2}},
        {"t": 1.4, "type": "input", "detail": {"len": 3}},
        {"t": 5.0, "type": "click", "detail": {"text": "submit"}},
    ]
    a = analyze_events(events, duration=10.0)
    input_anchors = [anchor for anchor in a.anchors if anchor.kind == "input_end"]
    assert len(input_anchors) == 1
    assert input_anchors[0].t == 1.4


def test_scenes_split_on_gap() -> None:
    """A gap larger than scene_gap should produce separate scenes."""
    events = [
        {"t": 0.5, "type": "page_load"},
        {"t": 1.0, "type": "scroll", "detail": {"y": 100}},
        # 4 second gap >> default 1.5s
        {"t": 5.5, "type": "click", "detail": {"text": "x"}},
        {"t": 6.0, "type": "scroll", "detail": {"y": 200}},
    ]
    a = analyze_events(events, duration=10.0)
    assert len(a.scenes) >= 2


def test_scroll_stop_emitted_after_silence() -> None:
    events = [
        {"t": 1.0, "type": "scroll", "detail": {"y": 100}},
        {"t": 1.1, "type": "scroll", "detail": {"y": 200}},
        # last scroll, then silence — should be a scroll_stop
    ]
    a = analyze_events(events, duration=5.0)
    stops = [anchor for anchor in a.anchors if anchor.kind == "scroll_stop"]
    assert len(stops) >= 1
