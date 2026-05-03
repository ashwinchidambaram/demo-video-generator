# Architectural Decisions

ADR-lite: dated records of decisions that shape the project. Each entry is short. Append-only — supersede via a new entry, do not rewrite history.

---

## Phase -1 Pre-Flight Decisions (must resolve before Phase 0)

### D1. Lyria access verification & music fallback
**Status:** 🔴 TBD
**Question:** Does `lyria-3-clip-preview` and/or `lyria-3-pro-preview` work today on Ashwin's `GEMINI_API_KEY`? What's the fallback if not?
**Verified context (May 2026):** Both Lyria models are Preview, not GA. `lyria-3-clip-preview` returns 30s MP3; `lyria-3-pro-preview` returns ~2-3 min WAV. Reachable via `google-genai` SDK without GCP project setup.
**Decision:** —
**Implication if Lyria preview:** stitch/crossfade required in Phase 4 (not deferred).

### D2. Schema source-of-truth
**Status:** 🔴 TBD (recommend JSON Schema → codegen)
**Question:** JSON Schema → codegen Pydantic + Zod, OR hand-maintain both?
**Recommendation:** JSON Schema as source. `datamodel-code-generator` (Pydantic) + `json-schema-to-zod` (Zod). One `make schemas` target.
**Why blocking:** `composition.json` crosses Python↔Node boundary; hand-parity rots silently.
**Decision:** —

### D3. Capture default strategy
**Status:** 🔴 TBD (recommend headed Chromium + ffmpeg)
**Question:** Default web-recording approach?
**Verified:** Playwright's built-in recorder is hardcoded VP8 ~1 Mbit/s at 800×800.
**Recommendation:** Default = headed Chromium + ffmpeg avfoundation region capture. Built-in recorder = headless/CI fallback. Both shipped.
**Decision:** —

### D4. Caption timing ownership
**Status:** 🔴 TBD (recommend anchor-based)
**Question:** Who owns `start`/`end` timestamps on captions?
**Recommendation:** `caption-writer` owns `(text, mood, anchor_event_id, intent_duration)`; `composition-director` derives `(start, end, duck_window)` from anchor + intent.
**Schema implication:** `captions.json` has no absolute timestamps; `composition.json` does.
**Decision:** —

### D5. Knowledge-loading mechanism
**Status:** 🔴 TBD (recommend section-loader)
**Question:** How does `knowledge/` content reach the prompt at dispatch time? Claude Code does NOT auto-traverse `knowledge/`.
**Options:** (a) `agent.md` includes via `@.claude/agents/<x>/knowledge/core.md`; (b) build step concatenates; (c) section-loader markers + build step.
**Recommendation:** (c) — `<!-- @load: knowledge/core.md#api-surface -->` markers, `make agents` materializes `agent.compiled.md`. 8k token budget per agent context.
**Decision:** —

### D6. Error / failure JSON contract
**Status:** 🔴 TBD (recommendation below)
**Question:** Standard error shape across CLI primitives + agents.
**Recommendation:** CLI: exit 0 = JSON to stdout; exit ≠ 0 = stderr JSON of `{error, code, retryable, suggestion, schema_version}`. Agents: emit `error.json` in run dir, exit. Driver: `retryable=true` → retry once, then escalate to qa-reviewer.
**Decision:** —

### D7. Director: keep or kill
**Status:** 🟢 KILL (recommended)
**Question:** Keep `director` agent, or replace with deterministic driver?
**Decision:** KILL `director`. Replace with `dvg run` Python driver that walks `manifest.json` and dispatches the next missing artifact's owning agent. `make-video.md` is a thin wrapper.
**Why:** LLM orchestrator under context pressure may skip steps, reorder, hallucinate completion. Deterministic driver cannot. `--from <step>` becomes "delete artifact, re-run."
**Date:** 2026-05-03 (in plan v2)

---

## Future entries (post-Phase-0)

Decisions made during implementation get appended below as `Dn` with date and rationale.
