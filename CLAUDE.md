# demo-video-generator — Claude Code Instructions

## What this project is

A tool that turns "a thing you built" into a production-quality demo video with minimal friction. The product is a fleet of specialized Claude Code subagents (each at `.claude/agents/<name>/`) backed by a thin Python CLI of deterministic primitives. Orchestration is deterministic via a Python driver (`dvg run`) that walks a per-run manifest and dispatches the next missing artifact's owning agent.

**v1 scope:** automated capture → scene analysis (event-log + visual) → on-screen captions → Gemini Lyria music (or fallback) → SFX (Kenney CC0 pack) → Remotion composition → MP4 → automated QA. **No voiceover** (v2).

## Project status

**Planning.** Implementation plan at `.claude/plans/v2-implementation-plan.md`; under refinement via ultraplan. Phase -1 pre-flight decisions are tracked in `.claude/DECISIONS.md`. Phase status in `.claude/PM.md`.

## Architecture summary

- **Python (uv) + Typer CLI** — deterministic primitives (`dvg run`, `dvg capture`, `dvg analyze`, `dvg music`, `dvg sfx`, `dvg compose`, `dvg render`, `dvg review`)
- **Remotion v4 (Node)** — composition layer in `remotion/`
- **Schemas** — JSON Schema source-of-truth → codegen Pydantic + Zod (do NOT hand-edit `src/.../schemas/` or `remotion/src/schemas/`)
- **Agents** — `.claude/agents/<name>/` with `agent.md` + `prompts/` + `knowledge/` + `evals/` + `refresh.md`
- **Cross-agent knowledge** — `.claude/agents/_shared/`
- **Per-run state** — `runs/<ts>/manifest.json` + artifacts; the driver advances by inspecting this

## Working norms

- Use the optimized-plan-orchestration skill before any multi-task plan
- Do not skip phase entry/exit gates defined in the plan
- Schema changes go through `make schemas` codegen — never edit generated files
- Prompt revisions require eval comparison (rubric ≥ baseline AND judge ≥ baseline AND holdout ≥ baseline AND no individual case drops > 1 point)
- The PM (Ashwin) signs off every phase exit in `.claude/PM.md`

## Key files

- `.claude/plans/v2-implementation-plan.md` — the plan (latest)
- `.claude/DECISIONS.md` — architectural decisions (ADR-lite)
- `.claude/PM.md` — phase status, blockers, retros
- `.claude/worklog.md` — day-by-day work log (gitignored)
- `.claude/agents/_template/` — skeleton for new agents
- `.claude/agents/_shared/` — cross-agent knowledge
- `schemas/*.schema.json` — single source of truth for inter-agent contracts
- `Makefile` — `make schemas`, `make agents`, `make test`, `make eval`
