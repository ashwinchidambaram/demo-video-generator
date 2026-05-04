"""Standard error envelope per D6.

CLI primitives that exit non-zero must emit one of these to stderr as JSON.
Agents on failure write `error.json` into the run dir with the same shape.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

ERROR_SCHEMA_VERSION = 1


@dataclass(slots=True)
class DvgError:
    error: str
    code: str
    retryable: bool
    suggestion: str = ""
    stage: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    schema_version: int = ERROR_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class DvgRuntimeError(Exception):
    """Raised by CLI primitives when they need to exit non-zero with structured error.

    The CLI entry point catches this and writes the error envelope to stderr
    before exiting with the requested code (default 1).
    """

    def __init__(self, err: DvgError, exit_code: int = 1) -> None:
        super().__init__(err.error)
        self.err = err
        self.exit_code = exit_code


def die(err: DvgError, exit_code: int = 1) -> None:
    """Print error envelope to stderr and exit. Use only at CLI top-level."""
    print(err.to_json(), file=sys.stderr)
    raise SystemExit(exit_code)
