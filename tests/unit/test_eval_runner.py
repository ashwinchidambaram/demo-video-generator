"""Run the smoke evals from inside pytest so a regression in the deterministic
agent substrates breaks the unit-test build.

Holdouts are gated (require --reveal-holdout) per D15; this test only runs
the cheap smoke pass.
"""

from __future__ import annotations

from evals.runner import (
    CASE_CLASSES,
    discover_agents,
    discover_cases,
    run_smoke,
)


def test_evals_dir_has_63_cases() -> None:
    total = 0
    for agent in discover_agents():
        for cc in CASE_CLASSES:
            total += len(discover_cases(agent, cc))
    assert total >= 63, f"expected ≥63 case fixtures across the fleet, got {total}"


def test_smoke_evals_pass_for_every_agent() -> None:
    failed: list[str] = []
    for agent in discover_agents():
        for r in run_smoke(agent):
            if not r.passed:
                failed.append(f"{agent}/{r.case_id}: {r.notes}")
    if failed:
        raise AssertionError("\n  ".join(["smoke eval failures:", *failed]))
