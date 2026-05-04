# dvg (lean) — Claude Code Instructions

## Branch context

This is the `inventing-new-solutions` branch — a leaner alternative to main's plan v2.2. The architecture is intentionally different:

- **Single language Python** (no Node, no Remotion, no Zod codegen)
- **libass + Playwright** for caption rendering
- **Pydantic-only** schemas (JSON Schema is an exported artifact)
- **One director agent** (not nine), heuristic v1 with LLM swap-in interface
- **Telemetry rubric** instead of per-agent eval/refresh framework

For the full state of this branch, read `.claude/lean/MEMORY.md` first. Decisions log: `.claude/lean/decisions.md`.

## What this tool does

`dvg make-video <input>` turns a URL or video file into a production-grade demo MP4: 1080p, -14 LUFS YouTube-aligned mix, polished captions, mood-matched soundtrack.

Pipeline: capture → analyze (DOM events + frame-diff) → director (single brain → composition.json) → compose (ffmpeg filter graph) → render → QA.

## Architecture summary

- **Python 3.12 + uv + Typer CLI** — single language
- **Composition** — Python timeline DSL → ffmpeg filter graph (`src/dvg/composition/`)
- **Captions** — libass primary, Playwright HTML→PNG fallback for fancy moods
- **Audio** — ffmpeg pre-mix (-14 LUFS / -1 dBTP); ducking via sidechain
- **Per-run state** — `runs/<ts>/manifest.json` + artifacts; deterministic driver walks the DAG
- **Schemas** — Pydantic models in `src/dvg/models.py`; JSON Schema export via `dvg schemas export`

## Working norms

- Update `.claude/lean/MEMORY.md` at every decision and every hour
- Decisions go in `.claude/lean/decisions.md` with brief why
- Hourly worklog entries in `.claude/lean/worklog.md`
- Out-of-scope ideas → `.claude/lean/ideas.md` (parking lot)
- Push at every passing test or working slice + at least hourly
- Soundtrack library: `/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/`

## Key files

- `src/dvg/` — package source
- `src/dvg/models.py` — Pydantic models (single source of schema truth)
- `src/dvg/composition/` — timeline → ffmpeg compiler
- `src/dvg/director/` — single agent that emits composition.json
- `src/dvg/capture/` — Playwright-driven capture
- `src/dvg/review/` — audio QA + telemetry rubric
- `runs/<ts>/` — per-run artifacts
- `runs/_telemetry.jsonl` — append-only telemetry across runs

## Comparison with main

`main` is shipping a 9-agent fleet with Remotion + dual codegen + per-agent eval rubrics. This branch trades all of that for a thinner, single-language pipeline. See `.claude/lean/decisions.md` for the side-by-side rationale.
