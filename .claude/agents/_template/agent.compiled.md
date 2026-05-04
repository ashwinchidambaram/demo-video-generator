# <agent-name>

> Skeleton. Copy this directory to `.claude/agents/<your-agent-name>/` and
> replace placeholders. `make agents` materializes `agent.compiled.md` from the
> @load markers below.

## Role

You own the `<artifact>` artifact in `runs/<ts>/`. Your CLI primitive is
`dvg <subcommand>`. Inputs you read from the run dir; outputs you write
atomically to your declared artifact path.

## Contract

* Read: <list upstream artifacts you depend on>
* Write: `<artifact>` (validated against `schemas/<x>.schema.json`)
* On failure: emit `error.json` per the shared error contract.

## Knowledge

# Run Artifacts (LOCKED — schemas may not be modified after Phase 0)

> **v2.1 plan invariant:** the *schemas* in this file are locked at end of Phase 0.
> Only narrative/example sections (clearly marked) may change in later phases.
> Schema changes go through `schemas/*.schema.json` + `make schemas`.

## Run-directory layout

Every `dvg run` invocation creates a new directory under `runs/<ts>/`:

```
runs/<ts>/
├── manifest.json           # Driver state (manifest schema v1)
├── footage.mp4             # capture stage
├── footage.events.json     # DOM event log (Playwright)
├── analysis.json           # event-log + visual sections (analysis schema v1)
├── captions.json           # Anchored, no abs timestamps (captions schema v1)
├── music.mp3               # Music track (stitched if Lyria preview)
├── sfx/<event>-<idx>.wav   # SFX placements
├── composition.json        # composition schema v1; resolves abs caption timing
├── final.mp4               # Render output
├── audio_qa.json           # `dvg review` audio toolkit output
├── qa.json                 # qa-reviewer signoff
└── error.json              # Present iff a stage failed (error schema v1)
```

## Stage → artifact → owner mapping

Identical to the manifest's `stages[]`:

| Stage     | Artifact            | Owner                    | Depends on                       |
|-----------|---------------------|--------------------------|----------------------------------|
| capture   | `footage.mp4`       | `footage-capture`        | —                                |
| analyze   | `analysis.json`     | `event-log-analyst` (+ `visual-analyst` for gaps) | capture |
| captions  | `captions.json`     | `caption-writer`         | analyze                          |
| music     | `music.mp3`         | `music-prompt-engineer`  | analyze                          |
| sfx       | `sfx/`              | `sfx-curator`            | analyze                          |
| compose   | `composition.json`  | `composition-director`   | analyze, captions, music, sfx    |
| render    | `final.mp4`         | `_cli:render` (no agent) | compose                          |
| review    | `qa.json`           | `qa-reviewer`            | render                           |

## Atomic-write rule

Every artifact is written via tmpfile + `os.replace()`. A kill mid-stage leaves
either the old artifact (if any) or no artifact — never a partial one. See
`src/demo_video_generator/atomic.py`.

## Cascading invalidation (`--from <step>`)

Encoded in the manifest's per-stage `depends_on`, not driver heuristics. The
driver computes the transitive downstream set with BFS and deletes those
artifacts before re-walking.

---

<!-- The sections above are LOCKED. Phase 9 prose-only updates may extend the
notes below this marker. -->

# Error Contract (D6)

All CLI primitives and agents speak the same error envelope.

## Envelope

```json
{
  "schema_version": 1,
  "error": "human-readable message",
  "code": "STABLE_MACHINE_CODE",
  "retryable": true,
  "suggestion": "remediation hint",
  "stage": "music",
  "context": { "any": "structured-data" }
}
```

JSON Schema: [`schemas/error.schema.json`](../../../schemas/error.schema.json).

## CLI conventions

* **Exit 0** ⇒ success. JSON result on stdout.
* **Exit ≠ 0** ⇒ failure. Error envelope on stderr.
* No partial artifacts; atomic-write helpers ensure this.

## Agent conventions

On failure an agent emits `error.json` in the run dir and exits non-zero.

## Driver retry policy

The driver inspects `retryable`:

* `retryable=true` ⇒ retry once with the same inputs.
* `retryable=false` *or* second failure ⇒ escalate to `qa-reviewer` for
  triage; then surface to the user.

# core knowledge — <agent-name>

Stable per-agent knowledge: APIs the agent must know, key concepts, and
domain rules. Section headings (`## foo`) are addressable via the
section-loader (`<!-- @load: knowledge/core.md#foo -->`).

## api-surface

(Replace with the relevant API surface for this agent.)

## conventions

(Replace with project-specific conventions this agent must follow.)

## System prompt

# System prompt — <agent-name> v0.1

You are the `<agent-name>` agent. Replace this body with the agent's actual
instructions; the section-loader inlines this file at compile time.
