"""Auto-pilot scenarios for capture. Each scenario is an async function
`play(page, options)` that drives the page while capture is recording.

Built-in scenarios:
- `tour`: scroll down 1/3, pause, scroll back, pause, click first CTA if present
- `idle`: just sit on the page for `duration` seconds
- `script`: load a user-provided .py file with `play(page, options)`
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


@dataclass
class ScenarioOptions:
    duration: float
    width: int
    height: int


Scenario = Callable[["Page", ScenarioOptions], Awaitable[None]]


# ---- built-ins ----------------------------------------------------------


async def tour(page: "Page", options: ScenarioOptions) -> None:
    """Default tour: scroll, pause, scroll-up, pause, click first CTA-ish element."""
    total = options.duration
    # phase 1: settle (5%)
    await page.wait_for_timeout(int(total * 0.05 * 1000))

    # phase 2: smooth scroll down 1/3 of page (35%)
    await page.evaluate(
        """
        ([target_pct, duration_ms]) => {
            const start = window.scrollY;
            const end = document.body.scrollHeight * target_pct;
            const t0 = performance.now();
            return new Promise(resolve => {
                function step(now) {
                    const t = Math.min(1, (now - t0) / duration_ms);
                    const eased = 0.5 - 0.5 * Math.cos(Math.PI * t);
                    window.scrollTo(0, start + (end - start) * eased);
                    if (t < 1) requestAnimationFrame(step);
                    else resolve();
                }
                requestAnimationFrame(step);
            });
        }
        """,
        [0.33, total * 0.35 * 1000],
    )

    # phase 3: pause (10%)
    await page.wait_for_timeout(int(total * 0.10 * 1000))

    # phase 4: scroll to ~75% with hover over a CTA-ish element if present (25%)
    await page.evaluate(
        """
        (duration_ms) => {
            const start = window.scrollY;
            const end = document.body.scrollHeight * 0.75;
            const t0 = performance.now();
            return new Promise(resolve => {
                function step(now) {
                    const t = Math.min(1, (now - t0) / duration_ms);
                    const eased = 0.5 - 0.5 * Math.cos(Math.PI * t);
                    window.scrollTo(0, start + (end - start) * eased);
                    if (t < 1) requestAnimationFrame(step);
                    else resolve();
                }
                requestAnimationFrame(step);
            });
        }
        """,
        total * 0.25 * 1000,
    )

    # phase 5: click first prominent CTA-ish element if present (no nav)
    cta = await page.query_selector(
        "button, a[role='button'], a.btn, a.cta, a:has-text('Get'), a:has-text('Try'), a:has-text('Sign')"
    )
    if cta:
        try:
            await cta.hover()
            await page.wait_for_timeout(500)
        except Exception:
            pass

    # phase 6: scroll back to top (15%)
    await page.evaluate(
        """
        (duration_ms) => {
            const start = window.scrollY;
            const t0 = performance.now();
            return new Promise(resolve => {
                function step(now) {
                    const t = Math.min(1, (now - t0) / duration_ms);
                    const eased = 0.5 - 0.5 * Math.cos(Math.PI * t);
                    window.scrollTo(0, start * (1 - eased));
                    if (t < 1) requestAnimationFrame(step);
                    else resolve();
                }
                requestAnimationFrame(step);
            });
        }
        """,
        total * 0.15 * 1000,
    )

    # tail
    await page.wait_for_timeout(int(total * 0.10 * 1000))


async def idle(page: "Page", options: ScenarioOptions) -> None:
    await page.wait_for_timeout(int(options.duration * 1000))


def load_script(path: Path) -> Scenario:
    """Load a .py file exposing `play(page, options)` and return it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"dvg_scenario_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load scenario from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "play") or not callable(mod.play):
        raise RuntimeError(f"{path} must define an async `play(page, options)` function")
    return mod.play  # type: ignore[no-any-return]


def resolve(name_or_path: str) -> Scenario:
    if name_or_path == "tour":
        return tour
    if name_or_path == "idle":
        return idle
    p = Path(name_or_path)
    if p.exists():
        return load_script(p)
    raise ValueError(f"unknown scenario: {name_or_path}")
