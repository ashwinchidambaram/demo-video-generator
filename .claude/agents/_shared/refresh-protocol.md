# Refresh Protocol — shared knowledge

Loaded by `knowledge-curator/agent.md` and (selectively) by per-agent prompts.
Defines the contract every `refresh.md` must follow and the proposal-block
shape the curator emits.

## Required `refresh.md` shape

Every agent's `refresh.md` MUST contain these sections:

```markdown
## Sources
- <URL>  (one per canonical doc page; allowed-domain only)

## Queries
- "<query string>"  (only if WebSearch needed)

## Freshness target
<N> days  (defaults to 90 if absent)

## Scope
- knowledge/core.md  (which files refresh may propose against)
- knowledge/gotchas.md

## Pin facts
- "<exact verbatim sentence in current core.md>" → assert still present in source

## Anti-scope
- knowledge/inspiration.md  (curator never touches; only PM)
- prompts/  (curator never touches)
```

The **Pin facts** section is load-bearing: targeted yes/no verification ("this
exact sentence is supposed to still be true; does the source still say so?")
beats open-ended re-summarization. Cheaper, citation-clean, single-bit diffs.

## Allowed-domain rule

Each agent's `refresh.md` `Sources` URLs are restricted to a per-agent allow
list (declared in the agent's `knowledge/core.md`). Off-list sources fail the
curator's pre-flight. Examples:

- `composition-director` → `remotion.dev/docs/*`
- `footage-capture` → `playwright.dev/*`, `ffmpeg.org/ffmpeg-filters.html`
- `qa-reviewer` → `ffmpeg.org/*`, `aubio.org/manual/*`, `sox.sourceforge.net/*`

## Proposal block — what the curator emits

Each proposed update is a JSON block in `runs/refresh/<ts>/proposals.json`:

```json
{
  "agent": "composition-director",
  "file": "knowledge/core.md",
  "line_range": [42, 47],
  "old_excerpt": "<verbatim current text>",
  "new_excerpt": "<verbatim proposed text>",
  "citation": {
    "url": "https://www.remotion.dev/docs/offthreadvideo",
    "fetched_at": "2026-05-04T10:23:00Z",
    "excerpt": "<verbatim quote ≥40 chars, ≤500>",
    "excerpt_sha256": "<hex>"
  }
}
```

All four citation fields are required. Curator drops proposals missing any.

## Application protocol

The curator NEVER auto-applies. PM runs `make apply-refresh RUN=<ts>` which:

1. Re-fetches each citation URL.
2. Verifies `sha256(excerpt) == citation.excerpt_sha256` (otherwise drops).
3. Applies the diff atomically.
4. Appends entries to each modified agent's `knowledge/changelog.md`.
5. Updates `runs/refresh/manifest.json`.

## Cost cap

Default per-agent: $15 (per D16). Tracked cumulatively across WebFetch +
WebSearch + LLM tokens. Curator halts cleanly and emits
`{halted: true, reason: "cost_cap"}` when projected next call would exceed cap.

## Inspiration → core graduation

Three conditions, all required:

1. Used in production knowledge for ≥2 phases (loaded behind `[experimental]`
   tag and survived two refresh cycles without contradiction).
2. Validated by ≥1 eval case (headline or holdout case explicitly tests the pattern).
3. Citable via the same rule curator enforces (URL + verbatim excerpt + sha256).

PM-only action. Curator never auto-graduates even when conditions are met.
Graduation logged in `knowledge/changelog.md` with eval case ID + citation.
