"""Tests for the soundtrack picker."""

from __future__ import annotations

from pathlib import Path

import pytest

from dvg.library.soundtracks import Soundtrack, pick_soundtrack


def _mk(path: str, energy: float, tempo: float, mood: str, dur: float) -> Soundtrack:
    return Soundtrack(path=Path(path), energy=energy, tempo_bpm=tempo, mood=mood, duration_s=dur)


def test_picks_closest_energy() -> None:
    library = [
        _mk("/a", 0.2, 90, "chill", 60),
        _mk("/b", 0.6, 110, "neutral", 60),
        _mk("/c", 0.9, 130, "edm", 60),
    ]
    high = pick_soundtrack(library, target_energy=0.85, target_duration_s=10.0)
    assert high.mood == "edm"
    low = pick_soundtrack(library, target_energy=0.15, target_duration_s=10.0)
    assert low.mood == "chill"


def test_penalizes_short_tracks() -> None:
    library = [
        _mk("/short", 0.6, 110, "neutral", 5),  # too short for 30s comp
        _mk("/long", 0.6, 110, "neutral", 60),
    ]
    pick = pick_soundtrack(library, target_energy=0.6, target_duration_s=30.0)
    assert pick.path == Path("/long")


def test_preferred_mood_breaks_tie() -> None:
    library = [
        _mk("/edm", 0.7, 120, "edm", 60),
        _mk("/flow", 0.7, 120, "flow", 60),
    ]
    pick = pick_soundtrack(
        library, target_energy=0.7, target_duration_s=10.0, preferred_mood="flow"
    )
    assert pick.mood == "flow"


def test_empty_library_raises() -> None:
    with pytest.raises(ValueError):
        pick_soundtrack([], target_energy=0.5, target_duration_s=10.0)
