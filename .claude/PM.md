# Project Management — demo-video-generator

PM: Ashwin (executive). Subagents implement; PM reviews and signs off.

## Phase Status

| Phase | Name | Status | Sign-off date | Notes |
|---|---|---|---|---|
| -1 | Pre-Flight Decisions | 🟡 Partially resolved | — | D2–D7 locked (see DECISIONS.md). D1 (Lyria) empirical; gates Phase 4 entry, not Phase 0. |
| 0 | Foundation, Contracts & Infrastructure | 🟡 In progress | — | Scaffold + schemas + driver skeleton + agent template + Remotion v4 bootstrap built. Awaiting verification (`uv sync`, `make schemas`, `pytest`, `mypy`, `ruff`) and PM sign-off. |
| 1 | Walking Skeleton | ⏸ Blocked | — | Picks up `evals/runner.py`, GitHub Actions, perceptual-diff plumbing (deferred from P0 in v2.1). |
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
