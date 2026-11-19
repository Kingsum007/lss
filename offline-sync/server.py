#!/usr/bin/env python3
"""LSS reference server: bounded requests and transactional SQLite receipts.

Development: python server.py --demo
TLS: set LSS_API_TOKEN, then python server.py --cert cert.pem --key key.pem
Only the explicitly selected, loopback-only demo permits plaintext HTTP.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import socket
import sqlite3
import ssl
from typing import Callable
from urllib.parse import unquote, urlsplit
import uuid


MAX_BODY = 16 * 1024
DEMO_TOKEN = "local-demo-only"
ROOT = Path(__file__).resolve().parent
UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PAYLOAD_FIELDS = {"siteCode", "occurredAt", "activity", "quantity", "unit"}
MIME = {".js": "text/javascript", ".mjs": "text/javascript", ".svg": "image/svg+xml",
        ".webmanifest": "application/manifest+json", ".css": "text/css", ".html": "text/html"}


class OperationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class DropResponse(Exception):
    """Test-only fault raised by the constructor hook after a committed operation."""


def reject_constant(value: str):
    raise ValueError("Non-finite JSON number")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def decode_json(raw: bytes | str):
    return json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_pairs)


def valid_text(value, minimum: int, maximum: int) -> bool:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        return False
    if minimum and not value.strip():
        return False
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        return False
    return True


def validate_operation(operation: dict) -> tuple[str, int, str, str]:
    if not isinstance(operation, dict) or set(operation) != {"id", "schema", "payload", "digest"}:
        raise OperationError("INVALID_OPERATION")
    operation_id = operation["id"]
    if not isinstance(operation_id, str) or not UUID_PATTERN.fullmatch(operation_id):
        raise OperationError("INVALID_ID")
    try:
        uuid.UUID(operation_id)
    except ValueError:
        raise OperationError("INVALID_ID") from None
    if type(operation["schema"]) is not int or operation["schema"] != 1:
        raise OperationError("INVALID_SCHEMA")
    payload, digest = operation["payload"], operation["digest"]
    if not isinstance(payload, str) or not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
        raise OperationError("INVALID_OPERATION")
    try:
        encoded = payload.encode("utf-8", errors="strict")
    except UnicodeError:
        raise OperationError("INVALID_PAYLOAD") from None
    if not hmac.compare_digest(hashlib.sha256(encoded).hexdigest(), digest):
        raise OperationError("BAD_DIGEST")
    try:
        record = decode_json(payload)
    except (ValueError, TypeError, RecursionError):
        raise OperationError("INVALID_PAYLOAD") from None
    if not isinstance(record, dict) or not {"siteCode", "occurredAt", "activity"} <= set(record) <= PAYLOAD_FIELDS:
        raise OperationError("INVALID_PAYLOAD")
    if not valid_text(record["siteCode"], 1, 32) or not valid_text(record["activity"], 1, 1000):
        raise OperationError("INVALID_PAYLOAD")
    if not valid_text(record["occurredAt"], 1, 40):
        raise OperationError("INVALID_PAYLOAD")
    try:
        timestamp = datetime.fromisoformat(record["occurredAt"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Missing time zone")
    except ValueError:
        raise OperationError("INVALID_PAYLOAD") from None
    for field in ("quantity", "unit"):
        if field in record and not valid_text(record[field], 0, 32):
            raise OperationError("INVALID_PAYLOAD")
    return operation_id, operation["schema"], payload, digest


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    payload_schema INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    id TEXT PRIMARY KEY REFERENCES entries(id),
                    digest TEXT NOT NULL,
                    committed_at TEXT NOT NULL
                );
            """)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def apply(self, operation: dict) -> dict:
        operation_id, schema, payload, digest = validate_operation(operation)
        connection = self.connect()
        try:
            # Serialize competing requests before comparing identity and payload.
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT payload_schema,payload,digest FROM entries WHERE id=?", (operation_id,)
            ).fetchone()
            if existing:
                if existing != (schema, payload, digest):
                    raise OperationError("ID_CONFLICT")
                stored = connection.execute(
                    "SELECT digest,committed_at FROM receipts WHERE id=?", (operation_id,)
                ).fetchone()
                if stored is None:
                    raise sqlite3.DatabaseError("Entry is missing its committed receipt")
                receipt = {"id": operation_id, "digest": stored[0], "status": "COMMITTED", "committedAt": stored[1]}
            else:
                committed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                connection.execute("INSERT INTO entries VALUES (?,?,?,?)", (operation_id, schema, payload, digest))
                connection.execute("INSERT INTO receipts VALUES (?,?,?)", (operation_id, digest, committed_at))
                receipt = {"id": operation_id, "digest": digest, "status": "COMMITTED", "committedAt": committed_at}
            connection.commit()
            return receipt
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def stats(self) -> dict:
        connection = self.connect()
        try:
            return {"entries": connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0],
                    "receipts": connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]}
        finally:
            connection.close()


class SyncHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store: Store, token: str, public_dir: Path | str = ROOT / "public",
                 *, demo: bool = False, after_commit: Callable[[dict], None] | None = None):
        self.store = store
        self.token = token
        self.public_dir = Path(public_dir).resolve()
        self.demo = demo
        self.after_commit = after_commit
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LSS"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # Intentionally omit request URLs, credentials, and payloads from logs.
        return

    def send_bytes(self, status: int, content: bytes, content_type: str = "application/json", *, retry_after: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") or content_type == "application/json" else ""))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if retry_after is not None:
            self.send_header("Retry-After", retry_after)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(content)

    def send_json(self, status: int, value: dict, **kwargs):
        self.send_bytes(status, json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8"), **kwargs)

    def authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.token
        if hmac.compare_digest(header.encode("utf-8"), expected.encode("utf-8")):
            return True
        self.send_json(401, {"error": "UNAUTHORIZED"})
        return False

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            path = urlsplit(self.path).path
            if path == "/api/config":
                self.send_json(200, {"demo": self.server.demo})
                return
            if path == "/api/health":
                self.send_json(200, {"status": "ok"})
                return
            if path == "/api/stats":
                if self.authorized():
                    self.send_json(200, self.server.store.stats())
                return
            if path.startswith("/api/"):
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            decoded = unquote(path, errors="strict")
            if "\\" in decoded or "\x00" in decoded or any(part == ".." for part in decoded.split("/")):
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            relative = decoded.lstrip("/") or "index.html"
            target = (self.server.public_dir / relative).resolve()
            if not target.is_relative_to(self.server.public_dir) or not target.is_file():
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            content_type = MIME.get(target.suffix.lower()) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_bytes(200, target.read_bytes(), content_type)
        except (ValueError, OSError):
            self.send_json(400, {"error": "BAD_REQUEST"})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/sync":
            self.send_json(404, {"error": "NOT_FOUND"})
            return
        if not self.authorized():
            return
        if self.headers.get("Transfer-Encoding"):
            self.send_json(400, {"error": "UNSUPPORTED_TRANSFER_ENCODING"})
            return
        length_header = self.headers.get("Content-Length", "")
        if not length_header.isdecimal():
            self.send_json(411, {"error": "CONTENT_LENGTH_REQUIRED"})
            return
        length = int(length_header)
        if length > MAX_BODY:
            self.send_json(413, {"error": "BODY_TOO_LARGE"})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "JSON_REQUIRED"})
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                self.send_json(400, {"error": "INCOMPLETE_BODY"})
                return
            body = decode_json(raw.decode("utf-8", errors="strict"))
            if not isinstance(body, dict) or set(body) != {"operations"} or not isinstance(body["operations"], list) or not body["operations"]:
                self.send_json(400, {"error": "INVALID_BATCH"})
                return
            receipts, errors = [], []
            for operation in body["operations"]:
                try:
                    receipt = self.server.store.apply(operation)
                except OperationError as error:
                    operation_id = operation.get("id") if isinstance(operation, dict) else None
                    if not isinstance(operation_id, str) or len(operation_id) > 64:
                        operation_id = None
                    errors.append({"id": operation_id, "code": error.code, "permanent": True})
                    continue
                receipts.append(receipt)
                if self.server.after_commit:
                    self.server.after_commit(receipt)
            self.send_json(200, {"receipts": receipts, "errors": errors})
        except DropResponse:
            self.close_connection = True
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        except (ValueError, UnicodeError, RecursionError):
            self.send_json(400, {"error": "INVALID_JSON"})
        except sqlite3.Error:
            # Earlier per-record commits are safe to replay after a batch failure.
            self.send_json(503, {"error": "STORAGE_UNAVAILABLE"}, retry_after="1")
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "lss.sqlite3")
    parser.add_argument("--demo", action="store_true", help="Enable loopback-only HTTP demo with public demonstration credentials")
    parser.add_argument("--cert", type=Path)
    parser.add_argument("--key", type=Path)
    args = parser.parse_args(argv)
    if args.demo and args.host not in {"127.0.0.1", "localhost"}:
        parser.error("--demo must bind to 127.0.0.1 or localhost")
    if bool(args.cert) != bool(args.key):
        parser.error("--cert and --key must be provided together")
    if not args.demo and (not args.cert or not args.key):
        parser.error("Normal mode requires TLS: provide --cert and --key")
    token = DEMO_TOKEN if args.demo else os.environ.get("LSS_API_TOKEN", "")
    if not token or (not args.demo and len(token) < 32):
        parser.error("Set LSS_API_TOKEN to a secret of at least 32 characters")
    server = SyncHTTPServer((args.host, args.port), Store(args.db), token, demo=args.demo)
    scheme = "http"
    if args.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(args.cert), str(args.key))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    if args.demo:
        print("LSS loopback demonstration mode. Use synthetic data only.", flush=True)
    print(f"Open {scheme}://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
