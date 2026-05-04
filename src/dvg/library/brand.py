"""Brand pack — typography/color/logo defaults for the director.

A brand.json (or .toml) overrides Theme defaults for any composition the
director produces. Resolution order: explicit path > $DVG_BRAND > XDG default.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict


class BrandPack(BaseModel):
    """A brand pack. All fields optional; defaults come from Theme."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    color_text: str | None = None
    color_text_dim: str | None = None
    color_accent: str | None = None
    color_background: str | None = None
    font_family: str | None = None
    logo_path: Path | None = None
    logo_anchor: str = "top-right"
    logo_offset_px: tuple[int, int] = (40, 40)
    logo_scale: float = 0.4
    logo_opacity: float = 0.65

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls.model_validate_json(path.read_text())


def default_brand_path() -> Path | None:
    env = os.environ.get("DVG_BRAND")
    if env:
        p = Path(env)
        if p.exists():
            return p
    xdg = Path.home() / ".config" / "dvg" / "brand.json"
    if xdg.exists():
        return xdg
    cwd = Path.cwd() / "brand.json"
    if cwd.exists():
        return cwd
    return None


def load_default_brand() -> BrandPack | None:
    path = default_brand_path()
    if path is None:
        return None
    return BrandPack.load(path)
