# Morning summary — 2026-05-04

## What to look at first

1. **`runs/_demos/dvg_demo_v1.mp4`** — The primary deliverable. 22 s, 1080 p, MP4. Made with dvg.
2. **`runs/_demos/dvg_short_v1.mp4`** — Short-form variant (10 s, vibe-flow soundtrack).
3. **`README.md`** — Sells the tool; includes vs-Remotion comparison + full architecture.
4. **`runs/_demos/dvg_demo_v1_composition.json`** — The Composition that produced the demo.

## What was built

A working Python-only alternative to `main`'s plan v2.2. Same artifacts contract, ~50 % the surface area.

Modules in `src/dvg/`:

* **`models.py`** — Pydantic `Composition` with discriminated-union layers: `Video`, `Image`, `Caption`, `Title`, `Shape`, `HTML`, `Sequence`, `Audio`. `Sequence` flattens at compile time for nested-composition composability (Remotion's `<Sequence from={N}>` equivalent).
* **`easing.py`** — `linear`, `ease_in/out/in_out`, `cubic_bezier`, `Spring` (Remotion-compatible).
* **`keyframes.py`** — `Keyframe` model + ffmpeg-expression compiler. Non-linear easings densify to piecewise linear. `Transform.position` keyframes compile to `overlay=x='if(lt(t,…))…'`.
* **`composition/render.py`** — `Composition → ffmpeg complex-filter graph → MP4` in one invocation. Handles canvas, video layers (cover/contain/fill, ken_burns pan), image layers (anchor + offset), caption + title via libass, end-to-end with the audio stem muxed in.
* **`composition/audio.py`** — ffmpeg pre-mix per `D12` from main's plan: per-layer atrim/loudnorm/afade/adelay → optional sidechaincompress under caption windows → amix → final loudnorm + alimiter at the YouTube target (−14 LUFS / −1 dBTP, with 0.5 dB headroom for the limiter).
* **`composition/captions/ass.py`** — libass `.ass` emitter. Mood presets: `announce`, `explain`, `punchline`, `aside`, `callout`, `tagline`, `call_to_action` — each with size, color, outline, and motion override (`fade`, `pop`, `slide_up`, `fly_in`).
* **`composition/html_layer.py`** — Pre-renders an HTML page once via Playwright, drops it in as an Image layer.
* **`capture/playwright_capture.py`** — Headed/headless Chromium with DOM event logger + auto-pilot scenarios.
* **`capture/scenarios.py`** — `tour`, `idle`, `load_script` for custom Playwright recipes.
* **`analysis/events.py`** — Events → `Scenes` (gap-detected) + `Anchors` (clicks, navigations, input-burst-end, scroll-stop, page_load).
* **`director/heuristic.py`** — `plan_composition(ctx) -> Composition`. v1 is heuristic; the signature is shaped so an LLM-backed implementation drops in unchanged. Picks soundtrack by energy match against scene energy + duration check; places captions on anchors when informative, beat-paced when not. Now respects `ctx.narrations` for custom copy.
* **`library/soundtracks.py`** — Soundtrack picker (energy/tempo/mood tagged).
* **`review/qa.py`** — Audio + visual QA. ffprobe → dimensions/codec; ebur128 → integrated LUFS / true peak / LRA; aubio → BPM; silencedetect → dead-air segments. Severity-laddered findings with `proposed_action` codes.
* **`review/telemetry.py`** — Per-run rubric appended to `runs/_telemetry.jsonl`. Replaces main's per-agent eval framework.
* **`cli.py`** — `dvg version | render | plan | validate | schema | capture | analyze | direct | make-video | review | telemetry | doctor`.

## Quality numbers

* `mypy --strict` clean across all 23 source files (with `pydantic.mypy` plugin).
* 15 unit tests pass (smoke render, keyframes, capture, sequence flattening).
* Both demos `dvg review` PASS — no findings, audio in band.

## How dvg compares with main's plan

| | main (plan v2.2) | this branch |
| --- | --- | --- |
| Languages | Python + Node | Python |
| Composition | Remotion v4 (React) | ffmpeg DSL |
| Schemas | JSON Schema → Pydantic + Zod | Pydantic only |
| Agent fleet | 9 specialized | 1–3 thicker (capture-strategist, director, qa) |
| Per-agent evals | Headline + smoke + holdout, judge diversity, $25/phase | Per-run telemetry rubric |
| Caption typography | React/CSS | libass |
| Render path | bundle()→selectComposition()→renderMedia | ffmpeg one-shot |
| Audio | Manual + ffmpeg pre-mix per D12 | ffmpeg pre-mix (kept) |
| Mix targets | -14 LUFS / -1 dBTP per D9 | -14 LUFS / -1 dBTP (kept) |

## Decisions log

`.claude/lean/decisions.md` — L1 through L9, with side-by-side rationale vs main's D-series.

## Known limitations

* `HTMLLayer` per-frame animation is a sketch; only static path is wired through. Animated HTMLLayer + the live preview server are noted in `.claude/lean/ideas.md`.
* The director is heuristic; an LLM-backed swap will need access to model APIs (you said skip Lyria/ElevenLabs for now).
* The title intro centers slightly low in libass when subtitle is present — visually fine, but pixel-perfect centering would require `\\pos(x,y)` with manual coords instead of `\\an5`.
* Ken-burns pan is a left-right `sin` sweep on a fixed-size crop; a true zoom-in (vary crop dims) hit ffmpeg's even-dimension constraint and was rolled back.

## Toolchain note

The default Homebrew `ffmpeg` formula does **not** include libass. Use `homebrew-ffmpeg/ffmpeg/ffmpeg` for the libass build (already noted in the README). `dvg doctor` checks for the `subtitles` filter and prints the brew command if it's missing.

## Where to start in the morning

* Watch `runs/_demos/dvg_demo_v1.mp4`.
* Watch `runs/_demos/dvg_short_v1.mp4`.
* If you want to see dvg run end-to-end on something new:
  ```
  cd .worktrees/inventing-new-solutions
  uv run dvg make-video https://example.com --duration 8 --headless \
     --title "example.com" --tagline "captured by dvg"
  ```
* Compare to `main`'s `.claude/plans/v2-implementation-plan.md` if you want the side-by-side rationale.
