# dvg (lean) — Claude Code Instructions

## Branch context

This is the `inventing-new-solutions` branch — a Python-only alternative to main's plan v2.2. Built autonomously over an 8 h sprint on 2026-05-04. Same artifacts contract; ~50 % the surface area.

For the full state of this branch, read `.claude/lean/MEMORY.md` first. Decisions log: `.claude/lean/decisions.md`.

## What this tool does

`dvg make-video <input>` turns a URL or video file into a production-grade demo MP4: 1080 p, −14 LUFS YouTube-aligned mix, polished captions, mood-matched soundtrack.

Pipeline: capture → analyze (DOM events + frame-diff) → director (single brain → composition.json) → compose (ffmpeg filter graph) → render → QA.

## Architecture summary

* **Python 3.12 + uv + Typer CLI** — single language, 16 CLI commands
* **Composition** — Python timeline DSL → ffmpeg filter graph (`src/dvg/composition/`)
* **Layers** — Video, Image, Caption, Title, Shape (rect), HTML, Sequence, Audio. Discriminated-union via `kind`. Sequence flattens at compile time.
* **Animation** — `easing.py` (linear/cubic/spring/bezier), `keyframes.py` (Keyframe → ffmpeg expression compiler).
* **Captions** — libass primary; HTMLLayer Playwright fallback. 7 mood presets with motion overrides.
* **Audio** — ffmpeg pre-mix (-14 LUFS / -1 dBTP); ducking via sidechaincompress under caption windows.
* **Director** — heuristic v1 with `narrations` override and brand-pack support; LLM swap-in interface ready.
* **Live preview** — `dvg preview composition.json` opens a scrubbable timeline; mtime-watched re-render.
* **QA** — ebur128 / ffprobe / aubio / silencedetect → severity-laddered findings.
* **Telemetry** — per-run rubric in `runs/_telemetry.jsonl`.
* **Schemas** — Pydantic-source; `dvg schema -o` exports JSON Schema.

## Working norms

* Update `.claude/lean/MEMORY.md` at every decision and every hour.
* Decisions go in `.claude/lean/decisions.md` with brief why.
* Out-of-scope ideas → `.claude/lean/ideas.md` (parking lot).
* Push at every passing test or working slice + at least hourly.
* Soundtrack library: `DVG_SOUNDTRACK_DIR` env var, then `~/.config/dvg/soundtracks/`, then `./soundtracks/`.
* Brand pack: `DVG_BRAND` env var, then `~/.config/dvg/brand.json`, then `./brand.json`.

## Key files

* `src/dvg/` — package source (25 files, mypy --strict clean)
* `src/dvg/models.py` — Pydantic discriminated-union of layers
* `src/dvg/composition/render.py` — Composition → ffmpeg invocation
* `src/dvg/composition/audio.py` — pre-mix with sidechain ducking
* `src/dvg/composition/captions/ass.py` — libass emitter, mood presets
* `src/dvg/composition/html_layer.py` — Playwright HTML→PNG (static)
* `src/dvg/cli.py` — 16-command typer CLI
* `src/dvg/director/heuristic.py` — single-call composition planner
* `src/dvg/library/soundtracks.py` — energy + duration + mood matching
* `src/dvg/library/brand.py` — BrandPack loader
* `src/dvg/preview/server.py` — hot-reload preview HTTP server
* `runs/_demos/` — committed demo MP4s + composition.json pairs
* `tests/unit/` — 33 passing tests
* `scripts/build_*.py` — runnable demo builders
* `scripts/benchmark.py` — performance benchmarks

## Comparison with main

`main` is shipping a 9-agent fleet with Remotion + dual codegen + per-agent eval rubrics. This branch trades all of that for a thinner, single-language pipeline. See `.claude/lean/decisions.md` for the side-by-side rationale and `BENCHMARKS.md` for measured timing.

## Test/lint/type commands

```
uv run pytest tests/             # 33 tests, ~10 s
uv run mypy src/                 # strict, 25 files
uv run ruff check src/ tests/    # 14 stylistic warnings (UP037/UP042/SIM105)
uv run dvg doctor                # toolchain check
```
