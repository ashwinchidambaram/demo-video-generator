"""Knowledge-curator subcommand.

Phase 10 skeleton per .claude/agents/knowledge-curator/design.md and
_shared/refresh-protocol.md. Reads each agent's refresh.md, parses the
required sections (Sources / Queries / Freshness target / Scope / Pin
facts / Anti-scope), produces a structured report at
`runs/refresh/<ts>/report.md` and an empty proposals.json.

Real WebFetch + LLM proposal generation is gated on API keys + the curator
agent's prompt; this skeleton commits the workflow shape so:
  - `dvg refresh` walks the fleet and produces a report
  - `runs/refresh/manifest.json` updates last_run timestamps + per-agent
    staleness placeholders
  - The pre-commit `apply-refresh` flow has a target to slot into.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..atomic import write_atomic, write_json_atomic

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_ROOT = REPO_ROOT / ".claude" / "agents"
RUNS_REFRESH_ROOT = REPO_ROOT / "runs" / "refresh"


@dataclass(slots=True)
class RefreshDoc:
    agent: str
    sources: list[str]
    queries: list[str]
    freshness_target_days: int
    scope: list[str]
    pin_facts: list[str]
    anti_scope: list[str]


def _parse_refresh_md(path: Path, *, agent: str) -> RefreshDoc:
    """Parse a refresh.md per the shape declared in _shared/refresh-protocol.md."""
    text = path.read_text() if path.is_file() else ""

    def _section(name: str) -> str:
        pattern = re.compile(
            rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s+|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(text)
        return m.group(1) if m else ""

    def _bullet_lines(section_text: str) -> list[str]:
        out: list[str] = []
        for line in section_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("-"):
                value = stripped.lstrip("-").strip()
                # strip surrounding quotes/backticks so query strings round-trip
                value = value.strip('"').strip("'")
                if value and not value.startswith("("):
                    out.append(value)
        return out

    sources = _bullet_lines(_section("Sources"))
    queries = _bullet_lines(_section("Queries"))
    scope = _bullet_lines(_section("Scope"))
    pin_facts = _bullet_lines(_section("Pin facts"))
    anti_scope = _bullet_lines(_section("Anti-scope"))

    freshness_text = _section("Freshness target").strip()
    days_match = re.search(r"(\d+)\s*days?", freshness_text)
    freshness_target_days = int(days_match.group(1)) if days_match else 90

    return RefreshDoc(
        agent=agent,
        sources=sources,
        queries=queries,
        freshness_target_days=freshness_target_days,
        scope=scope,
        pin_facts=pin_facts,
        anti_scope=anti_scope,
    )


def discover_agents() -> list[str]:
    if not AGENTS_ROOT.is_dir():
        return []
    return sorted(
        d.name
        for d in AGENTS_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )


def refresh(*, agents: list[str] | None = None) -> dict[str, Any]:
    """Walk the fleet, parse each agent's refresh.md, write a report.

    Phase 10 stub: emits report + empty proposals.json. WebFetch + proposal
    generation are gated on API keys.
    """
    selected = agents or discover_agents()
    now = dt.datetime.now(dt.UTC)
    ts = now.strftime("%Y-%m-%dT%H-%M-%S")
    refresh_dir = RUNS_REFRESH_ROOT / ts
    refresh_dir.mkdir(parents=True, exist_ok=True)

    docs: dict[str, RefreshDoc] = {}
    for agent in selected:
        refresh_md = AGENTS_ROOT / agent / "refresh.md"
        docs[agent] = _parse_refresh_md(refresh_md, agent=agent)

    # Report (markdown, human-readable).
    lines: list[str] = []
    lines.append(f"# Refresh Report — {ts}")
    lines.append("")
    lines.append(f"Phase 10 skeleton run. {len(docs)} agents inspected; no proposals generated.")
    lines.append("Real WebFetch + LLM proposal generation requires API keys.")
    lines.append("")
    for agent, doc in docs.items():
        lines.append(f"## {agent}")
        lines.append(f"- freshness target: {doc.freshness_target_days} days")
        lines.append(f"- sources: {len(doc.sources)} configured")
        lines.append(f"- queries: {len(doc.queries)} configured")
        lines.append(f"- pin facts: {len(doc.pin_facts)} configured")
        if not doc.sources and not doc.queries:
            lines.append("- _stub_: refresh.md is the Phase 1 placeholder; real sources land with the agent's implementation phase")
        lines.append("")
    write_atomic(refresh_dir / "report.md", "\n".join(lines).encode("utf-8"))

    # Empty proposals (real proposals require WebFetch + LLM).
    write_json_atomic(
        refresh_dir / "proposals.json",
        {
            "schema_version": 1,
            "stub": True,
            "proposals": [],
        },
    )

    # Update freshness manifest.
    manifest_path = RUNS_REFRESH_ROOT / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {"schema_version": 1, "last_run": None, "agents": {}}
    manifest["last_run"] = now.isoformat()
    for agent, doc in docs.items():
        manifest["agents"][agent] = {
            "freshness_target_days": doc.freshness_target_days,
            "last_refresh": now.isoformat(),
            "staleness_days": 0,
        }
    write_json_atomic(manifest_path, manifest)

    return {
        "run_id": ts,
        "report": str(refresh_dir / "report.md"),
        "proposals": str(refresh_dir / "proposals.json"),
        "agents": list(docs.keys()),
    }
