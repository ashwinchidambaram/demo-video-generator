"""Tests for the error envelope contract (D6)."""

from __future__ import annotations

import json

from demo_video_generator.errors import ERROR_SCHEMA_VERSION, DvgError


def test_error_includes_required_fields() -> None:
    err = DvgError(
        error="capture failed",
        code="CAPTURE_TCC_DENIED",
        retryable=False,
        suggestion="Grant Screen Recording in System Settings.",
        stage="capture",
    )
    payload = json.loads(err.to_json())
    assert payload["schema_version"] == ERROR_SCHEMA_VERSION
    assert payload["error"] == "capture failed"
    assert payload["code"] == "CAPTURE_TCC_DENIED"
    assert payload["retryable"] is False
    assert payload["suggestion"]
    assert payload["stage"] == "capture"


def test_error_context_defaults_to_empty_dict() -> None:
    err = DvgError(error="x", code="X", retryable=True)
    payload = err.to_dict()
    assert payload["context"] == {}
