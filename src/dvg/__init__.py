"""dvg — lean demo-video generator. Multi-backend composition + ffmpeg renderer."""

__version__ = "0.2.0"

from dvg.models import (
    AudioLayer,
    CaptionLayer,
    Composition,
    HTMLLayer,
    ImageLayer,
    Mood,
    ShapeLayer,
    TitleLayer,
    VideoLayer,
)

__all__ = [
    "AudioLayer",
    "CaptionLayer",
    "Composition",
    "HTMLLayer",
    "ImageLayer",
    "Mood",
    "ShapeLayer",
    "TitleLayer",
    "VideoLayer",
]
