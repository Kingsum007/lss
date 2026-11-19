from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "src"))
from lss_sync.backend import BatchError, OperationError, ReceiptStore
from lss_sync.protocol import canonical_payload


def operation(value, operation_id=None):
    text = canonical_payload(value)
    return {"id": operation_id or str(uuid.uuid4()), "schema": 1, "payload": text,
            "digest": hashlib.sha256(text.encode("utf-8")).hexdigest()}


class ReceiptStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ReceiptStore(Path(self.temp.name) / "receipts.sqlite3")

    def test_arbitrary_json_payload_and_exact_replay(self):
        op = operation({"name": "اطلاعات آزمایشی", "flags": [True, False, None], "count": 14})
        first = self.store.apply(op, namespace="team-a")
        self.assertEqual(self.store.apply(op, namespace="team-a"), first)
        self.assertEqual(first["status"], "COMMITTED")
        self.assertEqual(self.store.stats(namespace="team-a"), {"entries": 1, "receipts": 1})
        with closing(self.store.connect()) as connection:
            saved = connection.execute("SELECT payload FROM lss_entries WHERE namespace=? AND id=?", ("team-a", op["id"])).fetchone()[0]
        self.assertEqual(saved, op["payload"])

    def test_namespace_isolation_with_same_operation_id(self):
        first = operation({"value": "a"})
        second = operation({"value": "b"}, first["id"])
        self.store.apply(first, namespace="team-a")
        self.store.apply(second, namespace="team-b")
        self.assertEqual(self.store.stats(namespace="team-a")["entries"], 1)
        self.assertEqual(self.store.stats(namespace="team-b")["entries"], 1)
        self.assertEqual(self.store.stats(namespace="team-c")["entries"], 0)

    def test_namespace_is_required_and_cannot_come_from_batch(self):
        op = operation({"value": 1})
        with self.assertRaises(TypeError):
            self.store.apply(op)
        for invalid in (None, "", "x" * 129, "\ud800"):
            with self.assertRaises(ValueError):
                self.store.apply(op, namespace=invalid)
        with self.assertRaises(BatchError):
            self.store.apply_batch({"namespace": "team-b", "operations": [op]}, namespace="team-a")

    def test_id_conflict_preserves_original(self):
        op = operation({"value": "original"})
        receipt = self.store.apply(op, namespace="team-a")
        with self.assertRaisesRegex(OperationError, "ID_CONFLICT"):
            self.store.apply(operation({"value": "changed"}, op["id"]), namespace="team-a")
        self.assertEqual(self.store.apply(op, namespace="team-a"), receipt)

    def test_rejects_bad_digest_unknown_fields_schema_and_ids(self):
        op = operation({"value": 1})
        for changed, code in [
            ({**op, "digest": "f" * 64}, "BAD_DIGEST"),
            ({**op, "extra": 1}, "INVALID_OPERATION"),
            ({**op, "schema": True}, "INVALID_SCHEMA"),
            ({**op, "id": "arbitrary-id"}, "INVALID_ID"),
        ]:
            with self.subTest(code=code), self.assertRaisesRegex(OperationError, code):
                self.store.apply(changed, namespace="team-a")
        self.assertEqual(self.store.stats(namespace="team-a")["entries"], 0)

    def test_rejects_noncanonical_or_unsafe_payloads(self):
        for text in ['{"b":2,"a":1}', '{"a": 1}', '{"value":1.0}', '{"x":9007199254740992}', '{"a":1,"a":1}']:
            op = {"id": str(uuid.uuid4()), "schema": 1, "payload": text, "digest": hashlib.sha256(text.encode()).hexdigest()}
            with self.subTest(text=text), self.assertRaisesRegex(OperationError, "INVALID_PAYLOAD"):
                self.store.apply(op, namespace="team-a")

    def test_single_operation_and_whole_request_caps(self):
        op = operation({"value": "x" * 1900})
        with self.assertRaisesRegex(OperationError, "OPERATION_TOO_LARGE"):
            self.store.apply(op, namespace="team-a")
        with self.assertRaisesRegex(BatchError, "BODY_TOO_LARGE"):
            self.store.apply_batch(b" " * 16385, namespace="team-a")
        self.assertEqual(self.store.stats(namespace="team-a")["entries"], 0)

    def test_partial_batch_commits_valid_entries_and_can_replay(self):
        valid = operation({"first": 1})
        invalid = {**operation({"second": 2}), "digest": "0" * 64}
        another = operation(["third", 3])
        body = {"operations": [valid, invalid, another]}
        response = self.store.apply_batch(body, namespace="team-a")
        self.assertEqual(len(response["receipts"]), 2)
        self.assertEqual(response["errors"], [{"id": invalid["id"], "code": "BAD_DIGEST", "permanent": True}])
        self.assertEqual(self.store.apply_batch(body, namespace="team-a"), response)
        self.assertEqual(self.store.stats(namespace="team-a"), {"entries": 2, "receipts": 2})

    def test_validator_is_applied_without_changing_protocol(self):
        store = ReceiptStore(Path(self.temp.name) / "validated.sqlite3", validator=lambda value: isinstance(value, dict) and value.get("type") == "invoice")
        accepted = operation({"type": "invoice", "amount": "12.50"})
        rejected = operation({"type": "other"})
        result = store.apply_batch({"operations": [rejected, accepted]}, namespace="team-a")
        self.assertEqual(len(result["receipts"]), 1)
        self.assertEqual(result["errors"][0]["code"], "INVALID_PAYLOAD")

    def test_receipt_failure_rolls_back_entry(self):
        with closing(self.store.connect()) as connection:
            connection.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON lss_receipts BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.apply(operation({"value": 1}), namespace="team-a")
        self.assertEqual(self.store.stats(namespace="team-a"), {"entries": 0, "receipts": 0})

    def test_concurrent_replay_creates_one_entry(self):
        op = operation({"value": 1})
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda _: self.store.apply(op, namespace="team-a"), range(12)))
        self.assertTrue(all(receipt == results[0] for receipt in results))
        self.assertEqual(self.store.stats(namespace="team-a"), {"entries": 1, "receipts": 1})

    def test_bad_envelopes_are_rejected_before_application(self):
        for body in [b'{"operations":[],"operations":[]}', b'{"operations":[]}', b'{"operations":null}', b'[]', b'\xff']:
            with self.subTest(body=body), self.assertRaises(BatchError):
                self.store.apply_batch(body, namespace="team-a")
        self.assertEqual(self.store.stats(namespace="team-a")["entries"], 0)


class ExampleHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        spec = importlib.util.spec_from_file_location("lss_example_server", ROOT / "examples" / "server.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.store = ReceiptStore(Path(cls.temp.name) / "http.sqlite3")
        cls.server = cls.module.ExampleServer(("127.0.0.1", 0), cls.store)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, method, target, body=None, authorized=True):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer local-demo-only"
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, target, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_example_api_auth_and_real_commit(self):
        body = json.dumps({"operations": [operation({"generic": True})]}).encode()
        self.assertEqual(self.request("POST", "/api/sync", body, authorized=False)[0], 401)
        status, raw = self.request("POST", "/api/sync", body)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["receipts"][0]["status"], "COMMITTED")

    def test_example_does_not_serve_repo_private_paths(self):
        for target in ["/python/src/lss_sync/backend.py", "/.git/config", "/src/../python/pyproject.toml", "/src/%2e%2e/python/pyproject.toml"]:
            with self.subTest(target=target):
                self.assertEqual(self.request("GET", target)[0], 404)


if __name__ == "__main__":
    unittest.main()
