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
**Status:** 🟢 ACCEPTED 2026-05-03
**Decision:** JSON Schema in `schemas/*.schema.json` is the source of truth. `make schemas` runs `datamodel-code-generator` → Pydantic v2 (`src/demo_video_generator/schemas/`) and `json-schema-to-zod` → Zod (`remotion/src/schemas/`). Schema hashes recorded in `schemas/.checksums`; `dvg doctor` and `make schemas-check` enforce freshness.
**Why:** `composition.json` crosses the Python↔Node boundary; hand-parity rots silently.

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
**Status:** ⏸ Deferred to Phase 2 entry spike (1-hour, per v2.1 plan).
**Question:** How to hide Chrome chrome (omnibox/tabs) for clean demos? Options: `--app=URL`, `--kiosk`, CDP CSS injection.
**Decision:** —

---

## Future entries (post-Phase-0)

Decisions made during implementation get appended below as `Dn` with date and rationale.
