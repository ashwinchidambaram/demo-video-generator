"""Tests for the schema migration registry (D14)."""

from __future__ import annotations

import pytest

from demo_video_generator import migrations as m


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Each test starts with an empty registry; restore after."""
    saved = dict(m.MIGRATIONS)
    m.MIGRATIONS.clear()
    try:
        yield
    finally:
        m.MIGRATIONS.clear()
        m.MIGRATIONS.update(saved)


def test_migrate_passthrough_when_current_version() -> None:
    doc = {"schema_version": 1, "x": "y"}
    assert m.migrate("captions", doc) == doc


def test_register_and_apply_single_migration() -> None:
    def v1_to_v2(d: dict) -> dict:
        return {**d, "schema_version": 2, "added": True}

    m.register_migration("captions", 1, v1_to_v2)
    out = m.migrate("captions", {"schema_version": 1, "x": "y"})
    assert out["schema_version"] == 2
    assert out["added"] is True
    assert out["x"] == "y"


def test_chained_migrations_v1_to_v3() -> None:
    def v1_to_v2(d: dict) -> dict:
        return {**d, "schema_version": 2}

    def v2_to_v3(d: dict) -> dict:
        return {**d, "schema_version": 3, "v3_field": "added"}

    m.register_migration("analysis", 1, v1_to_v2)
    m.register_migration("analysis", 2, v2_to_v3)
    out = m.migrate("analysis", {"schema_version": 1})
    assert out["schema_version"] == 3
    assert out["v3_field"] == "added"


def test_migration_must_advance_version_or_raise() -> None:
    def buggy(d: dict) -> dict:
        return d  # forgot to bump schema_version

    m.register_migration("captions", 1, buggy)
    with pytest.raises(RuntimeError, match="did not advance"):
        m.migrate("captions", {"schema_version": 1})


def test_duplicate_registration_raises() -> None:
    def fn(d: dict) -> dict:
        return {**d, "schema_version": 2}

    m.register_migration("captions", 1, fn)
    with pytest.raises(RuntimeError, match="duplicate"):
        m.register_migration("captions", 1, fn)
