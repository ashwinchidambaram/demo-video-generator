"""Unit tests for keyframe interpolation + ffmpeg expression compilation."""

from __future__ import annotations

from dvg.easing import Easing
from dvg.keyframes import (
    Keyframe,
    compile_to_ffmpeg_expr,
    evaluate_keyframes,
    from_pairs,
)


def test_constant_when_single_keyframe() -> None:
    kf = [Keyframe(t=0, v=42.0)]
    assert evaluate_keyframes(kf, 0.0) == 42.0
    assert evaluate_keyframes(kf, 999) == 42.0


def test_linear_lerp() -> None:
    kf = from_pairs([(0.0, 0.0), (10.0, 100.0)])
    assert evaluate_keyframes(kf, 0.0) == 0.0
    assert evaluate_keyframes(kf, 5.0) == 50.0
    assert evaluate_keyframes(kf, 10.0) == 100.0


def test_clamp_outside() -> None:
    kf = from_pairs([(2.0, 50.0), (4.0, 100.0)])
    assert evaluate_keyframes(kf, 0.0) == 50.0
    assert evaluate_keyframes(kf, 5.0) == 100.0


def test_tuple_lerp() -> None:
    kf = from_pairs([(0.0, (0.0, 0.0)), (1.0, (100.0, 50.0))])
    v = evaluate_keyframes(kf, 0.5)
    assert v == (50.0, 25.0)


def test_easing_changes_curve() -> None:
    linear = from_pairs([(0.0, 0.0), (1.0, 100.0)], easing=Easing.LINEAR)
    eased = [Keyframe(t=0, v=0), Keyframe(t=1, v=100, e=Easing.EASE_IN)]
    # at midpoint, linear=50, ease_in (cubic) = 12.5
    assert evaluate_keyframes(linear, 0.5) == 50.0
    eased_v = evaluate_keyframes(eased, 0.5)
    assert isinstance(eased_v, float)
    assert eased_v < 50.0


def test_compile_to_ffmpeg_expr_constant() -> None:
    expr = compile_to_ffmpeg_expr([Keyframe(t=0, v=100.0)])
    assert "100" in expr


def test_compile_to_ffmpeg_expr_linear() -> None:
    kf = from_pairs([(0.0, 0.0), (2.0, 200.0)])
    expr = compile_to_ffmpeg_expr(kf, layer_start=1.0)
    # the expression should reference time and contain a piecewise if
    assert "if(lt(t" in expr
    assert "200" in expr or "200.0000" in expr


def test_compile_to_ffmpeg_expr_tuple_component() -> None:
    kf = from_pairs([(0.0, (10.0, 20.0)), (1.0, (30.0, 40.0))])
    x_expr = compile_to_ffmpeg_expr(kf, component=0)
    y_expr = compile_to_ffmpeg_expr(kf, component=1)
    assert "10.0" in x_expr or "10.000" in x_expr
    assert "20.0" in y_expr or "20.000" in y_expr
    # ensure x and y are different
    assert x_expr != y_expr
