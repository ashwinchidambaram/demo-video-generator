# /refresh-agents — knowledge-curator entry point (Phase 10)

Usage: `/refresh-agents [<agent-name>...]`

Phase 0 ships the freshness-manifest scaffolding (`runs/refresh/manifest.json`,
per-agent `knowledge/changelog.md`). The actual curator agent lands in
Phase 10; this command file exists now so the convention is committed and
agents can begin accumulating changelogs.

When the curator ships, this command will:

1. Read each agent's `refresh.md`.
2. Fetch declared sources; produce a structured report with citations.
3. Write `runs/refresh/<ts>/report.md`.
4. Surface to PM for approval; never auto-applies.
