# Architectural Decisions

ADR-lite: dated records of decisions that shape the project. Each entry is short. Append-only — supersede via a new entry, do not rewrite history.

---

## Phase -1 Pre-Flight Decisions

### D1. Lyria access verification & music fallback
**Status:** 🔴 TBD (empirical — gates Phase 4 entry, not Phase 0)
**Question:** Does `lyria-3-clip-preview` and/or `lyria-3-pro-preview` work today on Ashwin's `GEMINI_API_KEY`? What's the fallback if not?
**Verified context (May 2026):** Both Lyria models are Preview, not GA. `lyria-3-clip-preview` returns 30s MP3; `lyria-3-pro-preview` returns ~2-3 min WAV. Reachable via `google-genai` SDK without GCP project setup.
**Decision:** Pending. Run smoke call before Phase 4 entry.
**Ranked fallback (per v2.1):** (1) Suno API, (2) Stable Audio Open API, (3) MusicGen-medium local (Apple Silicon MPS only), (4) Riffusion.
**Implication if Lyria preview:** stitch/crossfade required in Phase 4.
**Implication if local MusicGen:** Apple Silicon required; document Intel-mac unsupported in `dvg doctor`.

### D2. Schema source-of-truth
**Status:** 🟢 ACCEPTED 2026-05-03 (lock policy softened 2026-05-04 per ultraplan R4)
**Decision:** JSON Schema in `schemas/*.schema.json` is the source of truth. `make schemas` runs `datamodel-code-generator` → Pydantic v2 (`src/demo_video_generator/schemas/`) and `json-schema-to-zod` → Zod (`remotion/src/schemas/`). Schema hashes recorded in `schemas/.checksums`; `dvg doctor` and `make schemas-check` enforce freshness.
**Lock policy (v2.2):** Schemas are LOCKED at end of Phase 0 *except for additive non-breaking changes* (new optional field, new enum value, new optional sub-schema) signed off by PM in this DECISIONS.md. Breaking changes (removed field, type narrowing, removed enum value, required-field addition) require a `schema_version` bump per D14.
**Why:** `composition.json` crosses the Python↔Node boundary; hand-parity rots silently. The softer lock prevents the awkward "unfreeze ceremony" R4 flagged.

### D3. Capture default strategy
**Status:** 🟢 ACCEPTED 2026-05-03
**Decision:** Default web-recording = headed Chromium driven by Playwright + ffmpeg avfoundation region capture. Built-in Playwright recorder is the headless/CI fallback (hardcoded VP8 ~1 Mbit/s at 800×800 — not 1080p-grade). Both shipped.
**Note:** macOS TCC Screen Recording permission applies to web capture too, not just `--screen` mode.
**Implements via:** `src/demo_video_generator/capture/playwright_headed.py` (default) and `playwright_builtin.py` (CI). Phase 2.

### D4. Caption timing ownership
**Status:** 🟢 ACCEPTED 2026-05-03
**Decision:** `caption-writer` owns `(text, mood, anchor_event_id, intent_duration, anchor_offset, priority)`. `composition-director` derives final `(start, end, duck_window)` from the anchor event in `analysis.json` plus the intent duration. `captions.json` has no absolute timestamps; `composition.json` does.
**Why:** caption-writer can re-time by changing anchors without touching composition logic; composition can shift timing for audio mixing without rewriting copy.

### D5. Knowledge-loading mechanism
**Status:** 🟢 ACCEPTED 2026-05-03
**Decision:** Section-loader markers + build step (`make agents`). Each `agent.md` declares `<!-- @load: knowledge/core.md#section -->` markers; `compile_agents.py` materializes `agent.compiled.md` (the file Claude Code loads). Per-agent budget: 32k chars (~8k tokens). CI fails the build if any compiled agent exceeds budget.
**Why:** prevents prompt bloat; allows shared knowledge in `_shared/` to be referenced without duplication.

### D6. Error / failure JSON contract
**Status:** 🟢 ACCEPTED 2026-05-03
**Decision:** All CLI primitives: exit 0 = JSON to stdout; exit ≠ 0 = stderr JSON conforming to `schemas/error.schema.json` (`{schema_version, error, code, retryable, suggestion, stage, context}`). Agents on tool failure: emit `error.json` in the run dir and exit. Driver retry policy: `retryable=true` ⇒ retry once, then escalate to `qa-reviewer` for triage.
**Implementation:** `src/demo_video_generator/errors.py`. Shared docs in `.claude/agents/_shared/error-contract.md`.

### D7. Director: keep or kill
**Status:** 🟢 KILLED 2026-05-03
**Decision:** No `director` agent. Replaced with `dvg run` Python driver that walks `manifest.json` and dispatches the next missing artifact's owning agent. `make-video.md` is a thin wrapper.
**Why:** an LLM-orchestrator under context pressure may skip steps, reorder, or hallucinate completion. A deterministic driver walking `manifest.json` cannot. `--from <step>` becomes "delete the artifact, re-run."

---

## Phase 0 Decisions

### D8. Cascading invalidation lives in the manifest, not the driver
**Status:** 🟢 ACCEPTED 2026-05-03 (v2.1 plan revision)
**Decision:** Per-stage `depends_on: [stage_name]` in `manifest.schema.json`. The driver computes the transitive downstream set with BFS and deletes those artifacts before re-walking. Encoding lives in data, not driver heuristics.
**Implementation:** `src/demo_video_generator/manifest.py::downstream_of` + `invalidate`.

### D9. Audio mix targets — YouTube-aligned
**Status:** 🟢 ACCEPTED 2026-05-03 (v2.1 plan revision)
**Decision:** Final mix integrated -14 LUFS ±1, true peak ≤ -1 dBTP. Music ducking under SFX peaks ≤ -22 LUFS. Music stems pre-mix in [-16, -12] LUFS.
**Why:** YouTube normalizes to -14; targeting -16 means YouTube turns it up, which can clip transients that passed the true-peak check.
**Revisit:** if the dominant distribution channel changes (e.g. broadcast podcasts at -16).

### D10. Atomic writes for every artifact
**Status:** 🟢 ACCEPTED 2026-05-03
**Decision:** Every artifact write goes through `src/demo_video_generator/atomic.py::write_atomic` (tmpfile + fsync + `os.replace`). A kill mid-stage cannot poison re-runs.
**Why:** Phase 0 exit criterion: half-written `analysis.json` (or any other artifact) must never exist.

---

## Phase 2 entry decisions (deferred)

### D11. Headed Chromium chrome-hiding
**Status:** ⏸ Deferred to Phase 2 entry spike (per v2.1; ~1 hour, evidence-bundled per ultraplan R2).
**Question:** How to hide Chrome chrome (omnibox/tabs) for clean demos? Options: `--app=URL`, `--kiosk`, CDP CSS injection.
**Decision:** —
**Spike evidence requirement (added v2.2):** Each option must produce a 5-second sample MP4 committed under `tests/fixtures/spikes/d11-<option>.mp4` with verified (a) Playwright launches with the option; (b) DOM event recording (`addInitScript`) still fires; (c) ffmpeg-region coordinates produce a clean image without UI chrome bleed; (d) cursor visibility intact. A spike that produces only a written decision but no reproducible artifacts fails to convince a reviewer 6 weeks later.

---

## Phase 6 entry decisions (added v2.2 from ultraplan)

### D12. Audio ducking implementation
**Status:** 🟢 ACCEPTED 2026-05-04 (per ultraplan R1 §1.5)
**Decision:** Audio ducking is implemented as **ffmpeg pre-mix** into a single composite audio track Remotion plays as a single `<Audio>` source. NOT per-frame `volume` interpolation on Remotion `<Audio>` components.
**Why:** (a) deterministic — ebur128-verifiable before render lands; (b) simpler renderMedia parallelization (no per-frame React state); (c) predictable mix targets per D9. Per-frame volume would couple audio QA to render output and complicate the Phase 8 audio QA toolkit assertions.
**Implementation:** Phase 6 ships a Python `composition/audio_premix.py` that takes `composition.json.audio.{music, sfx, mix}` + per-caption `duck_window`s and produces `runs/<ts>/mix.mp3` for Remotion to play. Audio sidechain shape is a sum of duck_windows.

### D13. Footage layer Remotion primitive
**Status:** 🟢 ACCEPTED 2026-05-04 (per ultraplan R1 §2)
**Decision:** Footage layer = `<OffthreadVideo>` (from `@remotion/renderer`) for the renderMedia path. `<Video>` is allowed only in `npx remotion preview` for development.
**Why:** `<Video>` works in browser preview but degrades (audio sync drift) on `renderMedia`. `<OffthreadVideo>` is the documented v4 primitive for server-rendered pipelines. Locking this now prevents Phase 6 from re-deriving it as a research outcome.
**Caveat:** `<OffthreadVideo>` requires `@remotion/renderer`, NOT `@remotion/web-renderer`. Phase 1 task list pins `@remotion/renderer` in `remotion/package.json` to prevent accidental web-renderer imports.

---

## Cross-cutting decisions (added v2.2 from ultraplan)

### D14. Schema migration / version bump policy
**Status:** 🟢 ACCEPTED 2026-05-04 (per ultraplan R4 §2)
**Decision:** Schema versioning follows three rules:
1. **Bump rule:** `schema_version` (currently `const: 1` on every artifact) is a monotonic integer. Bump only on breaking changes (removed field, type narrowing, removed enum value, required-field addition).
2. **Minor versioning:** Additive non-breaking changes (per D2 lock policy) live in a separate `schema_minor` field (defaulted to 0). Bump `schema_minor` on each additive PR.
3. **Migration shim:** `src/demo_video_generator/schemas/migrations/v<N>_to_v<N+1>.py` per artifact, registered in a migration table loaded by the driver. Driver migrates forward on `manifest.json` load if `schema_version < CURRENT`. Old run dirs become readable; nobody writes v(N-1) after the bump.
4. **Codegen invariant:** `schemas/.checksums` already exists; also write `schemas/.versions` recording per-artifact `schema_version` + `schema_minor`. CI fails if a checksum changed without an explicit version bump.
5. **Golden-fixture routing:** `tests/fixtures/golden/v<N>/` per major version; perceptual-diff harness routes by manifest `schema_version`.
**Owner:** PM. The curator never bumps schemas.

### D15. Holdout rotation policy
**Status:** 🟢 ACCEPTED 2026-05-04 (per ultraplan R4 §4)
**Decision:** Holdout cases (2 per agent) rotate every **90 days** OR on any schema bump touching the agent's artifact, whichever first. Rotation logged in `evals/cases/<agent>/holdout/CHANGELOG.md`. Old holdouts move to `headline/` for ongoing tracking (not discarded).
**Why:** stale holdouts get memorized through prompt-tuning leakage (PM reads them while debugging). Rotating preserves the holdout-as-fresh-judgment property.

### D16. Eval cost cap revision
**Status:** 🟢 ACCEPTED 2026-05-04 (per ultraplan R4 §3)
**Decision:** Original $5/refresh and $10/phase-eval caps were under-modeled. Revised:
- **Phase eval cap:** $25/phase-eval (was $10). Rationale: 9 agents × 17 cases × Opus-judge realistic cost is ~$10–20 lower bound; with retries and large multi-artifact inputs (composition-director, qa-reviewer), $15–30 is realistic.
- **Refresh cap:** $15 *per agent refreshed* (was $5/run). Curator fetches 20–30 docs per agent.
- **Cost revisit gates:** Phase 4 entry (already in plan) AND **Phase 8 entry** (added — qa-reviewer evals are heaviest). Track per-stage `cost_usd` in `manifest.json` (field exists since Phase 0) starting Phase 2.
- **Amortization:** (1) headline judges run only on PR with `eval` label OR phase exit, NOT nightly; (2) nightly runs **one** randomly-rotated agent's quality eval, not the fleet; (3) Sonnet primary judge with Opus tiebreaker when scores within 1 point of baseline; (4) ephemeral cache rubric prompts (~50% input-token savings).

### D17. Content-aware cascading invalidation
**Status:** 🟢 ACCEPTED 2026-05-04 (per ultraplan R4 §1)
**Decision:** Each `manifest.stages[].artifact_sha256` records the SHA256 of the produced artifact bytes (Phase 0 schema already includes this field). On `--from <step>`, the driver re-runs the target stage; if the new artifact's hash matches `artifact_sha256`, downstream cascading is **skipped** (downstream stages' artifacts remain valid).
**Why:** structural `depends_on` over-invalidates. A re-run of `analyze` that produces byte-identical `analysis.json` shouldn't blow away captions/music/sfx. UX win is large; semantic change is small.
**Implementation:** Phase 1 task addition — driver hashes each stage output and updates `artifact_sha256`; `invalidate()` becomes a two-phase operation (target re-run, then conditional cascade).

### D18. Cross-agent contract registry
**Status:** 🟢 ACCEPTED 2026-05-04 (per ultraplan R4 §4)
**Decision:** `schemas/contracts.json` lists every consumer of every producer's schema fields. A pre-commit check fails if a producing agent's schema changes a field without all listed consumers acknowledging via a checksum bump in `contracts.json`.
**Why:** Zod/Pydantic validate *shape*, not *enum cross-reference*. When caption-writer adds a new mood, composition-director's caption-mood-style mapping silently maps unknown moods to a default. The registry forces explicit ack.
**Shape:**
```json
{
  "captions.json#captions[].mood": {
    "producers": ["caption-writer"],
    "consumers": ["composition-director", "qa-reviewer"],
    "consumer_acks": {
      "composition-director": "<sha256-of-acked-enum-set>",
      "qa-reviewer": "<sha256-of-acked-enum-set>"
    }
  }
}
```
Phase 1 task addition: scaffold `schemas/contracts.json` + pre-commit check.

### D19. Eval baseline + judge-version stamping
**Status:** 🟢 ACCEPTED 2026-05-04 (per ultraplan R4 §4)
**Decision:** Each `evals/cases/<agent>/baselines/v<N>.json` records `judge_model` (e.g. `claude-opus-4-7`) and `judge_version` (e.g. `4-7-20260403`). On judge major-version upgrade (Opus 4.7 → 4.8), full re-baseline required before any prompt revision lands. Promotion rule (≥ baseline) compares only against same-judge baselines.
**Why:** baselines are not portable across judge models. Without stamping, a judge upgrade silently shifts the bar.

---

## Future entries (post-Phase-0)

Decisions made during implementation get appended below as `Dn` with date and rationale.
