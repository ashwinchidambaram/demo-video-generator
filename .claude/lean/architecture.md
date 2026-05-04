# Lean DVG Architecture — "Better than Remotion"

## What Remotion does

1. React component model — declarative timeline
2. Frame-by-frame deterministic render via Chromium
3. `<OffthreadVideo>`, `<Audio>`, `<Sequence>`, `<Loop>`, `<Series>`, `<AbsoluteFill>`
4. `interpolate()` / `spring()` / `Easing` animation primitives
5. CSS-grade typography and animation
6. `bundle()` → `selectComposition()` → `renderMedia` programmatic API
7. Hot-reload preview studio (`npx remotion preview`)
8. Parametric compositions (props → re-shape video)
9. Lambda render farm (Remotion Cloud)
10. TypeScript types + browser devtools

## Where Remotion is weak / can be beaten

| Weakness | Lean DVG advantage |
|---|---|
| Webpack bundle step before render | No bundle step — Python composition runs directly |
| Browser-only render (Chromium per render) | Multi-backend: libass + Skia + browser; pick what each layer needs |
| Audio is afterthought (manual ducking) | Audio-first: BPM detection, declarative side-chain, LUFS-enforced |
| Node-only ecosystem | Python-native, pip-installable, integrates with Pillow/librosa/ffmpeg |
| No production guarantees | -14 LUFS / -1 dBTP enforced; perceptual diff CI-ready |
| Opaque render plan | Introspectable: print the ffmpeg graph, the layer count, ETA |
| TypeScript ergonomics | Pydantic ergonomics: schema validation = catch errors before render |
| No re-edit primitives | First-class "shorter", "mood swap", "translate captions" |
| Lambda needed for parallel | Layers parallelize naturally on the local machine |

## Architecture (revised, ambitious)

```
┌─────────────────────────────────────────────────────────────────┐
│ Composition (Pydantic)                                          │
│ - declarative timeline                                          │
│ - canvas, fps, duration, theme                                  │
│ - layers: List[Layer]                                           │
│ - audio: AudioMix                                               │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer types                                                     │
│ ──────────────                                                  │
│ • VideoLayer    — input MP4, time-shifted, transformed          │
│ • ImageLayer    — PNG/JPG with transforms                       │
│ • CaptionLayer  — text, mood, anchor, timing → libass backend   │
│ • TitleLayer    — title card composition (composite layer)      │
│ • ShapeLayer    — vector primitives → Skia backend              │
│ • HTMLLayer     — HTML template + props → Playwright backend    │
│ • AudioLayer    — music / sfx with volume + ducking             │
│                                                                 │
│ Each layer declares: time_range, transform (pos, scale, rotate, │
│ opacity), z-index, animation curves                             │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Animation primitives                                            │
│ ──────────────────────                                          │
│ • Easing.{linear, ease_in, ease_out, ease_in_out, bezier}       │
│ • spring(stiffness, damping, mass) → time→value                 │
│ • interpolate(time, [t0,t1], [v0,v1], easing)                   │
│ • Used in transforms, opacity, captions                         │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Compiler — Composition → RenderPlan                             │
│ ─────────────────────────────                                   │
│ Each layer compiles to one of:                                  │
│   • ffmpeg filter directly (overlay, drawbox, fade, scale)      │
│   • libass .ass file (captions, animated text)                  │
│   • Skia frame sequence in tmpdir                               │
│   • Playwright frame sequence in tmpdir                         │
│ + an audio filter graph (loudnorm, sidechaincompress, amerge)   │
│                                                                 │
│ Render plan introspection: `dvg plan composition.py` prints     │
│ the full ffmpeg invocation, ETA, intermediate file budget.      │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Renderer — single ffmpeg invocation                             │
│ ────────────────────────────────────                            │
│ • Pre-render Skia/HTML layers to PNG sequences                  │
│ • Compose ass file from caption layers                          │
│ • Build ffmpeg complex filter graph                             │
│ • One-shot render to final.mp4                                  │
│                                                                 │
│ Performance budget: ≤2x realtime for typical compositions       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Preview server (`dvg preview composition.py`)                   │
│ ───────────────────────────────────────────                     │
│ • Local HTTP server with simple scrub UI                        │
│ • watchdog watches composition.py                               │
│ • On change: invalidate cached frames, re-render scrubbed range │
│ • Per-layer cache (only re-render layers whose code changed)    │
│ • <100ms hot-reload for caption/text changes                    │
└─────────────────────────────────────────────────────────────────┘
```

## "Better than Remotion" measurable claims

These will be benchmarked at H8 against equivalent Remotion compositions:

1. **First-render time:** lean ≤ 50% of Remotion's (no bundle step).
2. **Caption-only edit hot-reload:** lean <500ms vs. Remotion's webpack rebuild.
3. **CPU per minute of output (caption-heavy):** lean ≤ 30% of Remotion's (libass not Chromium).
4. **Schema validation pre-render:** lean catches errors before render; Remotion catches at runtime.
5. **Audio compliance:** -14 LUFS guaranteed (enforced); Remotion makes you do this manually.

## What I won't claim
- Remotion's React component ergonomics for *novel* visual designs is genuinely better. Lean DVG bets that 80% of demo-video work is "video + captions + audio + occasional CSS," for which Lean DVG is faster and simpler.
- For very fancy bespoke graphics (Pudding-style scrollytelling visuals), the HTMLLayer with Playwright backend covers it but is the slowest path.

## Key abstractions to nail

```python
# What I want the user (or director agent) to write:

from dvg import Composition, VideoLayer, CaptionLayer, AudioLayer, mood

comp = Composition(
    fps=30, width=1920, height=1080, duration=22.5,
    background="#0a0a0a",
    layers=[
        VideoLayer(src="footage.mp4", time=(0, 22.5), fit="cover"),
        CaptionLayer(text="Built in a weekend", mood=mood.PUNCHLINE,
                     time=(0.5, 4.0), anchor="bottom-center"),
        CaptionLayer(text="Try it: dvg.dev", mood=mood.CALL_TO_ACTION,
                     time=(20.0, 22.5), anchor="bottom-center"),
        AudioLayer(src="vibe-edm.mp3", time=(0, 22.5),
                   target_lufs=-22, duck_under_captions=True),
    ],
    final_loudness=-14.0, peak_dbfs=-1.0,
)
comp.render("final.mp4")
```

The `Composition` is also serializable to JSON — that's `composition.json`. Director agent emits the JSON; Python reconstructs the model and renders. Both human-authoring and machine-authoring use the same surface.
