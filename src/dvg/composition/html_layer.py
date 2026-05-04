"""Render an HTMLLayer via Playwright.

Two modes:
- static (default): render the HTML to a single PNG. Use as ImageLayer. Fast.
- animated: render N frames at the composition fps, treating the HTML's
  optional `window.__dvg_setTime(t)` as the per-frame hook.

For v1 we build the static path. Animated path is sketched but not wired.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from dvg.models import HTMLLayer


async def render_static_html_to_png(
    layer: HTMLLayer,
    out_path: Path,
    *,
    width: int,
    height: int,
    transparent: bool = True,
) -> Path:
    """Render the layer's template to a single PNG.

    template can be a path or inline HTML. props are stringified and
    injected as `window.__dvg_props`.
    """
    from playwright.async_api import async_playwright

    out_path.parent.mkdir(parents=True, exist_ok=True)
    template = layer.template
    if isinstance(template, Path):
        url = f"file://{template.resolve()}"
    else:
        # inline HTML — write to temp
        tmp = out_path.parent / f"_html_{int(time.time())}.html"
        tmp.write_text(str(template))
        url = f"file://{tmp.resolve()}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page = await context.new_page()
        if layer.props:
            await context.add_init_script(
                f"window.__dvg_props = {_props_to_js(layer.props)};"
            )
        await page.goto(url, wait_until="networkidle", timeout=10_000)
        await page.wait_for_timeout(80)  # let CSS settle
        await page.screenshot(
            path=str(out_path),
            omit_background=transparent,
            full_page=False,
        )
        await browser.close()
    return out_path


def render_static_html_sync(
    layer: HTMLLayer,
    out_path: Path,
    *,
    width: int,
    height: int,
    transparent: bool = True,
) -> Path:
    return asyncio.run(
        render_static_html_to_png(
            layer, out_path, width=width, height=height, transparent=transparent
        )
    )


def _props_to_js(props: dict[str, Any]) -> str:
    import json as _json

    return _json.dumps(props)
