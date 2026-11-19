from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "src"))
from lss_sync import SyncClient, TransportResponse
from lss_sync.backend import ReceiptStore
from lss_sync.client import MAX_RESPONSE, _http_transport
from lss_sync.crypto import encrypt_record
from lss_sync.protocol import encode_batch, make_operation

PASSPHRASE = "example test passphrase 42"


def response_for(body):
    operations = json.loads(body)["operations"]
    return TransportResponse(200, json.dumps({"receipts": [
        {"id": item["id"], "digest": item["digest"], "status": "COMMITTED"}
        for item in operations
    ], "errors": []}).encode())


@contextmanager
def running_server(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "client.sqlite3"
        self.backend = ReceiptStore(Path(self.temp.name) / "server.sqlite3")
        self.requests = []
        self.client = SyncClient(self.path, token="private-access-token", transport=self.transport, random=lambda: 0)
        self.addCleanup(self.client.close)
        self.client.setup(PASSPHRASE)

    def transport(self, body, headers, timeout):
        self.requests.append((body, headers, timeout))
        return TransportResponse(200, json.dumps(self.backend.apply_batch(body, namespace="account-a")).encode())

    def queue_rows(self):
        with self.client.store.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM outbox ORDER BY seq")]

    def counts(self):
        with self.client.store.connect() as db:
            return {name: db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                    for name in ("records", "outbox", "nonces")}

    def restart(self):
        self.client.close()
        self.client = SyncClient(self.path, token="private-access-token", transport=self.transport, random=lambda: 0)
        self.addCleanup(self.client.close)
        self.assertEqual(self.client.phase, "LOCKED")
        self.client.unlock(PASSPHRASE)

    def test_save_is_encrypted_and_metadata_snapshot_does_not_leak(self):
        payload = {"secret": "TOP_SECRET_INSPECTION_8731", "passed": True, "quantity": "12.50"}
        saved = self.client.save(payload)
        self.assertGreaterEqual(saved["save_ms"], 0)
        self.assertEqual(self.counts(), {"records": 1, "outbox": 1, "nonces": 2})
        record = self.client.store.get_record(saved["id"])
        self.assertIsInstance(record["ciphertext"], bytes)
        self.assertNotIn(b"TOP_SECRET", record["ciphertext"])
        self.assertNotIn("payload", self.client.snapshot()["records"][0])
        self.assertEqual(self.client.snapshot(include_payloads=True)["records"][0]["payload"], payload)
        for filename in self.path.parent.glob("client.sqlite3*"):
            raw = filename.read_bytes()
            for private in (b"TOP_SECRET_INSPECTION_8731", PASSPHRASE.encode(), b"private-access-token", self.client._key):
                self.assertNotIn(private, raw, filename.name)
        self.client.lock()
        self.assertNotIn("payload", self.client.snapshot(include_payloads=True)["records"][0])
        self.assertFalse(self.client.unlocked)

    def test_restart_wrong_passphrase_and_successful_unlock(self):
        self.client.save({"value": "retained"})
        self.client.close()
        self.client = SyncClient(self.path, transport=self.transport, token="token")
        self.addCleanup(self.client.close)
        self.assertTrue(self.client.configured)
        self.assertFalse(self.client.unlocked)
        with self.assertRaisesRegex(ValueError, "incorrect passphrase"):
            self.client.unlock("a different bad passphrase")
        self.assertFalse(self.client.unlocked)
        self.assertEqual(self.client.phase, "LOCKED")
        self.client.unlock(PASSPHRASE)
        self.assertEqual(self.client.snapshot(include_payloads=True)["records"][0]["payload"], {"value": "retained"})

    def test_locked_save_and_sync_never_send(self):
        self.client.save(None)
        self.client.lock()
        with self.assertRaisesRegex(RuntimeError, "Unlock"):
            self.client.save({"value": 1})
        self.assertEqual(self.client.sync_once()["phase"], "LOCKED")
        self.assertEqual(self.requests, [])
        self.assertEqual(self.queue_rows()[0]["state"], "PENDING")

    def test_setup_cannot_replace_existing_vault(self):
        self.client.save({"value": "original"})
        config = self.client.store.get_config()
        with self.assertRaises(sqlite3.IntegrityError):
            self.client.setup("another valid passphrase")
        self.assertEqual(self.client.store.get_config(), config)
        self.assertEqual(self.client.snapshot(include_payloads=True)["records"][0]["payload"], {"value": "original"})

    def test_invalid_payload_or_validator_does_not_write(self):
        for payload in ({"float": 1.25}, {"value": "x" * 3000}, {"value": 9007199254740992}):
            with self.subTest(payload_type=next(iter(payload))), self.assertRaises(ValueError):
                self.client.save(payload)
        self.client.validator = lambda value: False
        with self.assertRaisesRegex(ValueError, "validation"):
            self.client.save({"valid": True})
        self.assertEqual(self.counts(), {"records": 0, "outbox": 0, "nonces": 1})

    def test_ciphertext_and_aad_tampering_are_blocked_locally(self):
        mutations = [
            ("ciphertext", b"corrupted authenticated ciphertext"),
            ("schema", 2),
            ("key_version", "unknown-key-version"),
            ("iv", "AAAAAAAAAAAAAAAA"),
        ]
        for field, value in mutations:
            saved = self.client.save({"field": field})
            with self.client.store.connect() as db:
                db.execute("UPDATE records SET " + field + "=? WHERE id=?", (value, saved["id"]))
        state = self.client.sync_once()
        self.assertEqual(state["counts"]["BLOCKED"], 4)
        self.assertTrue(all(row["error"] == "LOCAL_INTEGRITY_ERROR" for row in self.queue_rows()))
        self.assertEqual(self.requests, [])

    def test_local_save_failure_rolls_back_nonce_record_and_queue(self):
        with self.client.store.connect() as db:
            db.execute("CREATE TRIGGER fail_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.client.save({"value": "must not be partially saved"})
        self.assertEqual(self.counts(), {"records": 0, "outbox": 0, "nonces": 1})

    def test_iv_collision_retries_without_partial_rows(self):
        collision = {"iv": self.client.config["checkIv"], "ciphertext": b"not persisted"}
        with patch("lss_sync.client.encrypt_record", return_value=collision) as mocked:
            with self.assertRaises(sqlite3.IntegrityError):
                self.client.save({"value": "still collision"})
            self.assertEqual(mocked.call_count, 4)
        self.assertEqual(self.counts(), {"records": 0, "outbox": 0, "nonces": 1})
        calls = 0

        def collide_once(*args):
            nonlocal calls
            calls += 1
            return collision if calls == 1 else encrypt_record(*args)

        with patch("lss_sync.client.encrypt_record", side_effect=collide_once):
            saved = self.client.save({"value": "eventually saved"})
        self.assertEqual(calls, 2)
        self.assertEqual(self.counts(), {"records": 1, "outbox": 1, "nonces": 2})
        self.assertEqual(self.client.snapshot(include_payloads=True)["records"][0]["id"], saved["id"])

    def test_successful_receipt_acknowledges_original_id_and_plaintext_wire(self):
        saved = self.client.save({"generic": [True, False, None, "", "سلام", -9007199254740991]})
        state = self.client.sync_once()
        self.assertEqual(state["counts"]["ACKNOWLEDGED"], 1)
        self.assertEqual(self.queue_rows()[0]["id"], saved["id"])
        self.assertIsNotNone(self.queue_rows()[0]["acknowledged_at"])
        body, headers, timeout = self.requests[0]
        self.assertIn("سلام", body.decode())
        self.assertEqual(headers["Authorization"], "Bearer private-access-token")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(timeout, 30)
        self.assertEqual(state["metrics"]["request_bytes"], len(body))
        self.assertEqual(self.backend.stats(namespace="account-a"), {"entries": 1, "receipts": 1})

    def test_restart_recovers_inflight_and_reuses_identity(self):
        saved = self.client.save({"value": "interrupted before response"})
        self.client.store.transition([saved["id"]], lambda row: {**row, "state": "IN_FLIGHT"})
        self.restart()
        self.assertEqual(self.client.sync_once()["counts"]["ACKNOWLEDGED"], 1)
        self.assertEqual(json.loads(self.requests[0][0])["operations"][0]["id"], saved["id"])

    def test_lost_response_after_backend_commit_replays_one_entry(self):
        saved = self.client.save({"value": "committed before disconnect"})

        def lose_response(body, headers, timeout):
            self.transport(body, headers, timeout)
            raise ConnectionResetError("response lost")

        self.client.transport = lose_response
        self.assertEqual(self.client.sync_once()["counts"]["PENDING"], 1)
        self.assertEqual(self.backend.stats(namespace="account-a"), {"entries": 1, "receipts": 1})
        self.restart()
        self.assertEqual(self.client.sync_once()["counts"]["ACKNOWLEDGED"], 1)
        self.assertEqual(self.requests[0][0], self.requests[1][0])
        self.assertEqual(self.queue_rows()[0]["id"], saved["id"])
        self.assertEqual(self.backend.stats(namespace="account-a"), {"entries": 1, "receipts": 1})

    def test_acknowledgment_commit_failure_remains_recoverable(self):
        self.client.save({"value": "server confirmed but local commit fails"})
        with self.client.store.connect() as db:
            db.execute("CREATE TRIGGER fail_ack BEFORE UPDATE ON outbox WHEN NEW.state='ACKNOWLEDGED' BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.client.sync_once()
        self.assertEqual(self.client.phase, "STORAGE_ERROR")
        self.assertEqual(self.queue_rows()[0]["state"], "IN_FLIGHT")
        self.assertEqual(self.backend.stats(namespace="account-a")["entries"], 1)
        with self.client.store.connect() as db:
            db.execute("DROP TRIGGER fail_ack")
        self.restart()
        self.assertEqual(self.client.sync_once()["counts"]["ACKNOWLEDGED"], 1)
        self.assertEqual(self.requests[0][0], self.requests[1][0])
        self.assertEqual(self.backend.stats(namespace="account-a"), {"entries": 1, "receipts": 1})

    def test_invalid_receipts_never_acknowledge(self):
        self.client.save({"value": "receipt validation"})
        variants = [
            lambda r: {**r, "digest": "f" * 64},
            lambda r: {**r, "id": "00000000-0000-0000-0000-000000000000"},
            lambda r: {**r, "id": {}},
            lambda r: {**r, "status": "ACCEPTED"},
            lambda r: {"id": r["id"], "status": "COMMITTED"},
        ]
        for mutate in variants:
            def invalid(body, headers, timeout):
                reply = json.loads(response_for(body).body)
                reply["receipts"][0] = mutate(reply["receipts"][0])
                return TransportResponse(200, json.dumps(reply).encode())
            self.client.transport = invalid
            state = self.client.sync_once()
            self.assertEqual(state["counts"]["PENDING"], 1)
            self.assertEqual(state["counts"]["ACKNOWLEDGED"], 0)
        self.assertEqual(self.queue_rows()[0]["retries"], len(variants))

    def test_malformed_oversized_and_nonbyte_replies_remain_pending(self):
        self.client.save(False)
        replies = [b"not json", b"[]", b'{"receipts":[]}', b"x" * (MAX_RESPONSE + 1), "not bytes"]
        for raw in replies:
            with self.subTest(kind=type(raw).__name__, size=len(raw)):
                self.client.transport = lambda *args: TransportResponse(200, raw)
                self.assertEqual(self.client.sync_once()["counts"]["PENDING"], 1)

    def test_partial_receipts_leave_only_unconfirmed_item_pending(self):
        first = self.client.save({"value": "accepted"})
        second = self.client.save({"value": "no receipt"})

        def partial(body, headers, timeout):
            reply = json.loads(response_for(body).body)
            reply["receipts"] = reply["receipts"][:1]
            return TransportResponse(200, json.dumps(reply).encode())

        self.client.transport = partial
        counts = self.client.sync_once()["counts"]
        self.assertEqual(counts["ACKNOWLEDGED"], 1)
        self.assertEqual(counts["PENDING"], 1)
        self.assertEqual([(r["id"], r["state"]) for r in self.queue_rows()], [(first["id"], "ACKNOWLEDGED"), (second["id"], "PENDING")])

    def test_permanent_errors_block_only_explicit_recognized_rejections(self):
        first = self.client.save({"value": 1})
        second = self.client.save({"value": 2})
        reply = {"receipts": [], "errors": [
            {"id": first["id"], "code": "VALIDATION_ERROR", "permanent": True},
            {"id": second["id"], "code": "UNKNOWN", "permanent": True},
        ]}
        self.client.transport = lambda *args: TransportResponse(200, json.dumps(reply).encode())
        counts = self.client.sync_once()["counts"]
        self.assertEqual(counts["BLOCKED"], 1)
        self.assertEqual(counts["PENDING"], 1)
        self.assertEqual(self.queue_rows()[0]["error"], "VALIDATION_ERROR")

    def test_auth_failure_pauses_until_new_token(self):
        self.client.save("value")
        self.client.transport = lambda *args: TransportResponse(401, b"{}")
        self.assertEqual(self.client.sync_once()["phase"], "AUTH_REQUIRED")
        attempts = self.client.metrics["attempts"]
        self.client.sync_once()
        self.assertEqual(self.client.metrics["attempts"], attempts)
        self.client.set_token("refreshed-token")
        self.client.transport = self.transport
        self.assertEqual(self.client.sync_once()["counts"]["ACKNOWLEDGED"], 1)
        self.assertEqual(self.requests[-1][1]["Authorization"], "Bearer refreshed-token")

    def test_missing_configuration_or_token_preserves_queue(self):
        self.client.save(True)
        self.client.set_token("")
        self.assertEqual(self.client.sync_once()["phase"], "AUTH_REQUIRED")
        self.client.set_token("token")
        self.client.transport = None
        self.assertEqual(self.client.sync_once()["phase"], "CONFIG_REQUIRED")
        self.assertEqual(self.queue_rows()[0]["state"], "PENDING")
        self.assertEqual(self.requests, [])

    def test_retry_after_persists_and_force_cannot_bypass_gate(self):
        self.client.save({"value": "rate limited"})
        self.client.transport = lambda *args: TransportResponse(429, b"{}", {"rEtRy-AfTeR": "120"})
        self.client.sync_once()
        gate = self.client.store.get_config("retryGate")
        self.assertGreater(gate["until"], time.time() * 1000 + 110000)
        self.restart()
        self.assertEqual(self.client.sync_once(force=True)["phase"], "WAITING")
        self.assertEqual(self.requests, [])
        self.assertEqual(self.client.metrics["attempts"], 0)

    def test_sender_file_lock_excludes_second_client(self):
        self.client.save({"value": "single sender"})
        with self.client.store.sender_lock() as acquired:
            self.assertTrue(acquired)
            self.assertEqual(self.client.sync_once()["counts"]["PENDING"], 1)
            self.assertEqual(self.requests, [])
        self.assertEqual(self.client.sync_once()["counts"]["ACKNOWLEDGED"], 1)

    def test_worker_starts_once_stops_and_can_restart(self):
        completed = threading.Event()

        def notify(body, headers, timeout):
            result = self.transport(body, headers, timeout)
            completed.set()
            return result

        self.client.transport = notify
        self.client.save({"value": "background"})
        self.client.start()
        worker = self.client._thread
        self.addCleanup(lambda: worker.join(timeout=5))
        self.client.start()
        self.assertIs(self.client._thread, worker)
        self.assertTrue(completed.wait(5))
        self.client.stop()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.client.snapshot()["counts"]["ACKNOWLEDGED"], 1)
        self.client.start()
        second = self.client._thread
        self.assertIsNot(second, worker)
        self.client.stop()
        second.join(timeout=5)
        self.assertFalse(second.is_alive())

    def test_lock_during_dispatch_prevents_later_dispatch(self):
        self.client.save({"value": "already dispatched"})

        def lock_before_reply(body, headers, timeout):
            self.client.lock()
            return self.transport(body, headers, timeout)

        self.client.transport = lock_before_reply
        state = self.client.sync_once()
        self.assertEqual(state["phase"], "LOCKED")
        self.assertEqual(state["counts"]["ACKNOWLEDGED"], 1)
        self.client.sync_once()
        self.assertEqual(len(self.requests), 1)

    def test_closed_client_rejects_new_work(self):
        self.client.close()
        for action in (lambda: self.client.save(None), self.client.start, self.client.sync_once,
                       lambda: self.client.setup(PASSPHRASE), lambda: self.client.unlock(PASSPHRASE)):
            with self.assertRaisesRegex(RuntimeError, "closed"):
                action()


class HTTPTransportTests(unittest.TestCase):
    def test_endpoint_security_and_timeout_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queue.sqlite3"
            for endpoint in ("http://example.com/api", "http://localhost/api", "ftp://localhost/api", "https://user:pass@example.com/api", "https://example.com/api#fragment"):
                with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                    SyncClient(path, endpoint=endpoint)
            for timeout in (0, -1, float("inf"), float("nan")):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    SyncClient(path, timeout=timeout)
            with SyncClient(path, endpoint="http://127.0.0.1/api", allow_insecure_localhost=True) as client:
                self.assertEqual(client.phase, "SETUP")

    def test_default_transport_reads_actual_example_connection_close_reply(self):
        spec = importlib.util.spec_from_file_location("lss_client_example", ROOT / "examples" / "server.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            backend = ReceiptStore(Path(directory) / "server.sqlite3")
            with running_server(module.ExampleServer(("127.0.0.1", 0), backend)) as server:
                endpoint = f"http://127.0.0.1:{server.server_port}/api/sync"
                with SyncClient(Path(directory) / "client.sqlite3", endpoint=endpoint, token=module.TOKEN,
                                allow_insecure_localhost=True, timeout=5) as client:
                    client.setup(PASSPHRASE)
                    client.save({"value": "actual HTTP exchange"})
                    state = client.sync_once()
                    self.assertEqual(state["counts"]["ACKNOWLEDGED"], 1)
                    self.assertGreater(state["metrics"]["response_bytes"], 0)
                    self.assertEqual(backend.stats(namespace=module.NAMESPACE), {"entries": 1, "receipts": 1})

    def test_default_transport_bounds_response_and_total_read_deadline(self):
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    if self.path == "/oversized":
                        self.wfile.write(b"x" * (MAX_RESPONSE + 1))
                    else:
                        for _ in range(10):
                            self.wfile.write(b"x")
                            self.wfile.flush()
                            time.sleep(.06)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        with running_server(server):
            base = f"http://127.0.0.1:{server.server_port}"
            with self.assertRaisesRegex(ValueError, "64 KiB"):
                _http_transport(base + "/oversized", b"{}", {}, 3)
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                _http_transport(base + "/slow", b"{}", {}, .18)
            self.assertLess(time.monotonic() - started, 1.5)


if __name__ == "__main__":
    unittest.main()
