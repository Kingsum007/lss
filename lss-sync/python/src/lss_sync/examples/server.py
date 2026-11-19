#!/usr/bin/env python3
"""Loopback-only example endpoint. This is a research demo, not production hosting."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from urllib.parse import unquote, urlsplit

ROOT = None
from lss_sync.backend import BatchError, MAX_BODY, ReceiptStore

TOKEN = "local-demo-only"
NAMESPACE = "demo"
MIME = {".js": "text/javascript", ".html": "text/html", ".css": "text/css", ".svg": "image/svg+xml", ".json": "application/json"}


class ExampleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store):
        self.store = store
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LSS-Example"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        pass  # Credentials and record contents do not enter console logs.

    def send_content(self, status, content, content_type="application/json", retry_after=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") or content_type == "application/json" else ""))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(content)

    def send_json(self, status, value, **kwargs):
        self.send_content(status, json.dumps(value, separators=(",", ":")).encode("utf-8"), **kwargs)

    def authorized(self):
        if hmac.compare_digest(self.headers.get("Authorization", "").encode("utf-8"), ("Bearer " + TOKEN).encode("utf-8")):
            return True
        self.send_json(401, {"error": "UNAUTHORIZED"})
        return False

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            path = urlsplit(self.path).path
            if path == "/api/health":
                self.send_json(200, {"status": "ok"})
                return
            if path == "/api/config":
                self.send_json(200, {"demo": True})
                return
            if path == "/api/stats":
                if self.authorized():
                    self.send_json(200, self.server.store.stats(namespace=NAMESPACE))
                return
            if path.startswith("/api/"):
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            if ROOT is None:
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            decoded = unquote(path, errors="strict")
            if "\\" in decoded or "\x00" in decoded or any(part == ".." for part in decoded.split("/")):
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            if decoded.startswith("/src/"):
                base, relative = ROOT / "src", decoded.removeprefix("/src/")
            else:
                base, relative = ROOT / "examples" / "browser", decoded.lstrip("/") or "index.html"
            base = base.resolve()
            target = (base / relative).resolve()
            if not target.is_relative_to(base) or not target.is_file() or target.suffix not in MIME:
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            self.send_content(200, target.read_bytes(), MIME[target.suffix])
        except (ValueError, OSError):
            self.send_json(400, {"error": "BAD_REQUEST"})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/sync":
            self.send_json(404, {"error": "NOT_FOUND"})
            return
        if not self.authorized():
            return
        length = self.headers.get("Content-Length", "")
        if self.headers.get("Transfer-Encoding") or not length.isdecimal():
            self.send_json(400, {"error": "CONTENT_LENGTH_REQUIRED"})
            return
        if int(length) > MAX_BODY:
            self.send_json(413, {"error": "BODY_TOO_LARGE"})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "JSON_REQUIRED"})
            return
        try:
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                self.send_json(400, {"error": "INCOMPLETE_BODY"})
                return
            result = self.server.store.apply_batch(raw, namespace=NAMESPACE)
            self.send_json(200, result)
        except BatchError as error:
            self.send_json(413 if error.code == "BODY_TOO_LARGE" else 400, {"error": error.code})
        except sqlite3.Error:
            self.send_json(503, {"error": "STORAGE_UNAVAILABLE"}, retry_after=1)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True


def main(browser_root=None):
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=["127.0.0.1", "localhost"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--db", type=Path, default=Path("data") / "example-server.sqlite3")
    parser.add_argument("--browser-root", type=Path, default=browser_root, help="SDK directory containing src/ and examples/browser/")
    args = parser.parse_args()
    ROOT = args.browser_root.resolve() if args.browser_root else None
    server = ExampleServer((args.host, args.port), ReceiptStore(args.db))
    print("LSS local research example. Use synthetic records.", flush=True)
    print(f"Open http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
