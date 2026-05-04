"""Schema migration registry per D14.

When a JSON schema in `schemas/` increments its `schema_version` const,
register a forward migration here from version N to N+1. The driver runs
migrations forward on `manifest.json` load if `schema_version < CURRENT`.

Contracts:
- Migrations are pure functions: dict -> dict.
- Migrations MUST not lose information; if a field is removed, its data
  goes into a `_deprecated_<field>` key for one version's grace period.
- The migration table is keyed by (artifact_name, from_version).

v1 is the current target. No migrations exist yet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Migration table: (artifact_name, from_version) -> Callable[[dict], dict]
MIGRATIONS: dict[tuple[str, int], Callable[[dict[str, Any]], dict[str, Any]]] = {}


def migrate(artifact_name: str, doc: dict[str, Any]) -> dict[str, Any]:
    """Run all forward migrations for `artifact_name` until doc.schema_version
    is current. Idempotent: returns doc unchanged if already current.
    """
    while True:
        version = int(doc.get("schema_version", 1))
        key = (artifact_name, version)
        if key not in MIGRATIONS:
            return doc
        doc = MIGRATIONS[key](doc)
        new_version = int(doc.get("schema_version", version))
        if new_version <= version:
            raise RuntimeError(
                f"Migration {key} did not advance schema_version "
                f"(stuck at {version}); this is a registry bug."
            )


def register_migration(
    artifact_name: str,
    from_version: int,
    fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    """Register a forward migration. Caller is responsible for ensuring fn
    bumps doc['schema_version'] to from_version + 1.
    """
    key = (artifact_name, from_version)
    if key in MIGRATIONS:
        raise RuntimeError(f"duplicate migration registration: {key}")
    MIGRATIONS[key] = fn
