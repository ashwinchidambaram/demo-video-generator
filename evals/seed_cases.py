"""Seed the eval/cases/<agent>/{smoke,holdout}/ fixtures.

Each case is a directory with `case.json` describing:
- inputs: what the agent's CLI primitive will see
- expected: deterministic checks the smoke runner performs against output
- rationale: human-readable description of what this case stresses

Smoke cases (5 per agent) exercise the contract: schema-valid output for
typical inputs. Holdout cases (2 per agent) cover the failure modes from
the agent's design.md that prompt-tuners would over-fit on.

Run: `uv run python evals/seed_cases.py`
"""

from __future__ import annotations

import json
from pathlib import Path

EVALS_ROOT = Path(__file__).resolve().parent / "cases"


def _write_case(agent: str, case_class: str, case_id: str, doc: dict) -> Path:
    case_dir = EVALS_ROOT / agent / case_class / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    out = case_dir / "case.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    return out


# Per-agent fixture catalogs. Each entry: (case_id, doc).
# doc shape: {kind: "smoke"|"holdout", description: str, input: dict,
#             expected: {<assertion-key>: value, ...}}

CASES: dict[str, dict[str, list[tuple[str, dict]]]] = {
    "footage-capture": {
        "smoke": [
            (
                "url-typical",
                {
                    "kind": "smoke",
                    "description": "URL input → synthetic placeholder + valid events.json",
                    "input": {"input_kind": "url", "input_value": "http://localhost:0/"},
                    "expected": {
                        "footage_path_exists": True,
                        "events_log_schema_version": 1,
                        "duration_seconds_default": 10.0,
                    },
                },
            ),
            (
                "video-file-ingest",
                {
                    "kind": "smoke",
                    "description": "Pre-recorded video file → file-ingest path",
                    "input": {
                        "input_kind": "video",
                        "input_value": "demo-deliverable.mp4",
                    },
                    "expected": {
                        "footage_size_bytes_min": 1024,
                        "events_log_schema_version": 1,
                        "events_count": 0,
                    },
                },
            ),
            (
                "screen-synthetic",
                {
                    "kind": "smoke",
                    "description": "kind=screen → synthetic until ffmpeg avfoundation lands",
                    "input": {"input_kind": "screen", "input_value": "screen"},
                    "expected": {
                        "events_count": 0,
                        "duration_seconds_default": 10.0,
                    },
                },
            ),
            (
                "duration-override-from-env",
                {
                    "kind": "smoke",
                    "description": "DVG_DURATION env var changes synthetic placeholder duration",
                    "input": {
                        "input_kind": "url",
                        "input_value": "http://localhost:0/",
                        "env": {"DVG_DURATION": "25"},
                    },
                    "expected": {"duration_seconds": 25.0},
                },
            ),
            (
                "events-log-shape",
                {
                    "kind": "smoke",
                    "description": "events.json has fps + resolution + events array",
                    "input": {"input_kind": "url", "input_value": "http://x/"},
                    "expected": {
                        "events_log_has_fps": True,
                        "events_log_has_resolution": True,
                    },
                },
            ),
        ],
        "holdout": [
            (
                "tcc-denied-future-spec",
                {
                    "kind": "holdout",
                    "description": "macOS TCC denied → error.json with code TCC_DENIED, retryable=false (Phase 2.5; gated on real Playwright path)",
                    "input": {"input_kind": "url", "input_value": "http://x/"},
                    "expected": {"future_spec": True},
                },
            ),
            (
                "single-page-app-pushstate",
                {
                    "kind": "holdout",
                    "description": "SPA with pushState only — agent must inject popstate proxy listener (Phase 2.5)",
                    "input": {"input_kind": "url", "input_value": "http://x/spa"},
                    "expected": {"future_spec": True},
                },
            ),
        ],
    },
    "event-log-analyst": {
        "smoke": [
            (
                "linear-flow",
                {
                    "kind": "smoke",
                    "description": "Linear demo flow: 6 events → 4 scenes",
                    "input": {
                        "events": [
                            {"id": "e1", "t": 0.5, "kind": "navigation", "label": "load"},
                            {"id": "e2", "t": 5.0, "kind": "click", "label": "open"},
                            {"id": "e3", "t": 7.5, "kind": "submit", "label": "save"},
                            {"id": "e4", "t": 12.0, "kind": "modal_open", "label": "ok"},
                            {"id": "e5", "t": 15.0, "kind": "modal_close", "label": "done"},
                            {"id": "e6", "t": 20.0, "kind": "navigation", "label": "next"},
                        ],
                        "duration_seconds": 25.0,
                    },
                    "expected": {
                        "scenes_count_min": 3,
                        "events_round_trip": True,
                    },
                },
            ),
            (
                "empty-events",
                {
                    "kind": "smoke",
                    "description": "No events → visual-source placeholder + synthetic anchors",
                    "input": {"events": [], "duration_seconds": 10.0},
                    "expected": {
                        "scenes_count": 1,
                        "first_scene_source": "visual",
                        "synthetic_events_min": 3,
                    },
                },
            ),
            (
                "typing-storm-collapse",
                {
                    "kind": "smoke",
                    "description": "38 keydowns in 4s → 1 scene",
                    "input": {
                        "events": [
                            {
                                "id": f"k{i}",
                                "t": 0.1 * i,
                                "kind": "keydown",
                                "label": "K",
                            }
                            for i in range(38)
                        ],
                        "duration_seconds": 5.0,
                    },
                    "expected": {"scenes_count": 1},
                },
            ),
            (
                "stable-event-ids",
                {
                    "kind": "smoke",
                    "description": "Event ids round-trip byte-identical (caption anchor invariant)",
                    "input": {
                        "events": [
                            {"id": "very-stable-id", "t": 1.0, "kind": "click"}
                        ],
                        "duration_seconds": 5.0,
                    },
                    "expected": {"events_round_trip": True},
                },
            ),
            (
                "high-energy-cluster",
                {
                    "kind": "smoke",
                    "description": "submit + modal_open in cluster → energy=high",
                    "input": {
                        "events": [
                            {"id": "a", "t": 1.0, "kind": "click"},
                            {"id": "b", "t": 1.3, "kind": "submit"},
                        ],
                        "duration_seconds": 5.0,
                    },
                    "expected": {"first_scene_energy": "high"},
                },
            ),
        ],
        "holdout": [
            (
                "non-monotonic-timestamps",
                {
                    "kind": "holdout",
                    "description": "Replayed events with non-monotonic t — must EMIT EVENTS_OUT_OF_ORDER, not silently sort. Tests resistance to 'be helpful'.",
                    "input": {
                        "events": [
                            {"id": "a", "t": 1.0, "kind": "click"},
                            {"id": "b", "t": 0.92, "kind": "click"},
                        ],
                        "duration_seconds": 5.0,
                    },
                    "expected": {"future_spec": True},
                },
            ),
            (
                "high-density-tutorial",
                {
                    "kind": "holdout",
                    "description": "45 meaningful events in 12s — must NOT over-collapse",
                    "input": {
                        "events": [
                            {"id": f"t{i}", "t": 0.25 * i, "kind": "keydown"}
                            for i in range(45)
                        ],
                        "duration_seconds": 12.0,
                    },
                    "expected": {"future_spec": True},
                },
            ),
        ],
    },
    "visual-analyst": {
        "smoke": [
            (
                "rendered-demo-mp4",
                {
                    "kind": "smoke",
                    "description": "demo-deliverable.mp4 has 6 scene transitions; detector should find ≥1",
                    "input": {
                        "video_path": "demo-deliverable.mp4",
                        "duration_seconds": 32.0,
                    },
                    "expected": {"scenes_count_min": 1},
                },
            ),
            (
                "empty-footage",
                {
                    "kind": "smoke",
                    "description": "0-byte placeholder → no visual scenes",
                    "input": {"video_path_size_bytes": 0, "duration_seconds": 10.0},
                    "expected": {"scenes_count": 0},
                },
            ),
            (
                "gap-only-window",
                {
                    "kind": "smoke",
                    "description": "Visual analysis confined to a gap interval; outputs never exceed window",
                    "input": {
                        "video_path": "demo-deliverable.mp4",
                        "gap_intervals": [[10.0, 18.0]],
                    },
                    "expected": {"all_scenes_within_gap": True},
                },
            ),
            (
                "keyframe-cap",
                {
                    "kind": "smoke",
                    "description": "Long video → keyframes capped at 8/min",
                    "input": {
                        "video_path": "demo-deliverable.mp4",
                        "duration_seconds": 32.0,
                    },
                    "expected": {"scenes_count_max": 8},
                },
            ),
            (
                "source-tag",
                {
                    "kind": "smoke",
                    "description": "Every visual scene must carry source='visual'",
                    "input": {"video_path": "demo-deliverable.mp4"},
                    "expected": {"all_source_visual": True},
                },
            ),
        ],
        "holdout": [
            (
                "cursor-only-motion",
                {
                    "kind": "holdout",
                    "description": "Static screen with cursor moving — should emit ONE energy=low scene, not over-segment (Phase 3.5; needs LLM-on-keyframes)",
                    "input": {"video_path": "tests/fixtures/cursor-only.mp4"},
                    "expected": {"future_spec": True},
                },
            ),
            (
                "dark-mode-low-contrast",
                {
                    "kind": "holdout",
                    "description": "#1a1a1a on #0e0e0e — must escalate to AdaptiveDetector (Phase 3.5)",
                    "input": {"video_path": "tests/fixtures/dark-mode.mp4"},
                    "expected": {"future_spec": True},
                },
            ),
        ],
    },
    "caption-writer": {
        "smoke": [
            (
                "title-tagline-arc",
                {
                    "kind": "smoke",
                    "description": "Brief with title + tagline → announce + tagline emitted",
                    "input": {
                        "brief": {
                            "title": "Switchboard",
                            "tagline": "Calls that route themselves.",
                        }
                    },
                    "expected": {
                        "captions_count_min": 2,
                        "first_mood": "announce",
                        "last_mood": "tagline",
                    },
                },
            ),
            (
                "explainer-distribution",
                {
                    "kind": "smoke",
                    "description": "3 explainers across 5 events → distributed",
                    "input": {
                        "brief": {
                            "title": "X",
                            "explainers": ["one", "two", "three"],
                            "tagline": "Y",
                        },
                        "event_count": 5,
                    },
                    "expected": {"explain_count": 3},
                },
            ),
            (
                "callout-anchor",
                {
                    "kind": "smoke",
                    "description": "Callout anchored to specified event index",
                    "input": {
                        "brief": {
                            "title": "X",
                            "callouts": [
                                {"text": "<- look here", "anchor_event_idx": 2}
                            ],
                            "tagline": "Y",
                        }
                    },
                    "expected": {"callout_count": 1},
                },
            ),
            (
                "punchline-priority",
                {
                    "kind": "smoke",
                    "description": "Punchline gets priority 5 by default",
                    "input": {
                        "brief": {"title": "X", "punchline": "Done.", "tagline": "Y"}
                    },
                    "expected": {"punchline_priority": 5},
                },
            ),
            (
                "mood-mix",
                {
                    "kind": "smoke",
                    "description": "Brief with 5 fields → 5+ moods, never one-mood-dominant beyond 80%",
                    "input": {
                        "brief": {
                            "title": "X",
                            "explainers": ["one", "two"],
                            "callouts": [{"text": "c", "anchor_event_idx": 1}],
                            "punchline": "Done.",
                            "tagline": "Y",
                        }
                    },
                    "expected": {"distinct_moods_min": 4},
                },
            ),
        ],
        "holdout": [
            (
                "sad-path-ux",
                {
                    "kind": "holdout",
                    "description": "Form fails validation; LLM must NOT apologize ('oops!') — matter-of-fact voice (Phase 7.5; LLM-driven)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
            (
                "long-form-through-line",
                {
                    "kind": "holdout",
                    "description": "60s, 3 sub-features — tagline must reference opening (LLM judgment)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
        ],
    },
    "music-prompt-engineer": {
        "smoke": [
            (
                "soundtrack-ingest-flow",
                {
                    "kind": "smoke",
                    "description": "Pick vibe-flow → music.mp3 size > 100KB",
                    "input": {
                        "soundtrack_dir": "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks",
                        "hint": "flow",
                    },
                    "expected": {"music_size_bytes_min": 100_000},
                },
            ),
            (
                "soundtrack-deterministic-pick",
                {
                    "kind": "smoke",
                    "description": "Same run_id_seed → same track each time",
                    "input": {
                        "soundtrack_dir": "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks",
                        "run_id_seed": "stable",
                    },
                    "expected": {"deterministic": True},
                },
            ),
            (
                "music-meta-sidecar",
                {
                    "kind": "smoke",
                    "description": "music_meta.json sidecar emitted with mode/source/verification",
                    "input": {
                        "soundtrack_dir": "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks"
                    },
                    "expected": {
                        "meta_has_source": True,
                        "meta_has_verification": True,
                    },
                },
            ),
            (
                "missing-soundtrack-dir",
                {
                    "kind": "smoke",
                    "description": "No soundtrack dir → falls back to placeholder",
                    "input": {"soundtrack_dir": None},
                    "expected": {"placeholder_marker": True},
                },
            ),
            (
                "hint-substring-match",
                {
                    "kind": "smoke",
                    "description": "hint='flow' picks vibe-flow.mp3 over others",
                    "input": {
                        "soundtrack_dir": "/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks",
                        "hint": "flow",
                    },
                    "expected": {"source_name_contains": "flow"},
                },
            ),
        ],
        "holdout": [
            (
                "stitched-50s-output",
                {
                    "kind": "holdout",
                    "description": "50s demo via Lyria preview stitching — boundary-click detection (Phase 4.5; needs Lyria)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
            (
                "abrupt-energy-aba",
                {
                    "kind": "holdout",
                    "description": "Scene energies high→low→high — agent must NOT over-engineer two-section structure (Phase 4.5)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
        ],
    },
    "sfx-curator": {
        "smoke": [
            (
                "click-mapping",
                {
                    "kind": "smoke",
                    "description": "click event → click_soft_01.wav placement",
                    "input": {
                        "events": [
                            {"id": "e1", "t": 1.0, "kind": "click"}
                        ]
                    },
                    "expected": {"placements_count_min": 1},
                },
            ),
            (
                "submit-confirm-blip",
                {
                    "kind": "smoke",
                    "description": "submit event → confirm_blip_01.wav",
                    "input": {
                        "events": [
                            {"id": "e1", "t": 1.0, "kind": "submit"}
                        ]
                    },
                    "expected": {"placements_with_clip": "confirm_blip_01"},
                },
            ),
            (
                "modal-whoosh",
                {
                    "kind": "smoke",
                    "description": "modal_open → modal_whoosh_01.wav",
                    "input": {
                        "events": [
                            {"id": "e1", "t": 1.0, "kind": "modal_open"}
                        ]
                    },
                    "expected": {"placements_with_clip": "modal_whoosh_01"},
                },
            ),
            (
                "no-events-empty-manifest",
                {
                    "kind": "smoke",
                    "description": "0 events → empty placements manifest, schema-valid",
                    "input": {"events": []},
                    "expected": {"placements_count": 0},
                },
            ),
            (
                "unmapped-kind-skipped",
                {
                    "kind": "smoke",
                    "description": "Unknown event kind → no placement, no error",
                    "input": {
                        "events": [
                            {"id": "e1", "t": 1.0, "kind": "weird_kind"}
                        ]
                    },
                    "expected": {"placements_count": 0},
                },
            ),
        ],
        "holdout": [
            (
                "drag-drop-unmapped",
                {
                    "kind": "holdout",
                    "description": "drag_and_drop kind never seen — agent must apply taste rules, not memorized table (Phase 5.5; LLM-driven)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
            (
                "punchline-mood-trap",
                {
                    "kind": "holdout",
                    "description": "punchline-anchored event tempts cartoonish sound — must stay 'Linear not Mario'",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
        ],
    },
    "composition-director": {
        "smoke": [
            (
                "anchor-resolution",
                {
                    "kind": "smoke",
                    "description": "captions resolve to absolute (start, end) per D4",
                    "input": {
                        "captions": [
                            {
                                "id": "c1",
                                "text": "x",
                                "mood": "announce",
                                "anchor_event_id": "e1",
                                "intent_duration": 2.0,
                                "priority": 5,
                            }
                        ],
                        "events": [{"id": "e1", "t": 1.0}],
                    },
                    "expected": {
                        "first_caption_start": 1.0,
                        "first_caption_end": 3.0,
                    },
                },
            ),
            (
                "collision-resolution",
                {
                    "kind": "smoke",
                    "description": "lower-priority overlap dropped",
                    "input": {
                        "captions": [
                            {
                                "id": "c1",
                                "text": "a",
                                "mood": "announce",
                                "anchor_event_id": "e1",
                                "intent_duration": 3.0,
                                "priority": 5,
                            },
                            {
                                "id": "c2",
                                "text": "b",
                                "mood": "aside",
                                "anchor_event_id": "e1",
                                "intent_duration": 3.0,
                                "priority": 2,
                            },
                        ],
                        "events": [{"id": "e1", "t": 0.0}],
                    },
                    "expected": {"dropped_count": 1, "kept_count": 1},
                },
            ),
            (
                "style-preset-explain-soft",
                {
                    "kind": "smoke",
                    "description": "explain-heavy + low energy → explain-soft",
                    "input": {
                        "moods": ["explain", "explain", "explain"],
                        "energies": ["low", "low"],
                    },
                    "expected": {"preset": "explain-soft"},
                },
            ),
            (
                "audio-mix-d9",
                {
                    "kind": "smoke",
                    "description": "Default audio.mix targets match D9",
                    "input": {},
                    "expected": {
                        "integrated_lufs": -14,
                        "true_peak_dbtp": -1,
                        "duck_to_lufs": -22,
                    },
                },
            ),
            (
                "duck-window-emitted-for-loud-moods",
                {
                    "kind": "smoke",
                    "description": "announce/callout/punchline/tagline emit duck_window; explain/aside don't",
                    "input": {
                        "captions": [
                            {
                                "id": "c1",
                                "text": "x",
                                "mood": "announce",
                                "anchor_event_id": "e1",
                                "intent_duration": 2.0,
                                "priority": 5,
                            },
                            {
                                "id": "c2",
                                "text": "y",
                                "mood": "explain",
                                "anchor_event_id": "e2",
                                "intent_duration": 2.0,
                                "priority": 4,
                            },
                        ],
                        "events": [
                            {"id": "e1", "t": 0.5},
                            {"id": "e2", "t": 5.0},
                        ],
                    },
                    "expected": {
                        "duck_announce_present": True,
                        "duck_explain_null": True,
                    },
                },
            ),
        ],
        "holdout": [
            (
                "phantom-anchor",
                {
                    "kind": "holdout",
                    "description": "anchor_event_id refers to nonexistent event — must emit error.json, not produce composition.json (Phase 6.5)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
            (
                "aside-heavy-high-energy",
                {
                    "kind": "holdout",
                    "description": "high motion + aside-heavy captions → explain-soft (mood beats energy) — covered in test_composition.py",
                    "input": {"covered_in_test": True},
                    "expected": {"covered_in_test": True},
                },
            ),
        ],
    },
    "qa-reviewer": {
        "smoke": [
            (
                "happy-path-pass",
                {
                    "kind": "smoke",
                    "description": "demo-deliverable.mp4 → signoff: pass or warn (low LUFS), no high-severity",
                    "input": {"final_mp4": "demo-deliverable.mp4"},
                    "expected": {
                        "signoff_in": ["pass", "warn"],
                        "no_high_severity": True,
                    },
                },
            ),
            (
                "ffprobe-detects-h264-aac",
                {
                    "kind": "smoke",
                    "description": "ffprobe metadata has h264 + aac",
                    "input": {"final_mp4": "demo-deliverable.mp4"},
                    "expected": {"video_codec": "h264", "audio_codec": "aac"},
                },
            ),
            (
                "ebur128-canonical-scalars",
                {
                    "kind": "smoke",
                    "description": "ebur128 returns rounded integrated_lufs + true_peak_dbtp",
                    "input": {"final_mp4": "demo-deliverable.mp4"},
                    "expected": {"ebur128_canonical_scalars_present": True},
                },
            ),
            (
                "spectrogram-evidence",
                {
                    "kind": "smoke",
                    "description": "sox spectrogram emitted as evidence",
                    "input": {"final_mp4": "demo-deliverable.mp4"},
                    "expected": {"spectrogram_path_present": True},
                },
            ),
            (
                "missing-final-mp4-fail",
                {
                    "kind": "smoke",
                    "description": "Missing final.mp4 → signoff: fail with FINAL_MP4_MISSING",
                    "input": {"final_mp4": "/nonexistent.mp4"},
                    "expected": {"signoff": "fail"},
                },
            ),
        ],
        "holdout": [
            (
                "spectral-hole-detection",
                {
                    "kind": "holdout",
                    "description": "Music has 1.8-3.2 kHz notch — qa-reviewer must flag MUSIC_SPECTRAL_HOLE (Phase 8.5)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
            (
                "sfx-onset-misalignment",
                {
                    "kind": "holdout",
                    "description": "SFX placements drift 250ms from event timestamps — must flag SFX_ONSET_MISALIGNED (Phase 8.5)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
        ],
    },
    "knowledge-curator": {
        "smoke": [
            (
                "fleet-walk",
                {
                    "kind": "smoke",
                    "description": "Walks all 9 agents' refresh.md and produces a report",
                    "input": {},
                    "expected": {
                        "report_path_exists": True,
                        "agents_inspected": 9,
                    },
                },
            ),
            (
                "freshness-manifest-updated",
                {
                    "kind": "smoke",
                    "description": "runs/refresh/manifest.json gets last_run + per-agent staleness",
                    "input": {},
                    "expected": {"manifest_has_last_run": True},
                },
            ),
            (
                "empty-proposals",
                {
                    "kind": "smoke",
                    "description": "Skeleton emits empty proposals.json (no LLM yet)",
                    "input": {},
                    "expected": {"proposals_count": 0},
                },
            ),
            (
                "single-agent-filter",
                {
                    "kind": "smoke",
                    "description": "--agent flag limits scope to one",
                    "input": {"agent": "qa-reviewer"},
                    "expected": {"agents_inspected": 1},
                },
            ),
            (
                "refresh-md-shape",
                {
                    "kind": "smoke",
                    "description": "Parses Pin facts and Sources sections per refresh-protocol.md",
                    "input": {},
                    "expected": {"required_sections_parsed": True},
                },
            ),
        ],
        "holdout": [
            (
                "stale-trimleft-detection",
                {
                    "kind": "holdout",
                    "description": "_shared/remotion.md says trimLeft, cached docs say trimBefore — must propose correction with citation (Phase 10.5; needs WebFetch + LLM)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
            (
                "adversarial-paraphrase-trap",
                {
                    "kind": "holdout",
                    "description": "Cached source has fact in two phrasings — curator must pick verbatim form (Phase 10.5)",
                    "input": {"future_spec": True},
                    "expected": {"future_spec": True},
                },
            ),
        ],
    },
}


def main() -> int:
    count = 0
    for agent, classes in CASES.items():
        for case_class, cases in classes.items():
            for case_id, doc in cases:
                _write_case(agent, case_class, case_id, doc)
                count += 1
    print(f"Seeded {count} eval cases across {len(CASES)} agents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
