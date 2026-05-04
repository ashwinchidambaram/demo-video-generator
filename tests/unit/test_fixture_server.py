"""Verify the fixture HTTP server boots and serves the static page."""

from __future__ import annotations

import threading
import urllib.request

from tests.fixtures.server import serve


def test_fixture_server_serves_index() -> None:
    server, port = serve(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=2) as resp:
            body = resp.read().decode()
        assert "demo-video-generator fixture" in body
    finally:
        server.shutdown()
        thread.join(timeout=2)
