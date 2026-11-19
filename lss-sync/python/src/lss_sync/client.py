"""Reusable encrypted offline client with a small, optional background sender."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import http.client
import json
import math
import random as random_module
import sqlite3
import ssl
import threading
import time
from typing import Mapping
from urllib.parse import urlsplit

from .crypto import create_vault, unlock_vault, encrypt_record, decrypt_record
from .policy import BatchPolicy, retry_delay, retry_after
from .protocol import make_operation, encode_batch, parse_payload, digest_payload, MIN_BATCH
from .store import Store

PERMANENT = {"ID_CONFLICT", "INVALID_OPERATION", "INVALID_PAYLOAD", "INVALID_DIGEST", "BAD_DIGEST", "INVALID_ID", "INVALID_SCHEMA", "UNSUPPORTED_SCHEMA", "VALIDATION_ERROR", "OPERATION_TOO_LARGE"}
MAX_RESPONSE = 65536


@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _http_transport(endpoint: str, body: bytes, headers: dict, timeout: float) -> TransportResponse:
    parsed = urlsplit(endpoint)
    constructor = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    kwargs = {"timeout": timeout}
    if parsed.scheme == "https":
        kwargs["context"] = ssl.create_default_context()
    connection = constructor(parsed.hostname, parsed.port, **kwargs)
    deadline = time.monotonic() + timeout
    response = None
    try:
        connection.request("POST", (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""), body=body, headers=headers)
        network_socket = connection.sock
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Synchronization deadline exceeded")
        network_socket.settimeout(remaining)
        response = connection.getresponse()
        chunks, total = [], 0
        while not response.isclosed():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Synchronization deadline exceeded")
            network_socket.settimeout(remaining)
            chunk = response.read1(min(4096, MAX_RESPONSE + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESPONSE:
                raise ValueError("Response exceeds the 64 KiB limit")
            chunks.append(chunk)
        return TransportResponse(response.status, b"".join(chunks), dict(response.getheaders()))
    finally:
        if response is not None:
            response.close()
        connection.close()


class SyncClient:
    """One client per local vault; call start() to opt into background uploads.

    A custom transport receives (body_bytes, headers, timeout_seconds) and returns
    TransportResponse. It must honor its timeout and must not persist plaintext.
    """
    def __init__(self, path, endpoint: str | None = None, token: str = "", policy: str = "adaptive",
                 transport=None, validator=None, random=random_module.random,
                 *, allow_insecure_localhost: bool = False, timeout: float = 30.0):
        if endpoint:
            parsed = urlsplit(endpoint)
            if parsed.username or parsed.password or parsed.fragment or not parsed.hostname:
                raise ValueError("Use an endpoint without embedded credentials or fragments")
            local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            if parsed.scheme != "https" and not (parsed.scheme == "http" and allow_insecure_localhost and local):
                raise ValueError("HTTPS is required; loopback HTTP needs explicit opt-in")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be positive and finite")
        self.endpoint = endpoint
        self.timeout = timeout
        self.transport = transport
        self.validator = validator
        self.random = random
        self.store = Store(path)
        self.config = self.store.get_config()
        self.policy = BatchPolicy(policy)
        self._key = None
        self._epoch = 0
        self._token = str(token)
        self._mutex = threading.RLock()
        self._sync_lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self._closed = False
        self._auth_paused = False
        self._last_attempt = 0.0
        self._next_delay = 30.0
        self.phase = "LOCKED" if self.config else "SETUP"
        self.last_error = ""
        self.metrics = {"attempts": 0, "request_bytes": 0, "response_bytes": 0,
                        "last_duration_ms": 0, "unlock_ms": 0, "last_save_ms": 0}

    @property
    def configured(self) -> bool:
        return bool(self.config)

    @property
    def unlocked(self) -> bool:
        with self._mutex:
            return self._key is not None

    def _check_open(self):
        if self._closed:
            raise RuntimeError("This client is closed")

    def setup(self, passphrase: str) -> None:
        self._check_open()
        with self._mutex:
            self._epoch += 1
            epoch = self._epoch
        started = time.perf_counter()
        key, config = create_vault(passphrase)
        with self._mutex:
            if epoch != self._epoch:
                raise RuntimeError("Vault creation was cancelled")
            self.store.create_vault(config)
            self.config, self._key = config, key
            self.phase, self.last_error = "IDLE", ""
            self.metrics["unlock_ms"] = (time.perf_counter() - started) * 1000
        self._wake.set()

    def unlock(self, passphrase: str) -> None:
        self._check_open()
        with self._mutex:
            if self._key is not None:
                return
            self._epoch += 1
            epoch = self._epoch
        config = self.store.get_config()
        if not config:
            raise ValueError("Create a vault first")
        started = time.perf_counter()
        key = unlock_vault(passphrase, config)
        with self._mutex:
            if epoch != self._epoch:
                raise RuntimeError("Unlock was cancelled")
            self.config, self._key = config, key
            self.policy.set_mode(self.policy.mode)
            self.phase, self.last_error = "IDLE", ""
            self.metrics["unlock_ms"] = (time.perf_counter() - started) * 1000
        self._wake.set()

    def lock(self) -> None:
        with self._mutex:
            self._epoch += 1
            self._key = None
            self.phase = "LOCKED" if self.config else "SETUP"
            self.last_error = ""
        self._wake.set()

    def set_token(self, token: str) -> None:
        with self._mutex:
            self._token = str(token)
            self._auth_paused = False
        self._wake.set()

    def set_policy(self, mode: str) -> None:
        if not self._sync_lock.acquire(blocking=False):
            raise RuntimeError("Wait for the active transfer before changing policy")
        try:
            with self._mutex:
                self.policy.set_mode(mode)
        finally:
            self._sync_lock.release()

    def save(self, payload) -> dict:
        self._check_open()
        started = time.perf_counter()
        with self._mutex:
            if self._key is None:
                raise RuntimeError("Unlock the vault before saving")
            if self.validator is not None and self.validator(payload) is False:
                raise ValueError("Application validation rejected this payload")
            operation = make_operation(payload)
            for attempt in range(4):
                record = {"id": operation["id"], "schema": operation["schema"], "keyVersion": self.config["keyVersion"],
                          "createdAt": _utc_now(), **encrypt_record(self._key, operation["id"], operation["payload"])}
                try:
                    self.store.save(record, len(encode_batch([operation])))
                    break
                except sqlite3.IntegrityError as error:
                    if "nonces" not in str(error) or attempt == 3:
                        raise
            elapsed = (time.perf_counter() - started) * 1000
            self.metrics["last_save_ms"] = elapsed
        self._wake.set()
        return {"id": operation["id"], "save_ms": elapsed}

    def _select(self, key, epoch, force):
        operations, seq, full = [], 0, False
        while self.unlocked:
            with self._mutex:
                if self._epoch != epoch:
                    return [], False
            item = self.store.next_due(seq, float("inf") if force else time.time() * 1000)
            if not item:
                break
            seq = item["seq"]
            try:
                record = self.store.get_record(item["id"])
                if not record or record["keyVersion"] != self.config["keyVersion"]:
                    raise ValueError()
                text = decrypt_record(key, record)
                payload = parse_payload(text)
                if self.validator is not None and self.validator(payload) is False:
                    raise ValueError()
                operation = {"id": record["id"], "schema": record["schema"], "payload": text, "digest": digest_payload(text)}
                if len(encode_batch([operation])) > MIN_BATCH:
                    raise ValueError()
            except Exception:
                self.store.transition([item["id"]], lambda row: {**row, "state": "BLOCKED", "error": "LOCAL_INTEGRITY_ERROR"})
                continue
            if len(encode_batch(operations + [operation])) > self.policy.bytes:
                full = True
                break
            operations.append(operation)
        return operations, full

    def sync_once(self, force: bool = False) -> dict:
        """Attempt one bounded batch; force bypasses jitter but never Retry-After."""
        self._check_open()
        if not self._sync_lock.acquire(blocking=False):
            return self.snapshot()
        try:
            with self.store.sender_lock() as acquired:
                if not acquired:
                    self._next_delay = 1.0
                    return self.snapshot()
                with self._mutex:
                    key, epoch, token = self._key, self._epoch, self._token
                    if key is None:
                        self._next_delay = 30.0
                        return self.snapshot()
                    if self._auth_paused or not token:
                        self.phase, self._auth_paused = "AUTH_REQUIRED", True
                        self._next_delay = 30.0
                        return self.snapshot()
                    if not self.transport and not self.endpoint:
                        self.phase = "CONFIG_REQUIRED"
                        self.last_error = "Configure an HTTPS endpoint or custom transport"
                        self._next_delay = 30.0
                        return self.snapshot()
                self.store.recover()
                now_ms = time.time() * 1000
                gate = self.store.get_config("retryGate")
                if gate and gate["until"] > now_ms:
                    self.phase = "WAITING"
                    self._next_delay = (gate["until"] - now_ms) / 1000
                    return self.snapshot()
                if force and now_ms - self._last_attempt < 1000:
                    self._next_delay = (1000 - now_ms + self._last_attempt) / 1000
                    return self.snapshot()
                operations, full = self._select(key, epoch, force)
                with self._mutex:
                    if self._epoch != epoch or self._key is None:
                        return self.snapshot()
                if not operations:
                    due = self.store.earliest_due()
                    self.phase = "IDLE" if due is None else "WAITING"
                    self._next_delay = 30.0 if due is None else max(.01, (due - time.time() * 1000) / 1000)
                    return self.snapshot()
                ids = [op["id"] for op in operations]
                expected = {op["id"]: op["digest"] for op in operations}
                body = encode_batch(operations)
                self.store.transition(ids, lambda row: {**row, "state": "IN_FLIGHT"})
                with self._mutex:
                    if self._epoch != epoch or self._key is None:
                        self.store.transition(ids, lambda row: {**row, "state": "PENDING"})
                        return self.snapshot()
                    self.phase, self.last_error = "SYNCING", ""
                    self._last_attempt = time.time() * 1000
                    self.metrics["attempts"] += 1
                    self.metrics["request_bytes"] += len(body)
                started = time.monotonic()
                status, reply, gate_until, failed = 0, None, 0, False
                try:
                    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token, "Cache-Control": "no-store"}
                    response = self.transport(body, headers, self.timeout) if self.transport else _http_transport(self.endpoint, body, headers, self.timeout)
                    status = response.status
                    if status in (429, 503):
                        value = next((v for k, v in response.headers.items() if k.lower() == "retry-after"), None)
                        gate_until = retry_after(value)
                    if type(response.body) is not bytes or len(response.body) > MAX_RESPONSE:
                        raise ValueError("Invalid or oversized response body")
                    self.metrics["response_bytes"] += len(response.body)
                    if 200 <= status < 300:
                        reply = json.loads(response.body.decode("utf-8"))
                    else:
                        failed = True
                except Exception:
                    failed = True
                duration_ms = (time.monotonic() - started) * 1000
                self.metrics["last_duration_ms"] = duration_ms
                if gate_until:
                    self.store.put_config({"name": "retryGate", "until": gate_until})
                acknowledged, blocked = set(), {}
                if type(reply) is dict and type(reply.get("receipts")) is list and type(reply.get("errors")) is list:
                    for receipt in reply["receipts"]:
                        if type(receipt) is dict and type(receipt.get("id")) is str and receipt.get("status") == "COMMITTED" and receipt["id"] in expected and receipt.get("digest") == expected[receipt["id"]]:
                            acknowledged.add(receipt["id"])
                    for error in reply["errors"]:
                        if type(error) is dict and type(error.get("id")) is str and error["id"] in expected and error.get("permanent") is True and type(error.get("code")) is str and error["code"] in PERMANENT and error["id"] not in acknowledged:
                            blocked[error["id"]] = error["code"]
                if 400 <= status < 500 and status not in (401, 403, 408, 429):
                    blocked.update({operation_id: f"HTTP_{status}" for operation_id in ids})
                remaining = [operation_id for operation_id in ids if operation_id not in acknowledged and operation_id not in blocked]
                earliest = float("inf")

                def finish(row):
                    nonlocal earliest
                    if row["id"] in acknowledged:
                        return {**row, "state": "ACKNOWLEDGED", "error": None, "acknowledged_at": _utc_now()}
                    if row["id"] in blocked:
                        return {**row, "state": "BLOCKED", "error": blocked[row["id"]]}
                    retries = row["retries"] + 1
                    due = max(gate_until, time.time() * 1000 + retry_delay(retries, self.random))
                    earliest = min(earliest, due)
                    return {**row, "state": "PENDING", "retries": retries, "due_time": due}

                self.store.transition(ids, finish)
                transient_failure = failed or bool(remaining)
                with self._mutex:
                    self.policy.observe(transient_failure=transient_failure, duration_ms=duration_ms, full=full, all_acknowledged=len(acknowledged) == len(ids))
                    if self._epoch == epoch and self._key is not None:
                        if status in (401, 403) and self._token == token:
                            self.phase, self._auth_paused = "AUTH_REQUIRED", True
                            self.last_error = "Server authentication failed; provide a valid token to resume"
                        elif transient_failure:
                            self.phase = "WAITING"
                            self.last_error = "Transfer not fully confirmed; saved entries remain queued"
                        else:
                            self.phase, self.last_error = "IDLE", ""
                self._next_delay = max(.01, (earliest - time.time() * 1000) / 1000) if remaining else .01
                return self.snapshot()
        except (sqlite3.Error, OSError, RuntimeError):
            with self._mutex:
                if self._key is not None:
                    self.phase = "STORAGE_ERROR"
                    self.last_error = "Local state could not be committed; recovery will replay unfinished IDs"
            self._next_delay = 5.0
            raise
        finally:
            self._sync_lock.release()

    def snapshot(self, include_payloads: bool = False) -> dict:
        with self._mutex:
            summary = self.store.summary()
            records = []
            for row in summary["records"]:
                item = {"id": row["id"], "state": row["state"], "created_at": row["created_at"], "error": row["error"]}
                if include_payloads and self._key is not None:
                    try:
                        item["payload"] = parse_payload(decrypt_record(self._key, self.store.get_record(row["id"])))
                    except Exception:
                        pass
                records.append(item)
            return {"configured": self.configured, "unlocked": self._key is not None, "counts": summary["counts"],
                    "batch_bytes": self.policy.bytes, "phase": self.phase, "last_error": self.last_error,
                    "metrics": dict(self.metrics), "records": records}

    def start(self) -> None:
        self._check_open()
        with self._mutex:
            if self._thread and self._thread.is_alive():
                self._wake.set()
                return
            self._stop.clear()
            self._wake.set()
            self._thread = threading.Thread(target=self._run, name="lss-sync", daemon=True)
            self._thread.start()

    def _run(self):
        force = True
        while not self._stop.is_set():
            self._wake.clear()
            try:
                self.sync_once(force=force)
            except Exception:
                # Errors are exposed through phase/last_error; never log payloads.
                self._next_delay = 5.0
            force = self._wake.wait(min(max(self._next_delay, .01), 30.0))

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def close(self) -> None:
        self.stop()
        self.lock()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
