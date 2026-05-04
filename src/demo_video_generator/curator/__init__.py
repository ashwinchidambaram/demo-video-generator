"""Knowledge-curator subcommand.

Phase 10 (this commit): walks the fleet's refresh.md, parses the required
sections (Sources / Queries / Freshness target / Scope / Pin facts /
Anti-scope), and OPTIONALLY fetches Sources URLs via `requests`. For each
fetched source it computes the SHA256 of the response body, records
Last-Modified, and verifies whether each Pin Fact is still verbatim
present. This produces a real report + proposals.json shape — no LLM
involved.

LLM-driven proposal generation (semantic refresh, citation excerpt
extraction, paragraph-level diff) is the further Phase 10.5; that requires
API keys.

apply-refresh: see `dvg apply-refresh <ts>` — re-fetches each citation
URL and verifies sha256 matches before applying any proposal. Acts as the
post-hoc verifier per the curator design's "citation faking" mitigation.
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


def _fetch_url(url: str, *, timeout: int = 15) -> dict[str, Any]:
    """Fetch a URL via requests; return canonical fields for citation:
    {url, fetched_at, status, body_sha256, last_modified, body_excerpt}.

    Body excerpt is the first 500 chars (sanitized) — enough for Pin Fact
    verification without committing the full page to disk.
    """
    out: dict[str, Any] = {
        "url": url,
        "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
        "status": None,
        "body_sha256": None,
        "last_modified": None,
        "body_excerpt": None,
        "error": None,
    }
    try:
        import requests  # type: ignore[import-untyped]

        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        out["status"] = resp.status_code
        out["last_modified"] = resp.headers.get("Last-Modified")
        body = resp.text
        out["body_sha256"] = _sha256_str(body)
        out["body_excerpt"] = body[:500].replace("\n", " ").strip() if body else None
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


def _sha256_str(s: str) -> str:
    import hashlib

    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _verify_pin_facts(body: str, pin_facts: list[str]) -> list[dict[str, Any]]:
    """Per Pin Fact: check whether the verbatim string still appears in body."""
    out: list[dict[str, Any]] = []
    for fact in pin_facts:
        out.append({"fact": fact, "still_present": fact in body})
    return out


def refresh(
    *,
    agents: list[str] | None = None,
    fetch: bool = False,
) -> dict[str, Any]:
    """Walk the fleet, parse each agent's refresh.md, write a report.

    fetch=False (default): skeleton — fast, no network, empty proposals.
    fetch=True: WebFetch each Sources URL via requests, verify Pin Facts,
                emit citation-rich proposals.json. Still no LLM.
    """
    selected = agents or discover_agents()
    now = dt.datetime.now(dt.UTC)
    ts = now.strftime("%Y-%m-%dT%H-%M-%S")
    refresh_dir = RUNS_REFRESH_ROOT / ts
    refresh_dir.mkdir(parents=True, exist_ok=True)

    docs: dict[str, RefreshDoc] = {}
    fetched_by_agent: dict[str, list[dict[str, Any]]] = {}
    pin_facts_results_by_agent: dict[str, list[list[dict[str, Any]]]] = {}
    for agent in selected:
        refresh_md = AGENTS_ROOT / agent / "refresh.md"
        docs[agent] = _parse_refresh_md(refresh_md, agent=agent)
        if fetch:
            fetched: list[dict[str, Any]] = []
            pin_results: list[list[dict[str, Any]]] = []
            for url in docs[agent].sources:
                if not url.startswith(("http://", "https://")):
                    continue
                meta = _fetch_url(url)
                fetched.append(meta)
                # Pin Fact verification needs full body — re-fetch for a deeper read.
                # (We cap at 500 chars in body_excerpt for the citation; here we want full text.)
                if docs[agent].pin_facts and meta.get("status") == 200:
                    try:
                        import requests

                        resp = requests.get(url, timeout=15)
                        pin_results.append(_verify_pin_facts(resp.text, docs[agent].pin_facts))
                    except Exception:
                        pin_results.append(
                            [
                                {"fact": f, "still_present": None, "error": "fetch_failed"}
                                for f in docs[agent].pin_facts
                            ]
                        )
            fetched_by_agent[agent] = fetched
            pin_facts_results_by_agent[agent] = pin_results

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
        if fetch and agent in fetched_by_agent:
            for meta in fetched_by_agent[agent]:
                status = meta.get("status")
                err = meta.get("error")
                if err:
                    lines.append(f"- fetch error: {meta['url']} → {err}")
                else:
                    lm = meta.get("last_modified") or "unknown"
                    lines.append(
                        f"- fetched: {meta['url']} → {status}, "
                        f"sha256={meta['body_sha256'][:12] if meta['body_sha256'] else 'n/a'}, "
                        f"last-modified={lm}"
                    )
            for url_pin_results in pin_facts_results_by_agent.get(agent, []):
                for r in url_pin_results:
                    if r["still_present"] is False:
                        lines.append(
                            f"- ⚠ pin fact NOT FOUND in fetched body: {r['fact'][:60]}…"
                        )
        lines.append("")
    write_atomic(refresh_dir / "report.md", "\n".join(lines).encode("utf-8"))

    # Build proposals.json. Without an LLM we can't yet propose paragraph
    # rewrites; we DO emit pin-fact-failures as candidate proposals carrying
    # the citation envelope (so apply-refresh has something to verify).
    proposals: list[dict[str, Any]] = []
    if fetch:
        for agent, meta_list in fetched_by_agent.items():
            agent_pin_results = pin_facts_results_by_agent.get(agent, [])
            for url_idx, meta in enumerate(meta_list):
                if url_idx >= len(agent_pin_results):
                    continue
                this_url_pin_results: list[dict[str, Any]] = agent_pin_results[url_idx]
                failed_pins = [
                    r for r in this_url_pin_results if r.get("still_present") is False
                ]
                for fp in failed_pins:
                    proposals.append(
                        {
                            "agent": agent,
                            "kind": "pin_fact_drift",
                            "old_excerpt": fp["fact"],
                            "new_excerpt": "<requires LLM extraction; gated on API key>",
                            "citation": {
                                "url": meta["url"],
                                "fetched_at": meta["fetched_at"],
                                "excerpt": meta.get("body_excerpt", ""),
                                "excerpt_sha256": _sha256_str(meta.get("body_excerpt", "") or ""),
                                "body_sha256": meta.get("body_sha256"),
                                "last_modified": meta.get("last_modified"),
                            },
                        }
                    )

    write_json_atomic(
        refresh_dir / "proposals.json",
        {
            "schema_version": 1,
            "fetch_mode": "real" if fetch else "skeleton",
            "proposals": proposals,
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
