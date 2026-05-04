# Reelsmith

> A fleet of agents that crafts demo videos.

Turn "a thing you built" into a production-quality demo video, deterministically.

9 specialized Claude Code agents (capture, scene analysis, captions, music,
SFX, composition, QA, knowledge curation) coordinated by a thin Python driver
that walks a per-run JSON manifest. Render layer is Remotion v4 (programmatic
React video). Output is a 1920×1080 H.264+AAC MP4 with audio mixed to
YouTube-aligned loudness targets (-14 LUFS / -1 dBTP).

> **Name note.** Reelsmith is the project. The CLI ships as `dvg` and the
> Python package as `demo_video_generator` for now — those names predate the
> rename and renaming them touches every import, schema `$id`, codegen
> target, and the git remote. Tracked as a future migration.

This README is the user-facing entry point. Architectural decisions live in
`.claude/DECISIONS.md`, the implementation plan in
`.claude/plans/v2-implementation-plan.md`, per-agent designs in
`.claude/agents/<name>/design.md`, and phase status in `.claude/PM.md`.

---

## Quickstart

```bash
# Install
uv sync --all-extras
cd remotion && npm install && cd ..

# Codegen Pydantic + Zod from schemas/*.schema.json
make schemas
make agents          # compile per-agent prompts from section-loader markers
make qa-codes        # codegen issue-code registry → review/codes.py

# Verify environment
uv run dvg doctor

# Run an end-to-end render against a URL fixture
DVG_SOUNDTRACK_DIR=/path/to/your/soundtracks \
DVG_MUSIC_HINT=flow \
DVG_CAPTIONS_BRIEF=tests/fixtures/demo-brief.json \
DVG_DURATION=25 \
uv run dvg run "http://localhost:0/your-page"

# Render the self-demo (the project explaining itself)
cd remotion && \
  npx tsx src/render-self-demo.ts ../demo-deliverable.mp4 \
    --music /path/to/soundtrack.mp3
```

The deterministic driver walks `runs/<ts>/manifest.json`, dispatches the next
missing artifact's owning agent, validates the output against schema, and
advances. There is no LLM orchestrator — the driver cannot skip steps, reorder,
or hallucinate completion (DECISIONS.md §D7).

---

## Architecture

```
User input (URL / video file / "screen")
        │
        ▼
   /make-video <input>       (slash command — thin wrapper)
        │
        ▼
   dvg run <input> [--from <step>] [--keep-runs N] [--skip-render]
        │
        │ walks runs/<ts>/manifest.json
        ▼
   ┌──────────────┬──────────────┬─────────────┬────────────┐
   ▼              ▼              ▼             ▼            ▼
 capture      analyze       captions       music         sfx
 footage.mp4  analysis.json captions.json  music.mp3    sfx/manifest.json
 events.json
   │              │              │             │            │
   └──────────────┴───────┬──────┴─────────────┴────────────┘
                          ▼
                       compose
                       composition.json
                          │
                          ▼
                      render (Remotion v4 via renderMedia)
                       final.mp4
                          │
                          ▼
                       review
                       qa.json + audio_qa.json + spectrogram.png
```

Stages are coupled only through schema-validated JSON files in the run
directory. `depends_on` lives inside `manifest.json`, so the DAG is data, not
code. Driver auto-retries stages flagged with allowlisted QA codes (one retry
per stage per run); everything else escalates to the user.

### Run directory shape

```
runs/<ts>/
├── manifest.json            # driver state: per-stage status/duration/cost/sha256
├── footage.mp4              # capture output
├── footage.events.json      # DOM events from Playwright (or empty for file-ingest)
├── analysis.json            # events + visual scenes
├── captions.json            # anchored captions (no absolute timestamps; D4)
├── music.mp3                # ingested or generated audio
├── music_meta.json          # source / verification sidecar
├── sfx/
│   ├── manifest.json        # placement records
│   └── <event_id>-<idx>.wav # CC0 clips copied from pack/
├── composition.json         # the Python↔Node boundary; resolves abs caption timing
├── final.mp4                # rendered output
├── audio_qa.json            # toolkit measurements (canonical scalars)
├── spectrogram.png          # sox evidence
├── qa.json                  # signoff: pass/warn/fail + structured issues
└── error.json               # only present when a stage failed
```

---

## The 9 agents

Each agent lives at `.claude/agents/<name>/` with `design.md` (full spec),
`agent.md` (Claude Code's loaded prompt assembled via `@load` markers from
`prompts/system.md` + `knowledge/{core,patterns,gotchas,inspiration}.md`),
`refresh.md` (self-update protocol), and `evals/cases/{headline,smoke,holdout}/`.

| Agent | Owns | Reads | Status |
|---|---|---|---|
| **footage-capture** | `footage.mp4` + `footage.events.json` | URL / file / screen | Headed Chromium + ffmpeg avfoundation code in place; URL path gated on macOS Screen Recording TCC. File ingest live. |
| **event-log-analyst** | events-section of `analysis.json` | `footage.events.json` | Deterministic gap-clustering (1.2s default); per-cluster summary; energy assignment by event kind. **Live.** |
| **visual-analyst** | visual-source scenes in `analysis.json` | `footage.mp4` | PySceneDetect ContentDetector primary; AdaptiveDetector fallback; 8-keyframes-per-minute cap. **Live.** LLM-on-keyframes summaries gated on vision API. |
| **caption-writer** | `captions.json` | `analysis.json` | Brief-driven authoring path (`DVG_CAPTIONS_BRIEF`) live. LLM-driven authoring gated on `ANTHROPIC_API_KEY`. |
| **music-prompt-engineer** | `music.mp3` + `music_meta.json` | `analysis.json` + brief | Soundtrack-ingest path live (`DVG_SOUNDTRACK_DIR` + `DVG_MUSIC_HINT`); deterministic seeded selection. Lyria preview generation gated on `GEMINI_API_KEY` + D1 smoke. |
| **sfx-curator** | `sfx/manifest.json` + `.wav` placements | `analysis.json` events | Synthetic 4-clip CC0 pack (programmatically generated via `wave` module); kind→clip mapping. Real Kenney pack curation pending Phase 5.5. |
| **composition-director** | `composition.json` | everything upstream | **Live.** Resolves caption anchored→absolute timing per D4; collision resolution; style-preset selection from mood mix + scene energy; audio-QA-driven gain tuning. |
| **qa-reviewer** | `qa.json` + `audio_qa.json` | `final.mp4` + composition + manifest | **Live.** Full toolkit: ffprobe + ebur128 + aubio (tempo/onset) + librosa (segmentation) + sox (spectrogram). Severity ladder + proposed_action enum. Driver auto-retry allowlist codegen'd from agent's own knowledge file. |
| **knowledge-curator** | `runs/refresh/<ts>/{report.md, proposals.json}` | each agent's `refresh.md` | **Live.** Walks fleet; with `--fetch` does real WebFetch via `requests`, SHA256 body hashing, Pin Fact verbatim verification. LLM-driven semantic refresh gated on API key. |

---

## Decisions (DECISIONS.md)

19 architectural decisions, all logged in `.claude/DECISIONS.md`. Highlights:

- **D2: Schema source-of-truth.** JSON Schema → codegen Pydantic + Zod via `make schemas`. Single registry; CI enforces freshness.
- **D7: Kill the director.** No LLM orchestrator. Deterministic Python driver walks `manifest.json`. `--from <stage>` becomes "delete artifact, re-run."
- **D9: Audio targets.** Integrated -14 LUFS / true peak -1 dBTP / duck to -22 LUFS (YouTube-aligned).
- **D13: `<OffthreadVideo>` for renderMedia.** Remotion v4 server-rendered footage layer.
- **D14: Schema migrations.** `schema_version` monotonic; `schemas/migrations/` registry.
- **D15: Holdout rotation.** Eval holdouts rotate every 90 days or schema bump.
- **D16: Eval cost cap.** $25/phase-eval; nightly runs one rotated agent (cost amortization).
- **D17: Content-aware cascading invalidation.** `artifact_sha256` per stage; re-runs producing identical hashes preserve downstream.
- **D18: Cross-agent contract registry.** `schemas/contracts.json` with versioned consumer acks; pre-commit hook + CI check.
- **D19: Judge-version stamping.** Eval baselines tagged with judge model + version; full re-baseline on judge major upgrade.

---

## Schemas + codegen

```
schemas/
├── analysis.schema.json     # scenes + events
├── captions.schema.json     # anchored captions (no abs timestamps)
├── composition.schema.json  # the Python↔Node boundary
├── error.schema.json        # error envelope per D6
├── manifest.schema.json     # driver state + depends_on DAG + per-stage cost/sha256
├── qa.schema.json           # signoff + issues + measurements
├── contracts.json           # cross-agent contract registry (D18)
└── .checksums               # SHA256 of each schema file
```

`make schemas` runs `datamodel-code-generator` (Pydantic v2) and
`json-schema-to-zod` (Zod) at build time. `dvg doctor` and the pre-commit hook
fail if codegen is stale.

---

## Audio QA toolkit

The Phase 8 substrate that lets agents (and `dvg review`) judge audio without
ears. Every measurement returns canonical scalars (rounded; not raw stderr) per
ultraplan R3 to dodge cross-platform numpy/ffmpeg jitter.

| Tool | Purpose | Output |
|---|---|---|
| `ffprobe` | metadata | duration / codec / streams |
| `ffmpeg ebur128` | loudness | integrated LUFS / true peak (rounded 0.1) |
| `aubio tempo` | rhythm | median BPM (int, 30–240 range) |
| `aubio onset` | density | onset count |
| `librosa.segment.agglomerative` | structure | boundary timestamps (quantized 100ms) |
| `sox spectrogram` | evidence | 1920×1080 PNG |

Severity ladder: `high` (ship-blocker; LUFS off >2, true peak >-1 dBTP, dead air >2s) / `medium` (LUFS off 1-2, length 5-10% off) / `low` (cosmetic).

---

## Eval framework

```
evals/
├── runner.py                       # discover + run (smoke / headline / holdout)
├── seed_cases.py                   # regenerate the 63 fixture cases
└── cases/<agent>/
    ├── headline/                   # 5 LLM-judge cases (gated on API key)
    ├── smoke/                      # 5 contract-only cases (live)
    └── holdout/                    # 2 cases revealed only at phase exit (--reveal-holdout)
```

9 agents × 7 cases = 63 fixtures. The smoke runner exercises real CLI primitives
(no LLM); 45 cases pass cleanly today. Headline/holdout LLM judging requires
`ANTHROPIC_API_KEY`. Per D16: judge diversity (Sonnet primary, Opus tiebreak),
ephemeral rubric caching, nightly rotates a single agent (no fleet-wide nightly).

A pytest wrapper at `tests/unit/test_eval_runner.py` runs the smoke suite from
the regular test build, so a regression in any agent's deterministic substrate
breaks CI.

---

## CLI surface

```
dvg doctor [--strict-freshness]    # verify environment + codegen freshness
dvg run <input> [--from <stage>] [--skip-render] [--keep-runs N=20]
dvg refresh [--agent NAME] [--fetch]  # knowledge-curator fleet walk
```

`--from <stage>` uses content-aware invalidation (D17): clear the target,
re-run, then if new `artifact_sha256` matches the prior, downstream stays.

`--keep-runs N` (default 20) prunes oldest runs after each completion. Runs
with `severity:high` qa.json issues are preserved.

---

## Environment variables

| Variable | Purpose |
|---|---|
| `DVG_SOUNDTRACK_DIR` | Folder of MP3s for `music-prompt-engineer` ingest path |
| `DVG_MUSIC_HINT` | Substring to prefer when picking a track |
| `DVG_CAPTIONS_BRIEF` | Path to a JSON brief for `caption-writer` |
| `DVG_DURATION` | Synthetic capture duration (when URL/screen path is gated) |
| `DVG_HEADED_CAPTURE` | Set to `1` to opt into the real Playwright capture path |
| `GEMINI_API_KEY` | Lyria preview music generation |
| `ANTHROPIC_API_KEY` | LLM judges + LLM-driven agent prompts |

---

## Project layout

```
demo-video-generator/
├── src/demo_video_generator/
│   ├── cli.py                      # `dvg <subcommand>` entry
│   ├── run.py                      # deterministic driver
│   ├── manifest.py                 # DAG + content-aware invalidation
│   ├── atomic.py                   # tmpfile + os.replace writes
│   ├── errors.py                   # error envelope per D6
│   ├── doctor.py                   # preflight checks
│   ├── capture/                    # file-ingest + headed-Chromium + synthetic
│   ├── analysis/                   # event-log + visual (PySceneDetect)
│   ├── captions/                   # brief-driven authoring
│   ├── music/                      # soundtrack ingest
│   ├── sfx/pack/                   # synthetic CC0 clips + index
│   ├── composition/                # collision resolution + style + gain tuning
│   ├── render/                     # Remotion subprocess bridge
│   ├── review/                     # full audio QA toolkit
│   ├── curator/                    # WebFetch + Pin Fact verification
│   ├── migrations/                 # schema migration registry (D14)
│   ├── tools/                      # compile_agents, compile_qa_codes, check_contracts
│   └── schemas/                    # codegen Pydantic (gitignored)
├── schemas/                        # JSON Schema source-of-truth
├── remotion/                       # Remotion v4 composition layer
│   └── src/
│       ├── DemoVideo.tsx           # generic pipeline output (mood typography + audio + footage)
│       ├── DvgSelfDemo.tsx         # the self-walkthrough composition
│       ├── render.ts               # bundle + selectComposition + renderMedia
│       └── render-self-demo.ts     # dedicated render bridge for the self-demo
├── .claude/
│   ├── plans/v2-implementation-plan.md  # the plan (v2.2; ultraplan-revised)
│   ├── DECISIONS.md                # ADR-lite, D1–D19
│   ├── PM.md                       # phase status + retros
│   ├── agents/<name>/              # 9 agents: design.md + agent.md + prompts + knowledge + evals
│   └── agents/_shared/             # cross-agent: refresh-protocol, audio-qa-toolkit, etc.
├── tests/
│   ├── unit/                       # 90+ unit tests
│   ├── contract/                   # schema validity + Pydantic roundtrip
│   ├── e2e/                        # walking-skeleton regression
│   └── perceptual/                 # frame-hash dHash harness
├── evals/                          # 63 fixture cases + runner
├── .github/workflows/              # ci.yml (push/PR) + evals.yml (nightly + label)
├── Makefile                        # schemas, agents, qa-codes, check-contracts, ...
└── demo-deliverable.mp4            # the 70s walkthrough rendered through this system
```

---

## Demo deliverable

`demo-deliverable.mp4` (1920×1080 · 70s · 4.3MB · H.264+AAC) is a self-referential
walkthrough rendered through the system itself.

10 scenes:
1. Title — "autonomous build · 6 hours · no api keys"
2. Animated terminal — `dvg run` typing out + 9 dispatch lines + ✓ pass
3. Pipeline DAG lighting up stage-by-stage
4. Schema flow — JSON Schema → Pydantic + Zod, with stats
5. Audio QA toolkit readout — real measurements from this MP4
6. Eval framework — 9 agents · 63 cases · 45 smoke pass
7. Architecture — all 9 agents with phase numbers
8. Build stats — animated counters
9. What's deferred — gated items with stubs
10. Final card

Audio is **`vibe-flow.mp3`** ingested via the soundtrack-ingest path. Audio QA
on the output: integrated **-14.6 LUFS**, true peak **-1.4 dBTP**.

The system measured itself correctly — Phase 8 librosa segmentation found
boundaries at `[0.0, 0.1, 10.8, 19.7, 23.5]s`, which match the actual
inter-scene transitions in the rendered MP4.

---

## Status

10 of 11 phases complete or partial-with-stubs. The remaining work is gated on:

- `GEMINI_API_KEY` → Lyria preview music generation
- `ANTHROPIC_API_KEY` → LLM judges; LLM-driven caption-writer + music-prompt-engineer
- vision API → visual-analyst LLM-on-keyframes
- macOS Screen Recording TCC → footage-capture headed-Chromium runtime
- Kenney CC0 pack curation → Phase 5.5 manual vendoring (~1 hour)

Every gated component has a working stub or deterministic substrate so the
end-to-end pipeline runs today.

**33 commits · 4,700 LOC Python + Remotion · 103 unit tests passing · `mypy --strict` + `ruff` + `prettier` + `tsc` clean.**

---

## License

MIT.
