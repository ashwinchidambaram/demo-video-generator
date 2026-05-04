# composition-director — design (from A3 ultraplan)

> Implementation phase: **6**. Phase 1 ships stub. **Single most complex agent.**

## Role contract

- **Owns:** `composition.json` — and only that. Does NOT render. Does NOT invent captions or pick SFX clips.
- **Reads (everything):** `analysis.json` (canonical timing source), `captions.json` (anchored captions per D4), `music.mp3` (path + ffprobe metadata; audio analysis comes from `audio_qa.json` if present), `sfx/manifest.json`, `_shared/remotion.md`, `_shared/audio-qa-toolkit.md`.

### Derives (load-bearing work)

1. **Caption absolute timing per D4.** For each caption: `start = analysis.events[anchor_event_id].t + anchor_offset`, `end = start + intent_duration`. Then collision resolution: if two captions overlap and total priority weight exceeds capacity, drop lower-priority.
2. **Audio mix.** Sets `audio.mix` to D9 targets (-14 LUFS, -1 dBTP, duck to -22). Computes per-caption `duck_window` so music ducks under voiceless captions where SFX-density is low.
3. **Composition style.** Picks a style preset name from a small enum, mapped from dominant caption mood mix and analysis.scenes energy distribution.
4. **Layout.** Where each caption sits on screen (top-banner / bottom-third / corner-callout) based on `mood` and `analysis.scenes[].ui_elements`.

**Does not own:** font *files* (bundled with Remotion project), final pixel rendering, audio actually being mixed (Remotion does that during render).

## System prompt shape (load-bearing)

```
You are composition-director. You produce composition.json — the single
artifact that crosses the Python↔Node boundary into Remotion.

Three layers, in order:

1. RESOLVE TIMING (deterministic).
   For each caption in captions.json:
     start = analysis.events[anchor_event_id].t + (anchor_offset or 0)
     end   = start + intent_duration
   Then collision resolution per knowledge/patterns.md#collision-resolution.
   Drop priority<3 captions overlapping a higher-priority one beyond
   collision window.

2. PICK STYLE (judgment).
   Use style table in knowledge/patterns.md#style-presets.
   Inputs: dominant mood, scene energy distribution, presence of
   error/success events.
   Output: a single named preset (announce-clean, explain-soft,
   punchline-bold, retro-warm, neutral). Encode in composition.style.preset.

3. SET MIX (deterministic, audited).
   audio.mix = {integrated_lufs: -14, true_peak_dbtp: -1, duck_to_lufs: -22}
   For each caption with mood ∈ {announce, callout, punchline, tagline}:
     duck_window = {start: caption.start - 0.2, end: caption.end + 0.3}
   For mood ∈ {explain, aside}: no duck (let music carry).

MUST validate against composition.schema.json before exit. Emit error.json
if any anchor_event_id missing from analysis.events.

MAY shift caption start by ≤500ms to align with a music beat (reading
audio_qa.json if present), but MUST NOT change intent_duration.
```

## Knowledge files

- **core.md:** `composition.schema.json` walkthrough; D4 timing math with worked example; D9 audio targets; loads `@_shared/remotion.md`.
- **patterns.md:**
  - `#collision-resolution` — algorithm: sort by priority desc; place in order; drop if overlap >0.3s with placed caption of equal-or-higher priority.
  - `#style-presets` — table mapping `(dominant_mood, energy_profile)` → preset name. Each preset's spec lives in `remotion/src/styles/<preset>.ts`. **Knowledge file lists the decision rule; code owns the visuals.**
  - `#layout-rules` — bottom-third for `explain`, top-banner for `announce`, lower-corner for `aside`, full-bleed lower-third for `tagline`. Avoid collision with `analysis.scenes[].ui_elements`.
  - `#duck-shaping` — when to duck, ramp times.
- **gotchas.md:** Remotion v4 prop renames (`trimLeft → trimBefore`); `<OffthreadVideo>` requires `@remotion/renderer` not web-renderer (D13); missing anchor → fail loudly; duck windows past `duration_seconds` clamp not error.
- **inspiration.md:** `[experimental]` brand-pack support, multi-clip chapter markers, beat-synced caption snaps. None in v1.

## Caption-mood styles — separation of concerns

- **Decision rule** → `composition-director/knowledge/patterns.md#style-presets` (small table agent reads).
- **Preset name + caption mood** → `composition.json` (`per caption: mood`; top level: `style.preset`).
- **Visual realization** (font files, hex colors, motion easing, transition timings) → `remotion/src/styles/<preset>.ts` and `remotion/src/components/Caption<Mood>.tsx`.

Agent never picks a hex code or font URL — it picks a *name*; renderer looks up implementation. New presets are *code changes* with eval coverage, not agent-prompt drift.

## Tools

- `Read` (heavily — all upstream artifacts, all knowledge).
- `Bash`: `ffprobe -show_format music.mp3` (duration sanity); `python -m json.tool` or `dvg compose --check` for validation. **NO `ffmpeg ebur128`** — composition-director declares targets; qa-reviewer audits whether render hit them. Running ebur128 here is scope creep.

## Failure modes

1. **Phantom anchor** (caption references event not in analysis.events). Loud-fail rule + contract test.
2. **Caption pile-up** (two `announce` 0.5s apart with `intent_duration=4` overlap unreadably). Collision resolution + eval fixture.
3. **Duck-window leak** (`end > duration_seconds`). Clamp not error.
4. **Mix drift** (agent rewrites `audio.mix` defaults to "creative" values). Contract test: mix targets equal D9 defaults unless `--allow-mix-override` (not in v1).
5. **Style preset hallucination** (`cyberpunk-neon` not in enum). Schema enum on `composition.style.preset` (already added v2.2 commit).
6. **Overflow** (caption text exceeds layout box at chosen font size). Layout rule includes char-budget per slot; agent shrinks font tier (3 tiers per preset) before truncating.

## Headline cases (5)

1. Plain happy path (5 events, 4 captions, all `explain`, low energy). Expect `explain-soft` preset, no duck windows, captions in bottom-third.
2. Mixed-mood demo (opening `announce`, two `explain`, closing `tagline`, plus `punchline` mid-way). Tests preset choice + per-caption layout.
3. Dense-events trap (20 events in 10s, captions on consecutive events). Tests collision resolution.
4. Error-recovery story (failed submit + retry, two `callout` back to back). Tests duck shaping under SFX peaks.
5. Long demo (>2 min). Tests style preset stability + `intent_duration` end-to-end + duration-edge clamping for late captions.

## Holdout (2)

1. **Phantom anchor** (`anchor_event_id="evt-99"` not in events). Holdout because contract failure; right answer is "emit error.json, don't produce composition.json." Tests loud-fail under prompt drift. Producing *anything* is wrong.
2. **Style-fit ambiguity** (high visual energy but `aside`-heavy captions). "Obvious" choice (`punchline-bold` for high energy) is wrong; right choice is `explain-soft` because caption density is dominant signal. Stresses prompt fidelity over training instinct.

## Worked example

Input — `analysis.events`:
```json
[
  {"id": "evt-1", "t": 0.0,  "kind": "navigation", "label": "load /dashboard"},
  {"id": "evt-2", "t": 3.2,  "kind": "click",      "label": "open New Project"},
  {"id": "evt-3", "t": 5.8,  "kind": "modal_open", "label": "project modal"},
  {"id": "evt-4", "t": 9.4,  "kind": "click",      "label": "submit"},
  {"id": "evt-5", "t": 10.6, "kind": "modal_close","label": "success toast"}
]
```

Input — `captions.json`:
```json
{
  "schema_version": 1,
  "captions": [
    {"id": "c1", "text": "Meet your new dashboard.",
     "mood": "announce", "anchor_event_id": "evt-1",
     "intent_duration": 2.5, "priority": 5},
    {"id": "c2", "text": "One click to spin up a project.",
     "mood": "explain",  "anchor_event_id": "evt-2",
     "intent_duration": 2.0, "anchor_offset": -0.3, "priority": 4},
    {"id": "c3", "text": "Configure once.",
     "mood": "aside",    "anchor_event_id": "evt-3",
     "intent_duration": 2.0, "priority": 2},
    {"id": "c4", "text": "Done.",
     "mood": "punchline","anchor_event_id": "evt-5",
     "intent_duration": 1.5, "priority": 5}
  ]
}
```

Resolved `composition.json` excerpt:
```json
{
  "schema_version": 1,
  "fps": 30, "duration_seconds": 13.0,
  "resolution": {"width": 1920, "height": 1080},
  "footage": {"src": "footage.mp4"},
  "audio": {
    "music": {"src": "music.mp3", "gain_db": 0},
    "sfx": [
      {"src": "sfx/evt-2-0.wav", "t": 3.2, "anchor_event_id": "evt-2"},
      {"src": "sfx/evt-5-0.wav", "t": 10.6, "anchor_event_id": "evt-5"}
    ],
    "mix": {"integrated_lufs": -14, "true_peak_dbtp": -1, "duck_to_lufs": -22}
  },
  "captions": [
    {"id": "c1", "text": "Meet your new dashboard.", "mood": "announce",
     "start": 0.0, "end": 2.5, "priority": 5,
     "duck_window": {"start": -0.2, "end": 2.8}},
    {"id": "c2", "text": "One click to spin up a project.", "mood": "explain",
     "start": 2.9, "end": 4.9, "priority": 4, "duck_window": null},
    {"id": "c4", "text": "Done.", "mood": "punchline",
     "start": 10.6, "end": 12.1, "priority": 5,
     "duck_window": {"start": 10.4, "end": 12.4}}
  ],
  "dropped_captions": [
    {"id": "c3", "reason": "anchor_density",
     "details": "modal_open SFX + visual transition exceeds layout-density budget"}
  ],
  "style": {"preset": "announce-clean"}
}
```

Notes: c3 dropped (priority=2, anchor density too high). c1's `duck_window.start: -0.2` clamps fine at leading edge; trailing edge clamps against `duration_seconds`.
