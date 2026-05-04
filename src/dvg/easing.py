"""Animation easing primitives. Pure functions of t in [0, 1] returning [0, 1]."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class Easing(str, Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    CUBIC_BEZIER = "cubic_bezier"
    SPRING = "spring"


def linear(t: float) -> float:
    return max(0.0, min(1.0, t))


def ease_in(t: float) -> float:
    return t * t * t


def ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def cubic_bezier(p1x: float, p1y: float, p2x: float, p2y: float) -> Callable[[float], float]:
    """CSS-style cubic-bezier (p0=(0,0), p3=(1,1))."""

    def curve(t: float) -> float:
        # Newton-Raphson to invert x(s)=t
        s = t
        for _ in range(8):
            x = 3 * (1 - s) ** 2 * s * p1x + 3 * (1 - s) * s * s * p2x + s * s * s
            dx = 3 * (1 - s) ** 2 * (p1x) + 6 * (1 - s) * s * (p2x - p1x) + 3 * s * s * (1 - p2x)
            if abs(dx) < 1e-6:
                break
            s -= (x - t) / dx
            s = max(0.0, min(1.0, s))
        return 3 * (1 - s) ** 2 * s * p1y + 3 * (1 - s) * s * s * p2y + s * s * s

    return curve


@dataclass(frozen=True)
class Spring:
    """Critically-damped-ish spring. stiffness=170, damping=26 ≈ Remotion default."""

    stiffness: float = 170.0
    damping: float = 26.0
    mass: float = 1.0

    def __call__(self, t: float, duration: float = 1.0) -> float:
        if t <= 0:
            return 0.0
        if t >= duration:
            return 1.0
        # under-damped vs critically damped
        omega = math.sqrt(self.stiffness / self.mass)
        zeta = self.damping / (2.0 * math.sqrt(self.stiffness * self.mass))
        x = t  # in seconds
        if zeta < 1:
            wd = omega * math.sqrt(1 - zeta * zeta)
            value = 1 - math.exp(-zeta * omega * x) * (
                math.cos(wd * x) + (zeta * omega / wd) * math.sin(wd * x)
            )
        else:
            value = 1 - math.exp(-omega * x) * (1 + omega * x)
        return max(0.0, min(1.0, value))


def get(easing: Easing | str) -> Callable[[float], float]:
    if isinstance(easing, str):
        easing = Easing(easing)
    table: dict[Easing, Callable[[float], float]] = {
        Easing.LINEAR: linear,
        Easing.EASE_IN: ease_in,
        Easing.EASE_OUT: ease_out,
        Easing.EASE_IN_OUT: ease_in_out,
    }
    return table[easing]


def interpolate(
    t: float,
    domain: tuple[float, float],
    range_: tuple[float, float],
    easing: Easing | Callable[[float], float] = Easing.LINEAR,
) -> float:
    """Map t in domain to value in range, with easing.

    Equivalent to Remotion's `interpolate` with `extrapolateRight: 'clamp'`.
    """
    t0, t1 = domain
    if t1 == t0:
        return range_[0]
    norm = (t - t0) / (t1 - t0)
    norm = max(0.0, min(1.0, norm))
    fn = easing if callable(easing) else get(easing)
    eased = fn(norm)
    return range_[0] + (range_[1] - range_[0]) * eased
