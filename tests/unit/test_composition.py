"""Tests for Phase 6 composition-director judgment:
- collision resolution
- style preset selection
- audio-QA-driven gain tuning
"""

from __future__ import annotations

import json
from pathlib import Path

from demo_video_generator.composition import (
    _gain_from_audio_qa,
    _resolve_collisions,
    _select_style_preset,
)


def _cap(
    cid: str,
    *,
    start: float,
    end: float,
    priority: int,
    mood: str = "explain",
) -> dict:
    return {
        "id": cid,
        "text": cid,
        "mood": mood,
        "start": start,
        "end": end,
        "priority": priority,
        "anchor_event_id": "evt-1",
        "duck_window": None,
    }


# ---------- _resolve_collisions ----------


def test_no_overlap_keeps_all() -> None:
    caps = [
        _cap("a", start=0, end=1, priority=3),
        _cap("b", start=2, end=3, priority=3),
    ]
    kept, dropped = _resolve_collisions(caps)
    assert len(kept) == 2
    assert dropped == []


def test_lower_priority_dropped_when_overlapping() -> None:
    caps = [
        _cap("a", start=0, end=2, priority=5, mood="announce"),
        _cap("b", start=1, end=3, priority=2, mood="aside"),
    ]
    kept, dropped = _resolve_collisions(caps)
    assert [c["id"] for c in kept] == ["a"]
    assert len(dropped) == 1
    assert dropped[0]["id"] == "b"
    assert dropped[0]["reason"] == "priority_collision"


def test_equal_priority_first_placed_wins() -> None:
    """Sorted by priority desc then start; equal priority → earlier start wins."""
    caps = [
        _cap("a", start=0, end=2, priority=4),
        _cap("b", start=1, end=3, priority=4),
    ]
    kept, dropped = _resolve_collisions(caps)
    assert [c["id"] for c in kept] == ["a"]
    assert len(dropped) == 1


def test_brief_overlap_under_threshold_kept() -> None:
    """Overlap < 0.3s threshold doesn't trigger drop."""
    caps = [
        _cap("a", start=0.0, end=1.0, priority=4),
        _cap("b", start=0.95, end=2.0, priority=3),
    ]
    kept, _ = _resolve_collisions(caps)
    assert len(kept) == 2  # 0.05s overlap < 0.3s threshold


# ---------- _select_style_preset ----------


def test_punchline_dominant_picks_punchline_bold() -> None:
    caps = [_cap(f"c{i}", start=i, end=i + 1, priority=5, mood="punchline") for i in range(4)]
    caps.append(_cap("c5", start=5, end=6, priority=3, mood="explain"))
    preset = _select_style_preset(caps, [{"energy": "high"}])
    assert preset == "punchline-bold"


def test_announce_dominant_picks_announce_clean() -> None:
    caps = [_cap(f"c{i}", start=i, end=i + 1, priority=5, mood="announce") for i in range(3)]
    preset = _select_style_preset(caps, [{"energy": "medium"}])
    assert preset == "announce-clean"


def test_aside_dominant_picks_explain_soft() -> None:
    """Holdout case 2 from the agent design — aside-heavy with high
    visual energy. Right answer is 'explain-soft' (mood signal dominates,
    not energy)."""
    caps = [_cap(f"c{i}", start=i, end=i + 1, priority=2, mood="aside") for i in range(3)]
    caps.append(_cap("c4", start=4, end=5, priority=3, mood="explain"))
    preset = _select_style_preset(caps, [{"energy": "high"}, {"energy": "high"}])
    assert preset == "explain-soft"


def test_low_energy_explain_picks_explain_soft() -> None:
    caps = [_cap(f"c{i}", start=i, end=i + 1, priority=4, mood="explain") for i in range(3)]
    preset = _select_style_preset(
        caps, [{"energy": "low"}, {"energy": "low"}, {"energy": "medium"}]
    )
    assert preset == "explain-soft"


def test_empty_captions_neutral_default() -> None:
    assert _select_style_preset([], []) == "neutral"


# ---------- _gain_from_audio_qa ----------


def test_gain_from_audio_qa_no_file_returns_default(tmp_path: Path) -> None:
    """Without a prior audio_qa.json, default to -1 dB attenuation."""
    gain = _gain_from_audio_qa(tmp_path / "missing.json", target_lufs=-14)
    assert gain == -1.0


def test_gain_from_audio_qa_too_hot_attenuates_further(tmp_path: Path) -> None:
    """Prior render measured -12 LUFS (2 LU too hot); should bump attenuation by 2 dB."""
    qa_path = tmp_path / "audio_qa.json"
    qa_path.write_text(
        json.dumps({"measurements": {"ebur128": {"integrated_lufs": -12.0}}}),
    )
    gain = _gain_from_audio_qa(qa_path, target_lufs=-14)
    # delta = -12 - (-14) = 2 → recommend gain -1 - 2 = -3 dB
    assert gain == -3.0


def test_gain_from_audio_qa_too_quiet_clamps_at_zero(tmp_path: Path) -> None:
    """Prior render too quiet; we never AMPLIFY (max gain is 0)."""
    qa_path = tmp_path / "audio_qa.json"
    qa_path.write_text(
        json.dumps({"measurements": {"ebur128": {"integrated_lufs": -20.0}}}),
    )
    gain = _gain_from_audio_qa(qa_path, target_lufs=-14)
    assert gain == 0.0  # clamped


def test_gain_from_audio_qa_malformed_returns_default(tmp_path: Path) -> None:
    qa_path = tmp_path / "audio_qa.json"
    qa_path.write_text("{not valid json")
    gain = _gain_from_audio_qa(qa_path, target_lufs=-14)
    assert gain == -1.0
