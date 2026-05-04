"""Codegen the qa-reviewer issue-code registry into review/codes.py.

Parses the YAML block under `## issue-code-registry` in
`.claude/agents/qa-reviewer/knowledge/core.md` and writes a typed Python
module that the driver imports for the AUTO_RETRY_ALLOWLIST.

This keeps a single source of truth for issue codes — the agent's own
knowledge file. Without this, the agent prompt and the driver could
silently disagree about which codes are auto-retryable.

Run via `make qa-codes`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE = REPO_ROOT / ".claude" / "agents" / "qa-reviewer" / "knowledge" / "core.md"
OUT_PATH = REPO_ROOT / "src" / "demo_video_generator" / "review" / "codes.py"


def _extract_yaml_block(text: str) -> str | None:
    """Pull the first ```yaml ... ``` block under '## issue-code-registry'."""
    m = re.search(
        r"^##\s+issue-code-registry\s*\n(.*?)(?=^##\s+|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not m:
        return None
    section = m.group(1)
    code = re.search(r"```yaml\s*\n(.*?)```", section, flags=re.DOTALL)
    if not code:
        return None
    return code.group(1)


def _parse_yaml_block(block: str) -> dict[str, dict[str, str | bool]]:
    """Trivial YAML parser for the registry's nested-key shape.

    Avoids a YAML dep for this one tightly-controlled structure. Each top
    key is a CODE name; under it are 4 fields (severity, allowlist,
    target_stage, description).
    """
    out: dict[str, dict[str, str | bool]] = {}
    current: str | None = None
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Top-level key: "<CODE>:"
        if not raw.startswith(" "):
            key = line.rstrip(":").strip()
            if key:
                current = key
                out[current] = {}
            continue
        # Indented field: "  field: value"
        if current is None:
            continue
        m = re.match(r"\s+([a-z_]+):\s*(.*)$", line)
        if not m:
            continue
        field, value = m.group(1), m.group(2).strip()
        # Booleans
        if value in ("true", "True"):
            out[current][field] = True
        elif value in ("false", "False"):
            out[current][field] = False
        else:
            out[current][field] = value
    return out


HEADER = '''"""qa-reviewer issue codes — CODEGEN, do not edit.

Generated from .claude/agents/qa-reviewer/knowledge/core.md by
`make qa-codes`. Re-run codegen if the YAML registry changes.

This module is the single source of truth for which qa.json codes the
driver may auto-retry (see AUTO_RETRY_ALLOWLIST in run.py).
"""

from __future__ import annotations

# --- generated -------------------------------------------------------------

ISSUE_CODES: dict[str, dict[str, str | bool]] = {
'''


def main() -> int:
    if not KNOWLEDGE.is_file():
        print(f"FAIL: {KNOWLEDGE} missing", file=sys.stderr)
        return 1
    text = KNOWLEDGE.read_text()
    block = _extract_yaml_block(text)
    if block is None:
        print("FAIL: ## issue-code-registry block not found", file=sys.stderr)
        return 1
    parsed = _parse_yaml_block(block)
    if not parsed:
        print("FAIL: registry parsed empty", file=sys.stderr)
        return 1

    body = HEADER
    for code in sorted(parsed.keys()):
        entry = parsed[code]
        body += f"    {code!r}: {{\n"
        for field in ("severity", "allowlist", "target_stage", "description"):
            if field in entry:
                body += f"        {field!r}: {entry[field]!r},\n"
        body += "    },\n"
    body += "}\n"
    body += "\n"
    body += "\n"
    body += "AUTO_RETRY_ALLOWLIST: frozenset[str] = frozenset(\n"
    body += "    code for code, entry in ISSUE_CODES.items() if entry.get(\"allowlist\")\n"
    body += ")\n"

    OUT_PATH.write_text(body)
    print(
        f"Generated {OUT_PATH} with {len(parsed)} codes "
        f"({len([c for c, e in parsed.items() if e.get('allowlist')])} on allowlist)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
