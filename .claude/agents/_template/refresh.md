# refresh.md — <agent-name>

Self-update protocol. The `knowledge-curator` agent (Phase 10) reads this to
plan refresh runs.

## Sources

- (e.g. https://www.remotion.dev/docs)

## Queries

- (e.g. "Remotion v4 OffthreadVideo")

## Freshness target

(e.g. 30 days)

## Update procedure

1. Fetch sources; extract excerpts.
2. Diff against `knowledge/core.md`.
3. Propose changes via `runs/refresh/<ts>/report.md` with citations.
4. On approval, apply and append a `knowledge/changelog.md` entry.

## Citation rule

Every proposed update must include a fetched URL and a verbatim quoted excerpt.
Updates without citation are auto-rejected by the curator script.
