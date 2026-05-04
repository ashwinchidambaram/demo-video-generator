"""qa-reviewer issue codes — CODEGEN, do not edit.

Generated from .claude/agents/qa-reviewer/knowledge/core.md by
`make qa-codes`. Re-run codegen if the YAML registry changes.

This module is the single source of truth for which qa.json codes the
driver may auto-retry (see AUTO_RETRY_ALLOWLIST in run.py).
"""

from __future__ import annotations

# --- generated -------------------------------------------------------------

ISSUE_CODES: dict[str, dict[str, str | bool]] = {
    'CAPTION_OUT_OF_FRAME': {
        'severity': 'high',
        'allowlist': True,
        'target_stage': 'compose',
        'description': 'caption end > duration_seconds; clipped off-frame',
    },
    'DEAD_AIR': {
        'severity': 'high',
        'allowlist': True,
        'target_stage': 'music',
        'description': 'spectrogram shows >2s of silence in the middle of the track',
    },
    'FINAL_MP4_MISSING': {
        'severity': 'high',
        'allowlist': True,
        'target_stage': 'render',
        'description': 'render stage reported success but final.mp4 not on disk',
    },
    'LENGTH_DRIFT': {
        'severity': 'medium',
        'allowlist': False,
        'target_stage': 'render',
        'description': 'rendered duration 2-10% off declared',
    },
    'LENGTH_OFF_BY_>10PCT': {
        'severity': 'high',
        'allowlist': False,
        'target_stage': 'render',
        'description': 'rendered duration > 10% off composition.duration_seconds (escalate; usually fps misconfig)',
    },
    'MIX_LUFS_OFF_TARGET': {
        'severity': 'high',
        'allowlist': True,
        'target_stage': 'compose',
        'description': 'ebur128 integrated LUFS differs from D9 target by > 2 LU',
    },
    'MIX_TRUEPEAK_EXCEEDED': {
        'severity': 'high',
        'allowlist': True,
        'target_stage': 'compose',
        'description': 'ebur128 true peak > -1 dBTP target',
    },
    'MUSIC_BPM_OFF_TARGET': {
        'severity': 'medium',
        'allowlist': True,
        'target_stage': 'music',
        'description': 'aubio-detected BPM differs from brief target by >5',
    },
    'MUSIC_SPECTRAL_HOLE': {
        'severity': 'medium',
        'allowlist': False,
        'target_stage': 'music',
        'description': 'spectrogram shows a wide notch (likely mastering bug)',
    },
    'NO_AUDIO_STREAM': {
        'severity': 'high',
        'allowlist': False,
        'target_stage': 'compose',
        'description': 'ffprobe found no audio stream (escalate; check audio mix bridge)',
    },
    'SFX_ONSET_MISALIGNED': {
        'severity': 'medium',
        'allowlist': False,
        'target_stage': 'compose',
        'description': 'SFX placements drift from event timestamps by >100ms',
    },
}


AUTO_RETRY_ALLOWLIST: frozenset[str] = frozenset(
    code for code, entry in ISSUE_CODES.items() if entry.get("allowlist")
)
