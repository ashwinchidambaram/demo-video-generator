"""Tests for the Phase 2.5 headed-Chromium capture path.

Exercises the parsing/orchestration layer with mocked subprocess. The full
runtime path is gated on macOS TCC + playwright install, so we don't run
real captures here — but every shape of the integration is covered.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from demo_video_generator.capture.playwright_headed import (
    DOM_INSTRUMENTATION_JS,
    CaptureSpec,
    TccDeniedError,
    check_tcc,
    enumerate_avfoundation_devices,
)


def test_dom_instrumentation_js_has_load_bearing_listeners() -> None:
    """Per agent design / event-log-analyst contract, the JS must capture
    click/submit/keydown/pushstate/popstate."""
    for required in [
        "addEventListener('click'",
        "addEventListener('submit'",
        "addEventListener('keydown'",
        "history.pushState",
        "popstate",
    ]:
        assert required in DOM_INSTRUMENTATION_JS, f"missing instrumentation: {required}"


def test_dom_instrumentation_uses_capture_phase() -> None:
    """Capture-phase listeners (third arg = true) are necessary so the
    handler fires before the app's own click handlers swallow events."""
    # The JS uses `, true);` (capture-phase) on document.addEventListener.
    assert ", true);" in DOM_INSTRUMENTATION_JS


def test_capture_spec_defaults() -> None:
    spec = CaptureSpec(url="http://x", out_dir=Path("/tmp"))
    assert spec.duration_seconds == 10.0
    assert spec.viewport_width == 1920
    assert spec.viewport_height == 1080
    assert spec.fps == 30


def test_check_tcc_returns_true_on_non_darwin() -> None:
    """Non-macOS systems have no TCC concept."""
    with mock.patch("platform.system", return_value="Linux"):
        assert check_tcc() is True


def test_check_tcc_returns_false_when_ffmpeg_missing() -> None:
    """No ffmpeg → can't probe TCC; conservatively report denied."""
    with (
        mock.patch("platform.system", return_value="Darwin"),
        mock.patch("shutil.which", return_value=None),
    ):
        assert check_tcc() is False


def test_check_tcc_detects_operation_not_permitted() -> None:
    """ffmpeg returns 'Operation not permitted' → TCC denied."""

    class _Result:
        returncode = 1
        stderr = "[avfoundation] Operation not permitted\n"

    with (
        mock.patch("platform.system", return_value="Darwin"),
        mock.patch("shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
        mock.patch("subprocess.run", return_value=_Result()),
    ):
        assert check_tcc() is False


def test_check_tcc_detects_denied_keyword() -> None:
    """Various ffmpeg builds emit 'denied' instead of 'Operation not permitted'."""

    class _Result:
        returncode = 1
        stderr = "[avfoundation] Permission denied\n"

    with (
        mock.patch("platform.system", return_value="Darwin"),
        mock.patch("shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
        mock.patch("subprocess.run", return_value=_Result()),
    ):
        assert check_tcc() is False


def test_check_tcc_passes_on_zero_exit() -> None:
    class _Result:
        returncode = 0
        stderr = ""

    with (
        mock.patch("platform.system", return_value="Darwin"),
        mock.patch("shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
        mock.patch("subprocess.run", return_value=_Result()),
    ):
        assert check_tcc() is True


def test_enumerate_avfoundation_devices_empty_when_ffmpeg_missing() -> None:
    with mock.patch("shutil.which", return_value=None):
        assert enumerate_avfoundation_devices() == []


def test_enumerate_avfoundation_devices_returns_stderr_lines() -> None:
    """The function returns raw lines for the caller to parse."""
    sample_stderr = (
        "[AVFoundation] Video devices:\n"
        "[AVFoundation] [0] FaceTime HD Camera\n"
        "[AVFoundation] [1] Capture screen 0\n"
    )

    class _Result:
        returncode = 1
        stderr = sample_stderr

    with (
        mock.patch("shutil.which", return_value="/opt/homebrew/bin/ffmpeg"),
        mock.patch("subprocess.run", return_value=_Result()),
    ):
        lines = enumerate_avfoundation_devices()
    assert any("Capture screen 0" in line for line in lines)


def test_tcc_denied_error_is_runtime_error() -> None:
    """Driver must catch RuntimeError to reach this; ensure subclassing."""
    e = TccDeniedError("denied")
    assert isinstance(e, RuntimeError)
