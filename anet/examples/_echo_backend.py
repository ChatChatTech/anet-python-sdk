"""Tiny stdlib HTTP echo backend used by the SDK examples.

Listens on 127.0.0.1:$ECHO_PORT (default 7000), echoes the POST body back as
JSON, and exposes /health and /meta for service-gateway register/health/meta
probes.

Run standalone:

    python -m anet.examples._echo_backend
"""

from __future__ import annotations

import http.server
import json
import os
import signal
import sys

PORT = int(os.environ.get("ECHO_PORT", "7000"))


class Handler(http.server.BaseHTTPRequestHandler):
    def _write(self, status: int, payload: bytes, ctype: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802 (stdlib API)
        if self.path.startswith("/meta"):
            meta = {
                "name": "echo-demo",
                "version": "0.1.0",
                "description": "minimal echo backend (anet.examples)",
                "endpoints": [
                    {"method": "POST", "path": "/echo", "body": "any JSON"},
                    {"method": "GET", "path": "/health"},
                ],
            }
            self._write(200, json.dumps(meta).encode())
            return
        # /health and everything else
        self._write(200, json.dumps({"ok": True}).encode())

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n) if n else b"{}"
        did = self.headers.get("X-Agent-DID", "<missing>")
        sys.stderr.write(f"[echo] {self.path} did={did} body={body[:120]!r}\n")
        # Echo back as a JSON envelope so the body is always valid JSON
        # (the gateway expects JSON-shaped upstream bodies).
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError:
            decoded = body.decode("utf-8", "replace")
        out = json.dumps({"echo": decoded, "caller_did": did}).encode()
        self._write(200, out)

    def log_message(self, *_args):
        return


def main() -> None:
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print(f"[echo] listening on 127.0.0.1:{PORT}", flush=True)
    http.server.HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
