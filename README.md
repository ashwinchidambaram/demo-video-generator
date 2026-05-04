# demo-video-generator

Turn "a thing you built" into a production-quality demo video. A fleet of
specialized Claude Code subagents (capture, scene analysis, captions, music via
Gemini Lyria, SFX, Remotion composition, QA) coordinated by a deterministic
Python driver.

**Status:** Phase 0 (foundation, contracts, infrastructure). See
`.claude/PM.md` for phase status and `.claude/plans/v2-implementation-plan.md`
for the full plan.

## Quickstart (Phase 0 — scaffolding only)

```bash
# Sync Python deps
uv sync --all-extras

# Install Remotion deps
cd remotion && npm install && cd ..

# Codegen Pydantic + Zod from JSON Schemas
make schemas

# Verify environment
uv run dvg doctor

# Run the (announce-only) driver against any input
uv run dvg run http://localhost:8765/index.html
```

Phase 0 ships the deterministic driver skeleton, schema codegen pipeline, error
contract, atomic-write helpers, agent template, `_shared/` knowledge, and
fixture HTTP server. Real agent dispatch wires up in Phase 1.

## Architecture

```
User → /make-video <input> → dvg run → walks runs/<ts>/manifest.json
                                       → dispatches owning agent for next missing artifact
                                       → validates artifact against schema
                                       → advances until final.mp4 + qa.json
```

The manifest is the driver's only state. `depends_on` per stage encodes the
DAG that `--from <step>` walks for cascading invalidation.

## Repo layout

```
src/demo_video_generator/   # Python CLI primitives
schemas/                    # JSON Schema (single source of truth)
remotion/                   # Remotion v4 composition layer
.claude/agents/             # Per-agent definitions, prompts, knowledge, evals
.claude/plans/              # Implementation plans
tests/                      # unit + contract + e2e + perceptual
```

## Decisions

See `.claude/DECISIONS.md`. Phase -1 decisions D1–D7 must be locked before
Phase 0 work begins. v2.1 of the plan locks D2–D7; D1 (Lyria access) is
empirical and gates Phase 4 entry, not Phase 0.
