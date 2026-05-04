"""Per-run telemetry rubric.

Append a row to `runs/_telemetry.jsonl` after every `dvg make-video` run.
Each row records auto-measured signals (size, length, LUFS, peak, render
time, caption density) plus an optional PM rubric. Trend analysis on this
file replaces the per-agent eval framework from main's plan.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

from dvg.models import CaptionLayer, Composition, TelemetryRow


def build_row(
    *,
    run_id: str,
    input: str,
    composition: Composition,
    output_path: Path,
    render_time_s: float,
    output_lufs: float | None,
    output_peak_dbfs: float | None,
    rubric: dict[str, int] | None = None,
    notes: str | None = None,
) -> TelemetryRow:
    captions = [layer for layer in composition.layers if isinstance(layer, CaptionLayer)]
    moods = Counter(c.mood.value for c in captions)
    output_size = output_path.stat().st_size if output_path.exists() else None
    return TelemetryRow(
        run_id=run_id,
        ts=time.time(),
        input=input,
        duration_s=composition.duration,
        output_path=str(output_path),
        output_size_bytes=output_size,
        output_lufs=output_lufs,
        output_peak_dbfs=output_peak_dbfs,
        output_length_s=composition.duration,
        caption_count=len(captions),
        caption_density=len(captions) / max(1.0, composition.duration / 10.0),
        render_time_s=render_time_s,
        mood_distribution=dict(moods),
        stage_costs_usd={},  # populated by future LLM director
        rubric=rubric,
        notes=notes,
    )


def append_row(row: TelemetryRow, path: Path | None = None) -> Path:
    """Append a row to runs/_telemetry.jsonl. Creates the file if needed."""
    target = path or Path("runs/_telemetry.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a") as f:
        f.write(row.model_dump_json() + "\n")
    return target


def summary(path: Path | None = None) -> dict[str, object]:
    """Aggregate stats from the telemetry file."""
    target = path or Path("runs/_telemetry.jsonl")
    if not target.exists():
        return {"runs": 0}
    rows: list[TelemetryRow] = []
    for line in target.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(TelemetryRow.model_validate_json(line))
        except Exception:
            continue
    if not rows:
        return {"runs": 0}
    n = len(rows)
    avg = lambda key: sum(  # noqa: E731
        getattr(r, key) or 0 for r in rows if getattr(r, key) is not None
    ) / max(
        1, sum(1 for r in rows if getattr(r, key) is not None)
    )
    return {
        "runs": n,
        "avg_duration_s": avg("duration_s"),
        "avg_render_time_s": avg("render_time_s"),
        "avg_caption_count": avg("caption_count"),
        "avg_lufs": avg("output_lufs"),
        "avg_peak_dbfs": avg("output_peak_dbfs"),
        "first_run_ts": min(r.ts for r in rows),
        "last_run_ts": max(r.ts for r in rows),
    }
