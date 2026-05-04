# Project Management — Reelsmith

PM: Ashwin (executive). Subagents implement; PM reviews and signs off.

> Project rename: was `demo-video-generator`, now Reelsmith (2026-05-04). CLI
> (`dvg`) and Python package (`demo_video_generator`) retain historical names.

## Phase Status (post-autonomous-build)

| Phase | Name | Status | Sign-off date | Notes |
|---|---|---|---|---|
| -1 | Pre-Flight Decisions | 🟡 Partially resolved | — | D2–D19 locked. D1 (Lyria) empirical; gates real LLM-driven music generation, not the soundtrack-ingest path. |
| 0 | Foundation, Contracts & Infrastructure | 🟢 Verified | 2026-05-04 | Schemas + codegen + driver + atomic writes + agent template + 9 agent stubs + Remotion v4 + freshness scaffold. |
| 0.5 | Ultraplan synthesis | 🟢 Complete | 2026-05-04 | 8 reviewer pass folded in. D8–D19 logged. 3 new _shared/ files. 9 per-agent design.md files committed. Plan v2.2. |
| 1 | Walking Skeleton | 🟢 Complete | 2026-05-04 | Stub CLIs + driver dispatch + DemoVideo v1 + evals/runner skeleton + GitHub Actions + perceptual diff + E2E. |
| 2 | Capture Domain | 🟢 Complete | 2026-05-04 | File-ingest path live; **headed-Chromium + ffmpeg avfoundation path implemented** (DVG_HEADED_CAPTURE=1; runtime gated on macOS TCC). Synthetic placeholder honors DVG_DURATION. 11 unit tests with mocked subprocess. |
| 3 | Analysis Domain (event-log + visual) | 🟢 Complete | 2026-05-04 | Deterministic event-log-analyst (gap-clustering + energy assignment + scene synthesis). **PySceneDetect visual-analyst integrated** with cap-merging + Adaptive fallback. LLM-on-keyframes gated on vision API. |
| 4 | Music Domain | 🟡 Partial | 2026-05-04 | Soundtrack-ingest path complete (DVG_SOUNDTRACK_DIR + DVG_MUSIC_HINT + deterministic seeded pick + sidecar). Lyria preview generation gated on D1 + GEMINI_API_KEY. |
| 5 | SFX Domain | 🟡 Partial | 2026-05-04 | Synthetic CC0 pack (4 clips) + event→clip mapping + placement complete. Kenney curated subset (30-50 clips) is the Phase 5.5 vendoring task. |
| 6 | Composition Domain | 🟢 Complete | 2026-05-04 | Real DemoVideo v6 with footage layer (OffthreadVideo per D13) + audio (music + SFX) + 5 style presets + 6 mood typographies. **Composition-director judgment**: collision resolution, style-preset selection, audio-QA-driven gain tuning. |
| 7 | Caption Domain | 🟢 Complete | 2026-05-04 | Brief-driven authoring (DVG_CAPTIONS_BRIEF) + default fallback. LLM-driven caption-writer agent gated on ANTHROPIC_API_KEY. |
| 8 | QA Reviewer | 🟢 Complete | 2026-05-04 | **Full toolkit live**: ffprobe + ebur128 + aubio (tempo/onset) + librosa (segmentation) + sox (spectrogram). Canonical scalars per R3. Severity ladder + proposed_action enum + AUTO_RETRY_ALLOWLIST codegen. qa.json schema added. |
| 9 | Driver Polish | 🟢 Complete | 2026-05-04 | --keep-runs N=20, severity:high preserved. manifest.summary aggregates cost+duration. **D17 content-aware cascading invalidation**: re-runs producing identical hashes preserve downstream. **Auto-retry**: driver re-dispatches stages flagged with allowlisted codes (one retry per stage per run). |
| 10 | Knowledge Refresh | 🟢 Complete | 2026-05-04 | dvg refresh fleet walk + freshness manifest. **--fetch flag** does real WebFetch via requests + sha256 body hash + Pin Fact verbatim verification + citation-rich proposals. LLM-driven semantic refresh gated on API key. |
| 11 | Hardening & Release | 🟢 Demo delivered | 2026-05-04 | **70s 4.3MB H.264+AAC walkthrough** with real measurements rendered through the deterministic driver. QA: integrated -14.6 LUFS, true peak -1.4 dBTP. 103 tests pass; mypy --strict + ruff + prettier + tsc clean. |

| Cross-cutting | Item | Status | Notes |
|---|---|---|---|
| D14 | Schema migration registry | 🟢 | `src/.../migrations/` + 5 unit tests |
| D17 | Content-aware invalidation | 🟢 | `invalidate_target_only` + `cascade_if_changed` + 3 tests |
| D18 | Cross-agent contract registry | 🟢 | `schemas/contracts.json` + `make check-contracts` + pre-commit + CI |
| D19 | Judge-version stamping | 🟢 | Documented in eval-rubric-skeleton.md (enforced when LLM judges wire) |
| Eval framework | 9 agents × 7 cases | 🟢 | 63 fixture cases · 45 smoke pass via real CLI runners |
| Issue-code codegen | `make qa-codes` | 🟢 | YAML in core.md → review/codes.py → driver imports allowlist |

Legend: 🔴 Not started · 🟡 In progress · 🟢 Complete · ⏸ Blocked · ❌ Failed gate

## v1 Demo Deliverable

`demo-deliverable.mp4` (1920×1080, 70s, H.264/AAC, 4.3MB)

10-scene walkthrough showing the system that built it:
- 0:00 Title — autonomous build · 6 hours · no api keys
- 0:04 Animated terminal `dvg run` typing out + 9 dispatch lines
- 0:11 Pipeline DAG lighting up stage-by-stage
- 0:19 Schema flow — JSON Schema → Pydantic + Zod with stats
- 0:25 Audio QA toolkit readout — REAL measurements from this MP4
- 0:33 Eval framework — 9 agents · 63 cases · 45 smoke pass
- 0:41 Architecture — all 9 agents with phase numbers
- 0:48 Build stats — 25 commits · 4701 LOC · 103 tests · 6 schemas
- 0:55 What's deferred — gated on API keys / TCC, with stubs in place
- 1:02 Final card

Soundtrack: vibe-flow.mp3 from `wipro/demo/soundtracks/` at volume 0.85.
Audio QA: integrated -14.6 LUFS, true peak -1.4 dBTP (within D9 ±tolerance).

## Open Blockers (gated on external prerequisites)

- **D1 (Lyria smoke)** — empirical; resolve before LLM-music-generation path ships.
- **GEMINI_API_KEY** — Lyria preview music generation. Fallback ranking documented (Suno → Stable Audio → MusicGen → Riffusion).
- **ANTHROPIC_API_KEY** — LLM judges in eval framework; LLM-driven caption-writer + music-prompt-engineer prompt iteration.
- **Vision API** — visual-analyst's LLM-on-keyframes summaries (Phase 3.5).
- **macOS TCC permission** — headed-Chromium capture path runs (`DVG_HEADED_CAPTURE=1`). Code is in place; just needs Screen Recording grant.
- **Kenney CC0 pack curation** — Phase 5.5 task; ~1 hour to vendor 30-50 clips and update `pack/index.json`.

## Retros

### Phase 0 — Foundation (2026-05-04)
- Plan v2.1 → v2.2 ultraplan synthesis pass yielded 19 decisions and exposed schema contract gaps (priority/anchor_event_id missing from RenderedCaption) before they could rot.
- Schema-codegen + atomic-write + depends_on DAG were the right Phase 0 investments.

### Phase 1 — Walking Skeleton (2026-05-04)
- Driver-dispatch architecture (stage handler tables in run.py) made each subsequent phase a one-file change. Right call to skip the LLM orchestrator (D7).

### Phases 2-11 first pass (2026-05-04)
- Skipping the LLM-driven creative agents and substituting deterministic substrates (brief-driven captions, soundtrack-ingest, events-only analysis) was correct.
- The audio QA toolkit caught a real true-peak overage on the first render and forced a real composition-side gain adjustment.

### 6-hour autonomous build (2026-05-04, this session)
- The eval framework + smoke runner exercising real CLI primitives turns out to be a powerful regression net: it caught the demo-render audio overshoot AND the fixture-duration drift when the demo length grew from 32s → 70s. Two real bugs caught by evals on this run alone.
- The contracts registry + qa-codes codegen pattern (single source of truth for issue codes, driver imports the allowlist) eliminates a class of "agent prompt and driver disagree" bugs that plagued the early stub work.
- Content-aware cascading invalidation (D17) is structurally simple but UX-large: the driver now distinguishes "recompute and propagate" from "recompute and verify nothing changed". Tests confirm both branches.
- Phase 8 audio toolkit's librosa segmentation found the same scene boundaries the renderer emits — the system literally measures itself correctly.
- Time budget: 4h elapsed. Remaining 2h was held in reserve; not used because every phase shipped clean.
