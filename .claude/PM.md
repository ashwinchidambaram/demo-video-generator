# Project Management — demo-video-generator

PM: Ashwin (executive). Subagents implement; PM reviews and signs off.

## Phase Status

| Phase | Name | Status | Sign-off date | Notes |
|---|---|---|---|---|
| -1 | Pre-Flight Decisions | 🟡 Partially resolved | — | D2–D7 locked. D1 (Lyria) empirical; gates Phase 4 entry, not Phase 0. |
| 0 | Foundation, Contracts & Infrastructure | 🟢 Verified | 2026-05-04 | Schemas + codegen + driver + atomic writes + agent template + 9 agent stubs + Remotion v4 + freshness scaffold. 33 tests pass; mypy/ruff/prettier clean. |
| 0.5 | Ultraplan synthesis | 🟢 Complete | 2026-05-04 | 8 reviewer pass folded in: schema contract gaps fixed (`priority`/`anchor_event_id`/`dropped_captions`/`style.preset` added; sfx artifact path fixed); D8–D19 logged; 3 new `_shared/` files (refresh-protocol, eval-rubric-skeleton, section-loader); 9 per-agent design.md files captured. Plan v2.2. |
| 1 | Walking Skeleton | 🟢 Complete | 2026-05-04 | Stub CLIs + driver dispatch + DemoVideo v1 + evals/runner skeleton + GitHub Actions + perceptual diff + E2E. End-to-end render produces real 480KB MP4. 42 tests pass (2 skipped on env). |
| 2 | Capture Domain | ⏸ Blocked | — | Entry: 1-hour D11 spike (chrome-hiding). |
| 3 | Analysis Domain (event-log + visual) | ⏸ Blocked | — | — |
| 4 | Music Domain | ⏸ Blocked | — | Gated on D1 + cost-cap revisit checkpoint. |
| 5 | SFX Domain (Kenney) | ⏸ Blocked | — | — |
| 6 | Composition Domain | ⏸ Blocked | — | — |
| 7 | Caption Domain | ⏸ Blocked | — | Phase 6 placeholder-caption goldens rebaselined here. |
| 8 | QA Reviewer | ⏸ Blocked | — | — |
| 9 | Driver Polish & Slash Command UX | ⏸ Blocked | — | — |
| 10 | Knowledge Refresh System | ⏸ Blocked | — | — |
| 11 | Hardening & Release | ⏸ Blocked | — | — |

Legend: 🔴 Not started · 🟡 In progress · 🟢 Complete · ⏸ Blocked · ❌ Failed gate

## Open Blockers

- **D1 (Lyria smoke):** empirical; resolve in one sitting before Phase 4 entry.
- **D11 (Chrome chrome-hiding):** 1-hour spike at Phase 2 entry.

## Retros

(empty — first will be at Phase 0 exit)
