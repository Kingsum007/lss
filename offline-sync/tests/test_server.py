"""Backend contract, transaction, and interrupted-response tests; stdlib only."""

import concurrent.futures
from contextlib import closing, redirect_stderr
import hashlib
import http.client
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import DEMO_TOKEN, DropResponse, OperationError, Store, SyncHTTPServer, main


def operation(**changes):
    payload = json.dumps({"siteCode": "NBCC-01", "occurredAt": "2026-11-16T08:00:00.000Z",
                          "activity": "Synthetic site inspection"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    item = {"id": str(uuid.uuid4()), "schema": 1, "payload": payload,
            "digest": hashlib.sha256(payload.encode()).hexdigest()}
    item.update(changes)
    return item


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "server.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_replay_returns_exact_receipt_and_one_entry(self):
        op = operation()
        original = self.store.apply(op)
        self.assertEqual(original, self.store.apply(op))
        self.assertEqual({"entries": 1, "receipts": 1}, self.store.stats())
        self.assertEqual(original, Store(self.path).apply(op))

    def test_conflicting_id_does_not_replace_original(self):
        first = operation()
        self.store.apply(first)
        conflict = operation(id=first["id"], payload=first["payload"].replace("inspection", "delivery"))
        conflict["digest"] = hashlib.sha256(conflict["payload"].encode()).hexdigest()
        with self.assertRaisesRegex(OperationError, "ID_CONFLICT"):
            self.store.apply(conflict)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(first["payload"], connection.execute("SELECT payload FROM entries").fetchone()[0])

    def test_bad_digest_cannot_commit(self):
        with self.assertRaisesRegex(OperationError, "BAD_DIGEST"):
            self.store.apply(operation(digest="0" * 64))
        self.assertEqual(0, self.store.stats()["entries"])

    def test_receipt_insert_failure_rolls_back_entry(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON receipts BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.apply(operation())
        self.assertEqual({"entries": 0, "receipts": 0}, self.store.stats())

    def test_concurrent_duplicate_requests_are_idempotent(self):
        op = operation()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            receipts = list(pool.map(lambda _: self.store.apply(op), range(16)))
        self.assertTrue(all(receipt == receipts[0] for receipt in receipts))
        self.assertEqual({"entries": 1, "receipts": 1}, self.store.stats())

    def test_unicode_payload_is_preserved(self):
        payload = json.dumps({"siteCode": "کابل", "occurredAt": "2026-11-16T08:00:00Z", "activity": "بررسی ساختمان"}, ensure_ascii=False)
        self.store.apply(operation(payload=payload, digest=hashlib.sha256(payload.encode()).hexdigest()))
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(payload, connection.execute("SELECT payload FROM entries").fetchone()[0])

    def test_payload_validation(self):
        invalid_records = [
            {"siteCode": "", "occurredAt": "2026-11-16T08:00:00Z", "activity": "ok"},
            {"siteCode": "A", "occurredAt": "2026-11-16T08:00:00", "activity": "ok"},
            {"siteCode": "A", "occurredAt": "invalid", "activity": "ok"},
            {"siteCode": "A", "occurredAt": "2026-11-16T08:00:00Z", "activity": "ok", "quantity": 10},
            {"siteCode": "A", "occurredAt": "2026-11-16T08:00:00Z", "activity": "ok", "secret": "extra"},
        ]
        for record in invalid_records:
            with self.subTest(record=record):
                payload = json.dumps(record)
                with self.assertRaisesRegex(OperationError, "INVALID_PAYLOAD"):
                    self.store.apply(operation(payload=payload, digest=hashlib.sha256(payload.encode()).hexdigest()))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.public = root / "public"
        self.public.mkdir()
        (self.public / "index.html").write_text("<h1>LSS</h1>")
        (self.public / "test.mjs").write_text("export const ok = true;")
        (root / "outside.txt").write_text("private")
        self.store = Store(root / "server.sqlite3")
        self.server = SyncHTTPServer(("127.0.0.1", 0), self.store, DEMO_TOKEN, self.public, demo=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def request(self, method="POST", path="/api/sync", body=None, token=DEMO_TOKEN):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        data = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_authentication_and_stats(self):
        self.assertEqual(401, self.request(body={"operations": [operation()]}, token=None)[0])
        self.assertEqual(401, self.request(method="GET", path="/api/stats", token="wrong")[0])
        status, _, body = self.request(method="GET", path="/api/stats")
        self.assertEqual(200, status)
        self.assertEqual({"entries": 0, "receipts": 0}, json.loads(body))

    def test_batch_limit(self):
        self.assertEqual(413, self.request(body=b" " * 16385)[0])
        self.assertEqual(0, self.store.stats()["entries"])

    def test_independent_commits_and_permanent_errors(self):
        first, second = operation(), operation()
        bad = operation(digest="0" * 64)
        status, _, body = self.request(body={"operations": [first, bad, second]})
        response = json.loads(body)
        self.assertEqual(200, status)
        self.assertEqual(2, len(response["receipts"]))
        self.assertEqual([{"id": bad["id"], "code": "BAD_DIGEST", "permanent": True}], response["errors"])
        self.assertEqual({"entries": 2, "receipts": 2}, self.store.stats())

    def test_lost_response_after_partial_commit_is_replayable(self):
        batch = [operation(), operation(), operation()]
        def interrupt(_receipt):
            raise DropResponse()
        self.server.after_commit = interrupt
        with self.assertRaises(http.client.RemoteDisconnected):
            self.request(body={"operations": batch})
        self.assertEqual({"entries": 1, "receipts": 1}, self.store.stats())
        self.server.after_commit = None
        status, _, body = self.request(body={"operations": batch})
        self.assertEqual(200, status)
        self.assertEqual(3, len(json.loads(body)["receipts"]))
        self.assertEqual({"entries": 3, "receipts": 3}, self.store.stats())

    def test_static_files_and_traversal(self):
        status, headers, body = self.request(method="GET", path="/", token=None)
        self.assertEqual(200, status)
        self.assertIn(b"LSS", body)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertTrue(self.request(method="GET", path="/test.mjs")[1]["Content-Type"].startswith("text/javascript"))
        for path in ("/../outside.txt", "/%2e%2e/outside.txt", "/..%5coutside.txt", "/api/missing", "/%00"):
            self.assertEqual(404, self.request(method="GET", path=path)[0], path)

    def test_malformed_and_duplicate_json_fields(self):
        for body in (b"{", b'{"operations":[],"operations":[]}', b'{"operations":NaN}', b'{"operations":[]}'):
            self.assertEqual(400, self.request(body=body)[0])

    def test_configuration_has_no_credential(self):
        status, _, body = self.request(method="GET", path="/api/config", token=None)
        self.assertEqual(200, status)
        self.assertEqual({"demo": True}, json.loads(body))


class LaunchTests(unittest.TestCase):
    def test_demo_refuses_external_bind(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--demo", "--host", "0.0.0.0"])

    def test_normal_mode_requires_tls(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main([])


if __name__ == "__main__":
    unittest.main()
