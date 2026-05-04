# visual-analyst — design (from A1 ultraplan)

> Implementation phase: **3**. Phase 1 ships stub.

## Role contract

- **Reads:** `footage.mp4`, the events-section already written by event-log-analyst (knows uncovered ranges), `manifest.json`.
- **Writes (OWNS):** scenes with `source="visual"` in `analysis.json` + `keyframe_paths` arrays. Runs only on time ranges NOT covered by event-driven scenes (gap-filler) AND on entirety of `kind=screen` videos.
- **Tooling:** `dvg analyze --visual --gaps "<json>"` wraps PySceneDetect (`ContentDetector(threshold=27)` default; `AdaptiveDetector` for low-contrast UI; `ThresholdDetector` for fades), samples mid-frame to PNG, asks LLM to summarize each keyframe (1 call per scene, not per frame).

## System prompt shape

- **Voice:** descriptive, screen-aware. "What's on screen" not "what the user did" (that's event-log-analyst).
- **Principles:** Only fill gaps you were given. Visual scenes have lower confidence than event-driven scenes — `energy="low"` unless keyframe content strongly suggests otherwise. PySceneDetect is film-cut-tuned; UI demos have soft transitions; tune detector + threshold per case.
- **Hard constraints:** every `keyframe_paths` entry exists on disk in `runs/<ts>/keyframes/`. `Scene.start`/`end` quantized to fps boundary. Sum of visual durations ≤ sum of gap durations. **Keyframe count cap: 8/min footage** (cost guard per R2).
- **Refusal cases:** unreadable MP4 (corrupt). Empty PySceneDetect on non-empty gap → still emit one fallback scene per gap covering full duration with `summary="no detectable transitions"`.

## Knowledge files

- **core.md:** PySceneDetect API (`detect()`, detector classes, params). Detector selection rule (Content default; Adaptive if scene count < 1/30s; Threshold for fades). Frame sampling (`ffmpeg -ss <t> -i footage.mp4 -frames:v 1 -update 1`). LLM-on-keyframe prompt template returning `{summary, energy, ui_elements (≤5)}`. Output schema for visual scenes including `source="visual"`.
- **patterns.md:** Two-pass detector (Content first; retry Adaptive if density implausibly low). Keyframe deduplication (dHash, hamming ≤4 = duplicate; collapse adjacent). Gap-only invocation (per-gap `start_time`/`end_time` args). Idle-period heuristic.
- **gotchas.md:** Default `threshold=27` over-segments smooth scrolls (bump to 35). `min_scene_len=15` is fps-dependent (pin to fps/2). `OffthreadVideo` mistrusts non-keyframe-aligned cuts (round to GOP). Sample midpoint, not first frame (catches transitions mid-fade). LLM hallucinates UI labels confidently — `ui_elements` must be visually grounded; no business-logic guesses ("looks like a checkout page" forbidden). Cursor in screen recordings becomes "scene change" — mask bottom-right corner if `kind=screen`.
- **inspiration.md:** `[experimental]` OCR via `tesseract` for richer `ui_elements`. SAM-style segmentation. Cross-modal alignment (events vs visual to surface drift).

## Tools

- `Read` (manifest.json, existing analysis.json events section).
- `Bash` (`dvg analyze --visual`, `ffprobe`, `ffmpeg` for keyframe sampling).
- LLM vision (receives keyframe PNGs as image content).
- No `WebFetch`.

## Failure modes

1. Running on full video when events-driven analysis is already populated.
2. Hallucinating UI semantics from keyframes.
3. Emitting more scenes than gaps × reasonable density.
4. Picking ContentDetector for fade-heavy footage and reporting "no scenes."
5. Writing keyframe paths that don't exist on disk.

## Headline cases (5)

1. Pure screen recording, no events (60s, 5 distinct app states): 5–7 scenes, all keyframes exist, summaries grounded in visible UI.
2. Mixed coverage (events cover [0–10] and [20–30], gap [10–20]): produces ONLY visual scenes inside [10,20].
3. Smooth scroll demo (one continuous scroll): with default detector returns 1 scene + flag in summary that it switched to Adaptive after Content over-segmented; final 1–3 scenes.
4. Fade-to-black mid-demo: switches to ThresholdDetector, identifies fade as boundary.
5. Static idle gap (8s of no change): emits one `energy="low"` "idle/static" scene rather than dropping or hallucinating activity.

## Holdout (2)

1. **Cursor-only motion in screen recording** (15s of static screen, cursor moving): ContentDetector reports scene changes; right answer is one `energy="low"` scene noting cursor-only motion. Tests cursor-mask gotcha vs naive over-segmentation.
2. **Dark-mode app with low contrast** (`#1a1a1a` on `#0e0e0e`): default `ContentDetector(threshold=27)` finds nothing; agent must escalate to `AdaptiveDetector`. Tests that detector-selection rule applies on data, not on headline patterns.
