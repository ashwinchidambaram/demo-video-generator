"""Local fixture HTTP server.

Tests that need a deterministic page can spin this up and point Playwright at it.
Standalone-runnable: ``python -m tests.fixtures.server [port]``.
"""

from __future__ import annotations

import http.server
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).parent / "site"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, directory=str(ROOT), **kwargs)


def serve(port: int = 0) -> tuple[socketserver.TCPServer, int]:
    server = socketserver.TCPServer(("127.0.0.1", port), Handler)
    return server, server.server_address[1]


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server, bound = serve(port)
    print(f"Serving {ROOT} at http://127.0.0.1:{bound}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
