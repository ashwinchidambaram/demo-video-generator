"""Pydantic models for compositions, layers, audio, and the manifest.

Single source of schema truth for the lean stack.
A `Composition` is JSON-serializable; that's `composition.json` in a run dir.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dvg.keyframes import Keyframe

if TYPE_CHECKING:
    from dvg.composition.render import RenderResult as RenderResultLike

# ---- Animation primitives -------------------------------------------------


# A track is either a constant value or a keyframe list.
# In JSON: a constant scalar/tuple OR a list of {"t","v","e"} dicts.
ScalarTrack = float | int | list[Keyframe]
PairTrack = tuple[float, float] | list[Keyframe]
TripleTrack = tuple[float, float, float] | list[Keyframe]


class Mood(str, Enum):
    """Caption mood. Maps to a libass style preset + optional motion."""

    ANNOUNCE = "announce"
    EXPLAIN = "explain"
    PUNCHLINE = "punchline"
    ASIDE = "aside"
    CALLOUT = "callout"
    TAGLINE = "tagline"
    CALL_TO_ACTION = "call_to_action"


class Anchor(str, Enum):
    TOP_LEFT = "top-left"
    TOP_CENTER = "top-center"
    TOP_RIGHT = "top-right"
    MIDDLE_LEFT = "middle-left"
    MIDDLE_CENTER = "middle-center"
    MIDDLE_RIGHT = "middle-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT = "bottom-right"


class Fit(str, Enum):
    """Like CSS object-fit."""

    COVER = "cover"
    CONTAIN = "contain"
    FILL = "fill"
    NONE = "none"


# ---- Layer base + variants ------------------------------------------------


class Transform(BaseModel):
    """Time-varying transform applied to a layer.

    Each field is either a constant or a list of Keyframes (layer-relative time).
    Position is in canvas pixels; scale is multiplicative on prepared layer size;
    rotation is degrees; opacity is 0..1.
    """

    model_config = ConfigDict(extra="forbid")

    position: tuple[float, float] | list[Keyframe] | None = None
    scale: float | list[Keyframe] = 1.0
    rotation: float | list[Keyframe] = 0.0
    opacity: float | list[Keyframe] = 1.0


class _LayerBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    time: tuple[float, float] = Field(..., description="(start, end) in seconds")
    z: int = 0
    opacity: float = Field(1.0, ge=0.0, le=1.0)

    fade_in: float = 0.0
    fade_out: float = 0.0
    transform: Transform | None = None

    @model_validator(mode="after")
    def _check_time(self) -> Self:
        if self.time[1] <= self.time[0]:
            raise ValueError(f"layer time {self.time} must have end > start")
        if self.fade_in < 0 or self.fade_out < 0:
            raise ValueError("fades must be >= 0")
        if self.fade_in + self.fade_out > (self.time[1] - self.time[0]):
            raise ValueError("fade_in + fade_out exceeds layer duration")
        return self

    @property
    def duration(self) -> float:
        return self.time[1] - self.time[0]


class VideoLayer(_LayerBase):
    kind: Literal["video"] = "video"
    src: Path
    fit: Fit = Fit.COVER
    mute: bool = True  # by default audio comes from AudioLayer not VideoLayer
    speed: float = Field(1.0, gt=0)
    crop: tuple[float, float, float, float] | None = Field(
        None, description="(x, y, w, h) in 0..1 of source frame"
    )
    # Subtle zoom over time, ala Ken Burns. 0 = static. 0.05 = zoom from 1.0
    # to 1.05 over the layer's duration. Implemented via crop + scale.
    ken_burns: float = Field(
        0.0, ge=0.0, le=0.5, description="end zoom factor (0=static)"
    )


class ImageLayer(_LayerBase):
    kind: Literal["image"] = "image"
    src: Path
    anchor: Anchor = Anchor.MIDDLE_CENTER
    scale: float = 1.0
    offset: tuple[int, int] = (0, 0)


class CaptionLayer(_LayerBase):
    kind: Literal["caption"] = "caption"
    text: str
    mood: Mood = Mood.EXPLAIN
    anchor: Anchor = Anchor.BOTTOM_CENTER
    margin: int = Field(80, description="px from anchor edge")
    max_width_pct: float = Field(0.7, gt=0, le=1.0)

    # Style overrides. None ⇒ use mood preset.
    font: str | None = None
    font_size: int | None = None
    color: str | None = None  # &H00BBGGRR ASS or #RRGGBB
    outline: float | None = None
    shadow: float | None = None

    # Anchor metadata (filled by director). Not used by renderer; for re-edit.
    anchor_event_id: str | None = None
    intent_duration: float | None = None
    priority: int = 0


class TitleLayer(_LayerBase):
    """Multi-line title card with optional subtitle. Composite layer."""

    kind: Literal["title"] = "title"
    title: str
    subtitle: str | None = None
    background: str = "#0a0a0a"
    title_color: str = "#ffffff"
    subtitle_color: str = "#9ca3af"
    title_size: int = 96
    subtitle_size: int = 36
    align: Anchor = Anchor.MIDDLE_CENTER


class ShapeLayer(_LayerBase):
    """Vector shape (rect/circle/line). Skia backend."""

    kind: Literal["shape"] = "shape"
    shape: Literal["rect", "circle", "line", "rounded_rect"]
    bbox: tuple[int, int, int, int]  # (x, y, w, h)
    fill: str | None = None  # #RRGGBB or rgba(...)
    stroke: str | None = None
    stroke_width: float = 0.0
    radius: float = 0.0


class HTMLLayer(_LayerBase):
    """Render an HTML template via Playwright to a frame sequence.

    Slowest backend; use only when CSS-grade fidelity is required.
    """

    kind: Literal["html"] = "html"
    template: Path | str  # path to HTML file or inline HTML
    props: dict[str, str | int | float | bool] = Field(default_factory=dict)
    bbox: tuple[int, int, int, int] | None = None  # None ⇒ full canvas
    transparent: bool = True
    fps_override: int | None = None


class Sequence(_LayerBase):
    """A nested composition: contains layers with their own timeline.

    Child layer times are RELATIVE to this Sequence's start. At render time,
    Sequence is flattened into the parent: each child's time is shifted by the
    Sequence start, and the children are appended to the parent layer list.

    Sequences can nest. Their own `time` (start, end) clamps the inner span;
    children outside that range are dropped.
    """

    kind: Literal["sequence"] = "sequence"
    layers: list[Layer] = Field(default_factory=list)
    audio: list[AudioLayer] = Field(default_factory=list)


Layer = Annotated[
    VideoLayer
    | ImageLayer
    | CaptionLayer
    | TitleLayer
    | ShapeLayer
    | HTMLLayer
    | Sequence,
    Field(discriminator="kind"),
]


# ---- Audio ---------------------------------------------------------------


class AudioLayer(BaseModel):
    """Audio track. Music or SFX. ffmpeg pre-mix produces a single stem."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    src: Path
    time: tuple[float, float] = Field(..., description="(start, end) in seconds, -1 end ⇒ full")
    role: Literal["music", "sfx"] = "music"

    target_lufs: float = Field(-22.0, description="loudnorm target before final mix")
    volume: float = Field(1.0, ge=0)
    fade_in: float = 0.0
    fade_out: float = 0.0
    duck_under_captions: bool = False
    duck_db: float = Field(-9.0, description="dB attenuation under duck windows")

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.time[1] != -1 and self.time[1] <= self.time[0]:
            raise ValueError(f"audio time {self.time} invalid")
        return self


# ---- Composition ---------------------------------------------------------


class Theme(BaseModel):
    """Global typography + color tokens."""

    model_config = ConfigDict(extra="forbid")

    font_family: str = "Inter"
    font_family_mono: str = "JetBrains Mono"
    color_text: str = "#ffffff"
    color_text_dim: str = "#9ca3af"
    color_accent: str = "#3b82f6"
    color_background: str = "#0a0a0a"
    color_caption_bg: str = "#000000aa"


class Composition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    fps: int = 30
    width: int = 1920
    height: int = 1080
    duration: float = Field(..., gt=0)
    background: str = "#0a0a0a"
    theme: Theme = Field(default_factory=Theme)

    layers: list[Layer] = Field(default_factory=list)
    audio: list[AudioLayer] = Field(default_factory=list)

    final_loudness: float = Field(-14.0, description="integrated LUFS target")
    peak_dbfs: float = Field(-1.0, description="true peak ceiling")

    title: str | None = None  # for metadata
    description: str | None = None

    def render(self, out: str | Path, **kwargs: object) -> RenderResultLike:
        """Convenience: build → render. See dvg.composition.render.render()."""
        from dvg.composition.render import render

        return render(self, out, **kwargs)  # type: ignore[arg-type]

    def flatten(self) -> Composition:
        """Return a new Composition with all Sequences expanded inline."""

        flat_layers: list[Layer] = []
        flat_audio: list[AudioLayer] = list(self.audio)
        _flatten_into(self.layers, flat_layers, flat_audio, time_offset=0.0)
        out = self.model_copy(update={"layers": flat_layers, "audio": flat_audio})
        return out

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: str | Path) -> Composition:
        return cls.model_validate_json(Path(path).read_text())


# ---- Sequence flattening ------------------------------------------------


def _flatten_into(
    layers: list[Layer],
    out_layers: list[Layer],
    out_audio: list[AudioLayer],
    *,
    time_offset: float,
) -> None:
    """Recursively expand Sequence layers into a flat list."""
    for layer in layers:
        if isinstance(layer, Sequence):
            seq_start, seq_end = layer.time
            shift = time_offset + seq_start
            # recurse: children get their times shifted by `shift`, and clamped
            # to the sequence's (start, end) window.
            for child in layer.layers:
                shifted_child = _shift_and_clip(
                    child, shift=shift, clamp=(time_offset + seq_start, time_offset + seq_end)
                )
                if shifted_child is not None:
                    if isinstance(shifted_child, Sequence):
                        _flatten_into(
                            [shifted_child], out_layers, out_audio, time_offset=0.0
                        )
                    else:
                        out_layers.append(shifted_child)
            for audio in layer.audio:
                end = audio.time[1] if audio.time[1] != -1 else (seq_end - seq_start)
                shifted_a = audio.model_copy(
                    update={"time": (audio.time[0] + shift, end + shift)}
                )
                out_audio.append(shifted_a)
        else:
            shifted = _shift_and_clip(layer, shift=time_offset, clamp=None)
            if shifted is not None:
                out_layers.append(shifted)


def _shift_and_clip(
    layer: Layer,
    *,
    shift: float,
    clamp: tuple[float, float] | None,
) -> Layer | None:
    """Return a copy of layer with time shifted by `shift` and clamped to `clamp`."""
    s = layer.time[0] + shift
    e = layer.time[1] + shift
    if clamp is not None:
        c0, c1 = clamp
        s = max(s, c0)
        e = min(e, c1)
        if e <= s:
            return None
    return layer.model_copy(update={"time": (s, e)})


# ---- Manifest (driver state) --------------------------------------------


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class StageRecord(BaseModel):
    name: str
    status: StageStatus = StageStatus.PENDING
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    cost_usd: float = 0.0
    duration_s: float | None = None
    depends_on: list[str] = Field(default_factory=list)


class Manifest(BaseModel):
    schema_version: int = 2
    run_id: str
    input: str
    config: dict[str, object] = Field(default_factory=dict)
    stages: list[StageRecord] = Field(default_factory=list)
    created_at: float
    updated_at: float


# ---- Telemetry rubric ---------------------------------------------------


class TelemetryRow(BaseModel):
    """One row per `dvg make-video` run, appended to runs/_telemetry.jsonl."""

    run_id: str
    ts: float
    input: str
    duration_s: float | None = None
    output_path: str | None = None
    output_size_bytes: int | None = None
    output_lufs: float | None = None
    output_peak_dbfs: float | None = None
    output_length_s: float | None = None
    caption_count: int | None = None
    caption_density: float | None = None  # captions per 10s
    render_time_s: float | None = None
    mood_distribution: dict[str, int] = Field(default_factory=dict)
    stage_costs_usd: dict[str, float] = Field(default_factory=dict)
    rubric: dict[str, int] | None = None  # PM-filled, optional
    notes: str | None = None
