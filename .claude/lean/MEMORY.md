# Lean DVG — Working Memory

**Branch:** `inventing-new-solutions`
**Started:** 2026-05-04 01:44
**Deadline:** 2026-05-04 09:44 (Ashwin asleep — 8 hour autonomous build)
**Goal:** Build something incredible. A leaner, better demo-video tool than what's in `main`.

## North Star

Production-grade demo videos with minimal friction. Output: 1080p+ MP4, well-mixed audio (-14 LUFS YT-aligned, -1 dBTP peak), polished captions, smooth motion. Tool: clean Python package, tested, typed, packaged. Eventually shareable.

## Bar raised (2026-05-04 ~01:50)
Ashwin: "Whatever you build has to be better than remotion and be able to do everything remotion does but better."
**Implication:** lean stack must MATCH Remotion's expressive surface (React-grade typography/animation) AND beat on speed/efficiency/audio. New architecture in `architecture.md` — multi-backend (libass + Skia + Playwright) composition framework.

## Architectural Bet (vs main's plan v2.2)

| Dimension | main | lean |
|---|---|---|
| Composition | Remotion v4 (Node) | Pure Python → ffmpeg filter graph |
| Schemas | JSON Schema → Pydantic + Zod | Pydantic only (export JSON Schema as artifact) |
| Languages | Python + Node | Python |
| Agent fleet | 9 specialized | 1–3 thicker (director + qa + maybe capture-strategist) |
| Eval framework | per-agent rubric+judge+holdout, $25/phase | Telemetry rubric on every run, $0/run |
| Render path | bundle()→selectComposition()→renderMedia | ffmpeg one-shot |
| Caption layer | React components | libass / Skia / HTML→PNG (TBD hour 1) |

## What I keep from main
- atomic writes (`atomic.py`)
- manifest DAG + cascading invalidation (D8, D17)
- audio QA toolkit (ebur128, sox, aubio)
- run-dir layout
- `dvg run` deterministic driver concept
- audio mix targets (-14 LUFS / -1 dBTP)
- ffmpeg pre-mix for ducking (D12 — decided for me)

## What I drop / replace
- Remotion + `remotion/` Node project
- Zod codegen + `make schemas` dual codegen
- Section-loader / `make agents` agent compile step
- Per-agent `evals/cases/{headline,smoke,holdout}` infra
- Director kill (D7) — I'll bring back ONE smart director, stay deterministic via single tool-using call with strict schema validation
- PySceneDetect (replace with simple frame-diff + LLM-on-keyframes)

## Operating discipline (PM rules for myself)
- Update THIS file at every decision, every task switch, every hour. It's the single source of truth.
- Commit at every passing test or working slice; push every hour minimum
- Use subagents for: web research, parallel implementation, code review
- Decisions go in `decisions.md` with brief why
- Ideas (scrollytelling, etc.) park in `ideas.md` — out of scope for this run
- If stuck >15 min, write down what's stuck and try a different angle

## 8-hour plan (will adapt)
1. **H1 (01:44-02:44):** Architecture, strip Remotion, first end-to-end skeleton (fixture vid + caption + soundtrack → MP4)
2. **H2 (02:44-03:44):** Composition library — Python timeline → ffmpeg DSL; caption mood styles; audio mix
3. **H3 (03:44-04:44):** Capture (Playwright headed Chromium) + analysis (DOM events + frame-diff gap-filler)
4. **H4 (04:44-05:44):** Director (single LLM call producing full composition.json from inputs); soundtrack picker
5. **H5 (05:44-06:44):** QA toolkit + telemetry rubric + `dvg review`
6. **H6 (06:44-07:44):** Real demo end-to-end on a real input; iterate output quality
7. **H7 (07:44-08:44):** Polish — animations, mood transitions, title/end cards, types/tests clean
8. **H8 (08:44-09:44):** Documentation, killer demo committed, README, migration notes

## Current state (last update 02:00)
- ffmpeg with libass (homebrew-ffmpeg/ffmpeg/ffmpeg formula — required because default brew formula lacks libass)
- aubio, sox, ffprobe installed
- Soundtracks at `/Users/ashwinchidambaram/dev/projects/wipro/demo/soundtracks/` (7 mp3s)
- Old structure (src/demo_video_generator, remotion/, schemas/) deleted; replaced with src/dvg/
- pyproject points at `src/dvg`; package name = `dvg`; deps: typer, pydantic, rich, Pillow, imagehash, playwright, anyio
- ✅ H1 DONE 02:00 (16 min): models, easing, captions/ass.py, audio.py, render.py
  - Smoke test passes: video + 4 captions + title + soundtrack with ducking → 12s 1080p MP4 in 3.27s
  - Output: -15 LUFS (target -14, close), -2.6 dBFS peak (under -1 ceiling), 8.5 Mbps H.264, 195kbps AAC
  - Demo at `runs/demo_h1/final.mp4` (13MB)
- Pyright editor warnings (import resolution) are spurious — runtime works. Will fix in H7 polish.

## Risks I'm carrying
- Caption typography: ffmpeg drawtext is ugly. libass is better but learning curve. HTML→PNG via Playwright works but adds a moving part. Decision in H1.
- Real demo input: need to pick something good for H6. Default: demo this very tool.
- Without LLM keys, the "director" is a heuristic — that's fine for v1; structured to swap in Anthropic API later.
