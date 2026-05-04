# event-log-analyst — design (from A1 ultraplan)

> Implementation phase: **3**. Phase 1 ships stub.

## Role contract

- **Reads:** `footage.events.json` + `manifest.json` for duration/fps/resolution.
- **Writes (OWNS):** events-driven portion of `analysis.json` — every `Event` (copied through with stable ids) and any `Scene` whose `source="events"`. Writes top-level `duration_seconds`, `fps`, `resolution` if first analyst to land. **Never** writes keyframe-related fields.
- **Determinism contract:** for the same input, output bytes are identical (modulo fixed pretty-printer). LLM is used only for `Scene.summary` and `Scene.energy` — clustering is deterministic Python code in `dvg analyze`.

## System prompt shape

- **Voice:** analytical, structural. Reasons in event clusters and gaps.
- **Principles:** Events are ground truth. Don't invent. If `events.json` empty, emit `scenes=[]` and let visual-analyst handle it. Scene needs ≥1 event AND ≥1.5s duration; sub-1.5s clusters merge with nearest neighbor.
- **Hard constraints:** every `Scene.id` matches `^scene_\d{3}$`, sequential. Every input event id appears verbatim in output. Scenes non-overlapping and ordered.
- **Refusal cases:** events file missing (driver bug; emit error). Non-monotonic `t` (`code=EVENTS_OUT_OF_ORDER`, retryable=false).

## Knowledge files

- **core.md:** Event clustering rule (gap > 1.2s = boundary, configurable). Event taxonomy: `click`, `keydown`, `submit`, `framenavigated`, `pushstate`, `modal_open`, `console_error`, `network_failure` → default energy. Events section schema (verbatim from analysis.schema.json). Energy rubric: high = state-change events; medium = click/keydown bursts; low = scrolls/hovers/console info. Caption-anchor invariant: `Event.id` is opaque; preserve byte-for-byte.
- **patterns.md:** Cluster-then-summarize (deterministic clustering → LLM only on per-cluster summary, not whole log). Empty-coverage detection (mark gaps for visual-analyst via merge logic). Idle-period handling.
- **gotchas.md:** Filter `framenavigated` for `about:blank`. Synthetic events from devtools (`payload.isTrusted=false` downweight). `keydown` storms collapse to one event with `payload.text` summarized. `MutationObserver` modal-open lags click by ~100ms. Never rephrase `Event.label` (anchor lookup breaks).
- **inspiration.md:** `[experimental]` Cluster on event semantics for noisy demos. Detect "demo arc" (setup→action→result).

## Tools

- `Read` (events.json, manifest.json).
- `Bash` (call `dvg analyze --events-only` for deterministic clustering).
- No `WebFetch`/`WebSearch`.

## Failure modes

1. Calling LLM on entire event log (token blowup; non-determinism).
2. Mutating `Event.id` or `Event.label` during pass-through.
3. Producing overlapping scenes or duration overflow.
4. Inventing scenes for ranges with zero events (visual-analyst's job).
5. Treating `console.log`-spam as scene-defining.

## Headline cases (5)

1. Linear demo flow (login→form→submit→success, 8 events / 25s): 4 scenes, crisp boundaries at nav events.
2. Empty events file (screen recording): produces `events=[]`, `scenes=[]`. Does NOT emit visual-analyst output. Does NOT error.
3. Typing storm (38 keydowns / 4s): collapses to 1 scene with 1 representative event.
4. Console errors mid-flow: `console_error` does NOT split scenes (severity-tagged but folded).
5. Single 60s scene with one click: produces ONE scene spanning [0,60] anchored on the click. Does not artificially split.

## Holdout (2)

1. **Replayed events with non-monotonic timestamps** (clock skew): agent must emit `code=EVENTS_OUT_OF_ORDER` and not silently sort. The "right" tuning answer (sort + continue) is wrong — sorting masks a recording bug. Tests resistance to "be helpful" temptation.
2. **High-density UI tutorial** (45 events in 12s, all meaningful — keyboard shortcut tour): must NOT over-collapse. Tuning data tends to teach "merge aggressively"; rewards judgment about logical (not just temporal) boundaries.
