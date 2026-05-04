# sfx-curator — design (from A3 ultraplan)

> Implementation phase: **5**. Phase 1 ships stub.

## Role contract

- **Reads:** `analysis.json` (events[]), `captions.json` (events anchored to important callouts get priority), curated pack manifest at `src/demo_video_generator/sfx/pack/index.json` (~30–50 clips per R2 — Kenney curated DOWN from ~150).
- **Writes (OWNS):** `runs/<ts>/sfx/<event_id>-<idx>.wav` files (copies/trims from pack) + `runs/<ts>/sfx/manifest.json` listing `{event_id, clip_path, source_clip_id, gain_hint_db, rationale}` per placement.
- **Derives:** event-to-clip mapping, density (which events get SFX vs none), gain hints. Does NOT own absolute placement time (that's `t` in composition.json, derived by composition-director).

## Aesthetic anchor (load-bearing)

> **"Linear notification, not Mario coin."** Tasteful UI feedback over arcade. Agent must know this in its bones.

## System prompt shape

Sections:
1. Role + non-goals (you pick UI sounds; you don't time them; you don't render).
2. Aesthetic anchor (load-bearing).
3. Rules of taste:
   - Not every event gets a sound. Aim ~30–50% of events. Quiet UI is a feature.
   - NEVER pick clips tagged `8bit`, `retro_game`, `coin`, `powerup`.
   - Successful submits/saves: short positive blip ≤300ms.
   - Errors: muted thump, never a "buzzer".
   - Modal opens: subtle whoosh ≤200ms; modal closes: silence is fine.
   - Repeated identical events (typing) get one sound at the start only.
4. Output `error.json` per error contract if no acceptable clip exists for a high-priority event.

## Knowledge files

- **core.md:** Pack manifest schema; canonical event-kind taxonomy from `analysis.schema.json`; how to read `captions.json` for anchor priority; how to write `sfx/manifest.json`.
- **patterns.md:** Worked event→clip recipes — `{kind: "click", selector: "button[type=submit]"} → ui_confirm_03.wav, gain -3dB`. ~12 recipes covering common UI events.
- **gotchas.md:** Don't double-fire on debounced events; typing bursts collapse to one sound; navigation events near a modal_open should defer to modal sound (avoid stacking); some Kenney clips have 50ms silence prefix that pushes perceived hit-time off — list which ones.
- **inspiration.md:** `[experimental]` Material Design Sound Resource Kit clips for more muted palette in v2.

## Tools

- `Read` (manifest, schemas, run dir).
- `Bash` (read-only `ffprobe` for duration sanity, `cp` from pack to run dir, optional `ffmpeg -ss -t` for sub-clip trim). NO `sox`/`ebur128` (qa-reviewer's job; keep this agent fast).

## Failure modes

1. **Over-SFXing** (every click gets a sound). Density rule + eval scoring 30-event capture, fail if >70% get SFX.
2. **Game-y picks.** "Linear not Mario" anchor + judge rubric on aesthetic fit.
3. **Manifest drift.** Files written but `manifest.json` lists different paths. Contract test: every file referenced exists; every file in dir is referenced.
4. **Anchor mismatch.** Picks "modal close" for `modal_open` event because label was ambiguous. Prompt teaches: read `event.kind` first, `event.label` second.
5. **Silently skipping high-priority events.** Schema requires `manifest.json` to either place or skip-with-reason for any event referenced by a caption.

## Headline cases (5)

1. Form submission flow (8 events: typing, focus, submit, success modal). Expect ~3 SFX (submit confirm + modal + maybe one input commit).
2. Error path (failed submit → red toast → retry). Muted thump, not buzzer.
3. Long typing burst (40 keypresses). One sound at start.
4. Navigation-heavy SPA (12 nav events). Sparse SFX (≤4); judge on "feels overdone".
5. Empty events (analysis has 0 events, screen recording with visual-only). Empty manifest with clean rationale entry.

## Holdout (2)

1. **Unusual event kind** — `drag_and_drop` event never seen in headlines. Tests whether prompt's *rules* generalize vs memorized headline taxonomy.
2. **Mixed taste trap** — `punchline` mood caption anchored to an event. Tests "Linear not Mario" discipline when caption tone invites cartoonish sound. Stresses aesthetic anchor against tempting-but-wrong cue.
