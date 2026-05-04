"""Capture smoke test using a local file:// fixture. Real chromium spawn —
this is more of an integration test than a unit test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dvg.capture import capture_url_sync

FIXTURE_HTML = Path(__file__).parents[1] / "fixtures/site/index.html"


@pytest.mark.skipif(
    not FIXTURE_HTML.exists() or os.environ.get("DVG_SKIP_CAPTURE") == "1",
    reason="fixture missing or capture skipped",
)
def test_capture_smoke(tmp_path: Path) -> None:
    url = f"file://{FIXTURE_HTML.resolve()}"
    result = capture_url_sync(
        url,
        out_dir=tmp_path,
        duration=4.0,
        width=1280,  # smaller for fast test
        height=720,
        fps=30,
        scenario="tour",
        headed=False,  # CI-friendly
    )
    assert result.video_path.exists()
    assert result.video_path.stat().st_size > 50_000
    assert result.events_path.exists()
    assert result.events_count > 0  # at least page_load + scrolls
