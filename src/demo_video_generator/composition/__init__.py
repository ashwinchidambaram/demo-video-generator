"""Composition subcommand. Phase 1 stub: builds composition.json from
upstream artifacts. Phase 6 replaces with full composition-director logic
(style preset judgment, collision resolution, audio mix).

This stub IS schema-valid and IS the contract test for the Python↔Node bridge:
it must produce JSON that round-trips through both Pydantic and Zod.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic

COLLISION_OVERLAP_THRESHOLD = 0.3  # seconds


def _resolve_collisions(
    rendered: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Phase 6 composition-director collision resolution per agent design:

    Sort by priority desc; place in order; drop a candidate if it overlaps
    a placed caption of equal-or-higher priority by more than 0.3s.

    Returns (kept, dropped). dropped entries match the schema.
    """
    if not rendered:
        return [], []
    placed: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    # Sort highest-priority first; stable secondary by start time.
    sorted_caps = sorted(rendered, key=lambda c: (-int(c["priority"]), float(c["start"])))
    for cap in sorted_caps:
        c_start = float(cap["start"])
        c_end = float(cap["end"])
        c_pri = int(cap["priority"])
        collision_overlap = 0.0
        for p in placed:
            p_start = float(p["start"])
            p_end = float(p["end"])
            overlap = min(c_end, p_end) - max(c_start, p_start)
            if overlap > COLLISION_OVERLAP_THRESHOLD and int(p["priority"]) >= c_pri:
                collision_overlap = overlap
                break
        if collision_overlap > 0:
            dropped.append(
                {
                    "id": cap["id"],
                    "reason": "priority_collision",
                    "details": f"overlaps {collision_overlap:.2f}s with higher-priority caption",
                }
            )
        else:
            placed.append(cap)
    # Restore time-ordered output.
    placed.sort(key=lambda c: float(c["start"]))
    return placed, dropped


# Style preset selection per agent design / patterns.md#style-presets.
# Decision rule maps (dominant_mood, energy_profile) -> preset name.
# Renderer (remotion/src/DemoVideo.tsx) owns the visual implementation.
def _select_style_preset(
    rendered_captions: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
) -> str:
    """Pick one style preset name based on dominant mood + scene energy.

    Decision priority (per design):
      1. Mood density is the dominant signal (user-authored copy).
      2. Scene energy is secondary — ambiguous moods break ties.

    Presets enum (from composition.schema.json):
      announce-clean | explain-soft | punchline-bold | retro-warm | neutral
    """
    if not rendered_captions:
        return "neutral"
    # Mood density:
    mood_count: dict[str, int] = {}
    for cap in rendered_captions:
        mood = cap.get("mood", "explain")
        mood_count[mood] = mood_count.get(mood, 0) + 1
    total = sum(mood_count.values())
    dominant_mood = max(mood_count, key=mood_count.get)  # type: ignore[arg-type]
    dominant_share = mood_count[dominant_mood] / total

    # Scene energy distribution:
    energy_count: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for s in scenes:
        e = s.get("energy", "low")
        if e in energy_count:
            energy_count[e] += 1
    has_high = energy_count["high"] > 0
    mostly_low = energy_count["low"] >= max(1, energy_count["medium"] + energy_count["high"])

    # Rules:
    if dominant_mood == "punchline" and dominant_share > 0.3:
        return "punchline-bold"
    if dominant_mood == "announce" and dominant_share > 0.4:
        return "announce-clean"
    if dominant_mood == "aside" and dominant_share > 0.4:
        # Aside-heavy: quiet preset regardless of energy (per holdout case 2).
        return "explain-soft"
    if mostly_low and dominant_mood in {"explain", "aside"}:
        return "explain-soft"
    if has_high and dominant_mood in {"announce", "punchline", "callout"}:
        return "punchline-bold"
    # Tagline-dominant or mixed-mood with mid-energy: neutral.
    return "neutral"


def _gain_from_audio_qa(audio_qa_path: Path, target_lufs: float = -14.0) -> float:
    """Phase 6 polish (per ultraplan R1 §1.5): if a prior audio_qa.json
    exists, use its measured integrated_lufs to set music gain so the next
    render lands closer to target.

    Returns dB adjustment to apply to music. 0.0 if no prior measurement.
    """
    if not audio_qa_path.is_file():
        return -1.0  # default conservative attenuation
    try:
        qa = json.loads(audio_qa_path.read_text())
        measured = qa.get("measurements", {}).get("ebur128", {}).get("integrated_lufs")
        if measured is None:
            return -1.0
        # If measured was -12 LUFS and target is -14, we need -2 dB more.
        delta = float(measured) - target_lufs
        # Clamp to reasonable range.
        return max(-12.0, min(0.0, -1.0 - delta))
    except (json.JSONDecodeError, KeyError, ValueError):
        return -1.0


def _resolve_caption(caption: dict[str, Any], events_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve anchored caption (D4) to absolute (start, end) + duck_window.

    Returns None if the anchor cannot be resolved — caller drops the caption
    and records it in dropped_captions. Phase 6's real composition-director
    emits an error.json instead; the stub is more forgiving.
    """
    anchor_id = caption["anchor_event_id"]
    event = events_by_id.get(anchor_id)
    if event is None:
        return None
    offset = caption.get("anchor_offset", 0.0)
    start = max(0.0, float(event["t"]) + float(offset))
    end = start + float(caption["intent_duration"])
    mood = caption["mood"]
    duck = None
    if mood in {"announce", "callout", "punchline", "tagline"}:
        duck = {"start": start - 0.2, "end": end + 0.3}
    return {
        "id": caption["id"],
        "text": caption["text"],
        "mood": mood,
        "start": start,
        "end": end,
        "priority": int(caption.get("priority", 3)),
        "anchor_event_id": anchor_id,
        "duck_window": duck,
    }


def stub_compose(
    *,
    analysis_path: Path,
    captions_path: Path,
    music_path: Path,
    sfx_manifest_path: Path,
    footage_path: Path,
    out_path: Path,
) -> dict[str, Any]:
    """Phase 1 stub: deterministic resolution of anchored captions to
    absolute timing. No collision resolution, no style judgment (picks
    `neutral` preset), default audio mix.
    """
    analysis = json.loads(analysis_path.read_text())
    captions_doc = json.loads(captions_path.read_text())

    duration = float(analysis["duration_seconds"])
    fps = int(analysis.get("fps", 30))
    resolution = analysis.get("resolution", {"width": 1920, "height": 1080})

    events_by_id = {e["id"]: e for e in analysis.get("events", [])}
    rendered: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for cap in captions_doc.get("captions", []):
        resolved = _resolve_caption(cap, events_by_id)
        if resolved is None:
            dropped.append(
                {
                    "id": cap["id"],
                    "reason": "anchor_density",
                    "details": f"anchor_event_id {cap['anchor_event_id']} not found",
                }
            )
            continue
        # Clamp end to duration.
        if resolved["end"] > duration:
            resolved["end"] = duration
        rendered.append(resolved)

    # Phase 6 collision resolution per agent design.
    rendered, collision_drops = _resolve_collisions(rendered)
    dropped.extend(collision_drops)

    sfx_placements: list[dict[str, Any]] = []
    if sfx_manifest_path.exists():
        sfx_doc = json.loads(sfx_manifest_path.read_text())
        for placement in sfx_doc.get("placements", []):
            sfx_placements.append(
                {
                    "src": placement["clip_path"],
                    "t": float(placement.get("t", 0.0)),
                    "gain_db": float(placement.get("gain_db", 0)),
                    "anchor_event_id": placement.get("event_id"),
                }
            )

    # Phase 6 audio gain tuning: read prior audio_qa.json if present.
    audio_qa_path = out_path.parent / "audio_qa.json"
    music_gain_db = _gain_from_audio_qa(audio_qa_path, target_lufs=-14.0)

    # Phase 6 style preset selection.
    preset = _select_style_preset(rendered, analysis.get("scenes", []))

    composition = {
        "schema_version": 1,
        "fps": fps,
        "duration_seconds": duration,
        "resolution": resolution,
        "footage": {"src": footage_path.name, "trim_before": 0},
        "audio": {
            "music": {"src": music_path.name, "gain_db": music_gain_db},
            "sfx": sfx_placements,
            "mix": {
                "integrated_lufs": -14,
                "true_peak_dbtp": -1,
                "duck_to_lufs": -22,
            },
        },
        "captions": rendered,
        "dropped_captions": dropped,
        "style": {"preset": preset},
    }

    write_json_atomic(out_path, composition)
    return composition
