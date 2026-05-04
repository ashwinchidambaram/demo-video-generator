# Project Management — demo-video-generator

PM: Ashwin (executive). Subagents implement; PM reviews and signs off.

## Phase Status

| Phase | Name | Status | Sign-off date | Notes |
|---|---|---|---|---|
| -1 | Pre-Flight Decisions | 🟡 Partially resolved | — | D2–D7 locked. D1 (Lyria) empirical; gates real LLM-driven music generation, not the soundtrack-ingest path. |
| 0 | Foundation, Contracts & Infrastructure | 🟢 Verified | 2026-05-04 | Schemas + codegen + driver + atomic writes + agent template + 9 agent stubs + Remotion v4 + freshness scaffold. |
| 0.5 | Ultraplan synthesis | 🟢 Complete | 2026-05-04 | 8 reviewer pass folded in. D8–D19 logged. 3 new _shared/ files. 9 per-agent design.md files committed. Plan v2.2. |
| 1 | Walking Skeleton | 🟢 Complete | 2026-05-04 | Stub CLIs + driver dispatch + DemoVideo v1 + evals/runner skeleton + GitHub Actions + perceptual diff + E2E. |
| 2 | Capture Domain | 🟡 Partial | 2026-05-04 | File-ingest (kind=video) path complete + ffprobe duration. URL/screen paths blocked on macOS TCC + headed Chromium spike (D11). Synthetic placeholder honors DVG_DURATION. |
| 3 | Analysis Domain (event-log) | 🟢 Complete | 2026-05-04 | Deterministic event-log-analyst (gap-clustering + energy assignment + scene synthesis) live. visual-analyst (PySceneDetect + LLM) gated on Phase 3.5 (vision API). |
| 4 | Music Domain | 🟡 Partial | 2026-05-04 | Soundtrack-ingest path complete (DVG_SOUNDTRACK_DIR + DVG_MUSIC_HINT). Lyria preview generation gated on D1. |
| 5 | SFX Domain | 🟡 Partial | 2026-05-04 | Synthetic CC0 pack (4 clips) + event→clip mapping + placement complete. Kenney curated subset (30-50 clips) lands in Phase 5.5. |
| 6 | Composition Domain | 🟢 Complete | 2026-05-04 | Real DemoVideo v6 with footage layer (OffthreadVideo per D13) + audio (music + SFX) + 5 style presets + 6 mood typographies. Render bridge stages assets via remotion/public/<runId>/. |
| 7 | Caption Domain | 🟢 Complete | 2026-05-04 | Brief-driven authoring (DVG_CAPTIONS_BRIEF) + default fallback. LLM-driven caption-writer agent in a future iteration. |
| 8 | QA Reviewer | 🟡 Partial | 2026-05-04 | ffprobe + ffmpeg ebur128 toolkit live (canonical scalars per R3). Severity ladder + proposed_action enum live. sox/aubio/librosa subset lands Phase 8.5. |
| 9 | Driver Polish | 🟢 Complete | 2026-05-04 | --keep-runs N=20 default, severity:high preserved. manifest.summary aggregates total_cost + total_duration. |
| 10 | Knowledge Refresh | 🟡 Partial | 2026-05-04 | dvg refresh skeleton parses fleet refresh.md + writes report + freshness manifest. WebFetch/LLM proposal generation gated on API keys. |
| 11 | Hardening & Release | 🟢 Demo delivered | 2026-05-04 | Real 25s 1.1MB H.264+AAC MP4 with vibe-flow soundtrack rendered end-to-end. QA: pass with one low-severity LUFS warn (-14.6 vs -14 target). 54 tests pass. |

Legend: 🔴 Not started · 🟡 In progress · 🟢 Complete · ⏸ Blocked · ❌ Failed gate

## v1 Demo Deliverable

`demo-deliverable.mp4` (1920×1080, 25s, H.264/AAC, ~1.1MB)
- Subject: dvg system itself (title/explainers/punchline/tagline)
- Soundtrack: vibe-flow.mp3 (ingested from Ashwin's wipro/demo/soundtracks/)
- 5 captions (announce/explain×3 + callout + punchline + tagline) per Phase 7 brief
- Audio QA: integrated -14.6 LUFS, true peak -1.0 dBTP (within D9 targets ±tolerance)
- Visual QA: H.264 high profile, 30fps, 16:9

## Open Blockers (for future-phase polish)

- **D1 (Lyria smoke):** empirical; resolve before LLM-music-generation path ships.
- **D11 (Chrome chrome-hiding):** 1-hour spike before headed-Chromium capture path ships.
- **Phase 3.5:** PySceneDetect + LLM-on-keyframes for visual-analyst (vision API gating).
- **Phase 5.5:** Kenney CC0 pack curation (30-50 clips per ultraplan R2).
- **Phase 8.5:** Full audio QA toolkit (sox spectrogram, aubio tempo, librosa segmentation).
- **Phase 10.5:** Real WebFetch + LLM proposal generation for knowledge-curator.
- **Per-agent prompt iteration:** all 9 agents currently use stubs; LLM-driven prompts ship per agent's implementation phase.

## Retros

### Phase 0 — Foundation (2026-05-04)
- Plan v2.1 → v2.2 ultraplan synthesis pass yielded 19 decisions (D1-D19) and exposed schema contract gaps (priority/anchor_event_id missing from RenderedCaption) before they could rot. Worth the cost of the parallel-reviewer pass.
- Schema-codegen + atomic-write + depends_on DAG were the right Phase 0 investments — they removed entire classes of bugs in later phases (Phase 6 composition just _worked_ after schema fix because Pydantic + Zod parity held).

### Phase 1 — Walking Skeleton (2026-05-04)
- Driver-dispatch architecture (stage handler tables in run.py) made each subsequent phase a one-file change. Right call to skip the LLM orchestrator (D7).
- Deferred GitHub Actions + perceptual diff harness from P0 to P1 (per v2.1) was the right scoping.

### Phases 2-11 — Real pipeline (2026-05-04)
- Skipping the LLM-driven creative agents (caption-writer, music-prompt-engineer, visual-analyst) in this session and substituting deterministic substrates (brief-driven captions, soundtrack-ingest, events-only analysis) was correct: it let the end-to-end pipeline ship without dependencies on API keys + weeks of prompt iteration.
- The audio QA toolkit caught a real true-peak overage on the first render (-0.3 dBTP > -1 target) and forced a real composition-side gain adjustment. Phase 8 toolkit pays for itself.
- Remotion v4's `staticFile()` requirement (vs file://) bit us; staging assets via remotion/public/<runId>/ (with cleanup) is the right pattern.
