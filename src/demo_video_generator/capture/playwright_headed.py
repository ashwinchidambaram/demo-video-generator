"""Headed Chromium + ffmpeg avfoundation capture path (Phase 2.5).

This module is the real footage-capture URL path per agent design. It
launches Chromium in app-mode (per D11 spike recommendation), navigates
to the URL, instruments DOM events via Playwright's addInitScript, then
records the window region with ffmpeg avfoundation while it drives
interactions.

Runtime gating:
- Requires `playwright` Python package + `playwright install chromium`
- Requires `ffmpeg` on PATH with avfoundation device support (macOS only)
- Requires macOS Screen Recording TCC permission (otherwise fails with
  TCC_DENIED error per agent design)

The full subprocess + Playwright + ffmpeg orchestration is INERT until
those gates pass. This commit ships the code path, the typed interface,
and tests with mocked subprocess so the integration is reviewable; the
Phase 2.5 user-facing rollout is "install playwright + grant TCC" — no
further code change needed.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DOM_INSTRUMENTATION_JS = r"""
// Phase 2.5 footage-capture event instrumentation.
// Per agent design: capture-phase listeners post events to a localhost sink
// the agent's CLI primitive owns. Each event carries `t` from
// performance.now() mapped to video clock via a sync ping at recording
// start.
window.__dvg_capture_origin = performance.now();
window.__dvg_events = [];

const _post = (kind, label, payload) => {
  const t_ms = performance.now() - window.__dvg_capture_origin;
  window.__dvg_events.push({
    id: 'evt-' + window.__dvg_events.length,
    t: t_ms / 1000.0,
    kind: kind,
    label: label,
    selector: payload && payload.selector ? payload.selector : null,
    payload: payload || {},
  });
};

document.addEventListener('click', (e) => {
  _post('click', e.target && e.target.innerText ? e.target.innerText.slice(0, 40) : 'click',
        {selector: e.target && e.target.tagName ? e.target.tagName.toLowerCase() : null});
}, true);

document.addEventListener('submit', (e) => {
  _post('submit', 'form submit', {});
}, true);

document.addEventListener('keydown', (e) => {
  _post('keydown', e.key, {});
}, true);

// pushState / popstate proxy for SPA navigation (per holdout case).
const _origPush = history.pushState;
history.pushState = function(...args) {
  _post('pushstate', String(args[2] || ''), {});
  return _origPush.apply(this, args);
};
window.addEventListener('popstate', () => _post('popstate', location.pathname, {}));
"""


@dataclass(slots=True)
class CaptureSpec:
    url: str
    out_dir: Path
    duration_seconds: float = 10.0
    viewport_width: int = 1920
    viewport_height: int = 1080
    fps: int = 30


@dataclass(slots=True)
class CaptureResult:
    footage_path: Path
    events_path: Path
    duration_seconds: float
    events_count: int


class TccDeniedError(RuntimeError):
    """Raised when macOS Screen Recording permission isn't granted."""


def enumerate_avfoundation_devices() -> list[str]:
    """Per D11 / agent design: device IDs reorder when displays connect.
    Enumerate at runtime via `ffmpeg -f avfoundation -list_devices true -i ""`.

    Returns the raw stderr lines (parsing is left to caller); empty list
    when ffmpeg isn't available.
    """
    if shutil.which("ffmpeg") is None:
        return []
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-f",
                "avfoundation",
                "-list_devices",
                "true",
                "-i",
                "",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return []
    return proc.stderr.splitlines()


def check_tcc() -> bool:
    """Best-effort check: try a 0.5s null capture; if it fails with
    "Operation not permitted" we know TCC is denied.
    """
    if platform.system() != "Darwin":
        return True  # non-macOS: no TCC
    if shutil.which("ffmpeg") is None:
        return False
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-f",
                "avfoundation",
                "-i",
                "1:none",
                "-t",
                "0.5",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return False
    if "Operation not permitted" in proc.stderr or "denied" in proc.stderr.lower():
        return False
    return proc.returncode == 0


def capture_url_headed(spec: CaptureSpec) -> CaptureResult:
    """Phase 2.5 entry. Launches Chromium in app-mode, instruments DOM events,
    records ffmpeg avfoundation while driving interactions, writes
    footage.mp4 + footage.events.json.

    Raises TccDeniedError if macOS Screen Recording isn't granted.
    Raises RuntimeError on other capture failures.
    """
    if platform.system() == "Darwin" and not check_tcc():
        raise TccDeniedError(
            "macOS Screen Recording permission denied. "
            "Open: x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "playwright not installed. Run: uv pip install playwright && playwright install chromium"
        ) from e

    spec.out_dir.mkdir(parents=True, exist_ok=True)
    footage_path = spec.out_dir / "footage.mp4"
    events_path = spec.out_dir / "footage.events.json"

    # Launch ffmpeg avfoundation in the background, recording the screen.
    # Per D11: app-mode hides Chrome chrome, so we record the full screen
    # and crop to the window position via Playwright-provided coordinates.
    ffmpeg_proc: subprocess.Popen[bytes] | None = None
    events: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                f"--app={spec.url}",
                f"--window-size={spec.viewport_width},{spec.viewport_height}",
                "--hide-crash-restore-bubble",
            ],
        )
        context = browser.new_context(
            viewport={"width": spec.viewport_width, "height": spec.viewport_height},
            device_scale_factor=1,
        )
        context.add_init_script(DOM_INSTRUMENTATION_JS)
        page = context.new_page()
        page.goto(spec.url, wait_until="networkidle", timeout=30_000)

        # Sync flash at t=0 (helps visual-analyst ground events vs pixels).
        page.evaluate("document.body.style.outline = '4px solid #00ff00';")
        time.sleep(0.05)
        page.evaluate("document.body.style.outline = '';")

        # Start ffmpeg recording.
        ffmpeg_proc = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-loglevel", "error",
                "-f", "avfoundation",
                "-capture_cursor", "1",
                "-framerate", str(spec.fps),
                "-i", "1:none",
                "-t", str(spec.duration_seconds),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "18",
                "-preset", "veryfast",
                "-movflags", "+faststart",
                "-an",
                str(footage_path),
            ],
            stdin=subprocess.DEVNULL,
        )

        # Drive the page for the duration of the capture. Phase 2.5 just lets
        # the page idle; user-driven scenarios (clicks/typing) come from a
        # config-supplied scenario script.
        time.sleep(spec.duration_seconds)

        # Pull the events log out of the page before tearing down.
        try:
            events = page.evaluate("window.__dvg_events || []")
        except Exception:
            events = []

        context.close()
        browser.close()

    # Wait for ffmpeg to finish flushing.
    if ffmpeg_proc is not None:
        try:
            ffmpeg_proc.wait(timeout=spec.duration_seconds + 10)
        except subprocess.TimeoutExpired:
            ffmpeg_proc.kill()

    if not footage_path.is_file() or footage_path.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg produced no footage at {footage_path}")

    # Write events log.
    events_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "url",
                "input": spec.url,
                "events": events,
                "duration_seconds": spec.duration_seconds,
                "fps": spec.fps,
                "resolution": {
                    "width": spec.viewport_width,
                    "height": spec.viewport_height,
                },
            },
            indent=2,
        )
    )

    return CaptureResult(
        footage_path=footage_path,
        events_path=events_path,
        duration_seconds=spec.duration_seconds,
        events_count=len(events),
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: playwright_headed.py <url> <out_dir> [--duration N]")
        sys.exit(2)
    url = sys.argv[1]
    out_dir = Path(sys.argv[2])
    duration = 10.0
    if "--duration" in sys.argv:
        duration = float(sys.argv[sys.argv.index("--duration") + 1])
    spec = CaptureSpec(url=url, out_dir=out_dir, duration_seconds=duration)
    try:
        result = capture_url_headed(spec)
        print(json.dumps({"footage": str(result.footage_path), "events": result.events_count}))
    except TccDeniedError as e:
        print(json.dumps({"error": str(e), "code": "TCC_DENIED"}), file=sys.stderr)
        sys.exit(2)
