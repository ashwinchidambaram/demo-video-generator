"""Playwright-driven web capture.

Strategy:
1. Launch headed Chromium (so demos look real, not headless).
2. Open a context with recordVideo at canvas size.
3. Inject DOM event logger via add_init_script.
4. Navigate to URL, run scenario.
5. Close context (finalizes video).
6. Transcode WebM → MP4 with ffmpeg (libx264, faststart, target fps).
7. Pull events from page.evaluate.

Output: footage.mp4 + footage.events.json in the run directory.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dvg.capture.scenarios import Scenario, ScenarioOptions, resolve

EVENT_LOGGER_JS = """
window.__dvg_events = [];
window.__dvg_t0 = performance.now();

function dvgLog(type, detail) {
    window.__dvg_events.push({
        t: (performance.now() - window.__dvg_t0) / 1000.0,
        type,
        detail
    });
}

// click / mousedown
document.addEventListener('click', (e) => {
    const target = e.target;
    dvgLog('click', {
        x: e.clientX, y: e.clientY,
        tag: target?.tagName?.toLowerCase(),
        id: target?.id || null,
        text: (target?.innerText || '').trim().slice(0, 80)
    });
}, true);

// input
document.addEventListener('input', (e) => {
    const target = e.target;
    dvgLog('input', {
        tag: target?.tagName?.toLowerCase(),
        id: target?.id || null,
        len: (target?.value || '').length
    });
}, true);

// scroll (throttled)
let lastScrollT = 0;
window.addEventListener('scroll', () => {
    const now = performance.now();
    if (now - lastScrollT < 200) return;
    lastScrollT = now;
    dvgLog('scroll', { y: window.scrollY, max: document.body.scrollHeight });
}, true);

// navigation
let lastPath = location.pathname;
function checkNav() {
    if (location.pathname !== lastPath) {
        dvgLog('navigation', { from: lastPath, to: location.pathname });
        lastPath = location.pathname;
    }
}
window.addEventListener('popstate', checkNav);

// monkey-patch pushState/replaceState to detect SPA navigations
const origPush = history.pushState.bind(history);
const origReplace = history.replaceState.bind(history);
history.pushState = function(...args) { origPush(...args); checkNav(); };
history.replaceState = function(...args) { origReplace(...args); checkNav(); };

// page lifecycle
window.addEventListener('load', () => dvgLog('page_load', { url: location.href }));
"""


@dataclass
class CaptureResult:
    video_path: Path
    events_path: Path
    duration_s: float
    width: int
    height: int
    events_count: int
    raw_webm_path: Path | None = None


async def capture_url(
    url: str,
    *,
    out_dir: Path,
    duration: float = 12.0,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    scenario: str = "tour",
    headed: bool = True,
    keep_intermediates: bool = False,
) -> CaptureResult:
    """Capture a URL to a 1080p MP4 + DOM event log."""
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    video_dir = out_dir / "_capture_raw"
    video_dir.mkdir(exist_ok=True)
    final_video = out_dir / "footage.mp4"
    events_path = out_dir / "footage.events.json"

    scenario_fn: Scenario = resolve(scenario)
    options = ScenarioOptions(duration=duration, width=width, height=height)

    t_start = time.perf_counter()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=not headed,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                f"--window-size={width},{height}",
                "--app=" + url,  # hide chrome chrome
            ],
        )
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            record_video_dir=str(video_dir),
            record_video_size={"width": width, "height": height},
            device_scale_factor=1,
            ignore_https_errors=True,
        )
        await context.add_init_script(EVENT_LOGGER_JS)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        # tiny settle
        await page.wait_for_timeout(150)
        await scenario_fn(page, options)

        # extract events
        try:
            events = await page.evaluate("window.__dvg_events")
        except Exception:
            events = []

        # close to flush video
        await context.close()
        await browser.close()

    # find the produced webm
    webm = next(video_dir.glob("*.webm"), None)
    if webm is None:
        raise RuntimeError("Playwright did not produce a video")

    # transcode webm → mp4
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(webm),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-an",  # no audio (we add later)
        "-movflags",
        "+faststart",
        str(final_video),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"transcode failed: {proc.stderr[-1500:]}")

    events_path.write_text(json.dumps(events, indent=2))

    if not keep_intermediates:
        try:
            webm.unlink()
            video_dir.rmdir()
        except OSError:
            pass

    return CaptureResult(
        video_path=final_video,
        events_path=events_path,
        duration_s=time.perf_counter() - t_start,
        width=width,
        height=height,
        events_count=len(events),
        raw_webm_path=None if not keep_intermediates else webm,
    )


def capture_url_sync(url: str, **kwargs: Any) -> CaptureResult:
    """Sync wrapper for the async capture."""
    return asyncio.run(capture_url(url, **kwargs))
