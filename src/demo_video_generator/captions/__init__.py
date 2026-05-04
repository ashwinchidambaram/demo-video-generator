"""Captions subcommand.

Phase 7: supports both default-stub authoring AND brief-driven authoring
where the caller provides a JSON brief describing the subject + intent.
The caption-writer agent (per .claude/agents/caption-writer/design.md)
will eventually replace this with LLM-driven authoring; until then this
module supplies the deterministic substrate that hand-authored briefs
turn into schema-valid captions.json.

A brief looks like:

  {
    "title": "demo-video-generator",
    "tagline": "9 agents, one deterministic driver.",
    "explainers": [
      "Anchored captions resolve to absolute timing.",
      "Schemas are the source of truth.",
      ...
    ],
    "callouts": [{"text": "<- music: vibe-flow", "anchor_event_idx": 1}],
    "punchline": "It just works."
  }

Brief is loaded from `manifest.config.captions_brief` (path) or the
`DVG_CAPTIONS_BRIEF` env var. Without a brief we fall back to the Phase 1
stub authoring (announce/explain/tagline anchored to the synthesized
events).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic


def _load_brief(run_dir: Path) -> dict[str, Any] | None:
    brief_path_str = os.environ.get("DVG_CAPTIONS_BRIEF")
    if not brief_path_str:
        manifest_path = run_dir / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text())
                brief_path_str = (manifest.get("config") or {}).get("captions_brief")
            except (json.JSONDecodeError, KeyError):
                brief_path_str = None
    if not brief_path_str:
        return None
    brief_path = Path(brief_path_str)
    if not brief_path.is_file():
        return None
    try:
        brief: dict[str, Any] = json.loads(brief_path.read_text())
        return brief
    except json.JSONDecodeError:
        return None


def author_from_brief(
    *,
    brief: dict[str, Any],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert a brief + events list into anchored captions.

    Strategy:
    - title       → mood=announce, anchored to first event
    - explainers  → mood=explain, anchored to events evenly distributed
    - callouts    → mood=callout, anchored to event at provided index
    - punchline   → mood=punchline, anchored to penultimate event
    - tagline     → mood=tagline, anchored to last event with -0.5s pre-roll
    """
    captions: list[dict[str, Any]] = []
    if not events:
        return captions

    cap_id = 0

    def add(cap: dict[str, Any]) -> None:
        nonlocal cap_id
        cap_id += 1
        cap.setdefault("id", f"c{cap_id}")
        captions.append(cap)

    title = brief.get("title")
    if title:
        add(
            {
                "text": title,
                "mood": "announce",
                "anchor_event_id": events[0]["id"],
                "intent_duration": 3.0,
                "anchor_offset": 0.0,
                "priority": 5,
            }
        )

    explainers: list[str] = list(brief.get("explainers") or [])
    if explainers:
        # Distribute explainers across the inner events (skip first + last).
        inner = events[1:-1] if len(events) >= 3 else events
        for i, line in enumerate(explainers):
            if not inner:
                break
            anchor = inner[min(i, len(inner) - 1)]
            add(
                {
                    "text": line,
                    "mood": "explain",
                    "anchor_event_id": anchor["id"],
                    "intent_duration": 2.5,
                    "anchor_offset": 0.0,
                    "priority": 4,
                }
            )

    for callout in brief.get("callouts") or []:
        idx = int(callout.get("anchor_event_idx", 0))
        idx = max(0, min(idx, len(events) - 1))
        add(
            {
                "text": callout["text"],
                "mood": "callout",
                "anchor_event_id": events[idx]["id"],
                "intent_duration": float(callout.get("intent_duration", 2.5)),
                "anchor_offset": float(callout.get("anchor_offset", 0.0)),
                "priority": int(callout.get("priority", 3)),
            }
        )

    punchline = brief.get("punchline")
    if punchline and len(events) >= 2:
        anchor = events[-2]
        add(
            {
                "text": punchline,
                "mood": "punchline",
                "anchor_event_id": anchor["id"],
                "intent_duration": 1.8,
                "anchor_offset": 0.0,
                "priority": 5,
            }
        )

    tagline = brief.get("tagline")
    if tagline:
        add(
            {
                "text": tagline,
                "mood": "tagline",
                "anchor_event_id": events[-1]["id"],
                "intent_duration": 3.0,
                "anchor_offset": -0.5,
                "priority": 5,
            }
        )

    return captions


def _default_captions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Phase 1 fallback authoring: announce -> explain -> tagline."""
    captions: list[dict[str, Any]] = []
    if not events:
        return captions
    captions.append(
        {
            "id": "c1",
            "text": "demo-video-generator",
            "mood": "announce",
            "anchor_event_id": events[0]["id"],
            "intent_duration": 2.5,
            "anchor_offset": 0.0,
            "priority": 5,
        }
    )
    if len(events) >= 2:
        mid = events[len(events) // 2]
        captions.append(
            {
                "id": "c2",
                "text": "Walks the manifest.",
                "mood": "explain",
                "anchor_event_id": mid["id"],
                "intent_duration": 2.5,
                "anchor_offset": 0.0,
                "priority": 4,
            }
        )
    captions.append(
        {
            "id": "c3",
            "text": "Deterministic by design.",
            "mood": "tagline",
            "anchor_event_id": events[-1]["id"],
            "intent_duration": 3.0,
            "anchor_offset": -0.5,
            "priority": 5,
        }
    )
    return captions


def stub_captions(analysis_path: Path, out_path: Path) -> dict[str, Any]:
    """Driver entry. Reads analysis events; if a brief is configured uses it,
    otherwise falls back to default authoring."""
    analysis = json.loads(analysis_path.read_text())
    events = analysis.get("events", [])
    run_dir = out_path.parent

    brief = _load_brief(run_dir)
    if brief is not None:
        captions = author_from_brief(brief=brief, events=events)
    else:
        captions = _default_captions(events)

    payload = {"schema_version": 1, "captions": captions}
    write_json_atomic(out_path, payload)
    return payload
