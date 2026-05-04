"""Keyframe animation primitive.

A `Track[T]` is either a constant value or a list of `Keyframe`s with eased
interpolation between them. Compiled to ffmpeg expressions for time-varying
overlay positions / scales / opacities.

For caption layers, animation is handled by libass override tags; this module
is for video / image / shape layers.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

from dvg.easing import Easing
from dvg.easing import get as get_easing

T = TypeVar("T", float, tuple[float, float], tuple[float, float, float])


class Keyframe(BaseModel):
    """One keyframe. `e` is the easing INTO this keyframe from the previous one."""

    model_config = ConfigDict(extra="forbid")

    t: float = Field(..., description="time in seconds, layer-relative")
    v: float | tuple[float, ...]
    e: Easing = Easing.LINEAR


def evaluate_keyframes(
    keyframes: list[Keyframe], t: float
) -> float | tuple[float, ...]:
    """Evaluate a keyframe track at time t. Clamps outside the range."""
    if not keyframes:
        raise ValueError("empty keyframe list")
    if len(keyframes) == 1:
        return keyframes[0].v
    if t <= keyframes[0].t:
        return keyframes[0].v
    if t >= keyframes[-1].t:
        return keyframes[-1].v

    for i in range(len(keyframes) - 1):
        a, b = keyframes[i], keyframes[i + 1]
        if a.t <= t <= b.t:
            span = b.t - a.t
            if span <= 0:
                return b.v
            local_t = (t - a.t) / span
            eased = get_easing(b.e)(local_t)
            return _lerp(a.v, b.v, eased)
    return keyframes[-1].v


def _lerp(a: float | tuple[float, ...], b: float | tuple[float, ...], t: float) -> float | tuple[float, ...]:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * t
    if isinstance(a, tuple) and isinstance(b, tuple) and len(a) == len(b):
        return tuple(av + (bv - av) * t for av, bv in zip(a, b, strict=True))
    raise TypeError(f"cannot lerp {a!r} and {b!r}")


# ---- ffmpeg expression compiler -----------------------------------------


def compile_to_ffmpeg_expr(
    keyframes: list[Keyframe],
    component: int = 0,
    *,
    layer_start: float = 0.0,
) -> str:
    """Compile a Keyframe list into an ffmpeg expression for the given component.

    component=0 for scalar tracks; for tuple tracks use component=0/1/2
    to extract that index.

    Easing is approximated. ffmpeg can do linear easily; for cubic/spring,
    we densify by sampling and use piecewise linear segments.
    """
    if not keyframes:
        raise ValueError("empty keyframes")
    if len(keyframes) == 1:
        v = _component(keyframes[0].v, component)
        return f"({v:.4f})"

    # densify: any non-linear segment becomes 8 sub-keyframes
    densified = _densify(keyframes, samples_per_segment=8)
    parts: list[str] = []
    for i in range(len(densified) - 1):
        a, b = densified[i], densified[i + 1]
        a_t = a.t + layer_start
        b_t = b.t + layer_start
        a_v = _component(a.v, component)
        b_v = _component(b.v, component)
        # linear lerp between a_v..b_v over a_t..b_t
        if b.t == a.t:
            seg = f"{a_v:.4f}"
        else:
            seg = f"({a_v:.4f}+({b_v - a_v:.4f})*(t-{a_t:.4f})/({b.t - a.t:.4f}))"
        parts.append(f"if(lt(t,{b_t:.4f}),{seg}")

    # final fallback
    last_v = _component(densified[-1].v, component)
    expr = ",".join(parts) + f",{last_v:.4f}" + ")" * len(parts)
    return expr


def _component(v: float | tuple[float, ...], component: int) -> float:
    if isinstance(v, (int, float)):
        if component != 0:
            raise IndexError(f"scalar value, asked component {component}")
        return float(v)
    return float(v[component])


def _densify(keyframes: list[Keyframe], samples_per_segment: int) -> list[Keyframe]:
    """Replace non-linear segments with N linear sub-segments using the easing curve."""
    out: list[Keyframe] = [keyframes[0]]
    for i in range(len(keyframes) - 1):
        a, b = keyframes[i], keyframes[i + 1]
        if b.e == Easing.LINEAR or b.t == a.t:
            out.append(b)
            continue
        fn = get_easing(b.e)
        for k in range(1, samples_per_segment + 1):
            local = k / samples_per_segment
            t = a.t + (b.t - a.t) * local
            eased = fn(local)
            v = _lerp(a.v, b.v, eased)
            out.append(Keyframe(t=t, v=v, e=Easing.LINEAR))
    return out


# ---- Track helpers -------------------------------------------------------


def from_pairs(
    pairs: Iterable[tuple[float, float | tuple[float, ...]]],
    easing: Easing = Easing.LINEAR,
) -> list[Keyframe]:
    """Build keyframes from (t, v) pairs."""
    return [Keyframe(t=t, v=v, e=easing) for t, v in pairs]
