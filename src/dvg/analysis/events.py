"""Event-log analysis: turn DOM events from capture into scenes + anchors.

A `Scene` is a contiguous block of activity. An `Anchor` is a notable event
(click, navigation, input-burst-end, scroll-stop) that the director can use
to anchor caption timing.

This is the deterministic primary analysis pass. A visual gap-filler runs
when events are sparse (e.g. screen recording without DOM hooks).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Anchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="stable id like 'click_0', 'nav_1'")
    t: float
    kind: Literal["click", "input_end", "navigation", "scroll_stop", "page_load", "scene_start"]
    label: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    time: tuple[float, float]
    anchors: list[Anchor] = Field(default_factory=list)
    energy: float = Field(0.0, description="event density 0..1")
    description: str | None = None  # filled by director or visual analyst


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    duration_s: float
    scenes: list[Scene] = Field(default_factory=list)
    anchors: list[Anchor] = Field(default_factory=list)  # all anchors flattened
    source: Literal["events", "visual", "merged"] = "events"


# ---- analysis pipeline --------------------------------------------------


def analyze_events(
    events: list[dict[str, Any]],
    duration: float,
    *,
    scene_gap: float = 1.5,
    scroll_stop_window: float = 0.4,
) -> Analysis:
    """Compute scenes + anchors from a DOM event list.

    Heuristics:
    - Sort by t.
    - Group into scenes by gaps > scene_gap (with no events).
    - Promote events to anchors: clicks, navigations, page_load.
    - Detect scroll stops: scroll events followed by `scroll_stop_window` of silence.
    - Detect input bursts: contiguous input events; emit input_end at last.
    """
    sorted_events = sorted(events, key=lambda e: e.get("t", 0.0))

    scenes = _group_into_scenes(sorted_events, duration, scene_gap)
    all_anchors: list[Anchor] = []

    click_n = 0
    nav_n = 0
    input_n = 0
    scroll_n = 0

    # promote events
    for i, ev in enumerate(sorted_events):
        t = float(ev.get("t", 0.0))
        kind = ev.get("type")
        detail = ev.get("detail", {}) or {}

        if kind == "click":
            click_n += 1
            label = (detail.get("text") or detail.get("tag") or "click").strip()
            anchor = Anchor(
                id=f"click_{click_n - 1}",
                t=t,
                kind="click",
                label=label[:60] or "click",
                detail=detail,
            )
            all_anchors.append(anchor)

        elif kind == "navigation":
            nav_n += 1
            to = detail.get("to") or detail.get("url") or ""
            anchor = Anchor(
                id=f"nav_{nav_n - 1}",
                t=t,
                kind="navigation",
                label=f"→ {to}"[:60],
                detail=detail,
            )
            all_anchors.append(anchor)

        elif kind == "page_load":
            anchor = Anchor(
                id="page_load",
                t=t,
                kind="page_load",
                label="page loaded",
                detail=detail,
            )
            all_anchors.append(anchor)

        elif kind == "scroll":
            # detect a scroll stop: this event is a scroll, and either it's the
            # last event OR the next event is > scroll_stop_window away (or non-scroll).
            is_last = i == len(sorted_events) - 1
            if not is_last:
                nxt = sorted_events[i + 1]
                if nxt.get("type") == "scroll" and float(nxt.get("t", 0.0)) - t < scroll_stop_window:
                    continue  # not a stop yet
            scroll_n += 1
            anchor = Anchor(
                id=f"scroll_stop_{scroll_n - 1}",
                t=t + scroll_stop_window / 2,
                kind="scroll_stop",
                label="scroll stop",
                detail=detail,
            )
            all_anchors.append(anchor)

    # detect input bursts
    input_burst_start: float | None = None
    input_burst_end: float | None = None
    for ev in sorted_events:
        if ev.get("type") == "input":
            t = float(ev.get("t", 0.0))
            if input_burst_start is None:
                input_burst_start = t
            input_burst_end = t
        else:
            if input_burst_end is not None and input_burst_start is not None:
                input_n += 1
                all_anchors.append(
                    Anchor(
                        id=f"input_end_{input_n - 1}",
                        t=input_burst_end,
                        kind="input_end",
                        label="input complete",
                    )
                )
                input_burst_start = None
                input_burst_end = None
    if input_burst_end is not None:
        input_n += 1
        all_anchors.append(
            Anchor(
                id=f"input_end_{input_n - 1}",
                t=input_burst_end,
                kind="input_end",
                label="input complete",
            )
        )

    # attach anchors to scenes
    for scene in scenes:
        scene.anchors = [a for a in all_anchors if scene.time[0] <= a.t <= scene.time[1]]

    all_anchors.sort(key=lambda a: a.t)

    return Analysis(
        duration_s=duration,
        scenes=scenes,
        anchors=all_anchors,
        source="events",
    )


def _group_into_scenes(
    events: list[dict[str, Any]], duration: float, gap: float
) -> list[Scene]:
    if not events:
        return [Scene(id="scene_0", time=(0.0, duration), energy=0.0)]

    times = [float(e.get("t", 0.0)) for e in events]
    boundaries: list[float] = [0.0]
    for i in range(1, len(times)):
        if times[i] - times[i - 1] > gap:
            mid = (times[i - 1] + times[i]) / 2.0
            boundaries.append(mid)
    boundaries.append(duration)

    scenes: list[Scene] = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        # count events in this window
        n = sum(1 for t in times if s <= t < e)
        density = min(1.0, n / max(1.0, e - s) / 4.0)  # 4 events/sec → 1.0
        scenes.append(
            Scene(
                id=f"scene_{i}",
                time=(s, e),
                energy=density,
            )
        )
    return scenes
