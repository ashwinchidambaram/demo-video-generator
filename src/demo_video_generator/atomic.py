"""Atomic-write helper.

Phase 0 exit-criterion: a kill mid-stage must not poison re-runs. Every artifact
the driver writes goes through here: write to a sibling tmpfile, fsync, then
rename. Rename is atomic on the same filesystem (POSIX), so any reader either
sees the previous version or the new one — never a half-written file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_atomic(path: Path, data: bytes) -> None:
    """Write bytes to path atomically via tmpfile + rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json_atomic(path: Path, obj: Any, *, indent: int = 2) -> None:
    """Serialize obj to JSON and write atomically."""
    payload = json.dumps(obj, indent=indent, sort_keys=False, default=str).encode("utf-8")
    write_atomic(path, payload)
