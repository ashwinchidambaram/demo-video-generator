"""Review subcommand. Phase 1 stub: writes a minimal audio_qa.json + qa.json
asserting pass for any final.mp4 that exists. Phase 8 wires up the full audio
QA toolkit (ffprobe, ebur128, sox, aubio, librosa) and the severity ladder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..atomic import write_json_atomic


def stub_review(final_mp4: Path, run_dir: Path) -> dict[str, Any]:
    """Phase 1 stub: trivial pass if final.mp4 exists.

    Phase 8 replaces with the audio QA toolkit + structured issue reporting
    against the qa.json schema (added in Phase 8).
    """
    audio_qa = {
        "schema_version": 1,
        "stub": True,
        "measurements": {
            "final_exists": final_mp4.exists(),
            "size_bytes": final_mp4.stat().st_size if final_mp4.exists() else 0,
        },
    }
    qa: dict[str, Any] = {
        "schema_version": 1,
        "signoff": "pass" if final_mp4.exists() else "fail",
        "issues": (
            []
            if final_mp4.exists()
            else [
                {
                    "code": "FINAL_MP4_MISSING",
                    "severity": "high",
                    "stage": "render",
                    "evidence": {"path": str(final_mp4)},
                    "proposed_action": {"kind": "regenerate_stage", "target_stage": "render"},
                }
            ]
        ),
        "measurements": {},
        "evidence_paths": [],
    }
    write_json_atomic(run_dir / "audio_qa.json", audio_qa)
    write_json_atomic(run_dir / "qa.json", qa)
    return qa
