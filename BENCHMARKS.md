# dvg Benchmarks

Performance numbers from `scripts/benchmark.py`. M-series Mac, default `--preset medium --crf 18`.

## Render time vs composition complexity

| scenario | layers | output | render | size | LUFS | peak (dBFS) |
|---|---:|---:|---:|---:|---:|---:|
| minimal | 1 | 12.0 s | 3.17 s | 11.9 MB | −13.9 | −2.8 |
| typical | 6 | 12.0 s | 3.71 s | 14.7 MB | −14.4 | −1.5 |
| heavy | 13 | 22.0 s | 5.29 s | 15.4 MB | −14.3 | −1.4 |

Run `uv run python scripts/benchmark.py` to reproduce on your hardware.

## What's in each scenario

* **minimal**: a single `VideoLayer` + a single audio track. No captions, no titles. Bottom of the curve.
* **typical**: video + ken-burns pan + title intro + 3 captions (announce / explain / punchline) + image watermark + ducked audio. Realistic demo shape.
* **heavy**: 22 s, 13 layers — title + image watermark + 10 captions + heavy ken-burns + ducked audio. Stress test.

## Per-stage breakdown for `dvg make-video`

End-to-end on the polished landing-page fixture (real run, 22 s output):

```
[1/4] capturing fixture site...   17.7 s   ← Playwright runs the scenario in real time
[2/4] composition built            0.0 s   ← Pydantic validation
[3/4] rendering...                 4.8 s   ← single ffmpeg invocation
                                  ─────
                                  22.5 s   end-to-end
```

The capture stage dominates because Playwright runs the user's interaction script in
real time. **Render is one ffmpeg invocation** — no Webpack bundle, no Chromium spawn.

## Comparison context

For the same kind of content, Remotion's `bundle()` step alone is typically 10–25 s
*before any frames are rendered* (one-time per process; cached across renders if
you reuse the bundle). dvg has no bundle step.

Remotion's per-frame Chromium-driven render is ~1×–3× realtime on the same hardware.
dvg's ffmpeg render on equivalent compositions is ~0.2×–0.5× realtime.

Numbers vary with caption density and visual complexity. The benchmark above is
honest: my laptop, my fixtures, my measurement.
