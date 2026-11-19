"""LSS v1 interoperable JSON subset and byte-exact operation envelope."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

MIN_BATCH = 2048
MAX_BATCH = 16384
SCHEMA = 1
MAX_SAFE_INTEGER = 9007199254740991
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _validate(value: Any, active: set[int], depth: int) -> None:
    if depth > 32:
        raise ValueError("Payload nesting exceeds 32 levels")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("Integer exceeds the interoperable safe range")
        return
    if type(value) is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise ValueError("Lone Unicode surrogates are not supported") from None
        return
    if type(value) not in (dict, list):
        raise ValueError("Use JSON null, boolean, string, safe integer, array, or object; encode decimals as strings")
    identity = id(value)
    if identity in active:
        raise ValueError("Cyclic payloads are not supported")
    active.add(identity)
    try:
        if type(value) is dict:
            for key, item in value.items():
                if type(key) is not str:
                    raise ValueError("Object keys must be strings")
                _validate(key, active, depth)
                _validate(item, active, depth + 1)
        else:
            for item in value:
                _validate(item, active, depth + 1)
    finally:
        active.remove(identity)


def canonical_payload(value: Any) -> str:
    """Encode a validated payload with keys ordered by Unicode code point."""
    _validate(value, set(), 0)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def digest_payload(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def encode_batch(operations: list[dict]) -> bytes:
    return json.dumps({"operations": operations}, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def make_operation(payload: Any, operation_id: str | None = None) -> dict:
    text = canonical_payload(payload)
    operation = {"id": operation_id or str(uuid.uuid4()), "schema": SCHEMA, "payload": text, "digest": digest_payload(text)}
    validate_operation(operation)
    if len(encode_batch([operation])) > MIN_BATCH:
        raise ValueError("A complete single-operation request must fit within 2048 bytes")
    return operation


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate object key")
        result[key] = value
    return result


def parse_payload(text: str) -> Any:
    value = json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
    if canonical_payload(value) != text:
        raise ValueError("Payload is not in the LSS canonical representation")
    return value


def validate_operation(operation: dict) -> dict:
    if type(operation) is not dict or set(operation) != {"id", "schema", "payload", "digest"}:
        raise ValueError("Invalid operation envelope")
    if not isinstance(operation["id"], str) or not UUID_RE.fullmatch(operation["id"]):
        raise ValueError("Invalid operation ID")
    if type(operation["schema"]) is not int or operation["schema"] != SCHEMA:
        raise ValueError("Unsupported schema")
    if not isinstance(operation["payload"], str) or not isinstance(operation["digest"], str) or not DIGEST_RE.fullmatch(operation["digest"]):
        raise ValueError("Invalid operation payload or digest")
    parse_payload(operation["payload"])
    if digest_payload(operation["payload"]) != operation["digest"]:
        raise ValueError("Payload digest mismatch")
    return operation
