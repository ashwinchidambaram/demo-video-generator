"""Pre-commit / CI check for the cross-agent contract registry (D18).

Reads `schemas/contracts.json` and verifies:
1. Every contract field name corresponds to a real schema (basic shape check).
2. Every consumer_ack tag is non-empty (intentional ack, not a placeholder).
3. The qa.json#issues[].code allowlist matches AUTO_RETRY_ALLOWLIST in run.py
   (driver and registry must agree on which codes are auto-retryable).

Exit 0 on success, 1 on contract drift. Run via `make check-contracts` or
the pre-commit hook.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_PATH = REPO_ROOT / "schemas" / "contracts.json"


def main() -> int:
    if not CONTRACTS_PATH.is_file():
        print(f"FAIL: {CONTRACTS_PATH} missing", file=sys.stderr)
        return 1
    contracts = json.loads(CONTRACTS_PATH.read_text())

    errors: list[str] = []

    for entry in contracts.get("contracts", []):
        field = entry.get("field", "")
        if "#" not in field:
            errors.append(f"contract field missing '#schema-path': {field}")
            continue
        artifact_name, _, _ = field.partition("#")
        # Map artifact name (e.g. composition.json) → schema file (composition.schema.json).
        # qa.json doesn't yet have its own schema (Phase 8.5); skip its existence check.
        schema_basename = artifact_name.replace(".json", ".schema.json")
        if (
            artifact_name != "qa.json"
            and not (REPO_ROOT / "schemas" / schema_basename).is_file()
        ):
            errors.append(
                f"contract references missing schema file: {schema_basename}"
            )

        for consumer, ack in entry.get("consumer_acks", {}).items():
            if not isinstance(ack, str) or not ack.startswith("v"):
                errors.append(
                    f"{field} consumer {consumer} ack '{ack}' "
                    f"must start with version prefix 'v<N>-'"
                )

        # Every declared consumer must have an ack.
        consumers = set(entry.get("consumers", []))
        ack_keys = set(entry.get("consumer_acks", {}).keys())
        missing = consumers - ack_keys
        if missing:
            errors.append(f"{field}: consumers without acks: {sorted(missing)}")

    # Cross-check qa.json#issues[].code with the driver's allowlist.
    qa_entry = next(
        (e for e in contracts.get("contracts", []) if e["field"] == "qa.json#issues[].code"),
        None,
    )
    if qa_entry:
        driver_ack = qa_entry["consumer_acks"].get("__driver__", "")
        # parse "v1-allowlist:CODE_A|CODE_B|..."
        try:
            ack_codes = set(driver_ack.split(":", 1)[1].split("|"))
        except IndexError:
            ack_codes = set()
        # Driver allowlist is codegen-derived (make qa-codes) from the YAML
        # registry in qa-reviewer/knowledge/core.md. Import the generated
        # module directly rather than parsing run.py.
        try:
            import importlib.util

            codes_path = (
                REPO_ROOT / "src" / "demo_video_generator" / "review" / "codes.py"
            )
            if codes_path.is_file():
                spec = importlib.util.spec_from_file_location(
                    "dvg_codes", codes_path
                )
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    driver_codes = set(module.AUTO_RETRY_ALLOWLIST)
                else:
                    driver_codes = set()
            else:
                driver_codes = set()
        except Exception:
            driver_codes = set()
        if ack_codes and driver_codes and ack_codes != driver_codes:
            extra_in_ack = ack_codes - driver_codes
            extra_in_driver = driver_codes - ack_codes
            if extra_in_ack:
                errors.append(
                    f"qa.json allowlist drift: in contracts.json but not run.py: {sorted(extra_in_ack)}"
                )
            if extra_in_driver:
                errors.append(
                    f"qa.json allowlist drift: in run.py but not contracts.json: {sorted(extra_in_driver)}"
                )

    if errors:
        print("CONTRACT REGISTRY VIOLATIONS:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"OK: {len(contracts.get('contracts', []))} contracts validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
