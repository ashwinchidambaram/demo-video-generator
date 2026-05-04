"""Compile agent.md files from section-loader markers (D5).

Each ``.claude/agents/<name>/agent.md`` may contain markers like:

    <!-- @load: knowledge/core.md#api-surface -->
    <!-- @load: _shared/audio-qa-toolkit.md -->

This tool resolves those into ``agent.compiled.md``, the file Claude Code
actually loads. CI fails the build if any compiled agent exceeds the per-agent
token budget (default 8k chars as a coarse proxy).

A section reference like ``foo.md#bar`` extracts content under the ``## bar``
heading (case-insensitive) up to the next ``## `` heading or EOF. A bare path
inlines the whole file.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_ROOT = REPO_ROOT / ".claude" / "agents"
SHARED_ROOT = AGENTS_ROOT / "_shared"

# Coarse-grained budget proxy. A real token count would use tiktoken; this is
# a chars-based ceiling we'll calibrate as agents accrue knowledge.
TOKEN_BUDGET_CHARS = 32_000  # ~8k tokens at 4 chars/token avg

LOAD_RE = re.compile(r"<!--\s*@load:\s*([^\s>]+)\s*-->")


@dataclass(slots=True)
class CompileResult:
    agent_name: str
    source: Path
    compiled: Path
    char_count: int
    over_budget: bool


def _resolve_section(target: str, *, agent_dir: Path) -> str:
    """Resolve a @load target to its inlined content.

    Forms supported:
      * ``knowledge/core.md`` — relative to the agent dir
      * ``knowledge/core.md#api-surface`` — section under ``## api-surface``
      * ``_shared/audio-qa-toolkit.md`` — resolved against AGENTS_ROOT
      * ``_shared/audio-qa-toolkit.md#catalog`` — section under heading
    """
    section: str | None = None
    if "#" in target:
        path_part, section = target.split("#", 1)
    else:
        path_part = target

    path = (
        AGENTS_ROOT / path_part
        if path_part.startswith("_shared/")
        else agent_dir / path_part
    )

    if not path.is_file():
        return f"<!-- @load: {target} (MISSING) -->"

    content = path.read_text()
    if section is None:
        return content.strip()

    pattern = re.compile(rf"^##\s+{re.escape(section)}\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return f"<!-- @load: {target} (SECTION '{section}' NOT FOUND) -->"
    start = match.end()
    next_heading = re.search(r"^##\s+", content[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(content)
    return content[start:end].strip()


def compile_agent(agent_dir: Path) -> CompileResult:
    src = agent_dir / "agent.md"
    out = agent_dir / "agent.compiled.md"
    text = src.read_text()

    def replace(match: re.Match[str]) -> str:
        return _resolve_section(match.group(1), agent_dir=agent_dir)

    compiled = LOAD_RE.sub(replace, text)
    out.write_text(compiled)
    return CompileResult(
        agent_name=agent_dir.name,
        source=src,
        compiled=out,
        char_count=len(compiled),
        over_budget=len(compiled) > TOKEN_BUDGET_CHARS,
    )


def main() -> int:
    if not AGENTS_ROOT.is_dir():
        print(f"No agents dir at {AGENTS_ROOT}", file=sys.stderr)
        return 1

    results: list[CompileResult] = []
    for agent_dir in sorted(AGENTS_ROOT.iterdir()):
        if not agent_dir.is_dir():
            continue
        if agent_dir.name.startswith("_"):
            continue  # _template, _shared
        if not (agent_dir / "agent.md").is_file():
            continue
        results.append(compile_agent(agent_dir))

    # Always compile the template too, so build-time failures surface early.
    template = AGENTS_ROOT / "_template"
    if (template / "agent.md").is_file():
        results.append(compile_agent(template))

    over = [r for r in results if r.over_budget]
    for r in results:
        flag = " OVER BUDGET" if r.over_budget else ""
        print(f"  {r.agent_name}: {r.char_count} chars{flag}")

    if over:
        print(
            f"FAIL: {len(over)} agent(s) exceeded {TOKEN_BUDGET_CHARS}-char budget.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
