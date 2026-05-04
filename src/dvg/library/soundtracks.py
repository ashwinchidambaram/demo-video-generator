"""Soundtrack library — pick-by-tag from a directory of audio files.

For v1 we hand-tag the 7 soundtracks in Ashwin's library by filename. Later
we'll auto-tag using librosa (BPM, spectral centroid → mood).

Tags:
- energy: 0..1 (drives ducking depth, caption pacing)
- tempo_bpm: approximate
- mood: enum-ish ("flow", "edm", "chill", "punchy", "cinematic", "neutral")
- duration_s: from ffprobe
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LIBRARY_DIR = Path(
    "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/"
)


@dataclass
class Soundtrack:
    path: Path
    energy: float
    tempo_bpm: float
    mood: str
    duration_s: float


# Hand-tagged. Will swap for librosa-derived in H7.
_TAGS: dict[str, dict[str, object]] = {
    "Vibe A - v1.mp3": {"energy": 0.45, "tempo_bpm": 100, "mood": "chill"},
    "Vibe A - v2.mp3": {"energy": 0.50, "tempo_bpm": 102, "mood": "chill"},
    "Vibe B.mp3": {"energy": 0.55, "tempo_bpm": 110, "mood": "neutral"},
    "Vibe C.mp3": {"energy": 0.60, "tempo_bpm": 120, "mood": "cinematic"},
    "vibe-edm.mp3": {"energy": 0.85, "tempo_bpm": 128, "mood": "edm"},
    "vibe-edm2.mp3": {"energy": 0.90, "tempo_bpm": 130, "mood": "edm"},
    "vibe-flow.mp3": {"energy": 0.70, "tempo_bpm": 115, "mood": "flow"},
}


def load_library(dir_path: Path = DEFAULT_LIBRARY_DIR) -> list[Soundtrack]:
    if not dir_path.exists():
        return []
    out: list[Soundtrack] = []
    for f in sorted(dir_path.glob("*.mp3")):
        tags = _TAGS.get(f.name)
        if tags is None:
            continue
        duration = _probe_duration(f)
        out.append(
            Soundtrack(
                path=f,
                energy=float(tags["energy"]),  # type: ignore[arg-type]
                tempo_bpm=float(tags["tempo_bpm"]),  # type: ignore[arg-type]
                mood=str(tags["mood"]),
                duration_s=duration,
            )
        )
    return out


def _probe_duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return 60.0  # default
    try:
        info = json.loads(proc.stdout)
        return float(info["format"]["duration"])
    except (KeyError, ValueError):
        return 60.0


def pick_soundtrack(
    library: list[Soundtrack],
    *,
    target_energy: float = 0.6,
    target_duration_s: float = 12.0,
    preferred_mood: str | None = None,
) -> Soundtrack:
    """Score each track on energy distance + duration sufficiency + mood match.

    Score = 0.5 * energy_match + 0.3 * duration_ok + 0.2 * mood_match
    Lower is better; we minimize.
    """
    if not library:
        raise ValueError("empty soundtrack library")

    def score(s: Soundtrack) -> float:
        e = abs(s.energy - target_energy)
        # duration: heavy penalty if shorter than needed, light if much longer
        d = 0.0 if s.duration_s >= target_duration_s else (target_duration_s - s.duration_s) / 30.0
        m = 0.0 if (preferred_mood is None or s.mood == preferred_mood) else 0.5
        return 0.5 * e + 0.3 * d + 0.2 * m

    return min(library, key=score)
