"""HTTP server for `cct web`. Binds to 127.0.0.1 only, checks the Host header, and never writes."""

from __future__ import annotations

import json
import pkgutil
import platform
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cct.config import load_config
from cct.errors import CctError
from cct.services.sessions import recent_sessions
from cct.services.usage import usage_rows

HOST = "127.0.0.1"


def load_page(nonce: str) -> bytes:
    """The dashboard HTML with this run's script nonce filled in."""
    try:
        # pkgutil also reads files from inside a zipapp.
        raw = pkgutil.get_data(__package__, "static/index.html")
    except OSError as err:
        raise CctError(f"The dashboard page is missing from this install ({err}). Reinstall cct.") from err
    if raw is None:
        raise CctError("The dashboard page is missing from this install. Reinstall cct.")
    return raw.decode("utf-8").replace("__NONCE__", nonce).encode("utf-8")


def make_handler(nonce: str):
    page = load_page(nonce)
    csp = (
        f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'"
    )

    class Handler(BaseHTTPRequestHandler):
        server_version = "cct"

        def do_GET(self):
            # A web page on some other site can point a DNS name at 127.0.0.1;
            # checking Host stops it from reading this data.
            port = self.server.server_address[1]
            if self.headers.get("Host") not in (f"{HOST}:{port}", f"localhost:{port}"):
                self.send_error(403, "Host not allowed")
                return
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, "text/html; charset=utf-8", page)
            elif path == "/api/status":
                try:
                    cfg = load_config()
                except CctError as err:
                    self._send(500, "application/json", json.dumps({"error": str(err)}).encode())
                    return
                body = {
                    "now": time.time(),
                    "host": platform.node(),
                    "accounts": usage_rows(cfg),
                    "sessions": recent_sessions(),
                }
                self._send(200, "application/json", json.dumps(body).encode("utf-8"))
            else:
                self.send_error(404)

        def _send(self, code: int, ctype: str, body: bytes):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return  # quiet on purpose: the page polls every 10 seconds

    return Handler


def create_server(port: int) -> ThreadingHTTPServer:
    """Bind the dashboard. Port 0 picks a free port (used by the tests)."""
    handler = make_handler(secrets.token_urlsafe(16))
    try:
        # 127.0.0.1 only: nothing on your network can reach this page.
        return ThreadingHTTPServer((HOST, port), handler)
    except OSError as err:
        raise CctError(f"Can't use port {port} ({err.strerror}). Try: cct web --port {port + 1}") from err
