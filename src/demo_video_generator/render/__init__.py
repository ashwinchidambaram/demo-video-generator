"""Render subcommand. Bridges to remotion/src/render.ts via subprocess.

Per ultraplan R1 / D13: uses bundle() + selectComposition() + renderMedia
chain on the Node side. Bundle output is cached at runs/<ts>/.remotion-bundle/
so a `--from render` doesn't re-bundle.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
REMOTION_DIR = REPO_ROOT / "remotion"


class RenderError(RuntimeError):
    pass


def render(composition_json: Path, out_path: Path, *, bundle_dir: Path | None = None) -> dict[str, Any]:
    """Invoke the Remotion bridge to render an MP4 from composition.json."""
    if not composition_json.is_file():
        raise RenderError(f"composition.json not found: {composition_json}")
    if shutil.which("npm") is None:
        raise RenderError("npm not on PATH; install Node 20+ to render.")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "npm", "run", "--silent", "render", "--",
        str(composition_json.resolve()),
        str(out_path.resolve()),
    ]
    if bundle_dir is not None:
        bundle_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--bundle-dir", str(bundle_dir.resolve())])

    proc = subprocess.run(
        cmd,
        cwd=REMOTION_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RenderError(
            f"Remotion render failed (exit {proc.returncode}):\n"
            f"stdout: {proc.stdout}\n"
            f"stderr: {proc.stderr}"
        )

    # render.ts emits JSON on the last non-empty stdout line.
    last_line = ""
    for line in reversed(proc.stdout.splitlines()):
        if line.strip().startswith("{"):
            last_line = line
            break
    try:
        result = json.loads(last_line) if last_line else {"output": str(out_path)}
    except json.JSONDecodeError:
        result = {"output": str(out_path), "raw_stdout": proc.stdout}
    if not out_path.exists():
        raise RenderError(f"Renderer reported success but {out_path} does not exist.")
    return result
