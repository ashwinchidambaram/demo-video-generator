# footage-capture — design (from A1 ultraplan)

> Implementation phase: **2**. Until then, this file is the design spec; Phase 1
> ships a stub CLI primitive.

## Role contract

- **Reads:** `manifest.json` (`input.kind`, `input.value`, `config`).
- **Writes (OWNS):** `footage.mp4` + `footage.events.json` in run dir, atomic.
- **Decides:** capture mode (`headed` Chromium / `builtin` Playwright / `screen` ffmpeg avfoundation), fps (default 30), resolution (default 1920×1080), Playwright DOM-event instrumentation when `kind=url`.
- **Hard boundary:** for `kind=video` (pre-recorded file), normalizes to H.264/yuv420p and writes empty-but-valid `footage.events.json`. Never fabricates events.

## System prompt shape

- **Voice:** terse operator. Picks a mode, states why in one line, executes.
- **Principles:** Prefer highest-fidelity path that preserves DOM events. Order: `headed` > `screen` > `builtin`. Never silently downgrade modes. `builtin` is CI/headless fallback only.
- **Hard constraints:** must not run unless `dvg doctor` exit was 0 within 24h. Must not exceed `config.max_duration_seconds`. Canonical event listeners live in `core.md`, not the prompt.
- **Refusal cases:** localhost URL with no fixture server running; `kind=screen` on non-macOS (v1 macOS-only); requested duration > 600s.

## Knowledge files

- **core.md:** Three modes' invocation commands; ffmpeg avfoundation command; Playwright launch options (`--app=URL`, `--window-size=1920,1080`, `--hide-crash-restore-bubble`); built-in recorder call; canonical DOM-event instrumentation (`addInitScript` injecting capture-phase listeners); `footage.events.json` shape; output normalization (`-c:v libx264 -pix_fmt yuv420p -crf 18 -preset veryfast -movflags +faststart -an`); macOS TCC.
- **patterns.md:** Mode-selection decision tree; cursor visibility; sync flash at t=0 for visual-analyst grounding; "quiet the chrome" patterns per D11.
- **gotchas.md:** avfoundation device IDs reorder on display reconnect (enumerate at runtime via `ffmpeg -f avfoundation -list_devices true -i ""`); `record_video_size` larger than viewport silently letterboxes; Retina 2× DPR (pass `device_scale_factor=1`); `page.close()` BEFORE `context.close()` flushes builtin video; VP8 from builtin not seekable in `OffthreadVideo` without re-mux; cursor jitter at 60fps; macOS Sonoma+ screen-recording indicator pixel bleed (crop with `-vf crop=iw:ih-22:0:22`).
- **inspiration.md:** `[experimental]` Playwright trace files alongside MP4; auto-zoom on click events; Retina-aware smart resolution.

## Tools

- `Bash` (run `dvg capture`, `ffmpeg`, `ffprobe`, enumerate avfoundation devices).
- `Read` (manifest.json, doctor cache, fixture HTML).
- No `WebFetch`/`WebSearch`.

## Failure modes

1. Picking `builtin` when `headed` would have worked (silently ships 800×800).
2. Recording without DOM instrumentation when `kind=url` (kills downstream determinism).
3. Writing events.json with `Date.now()` instead of video-clock-aligned timestamps.
4. Continuing past `max_duration_seconds` "just in case."
5. Catching ffmpeg errors and retrying with degraded settings instead of escalating.

## Headline cases (5)

1. URL with rich interaction (form submit + nav): 1080p H.264 MP4 with ≥6 events covering click→submit→nav arc, `t` aligned to video clock within 50ms.
2. CI/headless run (`config.headless=true`): picks `builtin`, doesn't error on missing display.
3. Pre-recorded file input (`kind=video`, 720p MOV): normalizes to 1080p H.264 yuv420p, empty `events.json`.
4. macOS TCC denied: emits `error.json` `code=TCC_DENIED`, `retryable=false`, system-prefs URL in `suggestion`. Does NOT retry. Does NOT downgrade.
5. Long page with deferred load: waits on `networkidle` BEFORE starting recording clock + sync flash.

## Holdout (2)

1. **External-display reconnect mid-init:** avfoundation device list reorders between `dvg doctor` and `dvg capture`. Must re-enumerate. Tests *don't-hardcode-device-id* gotcha; easy to study to the test if seen in tuning.
2. **Single-page app with `pushState` only:** `framenavigated` fires once; route changes via History API. Agent must inject `popstate`+`pushState` proxy listener. Failure mode is silent (events.json looks fine, just thin).
