# Section Loader — shared

Defines the `<!-- @load: ... -->` syntax, the `make agents` build step, and the
section-naming convention. Loaded by no agent at runtime; this is dev-time
documentation for prompt authors.

## Syntax

In any `agent.md`:

```markdown
<!-- @load: knowledge/core.md#api-surface -->
<!-- @load: knowledge/patterns.md -->
<!-- @load: _shared/audio-qa-toolkit.md#catalog -->
```

Forms:

- `path.md` — inlines whole file.
- `path.md#section` — inlines content under the `## section` heading
  (case-insensitive) up to the next `## ` heading or EOF.
- `_shared/<file>.md` — resolved against `.claude/agents/_shared/`.
- Bare path — resolved against the current agent's directory.

## Build step

`make agents` runs `compile_agents.py` which:

1. Iterates `.claude/agents/<name>/agent.md` for each agent (skipping `_template`, `_shared`).
2. Resolves every `@load` marker.
3. Writes `.claude/agents/<name>/agent.compiled.md` (the file Claude Code loads).
4. Fails the build if any compiled agent exceeds the **32k char budget** (~8k tokens, the D5 ceiling).

## Section-naming convention

Stable section anchors that compose well across agents:

| Section anchor | File | Loaded by |
|---|---|---|
| `#schemas` | `_shared/run-artifacts.md` | every artifact-producing agent |
| `#error-contract` | `_shared/error-contract.md` | every agent (small, cheap) |
| `#catalog` | `_shared/audio-qa-toolkit.md` | music, qa-reviewer |
| `#mix-targets` | `_shared/audio-qa-toolkit.md` | music, composition, qa-reviewer |
| `#dynamic-media` | `_shared/remotion.md` | composition |
| `#layering` | `_shared/remotion.md` | composition, qa-reviewer |
| `#audio-mix` | `_shared/remotion.md` | composition, qa-reviewer |
| `#proposal-shape` | `_shared/refresh-protocol.md` | curator + (selectively) per-agent prompts |

## Anti-pattern

If two agents would write the same paragraph in their `core.md`, that paragraph
belongs in `_shared/`. Per-agent knowledge should be agent-specific judgment,
not shared facts.

## Token-budget enforcement

CI fails the build when any compiled agent exceeds 32k chars. When pushing
beyond the budget, options:

1. Move sections to `_shared/` and reference (preferred).
2. Trim `inspiration.md` from the @load list (it's experimental ideas, not
   needed at runtime — load only during refresh runs).
3. Compress `gotchas.md` to a one-line-per-gotcha format.

The budget exists because prompt bloat compounds: a 9-agent fleet at 32k chars
each = ~290k chars total system+knowledge. Halving via `_shared/` keeps the
fleet livable.
