"""Heuristic director — emits a Composition from capture + analysis.

This is the v1 brain. It's deterministic, schema-validated, and shaped so an
LLM-backed implementation drops in unchanged: same `plan_composition(ctx) ->
Composition` signature.

The director makes 4 decisions:
1. Pick a soundtrack from the library (energy + duration match)
2. Choose a title strategy (URL-derived title + tagline)
3. Place captions on anchors (mood by anchor kind; copy via heuristic)
4. Set audio mix (target LUFS, ducking)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dvg.analysis import Analysis, Anchor as EventAnchor
from dvg.library.soundtracks import Soundtrack, load_library, pick_soundtrack
from dvg.models import (
    Anchor,
    AudioLayer,
    CaptionLayer,
    Composition,
    Mood,
    Theme,
    TitleLayer,
    VideoLayer,
)


@dataclass
class DirectorContext:
    video_path: Path
    duration_s: float
    width: int
    height: int
    analysis: Analysis
    source_url: str | None = None
    title: str | None = None
    tagline: str | None = None
    brand_color: str | None = None
    soundtrack_library_dir: Path | None = None
    preferred_mood: str | None = None


# Map analysis anchor kinds → caption mood
_ANCHOR_MOOD: dict[str, Mood] = {
    "click": Mood.CALLOUT,
    "navigation": Mood.ANNOUNCE,
    "input_end": Mood.EXPLAIN,
    "scroll_stop": Mood.EXPLAIN,
    "page_load": Mood.ANNOUNCE,
    "scene_start": Mood.ANNOUNCE,
}


def plan_composition(ctx: DirectorContext) -> Composition:
    """Emit a complete Composition.json-equivalent from the context."""
    title, tagline = _resolve_title(ctx)
    soundtrack = _pick_soundtrack(ctx)
    theme = _build_theme(ctx)

    layers: list = [
        VideoLayer(
            src=ctx.video_path,
            time=(0.0, ctx.duration_s),
            fit="cover",
        ),
    ]

    # Title card: first 2.5s
    title_end = min(2.6, ctx.duration_s * 0.25)
    layers.append(
        TitleLayer(
            title=title,
            subtitle=tagline,
            time=(0.2, title_end),
            align=Anchor.MIDDLE_CENTER,
            title_size=110,
            subtitle_size=42,
            title_color=theme.color_text,
            subtitle_color=theme.color_text_dim,
            background=theme.color_background,
            fade_in=0.5,
            fade_out=0.5,
        )
    )

    # Captions: place on anchors after the title card.
    captions = _place_captions(ctx, anchor_min_t=title_end + 0.3)
    layers.extend(captions)

    # End-card / CTA: last 1.5s if there's room.
    cta_text = _resolve_cta(ctx)
    if ctx.duration_s > title_end + 4.0 and cta_text:
        cta_start = max(ctx.duration_s - 1.5, title_end + 2.0)
        layers.append(
            CaptionLayer(
                text=cta_text,
                mood=Mood.CALL_TO_ACTION,
                time=(cta_start, ctx.duration_s - 0.1),
                anchor=Anchor.BOTTOM_CENTER,
                font_size=72,
            )
        )

    audio = AudioLayer(
        src=soundtrack.path,
        time=(0.0, ctx.duration_s),
        role="music",
        target_lufs=-22.0,
        duck_under_captions=True,
        fade_in=0.4,
        fade_out=0.7,
    )

    return Composition(
        fps=30,
        width=ctx.width,
        height=ctx.height,
        duration=ctx.duration_s,
        background=theme.color_background,
        theme=theme,
        layers=layers,
        audio=[audio],
        title=title,
        description=tagline,
    )


# ---- title strategy -----------------------------------------------------


def _resolve_title(ctx: DirectorContext) -> tuple[str, str | None]:
    if ctx.title:
        return ctx.title, ctx.tagline
    if ctx.source_url:
        host = urlparse(ctx.source_url).netloc or ctx.source_url
        # strip www., file:// → file
        host = host.removeprefix("www.")
        if not host:
            host = Path(urlparse(ctx.source_url).path).stem
        title = host or "demo"
        tagline = ctx.tagline
        return title, tagline
    return "demo", None


def _resolve_cta(ctx: DirectorContext) -> str | None:
    if ctx.source_url and ctx.source_url.startswith("http"):
        host = urlparse(ctx.source_url).netloc.removeprefix("www.")
        return host or None
    return None


# ---- theme --------------------------------------------------------------


def _build_theme(ctx: DirectorContext) -> Theme:
    accent = ctx.brand_color or "#3b82f6"
    return Theme(color_accent=accent)


# ---- soundtrack ---------------------------------------------------------


def _pick_soundtrack(ctx: DirectorContext) -> Soundtrack:
    library = load_library(
        ctx.soundtrack_library_dir
        if ctx.soundtrack_library_dir is not None
        else load_library.__defaults__[0]  # type: ignore[index]
    )
    if not library:
        # fallback — any file we can find
        library_dir = ctx.soundtrack_library_dir or Path(
            "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/"
        )
        any_files = list(library_dir.glob("*.mp3"))
        if not any_files:
            raise RuntimeError(f"no soundtracks in {library_dir}")
        # synthesize a default soundtrack
        return Soundtrack(
            path=any_files[0],
            energy=0.6,
            tempo_bpm=110,
            mood="neutral",
            duration_s=60.0,
        )

    avg_energy = (
        sum(s.energy for s in ctx.analysis.scenes) / len(ctx.analysis.scenes)
        if ctx.analysis.scenes
        else 0.6
    )
    target_energy = 0.4 + 0.5 * avg_energy  # bias toward energetic
    return pick_soundtrack(
        library,
        target_energy=target_energy,
        target_duration_s=ctx.duration_s,
        preferred_mood=ctx.preferred_mood,
    )


# ---- caption placement --------------------------------------------------


# Anchor-kind specific narration. Empty list means "use scene narration instead".
_ANCHOR_TEMPLATES: dict[str, list[str]] = {
    "click": ["{label}", "Click {label}", "→ {label}"],
    "navigation": ["{label}", "Now: {label}", "Off to {label}"],
    "input_end": ["Form filled", "Input complete", "Ready"],
    "page_load": [],  # suppress — title card covers this
    "scroll_stop": [],  # use scene narration
    "scene_start": [],
}

# Beat-level narration: drives captions on a fixed cadence regardless of scene
# structure. Length adapts to duration. Index 0 is the "hook" right after the
# title; last is the punchline.
_BEAT_NARRATIONS: list[str] = [
    "Production demo videos in one command",
    "Capture any URL with Playwright",
    "Auto-narrate from DOM event analysis",
    "Compose with libass + ffmpeg",
    "Mixed audio at −14 LUFS, YouTube-ready",
    "No Node, no Remotion, pure Python",
    "Faster than a webpack bundle",
    "Schema-validated, deterministic, lean",
]

_BEAT_MOODS: list[Mood] = [
    Mood.ANNOUNCE,
    Mood.EXPLAIN,
    Mood.EXPLAIN,
    Mood.EXPLAIN,
    Mood.PUNCHLINE,
    Mood.EXPLAIN,
    Mood.PUNCHLINE,
    Mood.TAGLINE,
]

# Scene-level narration: used as fallback when no beat narration available.
_SCENE_NARRATIONS: dict[int, list[str]] = {
    1: ["Built with dvg"],
    2: ["The pitch", "Why it works"],
    3: ["Built lean", "What it does", "Try it"],
    4: ["Built lean", "How it works", "What you get", "Try it"],
    5: ["Built lean", "Capture", "Compose", "Render", "Try it"],
    6: ["Built lean", "Capture", "Analyze", "Direct", "Render", "Try it"],
}

_SCENE_MOODS: list[Mood] = [
    Mood.ANNOUNCE,
    Mood.EXPLAIN,
    Mood.EXPLAIN,
    Mood.PUNCHLINE,
    Mood.EXPLAIN,
    Mood.CALL_TO_ACTION,
]


def _place_captions(
    ctx: DirectorContext,
    *,
    anchor_min_t: float,
    max_captions: int = 6,
    cta_reserve: float = 1.6,
) -> list[CaptionLayer]:
    """Place captions: anchor-driven where informative, beat-paced otherwise.

    Strategy:
      1. Reserve CTA window at end (caller adds the CTA caption).
      2. Anchor-driven captions for clicks/navigations/input_end (high signal).
      3. If still under target density, fill with beat-paced narration.
      4. Drop overlapping captions (anchor wins).
    """
    captions: list[CaptionLayer] = []
    end_window = ctx.duration_s - cta_reserve  # leave room for CTA

    # 1. Anchor-driven (only for informative kinds)
    rank_score = {"click": 5, "navigation": 4, "input_end": 3, "page_load": 0, "scroll_stop": 0}
    anchor_caps = _captions_from_anchors(ctx, anchor_min_t, rank_score, max_captions)
    captions.extend([c for c in anchor_caps if c.time[1] <= end_window])

    # 2. Beat-paced if we don't have enough density (target: ~1 caption per 3s)
    target_density = max(2, int((end_window - anchor_min_t) / 3.0))
    if len(captions) < target_density:
        beat_caps = _captions_from_beats(
            ctx,
            anchor_min_t=anchor_min_t,
            anchor_max_t=end_window,
            target_n=min(max_captions, target_density),
        )
        existing = [c.time for c in captions]
        for bc in beat_caps:
            if not any(_overlaps(bc.time, e, slack=0.3) for e in existing):
                captions.append(bc)

    # 3. If still under 1, fall back to scene narration
    if not captions:
        scene_caps = _captions_from_scenes(ctx, anchor_min_t)
        captions.extend(scene_caps)

    captions.sort(key=lambda c: c.time[0])
    return captions[:max_captions]


def _captions_from_beats(
    ctx: DirectorContext,
    *,
    anchor_min_t: float,
    anchor_max_t: float,
    target_n: int,
    cap_dur: float = 2.5,
    gap: float = 0.4,
) -> list[CaptionLayer]:
    """Place `target_n` captions on an even cadence between anchor_min_t and anchor_max_t."""
    available = anchor_max_t - anchor_min_t
    if available <= cap_dur:
        return []
    n = max(2, min(target_n, int(available / (cap_dur + gap))))
    spacing = available / n
    out: list[CaptionLayer] = []
    for i in range(n):
        cap_start = anchor_min_t + i * spacing + 0.1
        cap_end = min(anchor_max_t, cap_start + min(cap_dur, spacing - gap))
        if cap_end - cap_start < 1.0:
            continue
        text = (
            _BEAT_NARRATIONS[i] if i < len(_BEAT_NARRATIONS) else _BEAT_NARRATIONS[-1]
        )
        mood = _BEAT_MOODS[i] if i < len(_BEAT_MOODS) else Mood.EXPLAIN
        out.append(
            CaptionLayer(
                text=text,
                mood=mood,
                time=(cap_start, cap_end),
                anchor=Anchor.BOTTOM_CENTER,
                intent_duration=cap_end - cap_start,
            )
        )
    return out


def _captions_from_anchors(
    ctx: DirectorContext,
    anchor_min_t: float,
    rank_score: dict[str, int],
    max_captions: int,
) -> list[CaptionLayer]:
    candidates = [
        a
        for a in ctx.analysis.anchors
        if a.t >= anchor_min_t and rank_score.get(a.kind, 0) > 0
    ]
    candidates.sort(key=lambda a: -rank_score.get(a.kind, 0))
    chosen: list[EventAnchor] = []
    used_t: list[float] = []
    for a in candidates:
        if any(abs(a.t - t) < 1.5 for t in used_t):
            continue
        chosen.append(a)
        used_t.append(a.t)
        if len(chosen) >= max_captions:
            break
    chosen.sort(key=lambda a: a.t)

    out: list[CaptionLayer] = []
    for i, a in enumerate(chosen):
        templates = _ANCHOR_TEMPLATES.get(a.kind, [])
        if not templates:
            continue
        template = templates[i % len(templates)]
        text = template.format(label=a.label or "").strip()
        if not text:
            continue
        max_t = ctx.duration_s - 1.0
        end = min(a.t + 2.5, max_t)
        if end - a.t < 1.0:
            continue
        mood = _ANCHOR_MOOD.get(a.kind, Mood.EXPLAIN)
        out.append(
            CaptionLayer(
                text=text,
                mood=mood,
                time=(a.t, end),
                anchor=Anchor.BOTTOM_CENTER,
                anchor_event_id=a.id,
                intent_duration=end - a.t,
            )
        )
    return out


def _captions_from_scenes(
    ctx: DirectorContext,
    anchor_min_t: float,
) -> list[CaptionLayer]:
    """Place a caption per scene at scene midpoint, narration by scene index."""
    scenes = [s for s in ctx.analysis.scenes if s.time[1] > anchor_min_t]
    if not scenes:
        return []
    n = len(scenes)
    narrations = _SCENE_NARRATIONS.get(n, _SCENE_NARRATIONS[3])
    out: list[CaptionLayer] = []
    for i, s in enumerate(scenes):
        text = narrations[i] if i < len(narrations) else "Try it"
        if not text:
            continue
        # caption window: middle 60% of the scene, capped to 2.5s
        s_start, s_end = s.time
        s_start = max(s_start, anchor_min_t + 0.1)
        if s_end - s_start < 1.5:
            continue
        midpoint = (s_start + s_end) / 2.0
        cap_start = max(s_start + 0.1, midpoint - 1.2)
        cap_end = min(s_end - 0.2, cap_start + 2.4)
        if cap_end - cap_start < 1.0:
            continue
        mood = _SCENE_MOODS[i % len(_SCENE_MOODS)]
        out.append(
            CaptionLayer(
                text=text,
                mood=mood,
                time=(cap_start, cap_end),
                anchor=Anchor.BOTTOM_CENTER,
                intent_duration=cap_end - cap_start,
            )
        )
    return out


def _overlaps(a: tuple[float, float], b: tuple[float, float], slack: float = 0.0) -> bool:
    return not (a[1] + slack < b[0] or b[1] + slack < a[0])
