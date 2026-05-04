"""evals/runner.py — eval framework skeleton.

Phase 1 ships the skeleton (deferred from Phase 0 in v2.1). Each phase as it
ships its agent populates `evals/cases/<agent>/{headline,smoke,holdout}/` with
case fixtures; the runner orchestrates judge calls and rubric scoring.

Phase 1 capabilities:
- Discover cases per agent / case-class.
- Run the smoke suite (contract-only — exercises agent's CLI primitive against
  fixture inputs and validates output against schema).
- Skeleton hooks for headline (LLM-judge) and holdout (PM-only) suites.

Real LLM-judge wiring lands in Phase 2+ as agents start producing real output.
The skeleton + invariants (judge diversity, baseline rule per D19, holdout
rotation per D15, cost cap per D16) are committed now so they are ready when
needed.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_ROOT = REPO_ROOT / "evals" / "cases"

CASE_CLASSES: tuple[str, ...] = ("headline", "smoke", "holdout")


@dataclass(slots=True)
class CaseResult:
    agent: str
    case_class: str
    case_id: str
    passed: bool
    score: float | None = None
    notes: str = ""


def discover_agents() -> list[str]:
    if not EVALS_ROOT.is_dir():
        return []
    return sorted(d.name for d in EVALS_ROOT.iterdir() if d.is_dir())


def discover_cases(agent: str, case_class: str) -> list[Path]:
    base = EVALS_ROOT / agent / case_class
    if not base.is_dir():
        return []
    # Each case is a directory with a `case.json` describing inputs + expected outputs.
    return sorted(d for d in base.iterdir() if d.is_dir() and (d / "case.json").is_file())


def run_smoke(agent: str) -> list[CaseResult]:
    """Smoke suite: contract-only. Phase 1 stub — real impl invokes agent CLI."""
    results: list[CaseResult] = []
    for case_dir in discover_cases(agent, "smoke"):
        case_id = case_dir.name
        # Phase 1: just verify the case fixture is well-formed.
        try:
            json.loads((case_dir / "case.json").read_text())
            results.append(CaseResult(agent, "smoke", case_id, passed=True, notes="fixture parsed"))
        except json.JSONDecodeError as e:
            results.append(CaseResult(agent, "smoke", case_id, passed=False, notes=f"bad JSON: {e}"))
    return results


def run_headline(agent: str) -> list[CaseResult]:
    """Headline suite: LLM-judge graded. Phase 1 stub — real impl wires
    judge diversity (Sonnet primary, Opus tiebreaker per D16) + rubric.
    """
    results: list[CaseResult] = []
    for case_dir in discover_cases(agent, "headline"):
        results.append(CaseResult(agent, "headline", case_dir.name, passed=True, notes="stub: not run"))
    return results


def run_holdout(agent: str) -> list[CaseResult]:
    """Holdout suite: never shown during prompt tuning. Per D15, rotated every
    90 days or on schema bump. Revealed only at phase exit.
    """
    results: list[CaseResult] = []
    for case_dir in discover_cases(agent, "holdout"):
        results.append(CaseResult(agent, "holdout", case_dir.name, passed=True, notes="stub: not run"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="dvg eval runner (Phase 1 skeleton)")
    parser.add_argument("--agent", help="Run evals for one agent only")
    parser.add_argument(
        "--class",
        dest="case_class",
        choices=CASE_CLASSES,
        help="Run only one case class",
    )
    parser.add_argument("--list", action="store_true", help="List discovered agents/cases and exit")
    args = parser.parse_args(argv)

    agents = [args.agent] if args.agent else discover_agents()
    if not agents:
        print(f"no agents found under {EVALS_ROOT}")
        return 0

    if args.list:
        for agent in agents:
            print(f"agent: {agent}")
            for cc in CASE_CLASSES:
                cases = discover_cases(agent, cc)
                print(f"  {cc}: {len(cases)} case(s)")
        return 0

    classes = [args.case_class] if args.case_class else list(CASE_CLASSES)
    runners = {"smoke": run_smoke, "headline": run_headline, "holdout": run_holdout}
    failed = 0
    total = 0
    for agent in agents:
        for cc in classes:
            for r in runners[cc](agent):
                total += 1
                status = "PASS" if r.passed else "FAIL"
                print(f"[{status}] {agent} {cc} {r.case_id}: {r.notes}")
                if not r.passed:
                    failed += 1
    print(f"\n{total - failed}/{total} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
