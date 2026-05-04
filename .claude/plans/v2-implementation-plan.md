# demo-video-generator — Phased Implementation Plan (v2, post-bar-raise)

## Revision History
- **v1** — initial plan
- **v2** — folded in 4 Opus reviewer findings + audio-QA toolkit insight. Major changes: dropped `director` agent in favor of deterministic `dvg run` driver; added Phase -1 Pre-Flight Decisions; verified-fact updates to Lyria / Playwright / Remotion; split `scene-analyst` into event-log + visual; demoted `render-engineer` to CLI-only; added audio-QA shell toolkit as the audio-judgment substrate; promoted CI, schema codegen, perceptual diff, judge diversity, `_shared/` knowledge, and held-out eval cases into Phase 0.
- **v2.1** — self-review pass. Trimmed Phase 0 by deferring eval-runner scaffolding / GitHub Actions / perceptual-diff plumbing to Phase 1; promoted cascading-invalidation (`depends_on`) and freshness-manifest scaffolding into Phase 0 so the manifest contract is locked once; defined the "first revision is baseline" eval rule; added cost-cap revisit gate before Phase 4; moved headed-Chromium chrome-hiding spike to Phase 2 entry; flipped LUFS target to -14 integrated / -1 dBTP for YouTube alignment; marked Phase 6 golden MP4s as placeholder-caption with explicit Phase 7 rebaseline; added artifact atomic-write requirement; defined Phase 11 "successful demo" criteria; added `dvg doctor` schema-hash freshness check and TCC-URL remediation.

---

## Context

Tool that turns "a thing you built" into a production-quality demo video with minimal friction. Product is a fleet of specialized Claude Code subagents (each at `.claude/agents/<name>/`) backed by a thin Python CLI of deterministic primitives. Orchestration is **deterministic**: a Python driver (`dvg run`) walks a per-run manifest and dispatches the next missing artifact's owning agent. This replaces the v1 plan's "Claude Code is the orchestrator" approach, which had nondeterministic-dispatch failure modes.

**v1 scope:** automated capture → scene analysis (event-log + visual) → on-screen captions → Gemini Lyria music (or fallback) → SFX (Kenney CC0 pack) → Remotion composition → MP4 → automated QA. **No voiceover** (v2).

**Why this shape:** intelligence lives in agent definitions; the package is a thin set of deterministic tools the agents drive. Inter-agent communication is JSON-on-disk (run directory) validated by codegenerated schemas (Pydantic + Zod from one JSON Schema source).

---

## Phase -1 — Pre-Flight Decisions (must complete before any code)

These are the convergent blockers all four reviewers flagged. They are decisions, not implementation, and must be locked before Phase 0 begins. Each produces a row in `.claude/DECISIONS.md`.

### D1. Lyria access verification
**Decide:** Does `lyria-3-clip-preview` and/or `lyria-3-pro-preview` work today on Ashwin's `GEMINI_API_KEY`? What's the fallback?
**Action:** Run a smoke call against both Lyria preview models — this is the only empirical Phase -1 item and gates Phase 4 entry. Target: resolve in one sitting (≤1 hour). If accessible, commit. If not, decide fallback in ranked order: (1) Suno API, (2) Stable Audio Open API, (3) MusicGen-medium local (Apple Silicon MPS only — Intel mac too slow for v1 latency budget), (4) Riffusion. **Do not start Phase 0 with this unresolved** — it determines `music-prompt-engineer`'s entire knowledge base target.
**Verified context (May 2026):** Both Lyria models are in **Preview**, not GA. `lyria-3-clip-preview` returns 30s MP3 only; `lyria-3-pro-preview` returns ~2-3 min WAV. Reachable via `google-genai` SDK without GCP project setup.
**Implication if Lyria:** stitch/crossfade for >30s outputs is required in Phase 4 (not deferred).
**Implication if local MusicGen fallback:** Apple Silicon required; document Intel-mac unsupported in `dvg doctor`.

### D2. Schema source-of-truth
**Decide:** JSON Schema → codegen Pydantic + Zod, OR hand-maintain both.
**Recommendation:** JSON Schema as source. Use `datamodel-code-generator` (Pydantic) and `json-schema-to-zod` (Zod) at build time. One `make schemas` target.
**Why blocking:** the `composition.json` schema crosses the Python↔Node boundary. Hand-parity rots silently and surfaces as "Remotion renders garbage" mid-Phase 6.

### D3. Capture default strategy
**Decide:** Default web-recording approach.
**Verified:** Playwright's built-in recorder is hardcoded VP8 at ~1 Mbit/s scaled to 800×800. Not 1080p-grade.
**Recommendation:** Default = **headed Chromium driven by Playwright + ffmpeg avfoundation region capture**. Built-in recorder is the headless/CI fallback. Both paths shipped, agent picks.
**Implication:** macOS TCC Screen Recording permission applies to web capture too, not just `--screen` mode.

### D4. Caption timing ownership
**Decide:** Who owns `start`/`end` timestamps on captions?
**Recommendation:** `caption-writer` owns `(text, mood, anchor_event_id, intent_duration)`; `composition-director` derives final `(start, end, duck_window)` from the anchor event in `analysis.json` plus the intent duration. This means caption-writer can re-time by changing anchors without touching composition logic, and composition can shift timing for audio mixing without rewriting copy.
**Schema implication:** `captions.json` has no absolute timestamps. `composition.json` does.

### D5. Knowledge-loading mechanism
**Decide:** How does each agent's `knowledge/` content reach the prompt at dispatch time?
**Constraint:** Claude Code loads `agent.md` literally; it does not auto-traverse `knowledge/`.
**Options:**
  - (a) `agent.md` references files via `@.claude/agents/<x>/knowledge/core.md` and trusts file-include
  - (b) build step concatenates `knowledge/*.md` into `agent.md` at install time
  - (c) section-loader pattern: `<!-- load: api-surface, layering -->` markers; build step inlines selected sections
**Recommendation:** (c). Each agent has an explicit token budget (default 8k for system+knowledge); only declared sections are inlined. Prevents prompt bloat by Phase 6.

### D6. Error / failure JSON contract
**Decide:** Standard error shape across CLI primitives + agents.
**Recommendation:** All CLI primitives: exit 0 = JSON to stdout; exit ≠ 0 = stderr JSON of `{error: str, code: str, retryable: bool, suggestion: str, schema_version: int}`. Agents: on tool failure, emit `error.json` in the run dir and exit. Driver policy: `retryable=true` → retry once, then escalate to `qa-reviewer` for triage.

### D7. Director: keep or kill
**Decide:** Confirmed kill. Replace with deterministic `dvg run` driver (Python). `make-video.md` slash command becomes a thin user-facing wrapper that calls `dvg run` and surfaces progress.
**Why:** an LLM-orchestrator under context pressure may skip steps, reorder, or hallucinate completion. A deterministic driver walking `manifest.json` cannot. `--from <step>` becomes "delete the artifact, re-run."

---

## Architecture

```
User / Claude Code
        │
        ▼
   .claude/commands/make-video.md   (entry slash command — thin wrapper)
        │
        ▼
   dvg run <input> [--from <step>]   (deterministic driver, Python)
        │
        ├── inspects runs/<ts>/manifest.json
        ├── for each missing artifact, dispatches owning agent via `claude -p`
        ├── validates output against codegenerated schema
        ├── on failure: applies retry policy, then escalates to qa-reviewer
        └── advances until final.mp4 exists and qa-reviewer signs off
        
Agents (each owns one artifact in the run dir):
  ├── footage-capture-agent      → footage.mp4 + footage.events.json
  ├── event-log-analyst          → analysis.json (event-driven section)
  ├── visual-analyst             → analysis.json (visual section, gap-filler)
  ├── caption-writer-agent       → captions.json (anchored, no abs timestamps)
  ├── music-prompt-engineer      → music.mp3 (+ stitched if needed)
  ├── sfx-curator-agent          → sfx/<event>-<idx>.wav
  ├── composition-director-agent → composition.json (resolves caption timing, audio mix)
  └── qa-reviewer-agent          → qa.json (audio + visual + length checks)

Plus meta:
  └── knowledge-curator-agent    → runs/refresh/<ts>/report.md (no auto-apply)

render-engineer is no longer an agent — `dvg render` is a CLI primitive only.
```

The two-pass scene analysis: `event-log-analyst` runs first and is deterministic when DOM events exist. `visual-analyst` only runs for gaps (or for screen recordings with no event log). Same `analysis.json` schema; sections are merged.

---

## Tech Stack (verified May 2026)

| Layer | Choice | Notes |
|---|---|---|
| Language / package mgr | **Python 3.12 + uv** | — |
| CLI framework | **Typer** | — |
| Web recording (default) | **Playwright headed Chromium + ffmpeg avfoundation** | Built-in recorder is the CI fallback (hardcoded VP8 800×800) |
| Screen recording | **ffmpeg + avfoundation** | macOS TCC permission applies to both paths; `dvg doctor` checks |
| Scene analysis (primary) | **DOM event log from Playwright** | Deterministic when available |
| Scene analysis (gap-filler) | **PySceneDetect** + frame sampling + LLM-on-keyframes | PySceneDetect is film-cut tuned; expect tuning |
| Audio analysis (input) | **librosa**, **pydub** | — |
| Audio QA (output) | **ffprobe, ffmpeg ebur128, sox spectrogram, aubio tempo/onset** | See "Audio QA Toolkit" section. New homebrew deps. |
| Music generation | **`google-genai` → Lyria preview** (or fallback per D1) | `lyria-3-clip-preview` 30s/MP3; `lyria-3-pro-preview` ~3min/WAV. Both Preview, not GA |
| SFX | **Kenney UI Audio + Interface Sounds** (CC0) | ~150 clips. Skip Freesound for v1 |
| Composition | **Remotion v4** (Node, in `remotion/`) | v4 breaking changes noted: `imageFormat` removed, `trimLeft → trimBefore`, `OffthreadVideo` not in `@remotion/web-renderer` |
| Bridge | `renderMedia` programmatic API (Node script invoked from Python) | Not CLI flag scraping |
| Schemas / contracts | **JSON Schema → datamodel-code-generator (Pydantic v2)** + **json-schema-to-zod** | Single source; codegen both sides |
| Testing | **pytest** + **vitest** (Remotion) + **golden fixtures** + **perceptual diff** | Frame-hash + audio-fingerprint regression on golden MP4 set |
| Lint / format | **ruff**, **mypy --strict**, **prettier** | — |
| CI | **GitHub Actions** | unit + contract + lint on push; quality evals nightly + on PR with `eval` label |
| Eval framework | Custom thin layer on pytest + LLM-as-judge | Different model family for judge vs agent (bias mitigation) |
| Speech-to-text (v2) | Whisper (local) | — |
| Voiceover (v2) | ElevenLabs primary + edge-tts fallback | — |

---

## Project Structure

```
demo-video-generator/
├── src/demo_video_generator/
│   ├── __init__.py
│   ├── cli.py                         # Typer entry: dvg <subcommand>
│   ├── run.py                         # `dvg run` deterministic driver
│   ├── schemas/                       # CODEGEN OUTPUT (do not edit by hand)
│   │   ├── analysis.py
│   │   ├── captions.py
│   │   ├── composition.py
│   │   ├── manifest.py
│   │   └── error.py
│   ├── capture/
│   │   ├── detect.py
│   │   ├── playwright_headed.py       # Default: headed Chromium + ffmpeg
│   │   ├── playwright_builtin.py      # CI fallback
│   │   └── screen_recorder.py
│   ├── analysis/
│   │   ├── events.py                  # DOM-event-driven section
│   │   ├── visual.py                  # PySceneDetect + frame sampling + LLM-keyframes
│   │   └── audio.py
│   ├── music/
│   │   ├── lyria.py                   # If D1 = Lyria
│   │   └── stitch.py                  # Crossfade for >30s outputs
│   ├── sfx/
│   │   ├── library.py
│   │   └── pack/                      # Kenney CC0 .wav files + LICENSES.md
│   ├── composition/
│   │   └── remotion_bridge.py         # renderMedia programmatic API
│   ├── review/
│   │   └── qa.py                      # Audio QA toolkit pipeline + visual checks
│   └── doctor.py
├── schemas/                           # JSON Schema source-of-truth
│   ├── analysis.schema.json
│   ├── captions.schema.json
│   ├── composition.schema.json
│   ├── manifest.schema.json
│   └── error.schema.json
├── remotion/                          # Node project (separate package.json)
│   ├── package.json
│   ├── remotion.config.ts
│   └── src/
│       ├── Root.tsx
│       ├── DemoVideo.tsx
│       └── schemas/                   # CODEGEN OUTPUT (Zod)
├── .claude/
│   ├── commands/
│   │   ├── make-video.md
│   │   ├── refresh-agents.md
│   │   └── eval-agents.md
│   ├── agents/
│   │   ├── _template/                 # Skeleton for a new agent
│   │   ├── _shared/                   # Cross-agent knowledge
│   │   │   ├── remotion.md
│   │   │   ├── run-artifacts.md
│   │   │   ├── audio-qa-toolkit.md
│   │   │   └── error-contract.md
│   │   ├── footage-capture/
│   │   ├── event-log-analyst/
│   │   ├── visual-analyst/
│   │   ├── caption-writer/
│   │   ├── music-prompt-engineer/
│   │   ├── sfx-curator/
│   │   ├── composition-director/
│   │   ├── qa-reviewer/
│   │   └── knowledge-curator/
│   ├── PM.md
│   ├── DECISIONS.md
│   └── worklog.md
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── e2e/
│   ├── perceptual/                    # Frame-hash + audio-fingerprint regression
│   └── fixtures/
│       ├── site/                      # Local HTTP server fixture for Playwright
│       ├── videos/                    # Reference MP4s
│       └── golden/                    # Golden output MP4s + their hashes
├── evals/
│   ├── runner.py
│   └── cases/<agent-name>/
│       ├── headline/                  # 5 LLM-judge cases
│       ├── smoke/                     # 10 contract-only cases
│       └── holdout/                   # 2 cases never used in tuning
├── .github/workflows/
│   ├── ci.yml                         # unit + contract + lint on push
│   └── evals.yml                      # nightly + on `eval` PR label
├── pyproject.toml
├── Makefile                           # `make schemas`, `make test`, `make eval`
├── README.md
├── CLAUDE.md
├── .env.example                       # GEMINI_API_KEY (Lyria) or chosen fallback
├── .pre-commit-config.yaml            # ruff + mypy + prettier + gitleaks
└── .gitignore
```

---

## Per-Agent Infrastructure

```
.claude/agents/<name>/
├── agent.md                # Loaded by Claude Code; uses section-loader markers
├── prompts/
│   ├── system.md           # Current system prompt
│   ├── examples.md         # Few-shot examples
│   ├── style.md            # Voice/tone
│   └── revisions/          # Past versions
├── knowledge/
│   ├── core.md             # Stable: API surface, key concepts
│   ├── patterns.md         # Reusable patterns
│   ├── gotchas.md          # Failure modes + workarounds
│   ├── inspiration.md      # Community ideas, [experimental] tagged
│   └── changelog.md        # Refresh history
├── refresh.md              # Self-update protocol
└── evals/
    ├── cases/
    │   ├── headline/       # 5 LLM-judge cases
    │   ├── smoke/          # 10 contract-only cases
    │   └── holdout/        # 2 untouched cases (revealed only at phase exit)
    ├── rubric.md
    └── results/
```

**Knowledge-loading mechanism (D5):** `agent.md` declares which sections to inline:
```markdown
<!-- @load: knowledge/core.md#api-surface -->
<!-- @load: knowledge/patterns.md#smooth-scroll -->
<!-- @load: _shared/remotion.md#dynamic-media -->
```
A build step (`make agents`) materializes these into Claude-Code-loadable agent files at `.claude/agents/<name>/agent.compiled.md`. Token budget: 8k system + knowledge per agent. CI fails the build if any agent exceeds budget.

**Cross-agent shared knowledge (`_shared/`)** is referenced via `@load`; never duplicated.

---

## Knowledge & Self-Improvement System

Each agent's `refresh.md` declares sources, queries, freshness target, and update procedure. The `knowledge-curator` agent runs them and produces a refresh report — **never auto-applies**.

**Anti-hallucination rule:** every proposed update must include a fetched URL and a quoted excerpt. Updates without citation are auto-rejected by the curator script before reaching the PM.

**Freshness manifest:** curator writes `runs/refresh/manifest.json` with `last_run` and `staleness_per_agent`. `dvg doctor --strict-freshness` fails if any agent is past its freshness target. Phase exit gates run this.

**Budget:** curator has a per-run cost cap (default $5) and a phase-exit eval cap ($10). `evals/runner.py` aborts and reports if exceeded.

---

## Audio QA Toolkit

The QA gap in v1 was: how does an agent (or `dvg review`) judge audio without ears? Answer: shell tools that produce objective signals an LLM can read and reason about.

### Tools (homebrew + pip)
- `ffmpeg` / `ffprobe` (already required for capture)
- `sox`
- `aubio`
- `librosa` (already required) for advanced segmentation

`dvg doctor` verifies all of these.

### Catalog (lives in `.claude/agents/_shared/audio-qa-toolkit.md`)

| Signal | Command | Tells you |
|---|---|---|
| Metadata | `ffprobe -v error -show_format -show_streams -of json <file>` | Duration, bitrate, sample rate, channels, codec |
| Loudness | `ffmpeg -i <file> -filter_complex ebur128=peak=true -f null -` | Integrated LUFS, true peak dB, LRA |
| Energy curve | `ffmpeg -i <file> -af "astats=...:reset=0.5,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=energy.csv" -f null -` | RMS every 0.5s — answers "is there a build at 0:30?" |
| Tempo | `aubio tempo -i <file>` | Global BPM (or per-segment) |
| Onsets | `aubio onset -i <file>` | Onset density → "busy" vs "sparse" sections |
| Spectrogram | `sox <file> -n spectrogram -o spec.png -x 1920 -y 1080 -z 90` | PNG; the closest thing the agent has to "listening" |
| Waveform | `ffmpeg -i <file> -filter_complex "showwavespic=s=1920x240" -frames:v 1 wave.png` | Amplitude envelope |
| Section structure | `librosa.segment.agglomerative(librosa.feature.mfcc(...), 6)` | Boundary timestamps where character changes |

### Where it's used
- **`music-prompt-engineer/evals/rubric.md`** — converts subjective "matches vibe" into measurable assertions: BPM within ±5 of brief, integrated LUFS in [-18, -12], energy CSV shows declared shape (build/plateau/dip), spectrogram has continuous mid-band content (no dead air at boundaries).
- **`qa-reviewer/knowledge/core.md`** (loads `_shared/audio-qa-toolkit.md`) — battery of checks before signing off final.mp4.
- **`src/.../review/qa.py`** — `dvg review` runs the battery automatically and writes `audio_qa.json` to the run dir.
- **`composition-director/knowledge/patterns.md`** — concrete LUFS targets (music ducks to ≤ -22 LUFS under SFX peaks; final mix **integrated -14 LUFS, true peak ≤ -1 dBTP** — YouTube-aligned).

The one thing this still can't do: render a value judgment on taste ("does this song feel cool"). That stays a manual PM check at phase exit.

---

## Testing & Evaluation Framework

Three layers, every agent gets all three. Plus regression discipline.

### Layer 1 — Unit (pytest, hermetic, every commit)
Tests the CLI primitive. VCR cassettes for any external API.

### Layer 2 — Contract (pytest + Pydantic + Zod, every PR)
Agent output validates against codegenerated schema. Runs the agent via `claude -p` against fixture inputs.

### Layer 3 — Quality eval (`evals/runner.py`)
Three case classes per agent:
- **Headline (5)** — LLM-judge graded on 1-5 scale + rubric checklist
- **Smoke (10)** — contract-only; cheap; catch format regressions
- **Holdout (2)** — never shown during prompt tuning; revealed only at phase exit

**Judge diversity:** the LLM judge runs on a *different model family* than the agent. Agent on Sonnet → judge on Opus + a Haiku rubric-only check. This mitigates self-preference bias (5–25% in literature).

**Baseline rule:** the *first* revision of an agent's prompt that passes contract tests is recorded as `evals/cases/<agent>/baselines/v1.json` (full headline + holdout scores). Subsequent revisions compare against the most recent green baseline. Baselines roll forward only when a revision is promoted.

**Promotion rule for new prompt revisions:**
- Headline rubric ≥ baseline AND
- Headline judge ≥ baseline AND
- Holdout score ≥ baseline AND
- No individual case drops > 1 point

### Regression suite (named, scoped, automated)
- All Layer 1 + 2 + perceptual diff on `tests/perceptual/`
- Runs on every PR + every phase exit
- Quality evals (Layer 3) run on phase exit + nightly + on `eval` label

### Perceptual regression
Golden MP4 set in `tests/fixtures/golden/`. Each has a frame-hash + audio fingerprint. CI fails if a render differs by more than threshold. Manual review becomes a sanity check, not the gate.

### Eval cadence

| When | Unit | Contract | Quality | Perceptual |
|---|:---:|:---:|:---:|:---:|
| Every push | ✅ | | | |
| Every PR | ✅ | ✅ | | ✅ |
| PR with `eval` label | ✅ | ✅ | ✅ | ✅ |
| Phase exit | ✅ | ✅ | ✅ | ✅ |
| Nightly | | | ✅ | |

---

## Atomic Domains (revised v1 agent roster — 9 agents)

| # | Domain | Owns | Agent |
|---|---|---|---|
| 1–4 | Triage + headed/screen capture + post-processing | strategy → `footage.mp4` + DOM log | **footage-capture** |
| 5a | Event-driven scene analysis | DOM events → `analysis.json` (events section) | **event-log-analyst** |
| 5b | Visual scene analysis (gap-filler) | MP4 frames → `analysis.json` (visual section) | **visual-analyst** |
| 6 | Caption authoring (anchored, no abs timestamps) | analysis → `captions.json` | **caption-writer** |
| 7–8 | Music prompt + stitching + objective verification | analysis + captions → `music.mp3` | **music-prompt-engineer** |
| 9 | SFX curation (Kenney pack) | events → SFX placements | **sfx-curator** |
| 10–11 | Composition + theming + audio mix + caption-timing resolution | all artifacts → `composition.json` | **composition-director** |
| 13 | QA / final review (audio toolkit + visual checks) | final.mp4 + run dir → `qa.json` | **qa-reviewer** |
| meta | Knowledge refresh | refresh.md fleet → report | **knowledge-curator** |

**Removed:** `director` (replaced by `dvg run` driver), `render-engineer` (demoted to CLI primitive `dvg render`).

---

## CLI Surface (v1)

| Command | Purpose | Output |
|---|---|---|
| `dvg doctor [--strict-freshness]` | Verify Node 20+, ffmpeg ≥6, sox, aubio, Playwright browsers, Remotion Chromium cache, macOS TCC, env vars, codegen up-to-date | Pass/fail |
| `dvg run <input> [--from <step>] [--config FILE]` | **Deterministic driver.** Walks manifest, dispatches missing-artifact agents, validates outputs | `final.mp4` |
| `dvg capture <input> [--mode headed\|builtin\|screen] [--out FILE]` | Record (used by footage-capture agent) | `{video_path, duration, events?}` |
| `dvg analyze <video> [--events FILE]` | Event-log + visual analysis | `analysis.json` |
| `dvg music "<prompt>" --duration N --out FILE` | Generate (Lyria or fallback per D1) | `music.mp3` (stitched if >30s & Lyria preview) |
| `dvg sfx <event> [--out FILE]` | Kenney pack lookup | `sfx.wav` |
| `dvg compose <config.json>` | Validate composition | OK / errors |
| `dvg render <config.json> [--out FILE]` | Remotion render via `renderMedia` | `final.mp4` |
| `dvg review <final.mp4> [--run-dir DIR]` | Audio QA battery + visual checks + length | `qa.json` |

Standard run directory:
```
runs/<ts>/
├── manifest.json           # Driver state: input, config, per-stage status, costs
├── footage.mp4
├── footage.events.json
├── analysis.json
├── captions.json           # Anchored, no abs timestamps
├── music.mp3
├── sfx/<event>-<idx>.wav
├── composition.json        # Resolves caption timing, audio mix
├── final.mp4
├── audio_qa.json           # Output of dvg review's audio toolkit
├── qa.json                 # Final qa-reviewer signoff
└── error.json              # If any stage failed
```

---

## Phased Implementation Plan

Each phase: entry criteria / tasks (with model tier) / exit criteria / validation gate. No phase begins until prior is signed off in `.claude/PM.md`.

---

### Phase 0 — Foundation, Contracts & Infrastructure

**Entry:** All Phase -1 decisions logged in `.claude/DECISIONS.md`.

**Tasks:**
1. Scaffold project (Python + uv + Remotion + .claude/) — Haiku
2. **Author `schemas/*.schema.json`** (single source of truth) — Sonnet
3. **`make schemas` codegens Pydantic + Zod** — Sonnet
4. **`schema_version` field on every artifact** — Sonnet
5. **Manifest schema includes per-stage `depends_on: [stage_name]`** so `--from <step>` cascading invalidation is encoded in data, not driver heuristics — Sonnet
6. Author error contract module per D6 — Sonnet
7. Implement `dvg run` driver skeleton (walks manifest, no agents wired yet). Driver writes artifacts via tmpfile + atomic rename so a kill mid-stage cannot poison re-runs — Sonnet
8. Author `_template/` agent skeleton with section-loader markers per D5 — Sonnet
9. Author `_shared/` initial files. **Schemas in `_shared/run-artifacts.md` are LOCKED at end of Phase 0** — only prose updates allowed in later phases — Sonnet
   - `audio-qa-toolkit.md`, `run-artifacts.md` (schema-locked), `error-contract.md`, `remotion.md` stub
10. **Freshness-manifest scaffolding:** convention for `knowledge/changelog.md` per agent + `runs/refresh/manifest.json` shape. Curator agent itself ships in Phase 10, but the *files and schema* exist now so changelogs accumulate from day one — Sonnet
11. Set up pytest, ruff, mypy --strict, prettier, **pre-commit hooks (gitleaks)** — Haiku
12. **Local fixture HTTP server** (`tests/fixtures/site/`) — Haiku
13. Bootstrap `remotion/` Node project (Remotion v4) — Sonnet
14. Author `.claude/PM.md` and seed `DECISIONS.md` from D1-D7 — Haiku
15. `dvg doctor` v1: checks all required deps + **codegen freshness via SHA256 hash of `schemas/*.schema.json` recorded in `schemas/.checksums` — fails loudly if codegen is stale**. Includes `--strict-freshness` flag stub (no-op until Phase 10 wires curator) — Sonnet
16. **macOS TCC remediation:** `dvg doctor` *prints* `open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"` rather than auto-opening it — Haiku
17. Initial git commit, push — direct

**Deferred to Phase 1** (was in Phase 0 v2): `evals/runner.py` skeleton, GitHub Actions (`ci.yml` + `evals.yml`), perceptual-diff plumbing. Rationale: these add surface area before any agent exists and slow time-to-walking-skeleton. CI lives locally on `make` targets in Phase 0 and graduates to GitHub Actions in Phase 1 once the walking skeleton has something meaningful to run.

**Exit criteria:**
- [ ] `uv sync` succeeds
- [ ] `make schemas && pytest` green; `mypy --strict src/` clean; `ruff` clean; `prettier --check remotion/` clean
- [ ] Pre-commit hooks fire on test commit
- [ ] `npx remotion preview` boots
- [ ] `dvg doctor` green; codegen-hash check fails when a schema is touched without re-running `make schemas`
- [ ] `dvg run` driver runs against an empty fixture and exits cleanly with a "no agents wired" message
- [ ] Driver atomic-write check: kill driver mid-stage; restart; partial artifacts must not exist
- [ ] Manifest carries `depends_on` per stage; `--from <step>` invalidates downstream stages correctly per declared deps
- [ ] `_template/` produces a buildable compiled agent file via `make agents`
- [ ] All `_shared/` files exist and are referenced by `_template/`; `_shared/run-artifacts.md` schema section marked LOCKED
- [ ] `runs/refresh/manifest.json` schema and per-agent `knowledge/changelog.md` convention documented
- [ ] Local fixture HTTP server boots and serves a static page

**Validation gate:** code-reviewer subagent reviews scaffold + schemas + driver skeleton. PM signs off in PM.md.

---

### Phase 1 — Walking Skeleton (stub end-to-end via `dvg run`)

**Entry:** Phase 0 signed off.

**Goal:** prove the deterministic driver + schema contracts end-to-end with stub agents.

**Tasks:**
1. Stub `dvg capture` (copies fixture MP4) — Haiku
2. Stub `dvg analyze` (hardcoded valid analysis.json) — Haiku
3. Stub `dvg music` (30s silent MP3) — Haiku
4. Stub `dvg sfx` (silence) — Haiku
5. Stub `dvg review` (always pass + minimal audio_qa.json) — Haiku
6. Minimal `DemoVideo.tsx` consuming valid composition.json — Sonnet
7. `dvg render` via `renderMedia` programmatic API — Sonnet
8. Stub agent definitions for all 9 agents (each runs its stub CLI) — Sonnet
9. **`dvg run` wired to dispatch stub agents in order, honoring `depends_on` for `--from`** — Sonnet
10. `make-video.md` slash command wraps `dvg run` — Sonnet
11. **`evals/runner.py` skeleton** with judge-diversity + holdout support (deferred from Phase 0) — Sonnet
12. **GitHub Actions: `ci.yml` (unit + contract + lint on push) + `evals.yml` (nightly + on `eval` label)** (deferred from Phase 0) — Sonnet
13. **Perceptual-diff harness** in `tests/perceptual/` — frame-hash + audio-fingerprint with configurable similarity threshold (dHash ≥ 0.95 default) — Sonnet
14. E2E test against local fixture HTTP server — Sonnet

**Exit criteria:**
- [ ] All 9 agents have agent.md (compiled) + prompts/system.md + empty knowledge/ + empty evals/cases/ + refresh.md stub + `knowledge/changelog.md` (empty, per Phase 0 convention)
- [ ] `dvg doctor` green
- [ ] CI green on initial commit; both `ci.yml` and `evals.yml` validated
- [ ] `dvg run http://localhost:<port>/fixture.html` produces a valid (silent, blank-ish) MP4
- [ ] Driver correctly handles `--from <step>` and cascading invalidation honors `depends_on` (regenerates only the target stage and its declared downstream)
- [ ] All artifacts validate at every stage (asserted in e2e test)
- [ ] Run manifest captures per-stage status, duration, and (zeroed) cost
- [ ] Contract tests for all 9 agents: green on stub outputs
- [ ] Regression suite identified and named in `tests/README.md`
- [ ] Perceptual diff smoke test against the silent-blank golden MP4 passes

**Validation gate:** PM runs `/make-video <fixture-url>` and `dvg run --from sfx`. Code-reviewer signs off the driver design.

---

### Phase 2 — Capture Domain

**Entry:** Phase 1 signed off. **Plus:** 1-hour spike resolving Open Q B.3 — how to hide Chrome chrome (omnibox/tabs) for clean demos. Decide between `--app=URL`, `--kiosk`, or CDP-injected CSS. Lock the choice in `DECISIONS.md` as D8 before any capture code lands.

**Tasks:**
1. **Research spike (knowledge-curator):** Playwright headed-Chromium + ffmpeg avfoundation patterns; macOS TCC permission UX; cursor visibility — Opus run with WebFetch/WebSearch
2. Implement headed Chromium recorder (default) — Sonnet
3. Implement built-in Playwright recorder (CI fallback) — Haiku
4. Implement screen recorder (ffmpeg avfoundation) — Sonnet
5. Implement input detection / triage — Haiku
6. Implement footage post-processing (normalize fps/codec/dim) — Haiku
7. Author `footage-capture/knowledge/{core,patterns,gotchas}.md` — Sonnet
8. Author `footage-capture/prompts/system.md` v1 — Opus
9. Build evals: 5 headline + 10 smoke + 2 holdout — Sonnet
10. Wire agent to `dvg capture` real impl — Haiku

**Exit criteria:**
- [ ] Unit tests green for all three recorders against fixtures
- [ ] Contract tests green on all 17 cases
- [ ] Headline rubric ≥80%, judge ≥4.0; holdout ≥ baseline
- [ ] `dvg capture http://localhost:<port>/fixture.html` produces 1080p MP4 ≥5s with smooth interactions (headed mode)
- [ ] `dvg capture --mode screen` records 1080p screen for 5s
- [ ] All Phase 0/1 regression tests still pass; perceptual diff green
- [ ] Knowledge changelog entry; freshness manifest updated
- [ ] Code-reviewer signs off

**Validation gate:** PM reviews 3 captured videos; sign-off.

---

### Phase 3 — Analysis Domain (event-log + visual)

**Entry:** Phase 2 signed off.

**Tasks:**
1. **Research spike:** scene detection on UI footage; PySceneDetect tuning; LLM-on-keyframes — knowledge-curator (Opus)
2. Implement `dvg analyze` event-log section (deterministic from DOM events) — Sonnet
3. Implement `dvg analyze` visual section (PySceneDetect + frame sampling + LLM-keyframes; gap-filler logic) — Sonnet
4. Author event-log-analyst knowledge + prompt — Opus (prompt)
5. Author visual-analyst knowledge + prompt — Opus
6. Build evals for both agents (5+10+2 each) — Sonnet
7. Wire both agents; merge logic in `dvg analyze` writes single analysis.json with both sections — Sonnet

**Exit criteria:**
- [ ] Unit + contract + quality + holdout green for both agents
- [ ] On Playwright-captured fixture, event-log produces non-empty events; visual short-circuits where covered
- [ ] On screen-recorded fixture (no events), visual produces non-empty scenes
- [ ] Regression + perceptual green
- [ ] Code-reviewer signs off

**Validation gate:** PM reviews analysis.json on 3 videos; sign-off.

---

### Phase 4 — Music Domain

**Entry:** Phase 3 signed off + D1 confirmed (Lyria or fallback chosen) + **eval-cost actuals from Phases 2–3 reviewed against the $5/refresh and $10/phase-eval caps; revise caps in DECISIONS.md if Opus-judge spend is trending over budget.**

**Tasks:**
1. Implement `src/.../music/<lyria_or_fallback>.py` client with auth, retries, vcr cassettes — Sonnet
2. Implement `src/.../music/stitch.py` (crossfade for >30s if Lyria preview) — Sonnet
3. Author music-prompt-engineer knowledge: 10+ prompt patterns with examples — Opus
4. Author prompts/system.md v1 — Opus
5. **Author audio-QA-grounded eval rubric** (BPM ±5, integrated LUFS in [-16, -12] for music stems pre-mix, energy shape match, spectrogram continuity) — Opus
6. Build evals (5+10+2): upbeat tech, calm explainer, dramatic, retro, custom — Opus
7. Wire agent

**Exit criteria:**
- [ ] Unit (vcr) + contract + quality + holdout green
- [ ] `dvg music "upbeat tech demo, 90 BPM" --duration 30` produces playable MP3, BPM within ±5, length ±0.5s
- [ ] Audio QA toolkit assertions pass on all 5 headline cases
- [ ] Cost per call recorded in manifest
- [ ] Knowledge: ≥10 distinct prompt patterns with worked examples
- [ ] Regression + perceptual green
- [ ] Code-reviewer signs off

**Validation gate:** PM listens to 3 generated tracks; sign-off.

---

### Phase 5 — SFX Domain (Kenney CC0)

**Entry:** Phase 4 signed off.

**Tasks:**
1. Vendor Kenney UI Audio + Interface Sounds into `src/.../sfx/pack/` with `LICENSES.md` — Haiku
2. Implement `dvg sfx <event>` lookup — Haiku
3. Author sfx-curator knowledge: event→clip mapping aesthetic — Sonnet
4. Author prompt — Sonnet
5. Build evals (5+10+2) — Sonnet
6. Wire agent

**Exit criteria:**
- [ ] All bundled clips have CC0 documentation
- [ ] Unit + contract + quality + holdout green
- [ ] Regression + perceptual green
- [ ] Code-reviewer signs off

**Validation gate:** PM auditions SFX choices on 1 video; sign-off.

---

### Phase 6 — Composition Domain

**Entry:** Phase 5 signed off.

**Tasks:**
1. **Research spike:** Remotion v4 patterns; `OffthreadVideo` vs `Video`; dynamic media via `props`; `renderMedia` API — knowledge-curator (Opus)
2. Build `remotion/src/DemoVideo.tsx`: layered footage + caption overlays + audio mix + SFX placements — Sonnet
3. Caption layout components: typography, animation, mood-based variants (placeholder copy ok) — Sonnet
4. Audio mix: music ducking to ≤-22 LUFS under SFX peaks; **integrated -14 LUFS** (YouTube alignment); **true peak ≤ -1 dBTP** — Sonnet
5. **Resolve caption timing in composition-director per D4** (anchor_event_id + intent_duration → start/end) — Sonnet
6. `dvg compose` validator + `dvg render` via `renderMedia` — Sonnet
7. Author composition-director knowledge (Remotion API, layering, timing math, audio mix) — Opus
8. Author prompt — Opus
9. Build evals (5+10+2): different composition.json from same upstream — Opus
10. Wire agent

**Exit criteria:**
- [ ] Unit + contract + quality + holdout green
- [ ] `dvg render` from fixture composition.json produces MP4 in ≤2× realtime
- [ ] **Caption layout** (placeholder copy) renders without overflow on all 5 fixtures *(readability deferred to Phase 7)*
- [ ] Audio mix passes ebur128: integrated -14 LUFS ±1; true peak ≤ -1 dBTP
- [ ] Golden MP4s emitted from this phase are tagged `placeholder-caption` in `tests/fixtures/golden/` and slated for explicit rebaseline in Phase 7; perceptual-diff CI ignores caption text region until then
- [ ] Regression + perceptual green
- [ ] Code-reviewer signs off

**Validation gate:** PM watches all 5 rendered MP4s (placeholder copy); sign-off.

---

### Phase 7 — Caption Domain

**Entry:** Phase 6 signed off.

**Tasks:**
1. Author caption-writer knowledge: pacing rules, max words/sec, demo-video voice, "moods" — Opus
2. Author prompt — Opus
3. Build evals (5+10+2) graded on punchiness, accuracy, anchor correctness — Opus
4. Wire agent (writes anchored captions.json; no new CLI)
5. Re-run Phase 6 fixtures end-to-end with real captions; visual QA

**Exit criteria:**
- [ ] Contract + quality + holdout green
- [ ] Captions ≤7 words/line, ≥1.5s on screen (after composition-director resolves timing), no overlap with key UI elements
- [ ] **Phase 6 `placeholder-caption` golden MP4s rebaselined with real captions; perceptual-diff caption-region masking removed**
- [ ] Regression + perceptual green
- [ ] Code-reviewer signs off

**Validation gate:** PM watches 3 videos with real captions; sign-off.

---

### Phase 8 — QA Reviewer (with audio toolkit)

**Entry:** Phase 7 signed off.

**Tasks:**
1. Implement `dvg review`: full audio QA battery (ffprobe, ebur128, energy CSV, sox spectrogram, aubio tempo/onset, librosa segmentation) + visual checks (caption-in-frame heuristic, codec sanity, length) — Sonnet
2. Author qa-reviewer knowledge (loads `_shared/audio-qa-toolkit.md`) — Opus
3. Author prompt with structured `qa.json` output (issues + severity + suggested fixes) — Opus
4. Build evals (5+10+2): 5 deliberately-broken fixtures (clipping, captions cut, length mismatch, missing track, BPM off-target) — Opus
5. Wire QA into `dvg run`: failed QA → driver escalates (retry stage if `retryable`, else surface to user)

**Exit criteria:**
- [ ] All 5 broken fixtures correctly flagged with severity
- [ ] Audio QA toolkit produces deterministic outputs (snapshot-tested)
- [ ] Regression + perceptual green
- [ ] Code-reviewer signs off

**Validation gate:** PM intentionally breaks each stage and confirms QA flags it; sign-off.

---

### Phase 9 — Driver Polish & Slash Command UX

**Entry:** Phase 8 signed off.

**Tasks:**
1. Polish `dvg run`: progress reporting, structured logs, cost summary in manifest — Sonnet
2. `--from <step>` rigorous testing across all 8 stages including cascading invalidation per `depends_on` — Sonnet
3. Refine `make-video.md` UX (progress indicators, friendly errors) — Sonnet
4. **Prose-only update to `_shared/run-artifacts.md`** (schemas were locked at end of Phase 0; only narrative/example sections change here)
5. Run dir cleanup policy / `dvg run --keep-runs N`

**Exit criteria:**
- [ ] `/make-video <input>` produces a polished MP4 with no user intervention
- [ ] `--from <step>` works for every stage
- [ ] Manifest shows per-stage cost + duration + token counts
- [ ] Regression + perceptual green

**Validation gate:** PM runs `/make-video` on 3 different inputs (web, screen, file); sign-off.

---

### Phase 10 — Knowledge Refresh System & First Refresh

**Entry:** Phase 9 signed off.

**Tasks:**
1. Implement `knowledge-curator` agent — Opus
2. `/refresh-agents` slash command produces refresh report — Sonnet
3. **Wire `dvg doctor --strict-freshness`** against the freshness-manifest schema scaffolded in Phase 0 (so phase-exit gates can fail on stale agent knowledge) — Sonnet
4. Citation enforcement (auto-reject updates without URL+excerpt) — Sonnet
5. Run first full refresh; review and apply approved updates — manual
6. Document cadence in CLAUDE.md

**Exit criteria:**
- [ ] `/refresh-agents` produces structured report with citations
- [ ] At least one knowledge update applied via the workflow
- [ ] Each agent's `knowledge/changelog.md` shows recent activity
- [ ] `dvg doctor --strict-freshness` integrates with phase exit gates
- [ ] CLAUDE.md updated

**Validation gate:** PM walks through refresh workflow once end-to-end; sign-off.

---

### Phase 11 — Hardening & Release

**Entry:** Phase 10 signed off.

**Tasks:**
1. Run full eval suite across all agents; address regressions
2. End-to-end against ≥5 real-world inputs (own projects, sample sites)
3. README, docs, examples
4. `dvg doctor` first-run UX polish (clear remediation messages)
5. Decide PyPI publish or local-only
6. Tag v1.0

**Definition of "successful real-world demo"** (all must hold per video):
- `dvg run` produces a `final.mp4` without manual intervention
- `qa-reviewer` returns `qa.json` with no `severity: high` issues
- Audio QA: integrated -14 LUFS ±1, true peak ≤ -1 dBTP, no dead air >2s
- PM watches end-to-end and approves (subjective taste check, the one thing the toolkit can't automate)

**Exit criteria:**
- [ ] All agent evals at ≥ thresholds
- [ ] 5 successful real-world demos *per the definition above* (not just "PM watched and nodded")
- [ ] README quickstart works for a fresh user (verified by a clean-machine dry run)
- [ ] CLAUDE.md current

**Validation gate:** Final PM review; tag.

---

## PM Operating Model

I am executive PM: I decompose, dispatch, review, sign off. I do not write the bulk of implementation code; subagents do.

### Per-task dispatch loop
1. **Decompose** — self-contained brief (context, files, expected output, acceptance bar)
2. **Dispatch** — `claude -p --model <tier>` per the optimized-plan-orchestration skill (Haiku → Sonnet → Opus, escalate on QA failure)
3. **Receive** — read full output; verify file paths, schemas, that work actually got done
4. **Review** — code-reviewer subagent on non-trivial diffs (skip for pure scaffolding)
5. **Validate** — run relevant tests (unit/contract/quality per the cadence table)
6. **Decide** — accept, request revisions (re-dispatch with feedback), or escalate
7. **Log** — append to PM.md, worklog.md; record decisions in DECISIONS.md

### Per-phase loop
1. **Entry check** — prior phase signed off; if not, do not start
2. **Pre-phase research spike** — knowledge-curator runs first if the phase has one
3. **Dispatch tasks** — dependency order, parallelizing where safe
4. **Continuous validation** — unit + contract green at all times
5. **Exit gate** — full exit-criteria checklist + regression + perceptual + code-reviewer
6. **Retro** — short retro in PM.md; updates to DECISIONS.md if needed

### What I do directly
- Architectural decisions and trade-offs
- Reviewing subagent output
- Running and interpreting tests
- Manual quality review (watching MP4s, listening to music, reading spectrograms)
- Updating PM.md / DECISIONS.md / worklog.md

### What I never do
- Skip phase entry gate
- Accept subagent work without running validation
- Promote a prompt revision without an eval comparison
- Modify multiple agents in a single task

### Escalation
- Subagent fails QA → re-dispatch next tier with specific feedback
- Two failures at same tier → escalate
- Sonnet → Opus requires user (Ashwin) approval
- External blockers (Lyria, license issues) → surface immediately; never hack around

---

## Open Questions (remaining for ultra plan)

Most v1 open questions are now resolved by Phase -1 decisions. Remaining items:

### A. Agent roster & prompts
1. Should `event-log-analyst` and `visual-analyst` share a `_shared/scene-analysis.md` knowledge file, or is their work different enough to warrant separate KBs?
2. Caption "moods" — what's the v1 set? (announce / explain / punchline / aside / callout / tagline?)
3. ~~Composition-director audio mix targets~~ **RESOLVED in v2.1:** integrated -14 LUFS, true peak ≤ -1 dBTP (YouTube-aligned). Revisit only if dominant distribution channel changes.
4. Should `qa-reviewer` ever auto-loop back ("regenerate music with brighter prompt") or always escalate to user? Current plan: escalate.

### B. Tooling reality
1. If Lyria preview is gated/unstable, what's the ranked fallback list? (Suno API, Stable Audio Open, MusicGen-medium local, Riffusion?)
2. ~~macOS TCC permission UX~~ **RESOLVED in v2.1:** `dvg doctor` *prints* the `x-apple.systempreferences:` URL; user pastes/clicks. No auto-open.
3. ~~Headed Chromium chrome-hiding~~ **DEFERRED to Phase 2 entry spike (D8).** 1-hour decision between `--app=URL`, `--kiosk`, or CDP CSS injection.
4. Remotion v4: do we need `<OffthreadVideo>` for the footage layer, and does that require `@remotion/renderer` (not web-renderer)?
5. ffmpeg avfoundation device IDs are stable across macOS versions? `dvg doctor` should enumerate.

### C. Eval framework
1. Hold-out cases (2 per agent): how often do we rotate the holdout set? Stale holdouts get stale.
2. Judge model rotation: Opus 4.7 vs Sonnet 4.6 vs Haiku — should the rubric-only check always be Haiku, or rotate?
3. Cost cap: $5/refresh and $10/phase-eval — defensible? **Now a hard checkpoint at Phase 4 entry** (track actuals from Phases 2–3 and revise caps in DECISIONS.md before Music Domain begins).
4. ~~Perceptual diff threshold~~ **RESOLVED in v2.1:** dHash ≥ 0.95 default, configurable per fixture. Caption regions masked on `placeholder-caption`-tagged goldens until Phase 7 rebaseline.

### D. Architecture & schemas
1. `composition.json` is the most complex artifact. Should we version it more aggressively (semver per-phase) given expected churn?
2. Run-directory cleanup: keep last N runs? Compress old runs? Sync to cloud for sharing?
3. ~~`--from <step>` cascading invalidation~~ **RESOLVED in v2.1:** encoded as `depends_on: [stage_name]` per stage in the manifest schema (Phase 0). Driver computes the invalidation set from the DAG.
4. Should `dvg run` support `--dry-run` (validate config + manifest without dispatching agents)?

### E. Knowledge & self-improvement
1. Curator scope creep: should it propose new patterns from `inspiration.md` findings, or strictly refresh `core.md`? Current plan: strictly refresh; experimental patterns enter `inspiration.md` only.
2. Cross-agent knowledge sync: when `_shared/remotion.md` updates, does `dvg doctor` flag composition-director and what-was-render-engineer's downstream knowledge changelogs as needing review?
3. Eval drift: when judge model versions change (Opus 4.7 → 4.8), prior eval scores aren't comparable. How to handle? Re-baseline at major-version judge upgrades?

### F. New ideas worth considering
1. **Demo template library** — common demo shapes (product launch, feature walkthrough, before/after, oh-shit-it-broke). Each template = pre-set composition style + caption mood mix + music prompt seed. Could be a Phase 11+ addition.
2. **Re-edit mode** — given an existing run dir, let the user say "make it shorter / more energetic / different vibe" and the driver reruns only what's needed.
3. **Capture replay** — store Playwright trace alongside MP4 so capture is reproducible if we later want different framing/zoom.
4. **Multi-clip composition** — v1 = single capture. v2+ = stitch multiple captures with chapter markers.
5. **Auto-thumbnail** — pick the best frame for an MP4 thumbnail. Free fallout from `analysis.json`.
6. **Chapter markers in MP4** — derived from `analysis.json` scenes; helpful on YouTube uploads.
7. **Brand pack** — colors/fonts/logo lockup as a configurable input that composition-director consumes.

---

## v2 Scope (deferred)
- Voiceover: ElevenLabs primary + edge-tts fallback. New agents: `script-writer`, `voice-director`.
- STT-driven re-timing of captions to spoken narration
- Web UI
- Generative SFX
- Remotion Lambda render farm
- Multi-clip composition with chapters
- Brand pack support
