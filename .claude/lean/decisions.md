# Lean DVG Decisions

ADR-lite. Append-only. Every decision: status, date, why, what it implies.

---

## L1. Single language: Python only
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** No Node, no Remotion, no Zod codegen.
**Why:** Eliminates ~25-30% of main's surface area (dual codegen, two package managers, dual CI lanes, headless Chromium per render). The composition Remotion enables — video + styled captions + a single audio track — is achievable in pure ffmpeg + Python.
**Implies:** Lose React caption ergonomics + `npx remotion preview`. Caption typography handled by libass / Skia / HTML→PNG (decision L2 below).

## L2. Caption renderer choice
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** **libass (ASS subtitle format)** as primary; **Playwright HTML→PNG** as fallback for fancy mood-specific animations beyond ASS's reach.
**Why:**
- libass: mature, deterministic, integrated into ffmpeg as `subtitles` filter, supports rich typography (fades, fly-ins, scale, gradient, outline, shadow, karaoke), no spawn cost.
- HTML→PNG via Playwright: when we need CSS-grade effects (blur, custom layouts, complex animation curves). Playwright is already in the dep tree for capture.
- ASS covers ~90% of demo-video caption needs; HTML escape-hatch covers the rest.
**Implies:** Director emits `captions.json` with `(text, mood, anchor_event_id, intent_duration, style_overrides?)`. A "compile_to_ass" pass + optional "compile_to_html_pngs" pass produces inputs for ffmpeg. Mood→preset table.
**Rejected alternatives:**
- Pure ffmpeg drawtext: too primitive for production-grade typography.
- Pure Skia (skia-python): more code to write; loses the editability of ASS files (debugging is opening a `.ass` in any subtitle editor).
- React/Remotion: rejected at L1.

## L3. Schemas: Pydantic-source, JSON Schema as artifact
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** Pydantic models in Python are the single source of truth. `dvg schemas export` writes JSON Schema files for documentation. No codegen.
**Why:** Single language ⇒ no need for Zod. Writing Pydantic is faster than writing JSON Schema first.
**Implies:** Drop `make schemas`, `schemas/.checksums`, `datamodel-code-generator`. Keep schema_version field for future migrations.

## L4. Director: ONE smart agent (not nine)
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** A single director takes (capture metadata + events + analysis + soundtrack library) and emits a complete `composition.json` (with embedded captions + sfx placements + music pick + style). Deterministic Python turns it into MP4.
**Why:** Main's D7 "kill the director" was about *orchestration determinism*, not *intelligence centralization*. Determinism is preserved when the director is a single tool-using call producing one validated structured output.
**Implies:** No per-agent eval framework needed. Director's output is end-to-end testable. Capture-strategist and qa-reviewer remain (small, narrow tasks). Total agent count: 3.

## L5. No LLM keys in v1; heuristic director with structured swap-in
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** Director is a heuristic Python function in v1. The interface (`Director.plan(inputs) -> Composition`) is shaped so an LLM-backed implementation drops in unchanged.
**Why:** Ashwin asked to skip Gemini/ElevenLabs for now. Heuristic gets us to a working pipeline; quality bar will reveal whether LLM is needed.
**Implies:** Picks soundtrack by tag matching analysis "energy" axis; captions are template-driven from event names + LLM-friendly seed text we can later replace. Soundtrack tag table in `library/soundtracks.json`.

## L6. Audio mix unchanged from main: ffmpeg pre-mix → -14 LUFS / -1 dBTP
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** Adopt main's D9 (YouTube-aligned mix targets) and D12 (ffmpeg pre-mix not per-frame Remotion volume). The mix module produces `runs/<ts>/audio.mp3`; the compositor merges it with video as the final step.
**Why:** Decisions were correct in main. No reason to revisit.

## L7. Manifest DAG + atomic writes kept
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** Keep `atomic.py` (tmpfile + fsync + rename) and `manifest.py` (depends_on DAG + downstream BFS) unchanged from main. Add D17 content-aware invalidation now (not later).
**Why:** They're well-designed and load-bearing.

## L8. PySceneDetect dropped; frame-diff gap-filler
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** Visual scene analysis = ffmpeg-extracted frame samples + perceptual hash diff to find boundaries; LLM-on-keyframes (when LLM available) for labeling.
**Why:** PySceneDetect tunes for film cuts; UI demos don't have those. DOM event log is already the deterministic primary signal.
**Implies:** No `scenedetect` dep. `analysis/visual.py` uses imagehash + a configurable threshold.

## L9. Per-agent evals → telemetry rubric
**Status:** 🟢 ACCEPTED 2026-05-04
**Decision:** No headline/smoke/holdout per-agent. Instead: every `dvg run` writes a row to `runs/_telemetry.jsonl` with auto-measured signals (LUFS, length, caption density, render time, fail count) + an optional 5-question PM rubric.
**Why:** $25/phase × 11 phases = $275 of eval cost replaced by free per-run measurement. Trend analysis on telemetry catches regressions; manual rubric supplies taste judgment when watched.
**Implies:** Drop `evals/` infra. Build `dvg telemetry summary` CLI later.
