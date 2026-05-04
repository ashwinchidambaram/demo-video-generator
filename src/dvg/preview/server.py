"""Hot-reload preview server for compositions.

`dvg preview composition.json` opens an HTTP server with a scrubbable
timeline UI in the browser. Each scrub fetches a frame from the rendered
MP4 (cached); on composition.json change, the cache invalidates and
re-renders.

Implementation:
- stdlib http.server (no FastAPI dep)
- ffmpeg renders the full comp once to a temp MP4
- per-time PNG frames extracted via `ffmpeg -ss t -i tmp.mp4 -frames:v 1`
- mtime-watch on composition.json triggers cache invalidation
"""

from __future__ import annotations

import http.server
import socketserver
import subprocess
import tempfile
import threading
import urllib.parse
from pathlib import Path

from dvg.composition.render import render
from dvg.models import Composition

_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>dvg preview</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; background: #0a0a0a; color: #f5f5f5;
               font-family: -apple-system, "SF Pro Text", sans-serif; }
  .wrap { display: grid; grid-template-rows: 1fr auto auto; height: 100vh; padding: 1rem; gap: 1rem; }
  img { width: 100%; height: 100%; object-fit: contain; background: #000; border-radius: 8px; }
  .scrub { width: 100%; }
  input[type=range] { width: 100%; }
  .meta { font-size: 0.9rem; color: #9ca3af; display: flex; justify-content: space-between; }
  .meta b { color: #f5f5f5; font-variant-numeric: tabular-nums; }
</style></head>
<body>
<div class="wrap">
  <img id="frame" src="/frame?t=0.0" />
  <div class="scrub"><input id="t" type="range" min="0" max="__DURATION__" step="0.05" value="0.0" /></div>
  <div class="meta">
    <span>composition: <b id="src">__SRC__</b></span>
    <span>t = <b id="tval">0.00</b> s / <b>__DURATION__</b> s</span>
  </div>
</div>
<script>
  const img = document.getElementById('frame');
  const t = document.getElementById('t');
  const tval = document.getElementById('tval');
  let lastT = 0;
  let pending = false;
  function refresh() {
    if (pending) return;
    pending = true;
    const v = parseFloat(t.value);
    tval.textContent = v.toFixed(2);
    const u = new Image();
    u.onload = () => { img.src = u.src; pending = false; };
    u.onerror = () => { pending = false; };
    u.src = '/frame?t=' + v.toFixed(2) + '&_=' + Date.now();
  }
  t.addEventListener('input', refresh);
  // poll for composition changes — server reflects via /version
  let lastVersion = '';
  setInterval(async () => {
    try {
      const r = await fetch('/version');
      const v = await r.text();
      if (lastVersion && v !== lastVersion) {
        refresh();
      }
      lastVersion = v;
    } catch {}
  }, 1000);
</script>
</body></html>"""


class _State:
    def __init__(self, comp_path: Path) -> None:
        self.comp_path = comp_path
        self.tmpdir = Path(tempfile.mkdtemp(prefix="dvg-preview-"))
        self.tmp_mp4 = self.tmpdir / "preview.mp4"
        self.last_mtime = 0.0
        self.lock = threading.Lock()
        self.duration = 1.0
        self.refresh()

    def refresh(self) -> None:
        with self.lock:
            mtime = self.comp_path.stat().st_mtime
            if mtime == self.last_mtime and self.tmp_mp4.exists():
                return
            self.last_mtime = mtime
            comp = Composition.load(self.comp_path)
            self.duration = comp.duration
            print(f"[dvg-preview] re-rendering {self.comp_path.name} ...")
            render(
                comp,
                self.tmp_mp4,
                preset="ultrafast",
                crf=28,
                keep_intermediates=False,
            )

    def frame_at(self, t: float, out: Path) -> bool:
        self.refresh()
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, t):.3f}",
            "-i",
            str(self.tmp_mp4),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return proc.returncode == 0


class _Handler(http.server.SimpleHTTPRequestHandler):
    state: _State  # set on subclass

    def do_GET(self) -> None:  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        if url.path == "/" or url.path == "/index.html":
            html = (
                _HTML
                .replace("__DURATION__", f"{self.state.duration:.2f}")
                .replace("__SRC__", str(self.state.comp_path.name))
            )
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/version":
            body = f"{self.state.last_mtime:.6f}".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/frame":
            qs = urllib.parse.parse_qs(url.query)
            try:
                t = float(qs.get("t", ["0"])[0])
            except ValueError:
                t = 0.0
            png = self.state.tmpdir / f"frame_{t:.3f}.png"
            ok = self.state.frame_at(t, png)
            if not ok or not png.exists():
                self.send_error(500)
                return
            data = png.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # silent
        return


def serve(comp_path: Path, port: int = 8765) -> None:
    """Run the preview server until interrupted."""
    state = _State(comp_path)

    class Handler(_Handler):
        pass

    Handler.state = state

    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as httpd:
        print(f"[dvg-preview] http://127.0.0.1:{port}  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[dvg-preview] bye")
