# dvg — production demo videos in one command

> Capture any URL, narrate, render — all in pure Python. No Node, no Remotion, no Webpack bundle step.

```bash
pip install dvg
dvg make-video https://your-app.com
```

→ `final.mp4` · 1080p · −14 LUFS · ready for YouTube

[See the demo (made with dvg)](runs/_demos/dvg_demo_v1.mp4)

---

## What dvg does

```
URL  ─►  capture  ─►  analyze  ─►  direct  ─►  render  ─►  MP4
              │            │           │            │
         Playwright    DOM events    one brain   ffmpeg
         1080p MP4     scenes +     picks music  + libass
                       anchors      + captions
```

Four deterministic stages. Every stage is testable, every artifact is schema-validated. One CLI command runs the whole pipeline.

## Why dvg vs Remotion

|                              |                  Remotion |                       dvg |
| ---------------------------- | ------------------------: | ------------------------: |
| Language                     |        TypeScript on Node |             Python (pure) |
| Composition model            |          React components |          Pydantic / JSON  |
| Render engine                |      Webpack → Chromium    |              libass + ffmpeg |
| Bundle step before render    |              ~10–25 s |                       0 s |
| 12 s output, render time     |        ~12–20 s typical |                ~3–5 s typical |
| Caption typography           |             CSS via React |        libass (.ass)       |
| Custom fancy graphics        |               Yes (CSS)   |    HTMLLayer (Playwright)  |
| Audio mix                    |       Manual orchestration |  Pre-mixed by ffmpeg       |
| LUFS / true peak enforcement |                Manual     | −14 LUFS / −1 dBTP enforced |
| Schema validation pre-render |                       No  |                       Yes |
| Multi-backend rendering      |                       No  |  libass / ffmpeg / Playwright |

Remotion's React component model wins on novel custom graphics. dvg wins on demo-shaped content (capture + narration + audio) where speed, simplicity, and audio compliance matter more than CSS expressiveness.

## Quickstart

```bash
# Install
pip install dvg
playwright install chromium
brew install homebrew-ffmpeg/ffmpeg/ffmpeg  # default brew formula lacks libass

# Verify
dvg doctor

# Make a video
dvg make-video https://example.com --duration 12

# Or step by step
dvg capture  https://example.com -o runs/myrun -d 12
dvg analyze  runs/myrun --duration 12
dvg direct   runs/myrun --url https://example.com
dvg render   runs/myrun/composition.json -o final.mp4
dvg review   final.mp4
```

## Architecture (lean stack)

```
src/dvg/
├── models.py              # Pydantic Composition + layers (the schema)
├── easing.py              # linear / cubic / spring / cubic-bezier
├── keyframes.py           # Keyframe + ffmpeg expression compiler
├── cli.py                 # typer CLI
├── capture/               # Playwright headed Chromium + DOM event log
├── analysis/              # DOM events → Scenes + Anchors
├── library/               # soundtrack picker (energy + duration match)
├── director/              # one brain → composition.json (heuristic v1)
├── composition/           # Composition → ffmpeg invocation
│   ├── render.py          # main compiler
│   ├── audio.py           # ffmpeg mix with sidechain ducking
│   ├── captions/ass.py    # libass file emitter, mood presets
│   └── html_layer.py      # static HTML → PNG (Playwright)
└── review/                # QA + telemetry
    ├── qa.py              # ebur128 / ffprobe / aubio / silencedetect
    └── telemetry.py       # per-run rubric → runs/_telemetry.jsonl
```

## Layer types (composition primitives)

```python
from dvg import (
    Composition, VideoLayer, ImageLayer, CaptionLayer,
    TitleLayer, HTMLLayer, AudioLayer, Mood,
)

comp = Composition(
    fps=30, width=1920, height=1080, duration=12.0,
    layers=[
        VideoLayer(src="footage.mp4", time=(0, 12), fit="cover"),
        TitleLayer(
            title="dvg", subtitle="demo videos in one command",
            time=(0, 2.5), fade_in=0.5, fade_out=0.5,
        ),
        CaptionLayer(
            text="Built lean", mood=Mood.PUNCHLINE,
            time=(3, 5.5), anchor="bottom-center",
        ),
        ImageLayer(src="logo.png", time=(0, 12), anchor="top-right"),
    ],
    audio=[
        AudioLayer(
            src="vibe.mp3", time=(0, 12),
            target_lufs=-22, duck_under_captions=True,
        ),
    ],
)
comp.render("final.mp4")  # ffmpeg one-shot
```

A `Composition` is a Pydantic model. Errors surface at construction time, not at render time. The same model serializes to and from `composition.json` — that's the inter-stage contract. The director emits it; the renderer consumes it.

## Animation primitives

```python
from dvg.keyframes import Keyframe
from dvg.easing import Easing
from dvg.models import Transform, ImageLayer

# Logo slides in from off-canvas right with ease-out:
ImageLayer(
    src="logo.png", time=(0, 10),
    transform=Transform(position=[
        Keyframe(t=0.0, v=(2000, 80)),                       # off-canvas
        Keyframe(t=1.0, v=(1500, 80), e=Easing.EASE_OUT),    # settled
    ]),
)
```

Keyframes compile to ffmpeg overlay expressions. Non-linear easings densify to piecewise linear. No per-frame Python in the hot path; the entire animation is *data* → an ffmpeg filter expression.

## Mood presets (libass-driven)

| Mood             | Default style                                        | Motion preset       |
| ---------------- | ---------------------------------------------------- | ------------------- |
| `announce`       | 64 px, bold, white                                   | slide-up + fade     |
| `explain`        | 44 px, white                                         | fade                |
| `punchline`      | 84 px, bold, accent color                            | scale-pop + fade    |
| `aside`          | 32 px, dim, italic                                   | fade                |
| `callout`        | 48 px, bold, accent color, shadow                    | fly-in + fade       |
| `tagline`        | 56 px, bold, white                                   | slide-up + fade     |
| `call_to_action` | 60 px, bold, accent color                            | scale-pop + fade    |

Override any field per-caption (`font_size`, `color`, `outline`, `shadow`).

## Audio compliance, enforced

Every render targets:

* **Integrated loudness:** −14 LUFS ± 1 (YouTube normalization-aligned)
* **True peak:** ≤ −1 dBFS (alimiter-enforced)
* **Sidechain ducking:** music ducks under caption windows

`dvg review final.mp4` runs the audio QA toolkit and returns a structured report:

```
QA — final.mp4
duration         22.00 s
dimensions       1920×1080
fps              30.00
video codec      h264
audio codec      aac
integrated LUFS  −14.3
true peak        −1.0 dBFS
LRA              3.0
BPM              134
dead air         0.0 s in 0 segs

✓ no findings
PASS
```

Trend over time:

```bash
dvg telemetry
```

Reads `runs/_telemetry.jsonl` (one row per `make-video` run) and aggregates render time, output size, LUFS, peak, caption density.

## Performance

Real numbers from the demo build (M-series Mac, 22 s 1080p output):

```
[1/4] capturing fixture site...   17.7 s   (real-time scenario)
[2/4] composition built            0.0 s
[3/4] rendering...                 4.8 s   (ffmpeg)
                                  ─────
                                  22.5 s   end-to-end
```

Capture dominates because Playwright runs the scenario in real time. **Render is one ffmpeg invocation** (no Webpack bundle, no Chromium). For comparison, Remotion's `bundle()` step alone is typically 10–25 s *before any frames are rendered*.

## Customizing

### A custom scenario for capture

```python
# my_demo.py — pass via --scenario my_demo.py
async def play(page, options):
    await page.click("text=Sign in")
    await page.fill("input[type=email]", "demo@example.com")
    await page.fill("input[type=password]", "•••••••")
    await page.click("button[type=submit]")
    await page.wait_for_url("**/dashboard")
    await page.wait_for_timeout(2000)
```

```bash
dvg capture https://your-app.com --scenario my_demo.py -d 12
```

### A custom title-card via HTML

```python
HTMLLayer(
    template=Path("title.html"),     # full canvas HTML
    time=(0, 2.5),
    bbox=(0, 0, 1920, 1080),
    fade_in=0.4, fade_out=0.4,
)
```

The HTML is rendered once via Playwright with a transparent background, then composited as an ImageLayer in the ffmpeg graph. Inline JSON props are injected as `window.__dvg_props`.

### Hand-craft a composition

```python
comp = Composition(...)
comp.save("composition.json")        # serialize
comp.render("final.mp4")             # render
```

Or render an existing one:

```bash
dvg render composition.json -o final.mp4
```

### Scaffold a new composition

```bash
dvg new my_demo.json --duration 15
# or as runnable Python
dvg new my_demo.py --duration 15 --style py
```

### Live preview while editing

```bash
dvg preview composition.json --port 8765
```

Opens a local server with a scrubbable timeline. Edit `composition.json`
and the preview re-renders automatically (mtime-watched). No bundle step;
the cached MP4 lives in `/tmp` and is regenerated only when the source changes.

Both forms emit a starter file with title intro, video, captions, and end-card placeholders. Edit the `src` paths and run.

## Comparison with the original plan

This branch (`inventing-new-solutions`) replaces the project's `main` plan v2.2 — which proposed Remotion + a 9-agent fleet + per-agent eval/refresh + dual JSON-Schema → Pydantic + Zod codegen — with a leaner alternative built around the same artifacts contract:

* **Kept:** atomic writes, manifest DAG with `depends_on` + content-aware invalidation, ffmpeg pre-mix audio, −14 LUFS / −1 dBTP targets, `_shared` knowledge concept, deterministic driver.
* **Replaced:** Node/Remotion → ffmpeg DSL · 9 agents → 3 (capture-strategist, director, qa-reviewer) · per-agent evals → per-run telemetry rubric · Zod codegen → Pydantic-only · PySceneDetect → DOM-event-log primary + frame-diff gap-filler.

Net: ~50 % less surface area, same end-state, single language, single CI lane. See `.claude/lean/decisions.md` for the side-by-side rationale.

## Status

Single-language Python implementation, working end-to-end. 1080p MP4 output, libass typography, ffmpeg audio mix with sidechain ducking, heuristic director with LLM swap-in interface, multi-backend renderer (libass + ffmpeg + Playwright).

Committed example outputs in `runs/_demos/`:

* **`dvg_demo_v1.mp4`** — full pipeline demo (22 s, 3.7 MB, −14.3 LUFS) ← made with dvg
* **`dvg_short_v1.mp4`** — short-form 10 s variant (2.5 MB, −14.6 LUFS)
* **`dvg_moods_v1.mp4`** — caption-mood reference card (18 s, 0.5 MB)
* **`dvg_external_v2.mp4`** — example.com captured with `--narrations` (8 s, 331 KB)
* `h2_animated.mp4` — keyframe animation demo
* `h1/final.mp4` — first end-to-end render
* `*_composition.json` — the paired compositions for each

## License

MIT.
