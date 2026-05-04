# dvg Changelog

## v0.2.0 — 2026-05-04 (initial lean build)

Built autonomously over an 8 h sprint as an alternative to the project's
`main` plan v2.2. Same artifacts contract, ~50 % the surface area.

### Added

* **Composition framework** — Pydantic discriminated-union of layers:
  `Video`, `Image`, `Caption`, `Title`, `Shape` (rect), `HTML`, `Sequence`, `Audio`.
* **Animation primitives** — `easing.py` (linear / cubic / spring / bezier),
  `keyframes.py` (Keyframe + ffmpeg-expression compiler with non-linear
  densification).
* **Renderer** — `composition/render.py` — Composition → ffmpeg complex
  filter graph → MP4 in one invocation. Multi-backend: libass + ffmpeg + Playwright.
* **Audio mix** — `composition/audio.py` — per-layer atrim/loudnorm/afade,
  optional sidechain ducking under caption windows, final loudnorm + alimiter
  at YouTube target (-14 LUFS / -1 dBTP).
* **libass captions** — 7 mood presets (announce, explain, punchline, aside,
  callout, tagline, call_to_action) with motion overrides (fade, pop, slide_up,
  fly_in). Pixel-perfect title-card centering via `\pos`.
* **Caption backdrop** (opt-in) — drawbox strip behind a CaptionLayer for
  readability on busy footage.
* **Capture** — Playwright headed/headless Chromium with DOM event logger.
  Auto-pilot scenarios: `tour`, `idle`, `load_script`.
* **Analysis** — events → scenes (gap-detected) + anchors
  (clicks, navigations, input-burst-end, scroll-stop, page_load).
* **Director** — heuristic v1, single `plan_composition(ctx) -> Composition`.
  Soundtrack picker (energy + duration + mood matching). Custom narration
  override via `DirectorContext.narrations`.
* **Brand pack** — `brand.json` config: colors, font, logo. Resolution via
  `DVG_BRAND` env var, `~/.config/dvg/brand.json`, or `./brand.json`.
* **QA** — `dvg review`: ffprobe, ebur128, aubio, silencedetect → severity-
  laddered findings (high / medium / low) with `proposed_action` codes.
* **Telemetry** — per-run rubric appended to `runs/_telemetry.jsonl`.
  Replaces main's per-agent eval framework.
* **Live preview** — `dvg preview composition.json` opens an HTTP server
  with a scrubbable timeline; mtime-watched re-render of the cached MP4.
* **Visual debug** — `dvg frame --t <s>` extracts a single frame;
  `dvg contact-sheet --cols N --rows M` produces a tiled preview grid.
* **Scaffold** — `dvg new <out>` writes a starter composition (.json or .py).
* **Sequence composability** — nested compositions; `Composition.flatten()`
  recursively expands at compile time.
* **Ken-Burns pan** — `VideoLayer.ken_burns: float` (0..0.5) for cinematic
  slow pans on captured footage.

### Tooling

* **CLI** — 16 commands: `version | doctor | new | render | plan | validate |
  schema | capture | analyze | direct | make-video | review | telemetry |
  frame | contact-sheet | preview`.
* **Tests** — 33 unit tests, ~10 s wall time.
* **Types** — `mypy --strict` clean (with `pydantic.mypy` plugin), 25 source
  files.
* **Lint** — `ruff` mostly clean (14 stylistic warnings: UP037, UP042,
  SIM105 — non-blocking).

### Demos shipped (in `runs/_demos/`)

* `dvg_demo_v1.mp4` — flagship 22 s demo. Made with dvg.
* `dvg_short_v1.mp4` — short-form 10 s variant on `vibe-flow.mp3`.
* `dvg_moods_v1.mp4` — caption-mood reference card (every preset, in order).
* `dvg_sequence_v1.mp4` — Sequence composability proof.
* `dvg_external_v2.mp4` — example.com captured with `--narrations`.
* `h2_animated.mp4` — keyframe transform demo.
* `h1/final.mp4` — first end-to-end render.

### Architecture decisions

See `.claude/lean/decisions.md` for L1–L9 (this branch) and the side-by-side
mapping with main's D1–D19 series.

### Known gaps (deferred)

* `HTMLLayer` per-frame animated path (only static path is wired).
* `ShapeLayer.shape == "circle" | "line" | "rounded_rect"` — only `rect` wired.
* LLM-backed director — interface ready, swap-in future work.
* Animated transforms wired only for `transform.position`; scale/rotation/
  opacity over time partially supported.

### Toolchain note

The default Homebrew `ffmpeg` formula does not include libass. Use
`brew install homebrew-ffmpeg/ffmpeg/ffmpeg` for the libass build.
`dvg doctor` checks for the `subtitles` filter.
