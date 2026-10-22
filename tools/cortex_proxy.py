#!/usr/bin/env python3
"""Cortex LLMHoster dashboard proxy: 0.0.0.0:8624 -> 127.0.0.1:8625.

Cortex binds loopback only, and its dashboard sets ``X-Frame-Options`` /
``Content-Security-Policy frame-ancestors``, which an embedding host (MyGPT's
WebUI preview) would otherwise refuse to display. This proxy listens on all
interfaces and strips exactly those two response headers — it changes nothing
else about the traffic.

Cortex LLMHoster itself (https://github.com/codero-sus/Cortex_LLMHoster) is
used unmodified under its personal-use license; this proxy is MyGPT-side glue.

    python tools/cortex_proxy.py            # listens on 8624
    PORT=9000 python tools/cortex_proxy.py  # different listen port

License: MyGPT Personal-Use License (see LICENSE). All credit to codero-sus —
https://github.com/codero-sus
"""

from __future__ import annotations

import http.server
import os
import socketserver
import urllib.request

UPSTREAM = os.environ.get("CORTEX_UPSTREAM", "http://127.0.0.1:8625")
PORT = int(os.environ.get("PORT", "8624"))
STRIP = {"x-frame-options", "content-security-policy"}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(UPSTREAM + self.path, data=body,
                                     method=method)
        for key, value in self.headers.items():
            if key.lower() not in ("host", "content-length", "connection"):
                req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                for key, value in resp.headers.items():
                    if key.lower() in STRIP:
                        continue
                    if key.lower() in ("transfer-encoding", "connection",
                                       "content-length"):
                        continue
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except Exception as exc:                                # noqa: BLE001
            print(f"proxy error: {exc}", flush=True)
            try:
                self.send_response(502)
                self.send_header("Content-Length", "0")
                self.end_headers()
            except Exception:                                   # noqa: BLE001
                pass

    def do_GET(self):
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")

    def do_PUT(self):
        self._proxy("PUT")

    def do_DELETE(self):
        self._proxy("DELETE")

    def log_message(self, *args):
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    print(f"cortex proxy on {PORT} -> {UPSTREAM}", flush=True)
    Server(("0.0.0.0", PORT), Handler).serve_forever()
