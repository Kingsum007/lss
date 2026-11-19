"""Framework-independent receipt storage for an authenticated LSS endpoint.

The host application authenticates its request, chooses the namespace from that
identity, and passes it as a keyword argument. Never trust a namespace supplied
by the uploading client. This module provides storage, not an account system.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable
import uuid

from .protocol import canonical_payload

MAX_BODY = 16 * 1024
MAX_OPERATION_BODY = 2 * 1024
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class OperationError(ValueError):
    """A permanent rejection of one operation; its ID remains safe to inspect."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class BatchError(ValueError):
    """An invalid batch envelope, rejected before applying any operation."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _unique_pairs(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("Duplicate JSON field")
        values[key] = value
    return values


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant")


def _parse_json(value: str):
    return json.loads(value, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)


def _encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _namespace(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("A nonempty authenticated namespace is required.")
    try:
        if len(value.encode("utf-8")) > 128:
            raise ValueError("Namespace exceeds 128 UTF-8 bytes.")
    except UnicodeError:
        raise ValueError("Namespace must contain valid Unicode.") from None
    return value


def _operation(operation: dict, validator: Callable[[Any], Any] | None) -> tuple[str, int, str, str]:
    if not isinstance(operation, dict) or set(operation) != {"id", "schema", "payload", "digest"}:
        raise OperationError("INVALID_OPERATION")
    operation_id = operation["id"]
    if not isinstance(operation_id, str) or not UUID_RE.fullmatch(operation_id):
        raise OperationError("INVALID_ID")
    try:
        uuid.UUID(operation_id)
    except ValueError:
        raise OperationError("INVALID_ID") from None
    if type(operation["schema"]) is not int or operation["schema"] != 1:
        raise OperationError("INVALID_SCHEMA")
    payload, digest = operation["payload"], operation["digest"]
    if not isinstance(payload, str) or not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        raise OperationError("INVALID_OPERATION")
    try:
        payload_bytes = payload.encode("utf-8")
        if len(_encoded({"operations": [operation]})) > MAX_OPERATION_BODY:
            raise OperationError("OPERATION_TOO_LARGE")
    except (UnicodeError, TypeError):
        raise OperationError("INVALID_PAYLOAD") from None
    if not hmac.compare_digest(hashlib.sha256(payload_bytes).hexdigest(), digest):
        raise OperationError("BAD_DIGEST")
    try:
        parsed = _parse_json(payload)
        if canonical_payload(parsed) != payload:
            raise ValueError("Payload is not canonically encoded")
        if validator is not None and validator(parsed) is False:
            raise ValueError("Application validation rejected the payload")
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise OperationError("INVALID_PAYLOAD") from None
    return operation_id, operation["schema"], payload, digest


class ReceiptStore:
    """Persist one entry and receipt atomically, with namespace-scoped identity.

    Each call opens its own SQLite connection, so a store can be shared between
    request threads. Each operation in a batch commits independently. Retrying
    after a partially completed batch returns the previously committed receipts.
    """

    def __init__(self, path: str | Path, validator: Callable[[Any], Any] | None = None):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.validator = validator
        with closing(self.connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS lss_entries (
                    namespace TEXT NOT NULL,
                    id TEXT NOT NULL,
                    payload_schema INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    PRIMARY KEY (namespace, id)
                );
                CREATE TABLE IF NOT EXISTS lss_receipts (
                    namespace TEXT NOT NULL,
                    id TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    committed_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, id),
                    FOREIGN KEY (namespace, id) REFERENCES lss_entries(namespace, id)
                );
            """)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def apply(self, operation: dict, *, namespace: str) -> dict:
        """Commit an operation or return its identical receipt on safe replay."""
        namespace = _namespace(namespace)
        operation_id, schema, payload, digest = _operation(operation, self.validator)
        with closing(self.connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT payload_schema,payload,digest FROM lss_entries WHERE namespace=? AND id=?",
                    (namespace, operation_id),
                ).fetchone()
                if existing is not None:
                    if existing != (schema, payload, digest):
                        raise OperationError("ID_CONFLICT")
                    saved = connection.execute(
                        "SELECT digest,committed_at FROM lss_receipts WHERE namespace=? AND id=?",
                        (namespace, operation_id),
                    ).fetchone()
                    if saved is None:
                        raise sqlite3.DatabaseError("Stored entry is missing its receipt")
                    receipt = {"id": operation_id, "digest": saved[0], "status": "COMMITTED", "committedAt": saved[1]}
                else:
                    committed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                    connection.execute("INSERT INTO lss_entries VALUES (?,?,?,?,?)", (namespace, operation_id, schema, payload, digest))
                    connection.execute("INSERT INTO lss_receipts VALUES (?,?,?,?)", (namespace, operation_id, digest, committed_at))
                    receipt = {"id": operation_id, "digest": digest, "status": "COMMITTED", "committedAt": committed_at}
                connection.commit()
                return receipt
            except Exception:
                connection.rollback()
                raise

    def apply_batch(self, body: bytes | str | dict, *, namespace: str) -> dict:
        """Validate the envelope then independently commit its valid operations.

        For HTTP integrations pass the exact request bytes to enforce the actual
        wire size. A dict is supported for in-process adapters and tests.
        """
        namespace = _namespace(namespace)
        try:
            raw = body if isinstance(body, bytes) else body.encode("utf-8") if isinstance(body, str) else _encoded(body)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise BatchError("INVALID_JSON") from None
        if len(raw) > MAX_BODY:
            raise BatchError("BODY_TOO_LARGE")
        try:
            parsed = _parse_json(raw.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError):
            raise BatchError("INVALID_JSON") from None
        if not isinstance(parsed, dict) or set(parsed) != {"operations"} or not isinstance(parsed["operations"], list) or not parsed["operations"]:
            raise BatchError("INVALID_BATCH")
        receipts, errors = [], []
        for operation in parsed["operations"]:
            try:
                receipts.append(self.apply(operation, namespace=namespace))
            except OperationError as error:
                operation_id = operation.get("id") if isinstance(operation, dict) else None
                if not isinstance(operation_id, str) or len(operation_id) > 64:
                    operation_id = None
                errors.append({"id": operation_id, "code": error.code, "permanent": True})
        return {"receipts": receipts, "errors": errors}

    def stats(self, *, namespace: str) -> dict:
        namespace = _namespace(namespace)
        with closing(self.connect()) as connection:
            return {
                "entries": connection.execute("SELECT COUNT(*) FROM lss_entries WHERE namespace=?", (namespace,)).fetchone()[0],
                "receipts": connection.execute("SELECT COUNT(*) FROM lss_receipts WHERE namespace=?", (namespace,)).fetchone()[0],
            }
