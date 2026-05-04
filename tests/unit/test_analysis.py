"""Unit tests for the deterministic event-log clustering algorithm."""

from __future__ import annotations

from demo_video_generator.analysis import (
    DEFAULT_CLUSTER_GAP_SECONDS,
    _cluster_events,
    analyze_events_driven,
)


def _ev(eid: str, t: float, kind: str = "click", label: str | None = None) -> dict:
    return {"id": eid, "t": t, "kind": kind, "label": label, "payload": {}}


def test_cluster_events_groups_by_gap() -> None:
    """Events less than DEFAULT_CLUSTER_GAP_SECONDS apart cluster together."""
    events = [
        _ev("a", 0.0),
        _ev("b", 0.5),  # within gap of a
        _ev("c", 5.0),  # new cluster (>gap from b)
        _ev("d", 5.3),  # within gap of c
    ]
    clusters = _cluster_events(events, gap=DEFAULT_CLUSTER_GAP_SECONDS)
    assert len(clusters) == 2
    assert [e["id"] for e in clusters[0]] == ["a", "b"]
    assert [e["id"] for e in clusters[1]] == ["c", "d"]


def test_cluster_events_handles_empty() -> None:
    assert _cluster_events([]) == []


def test_cluster_events_sorts_by_time() -> None:
    """Out-of-order input still clusters correctly (stable on time)."""
    events = [_ev("a", 5.0), _ev("b", 0.5), _ev("c", 0.0)]
    clusters = _cluster_events(events)
    # First cluster should be the early events; second the late one.
    assert [e["id"] for e in clusters[0]] == ["c", "b"]
    assert [e["id"] for e in clusters[1]] == ["a"]


def test_analyze_events_driven_high_energy_dominates() -> None:
    """Cluster energy is the max over the cluster's event kinds."""
    events_log = {
        "schema_version": 1,
        "events": [
            _ev("a", 0.0, kind="click"),  # medium
            _ev("b", 0.3, kind="submit"),  # high
        ],
        "duration_seconds": 5.0,
        "fps": 30,
        "resolution": {"width": 1920, "height": 1080},
    }
    analysis = analyze_events_driven(events_log)
    assert len(analysis["scenes"]) == 1
    assert analysis["scenes"][0]["energy"] == "high"


def test_analyze_events_driven_no_events_emits_visual_placeholder() -> None:
    """No events → one source='visual' placeholder scene + synthetic anchors."""
    events_log = {
        "schema_version": 1,
        "events": [],
        "duration_seconds": 10.0,
        "fps": 30,
        "resolution": {"width": 1920, "height": 1080},
    }
    analysis = analyze_events_driven(events_log)
    assert len(analysis["scenes"]) == 1
    assert analysis["scenes"][0]["source"] == "visual"
    # Synthetic anchors so caption-writer / sfx-curator have something to use.
    assert len(analysis["events"]) == 3


def test_analyze_events_driven_preserves_event_ids() -> None:
    """Event ids round-trip exactly (caption-anchor invariant)."""
    events_log = {
        "schema_version": 1,
        "events": [_ev("very-stable-id", 1.0)],
        "duration_seconds": 5.0,
        "fps": 30,
        "resolution": {"width": 1920, "height": 1080},
    }
    analysis = analyze_events_driven(events_log)
    assert analysis["events"][0]["id"] == "very-stable-id"
