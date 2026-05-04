# knowledge-curator — design (from A4 ultraplan)

> Implementation phase: **10**. Phase 1 ships stub.

## Role contract

- **Input:** fleet of `.claude/agents/*/refresh.md` files + optional CLI args (`--agent <name>`, `--scope core|patterns|gotchas`).
- **Output:** `runs/refresh/<ts>/report.md` (human-readable) + `runs/refresh/<ts>/proposals.json` (machine-checked: per-agent diff blocks with citation manifest). Updates `runs/refresh/manifest.json` (`last_run`, `staleness_per_agent[<agent>]`).
- **Boundary:** NEVER auto-applies. PM applies via separate `make apply-refresh RUN=<ts>` step.

## System prompt shape

1. Role + iron rule: "Every proposed update MUST include `{url, fetched_at, sha256_of_excerpt, verbatim_excerpt}`. Updates without all four fields are dropped before report is written."
2. Citation enforcement (load-bearing): show proposal-block JSON shape with required fields; one good example, one rejected example.
3. Cost cap protocol: `$DVG_REFRESH_COST_CAP` (default $15/agent per D16). Track cumulative tokens × tier price after each WebFetch; if projected next call exceeds cap, halt and emit `{halted: true, reason: "cost_cap"}`. Never silently truncate.
4. Scope discipline: refresh existing knowledge files in scope. Experimental ideas → `inspiration.md` only, tagged `[experimental]`. Curator never proposes new agent or new `_shared/` file; surface in `report.md` "FYI" for PM.
5. Diff hygiene: minimal proposals — cite stale paragraph by line range, propose replacement; don't rewrite untouched paragraphs.
6. Loads: `<!-- @load: knowledge/core.md -->`, `<!-- @load: knowledge/citation-rules.md -->`, `<!-- @load: _shared/refresh-protocol.md -->`.
7. Output structure reminder for `report.md` (per-agent: queries fired, sources hit, cost, proposals, rejections-with-reason).

## Knowledge files

- **core.md:** Citation rules; allowed source domains per agent (e.g. `remotion.dev/docs` for composition-director, `playwright.dev`, `ffmpeg.org/ffmpeg-filters.html`); forbidden sources (StackOverflow accepted answers >2 years old, random Medium posts).
- **patterns.md:** Staleness heuristics — "if doc page's `Last updated` text newer than cached `fetched_at`, propose"; "if API surface count diverges from `core.md` example count by >2, deep-dive".
- **gotchas.md:** WebFetch returns Markdown-ified HTML with link rot; cache-buster headers; Anthropic rate limits during refresh; URL canonicalization (strip `?utm_*`).
- **inspiration.md:** `[experimental]` diff-against-last-fetch cache stored at `runs/refresh/cache/<sha256>.md`.

## Tools

- `Read` (agent files + cached fetches).
- `WebFetch` (primary; respects per-domain allow list from `core.md`).
- `WebSearch` (only when `refresh.md` declares queries and no direct URL; results normalized to URLs that survive a follow-up `WebFetch`).
- No `Bash`, no `Edit`/`Write`.

## Failure modes

1. **Citation faking** (model paraphrases instead of verbatim). Post-hoc verifier in `dvg apply-refresh` re-fetches URL; checks `sha256(excerpt) == declared sha256`.
2. **Cost overrun** (recursive WebFetch chains). Hard token meter; halt-and-report.
3. **Source drift** (refresh from non-canonical mirror). Domain allow list per agent.
4. **Apply-without-review.** Driver provides no `--auto-apply`. `make apply-refresh` requires interactive prompt unless `CI=1` AND signed PM approval token.
5. **Staleness lying** (manifest claims fresh because curator ran but found no diffs). `staleness_per_agent` keyed off *source* `Last-Modified`, not curator run time.

## Headline cases (5)

Each fixture is a frozen knowledge snapshot with a known-stale fact + frozen WebFetch cache (replay) containing the corrected fact. Curator must propose the correct minimal update with valid citation.

1. **`stale-remotion-trimleft`** — `_shared/remotion.md` references `trimLeft`; cached docs use `trimBefore`. Expected: cite Remotion changelog URL with verbatim excerpt.
2. **`stale-lyria-duration`** — `music-prompt-engineer/core.md` claims `lyria-3-clip-preview` returns 60s; Google docs (cached) say 30s. Numeric correction with URL+excerpt.
3. **`stale-playwright-builtin-res`** — `footage-capture/core.md` says built-in recorder is 1080p; cached docs say 800×800 VP8. Correction.
4. **`stale-ffmpeg-ebur128-flag`** — toolkit doc uses old `peak=true` syntax; cached ffmpeg-filters page shows current. Minor command correction.
5. **`no-stale-noop`** — all knowledge fresh; no cached deltas. Empty proposals.json, report says "no changes". Tests over-eagerness.

## Holdout (2)

1. **`stale-aubio-tempo-flag`** — `qa-reviewer/gotchas.md` references removed CLI flag. Correction with citation.
2. **`adversarial-paraphrase-trap`** — fixture's "cached source" contains the fact phrased two different ways. Curator must pick verbatim form, not paraphrase. Tests citation discipline.
