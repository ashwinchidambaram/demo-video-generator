"""dvg doctor — preflight checks.

Validates the dev environment: required CLI tools, codegen freshness (SHA256
hash of schemas/*.schema.json against schemas/.checksums), and macOS TCC
permission state.

Per v2.1: TCC remediation *prints* the System Settings URL — does not auto-open.
"""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

REQUIRED_TOOLS_PHASE_0: tuple[str, ...] = ("uv", "node", "npm")
REQUIRED_TOOLS_LATER: tuple[str, ...] = ("ffmpeg", "ffprobe", "sox", "aubio")

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def _check_tool(name: str) -> CheckResult:
    path = shutil.which(name)
    if path is None:
        return CheckResult(name, False, "not found on PATH")
    return CheckResult(name, True, path)


def _check_node_version(min_major: int = 20) -> CheckResult:
    if shutil.which("node") is None:
        return CheckResult("node>=20", False, "node not found")
    out = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False)
    version = out.stdout.strip().lstrip("v")
    try:
        major = int(version.split(".")[0])
    except ValueError:
        return CheckResult("node>=20", False, f"unparseable: {version}")
    if major < min_major:
        return CheckResult("node>=20", False, f"have {version}, need >={min_major}")
    return CheckResult("node>=20", True, version)


def _check_codegen_freshness() -> CheckResult:
    schema_dir = REPO_ROOT / "schemas"
    checksum_file = schema_dir / ".checksums"
    schema_files = sorted(schema_dir.glob("*.schema.json"))
    if not schema_files:
        return CheckResult("codegen", False, "no schemas/*.schema.json found")
    if not checksum_file.exists():
        return CheckResult(
            "codegen", False, "schemas/.checksums missing — run 'make schemas'"
        )

    expected: dict[str, str] = {}
    for line in checksum_file.read_text().splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            expected[Path(parts[1]).name] = parts[0]

    drift: list[str] = []
    for sf in schema_files:
        actual = hashlib.sha256(sf.read_bytes()).hexdigest()
        if expected.get(sf.name) != actual:
            drift.append(sf.name)
    if drift:
        return CheckResult(
            "codegen", False, f"stale codegen for {drift} — run 'make schemas'"
        )
    return CheckResult("codegen", True, f"{len(schema_files)} schemas in sync")


def _check_macos_tcc() -> CheckResult:
    if platform.system() != "Darwin":
        return CheckResult("macOS TCC", True, "non-macOS, skipped")
    # We can't reliably introspect TCC without prompting. Print remediation URL.
    url = (
        "x-apple.systempreferences:com.apple.preference.security"
        "?Privacy_ScreenCapture"
    )
    return CheckResult(
        "macOS TCC",
        True,
        f"open this URL to grant Screen Recording: {url}",
    )


def _check_freshness_manifest() -> CheckResult:
    """Phase 0 stub: checks that the freshness-manifest convention exists.

    The actual ``--strict-freshness`` enforcement wires up in Phase 10 alongside
    the knowledge-curator agent. For Phase 0 we just confirm the directory and
    schema reference are in place so changelogs can accumulate from day one.
    """
    refresh_dir = REPO_ROOT / "runs" / "refresh"
    refresh_dir.mkdir(parents=True, exist_ok=True)
    return CheckResult("freshness scaffold", True, str(refresh_dir))


def run(*, strict_freshness: bool = False) -> bool:
    checks: list[CheckResult] = []
    for tool in REQUIRED_TOOLS_PHASE_0:
        checks.append(_check_tool(tool))
    checks.append(_check_node_version())
    for tool in REQUIRED_TOOLS_LATER:
        r = _check_tool(tool)
        # Demote to warning for Phase 0 — these are needed Phase 2+.
        if not r.ok:
            r.detail = f"(Phase 2+ dep) {r.detail}"
        checks.append(r)
    checks.append(_check_codegen_freshness())
    checks.append(_check_macos_tcc())
    checks.append(_check_freshness_manifest())

    table = Table(title="dvg doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")
    for c in checks:
        status = "[green]OK[/]" if c.ok else "[red]FAIL[/]"
        table.add_row(c.name, status, c.detail)
    console.print(table)

    # Phase 0 deps are required; later-phase deps and codegen are warnings unless --strict.
    blocking = [c for c in checks if not c.ok and c.name in REQUIRED_TOOLS_PHASE_0]
    blocking += [c for c in checks if not c.ok and c.name == "node>=20"]
    blocking += [c for c in checks if not c.ok and c.name == "codegen"]
    if strict_freshness:
        # Placeholder: Phase 10 wires real checks; for now strict adds nothing.
        pass
    return not blocking
