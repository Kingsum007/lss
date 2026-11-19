"""Wire-format tests independent of the storage or transport implementation."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "src"))
from lss_sync.protocol import (
    MAX_SAFE_INTEGER, MIN_BATCH, canonical_payload, digest_payload,
    encode_batch, make_operation, parse_payload, validate_operation,
)


OPERATION_ID = "12345678-1234-4234-8234-123456789abc"


class CanonicalPayloadTests(unittest.TestCase):
    def test_json_primitives_preserve_types_and_empty_values(self):
        cases = [(None, "null"), (True, "true"), (False, "false"),
                 ("", '""'), (0, "0"), ([], "[]"), ({}, "{}")]
        for value, expected in cases:
            with self.subTest(value=value):
                text = canonical_payload(value)
                self.assertEqual(text, expected)
                decoded = parse_payload(text)
                self.assertEqual(decoded, value)
                self.assertIs(type(decoded), type(value))

    def test_safe_integer_boundaries_are_exact(self):
        for value in (-MAX_SAFE_INTEGER, -1, 0, 1, MAX_SAFE_INTEGER):
            with self.subTest(value=value):
                self.assertEqual(canonical_payload(value), str(value))
                self.assertEqual(parse_payload(str(value)), value)
        for value in (-MAX_SAFE_INTEGER - 1, MAX_SAFE_INTEGER + 1, 10 ** 100):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_payload(value)

    def test_keys_follow_unicode_code_points_and_numeric_keys_are_strings(self):
        value = {"\U0001f600": 5, "\ue000": 4, "a": 3, "2": 2, "10": 1, "": 0}
        expected = '{"":0,"10":1,"2":2,"a":3,"\ue000":4,"\U0001f600":5}'
        self.assertEqual(canonical_payload(value), expected)
        self.assertEqual(parse_payload(expected), value)

    def test_unicode_values_are_not_normalized_or_ascii_escaped(self):
        value = ["اطلاعات", "漢字", "\U0001f600", "é", "e\u0301", "\u2028\u2029"]
        expected = '["اطلاعات","漢字","\U0001f600","é","e\u0301","\u2028\u2029"]'
        self.assertEqual(canonical_payload(value), expected)
        self.assertEqual(parse_payload(expected), value)
        self.assertNotEqual(digest_payload(canonical_payload("é")),
                            digest_payload(canonical_payload("e\u0301")))

    def test_control_characters_and_quotation_marks_have_exact_escaping(self):
        value = '"\\\b\t\n\f\r\x00\x1f/'
        expected = r'"\"\\\b\t\n\f\r\u0000\u001f/"'
        self.assertEqual(canonical_payload(value), expected)
        self.assertEqual(parse_payload(expected), value)

    def test_rejects_all_floats_and_non_json_types(self):
        for value in (0.0, -0.0, 1.0, 0.25, float("nan"), float("inf"),
                      b"bytes", (1, 2), {1, 2}, object()):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                canonical_payload(value)
        for value in ({1: "integer key"}, {None: "null key"}, {"nested": [1.0]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_payload(value)

    def test_lone_surrogates_in_keys_or_values_are_rejected(self):
        for value in ("\ud800", "\udfff", {"\ud800": "value"}, {"value": "\udfff"}):
            with self.subTest(value=repr(value)), self.assertRaisesRegex(ValueError, "surrogate"):
                canonical_payload(value)

    def test_cycles_are_rejected_but_repeated_references_are_allowed(self):
        cyclic_list = []
        cyclic_list.append(cyclic_list)
        cyclic_dict = {}
        cyclic_dict["self"] = cyclic_dict
        for value in (cyclic_list, cyclic_dict):
            with self.subTest(kind=type(value).__name__), self.assertRaisesRegex(ValueError, "Cyclic"):
                canonical_payload(value)
        shared = {"ok": True}
        self.assertEqual(canonical_payload([shared, shared]), '[{"ok":true},{"ok":true}]')

    def test_nesting_boundary_is_32(self):
        value = None
        for _ in range(32):
            value = [value]
        text = "[" * 32 + "null" + "]" * 32
        self.assertEqual(canonical_payload(value), text)
        self.assertEqual(parse_payload(text), value)
        with self.assertRaisesRegex(ValueError, "32"):
            canonical_payload([value])
        with self.assertRaisesRegex(ValueError, "32"):
            parse_payload("[" + text + "]")

    def test_parser_rejects_duplicate_and_noncanonical_representations(self):
        invalid = ['{"x":1,"x":1}', '{"a":{"x":1,"x":2}}', '{"b":2,"a":1}',
                   '{"x": 1}', ' true', 'true\n', '"\\u0061"', '"\\/"', '-0',
                   '1.0', '1e0', 'NaN', 'Infinity', '-Infinity', str(MAX_SAFE_INTEGER + 1)]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_payload(text)


class OperationTests(unittest.TestCase):
    def test_operation_digest_is_sha256_of_exact_utf8_payload(self):
        operation = make_operation({"text": "سلام \U0001f600", "empty": ""}, OPERATION_ID)
        expected_payload = '{"empty":"","text":"سلام \U0001f600"}'
        self.assertEqual(operation, {"id": OPERATION_ID, "schema": 1, "payload": expected_payload,
                                     "digest": hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()})
        self.assertIs(validate_operation(operation), operation)

    def test_generated_ids_are_unique_lowercase_uuids(self):
        first = make_operation(None)
        second = make_operation(None)
        self.assertNotEqual(first["id"], second["id"])
        self.assertRegex(first["id"], r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

    def test_wire_bytes_include_outer_envelope_and_nested_string_escaping(self):
        operation = make_operation({"text": 'é"\n'}, OPERATION_ID)
        encoded = encode_batch([operation])
        self.assertIs(type(encoded), bytes)
        expected = ('{"operations":[{"id":"' + OPERATION_ID + '","schema":1,"payload":' +
                    json.dumps(operation["payload"], ensure_ascii=False) + ',"digest":"' +
                    operation["digest"] + '"}]}').encode("utf-8")
        self.assertEqual(encoded, expected)
        self.assertGreater(len(encoded), len(encoded.decode("utf-8")))
        self.assertEqual(json.loads(encoded), {"operations": [operation]})

    def test_single_operation_at_exact_wire_limit_is_accepted(self):
        overhead = len(encode_batch([make_operation("", OPERATION_ID)]))
        payload = "x" * (MIN_BATCH - overhead)
        operation = make_operation(payload, OPERATION_ID)
        self.assertEqual(len(encode_batch([operation])), MIN_BATCH)
        with self.assertRaisesRegex(ValueError, "2048"):
            make_operation(payload + "x", OPERATION_ID)

    def test_limit_counts_utf8_bytes_and_escaped_characters(self):
        overhead = len(encode_batch([make_operation("", OPERATION_ID)]))
        for character, width in [("é", 2), ("\U0001f600", 4), ('"', 4), ("\n", 3)]:
            with self.subTest(character=repr(character)):
                count = (MIN_BATCH - overhead) // width
                operation = make_operation(character * count, OPERATION_ID)
                self.assertLessEqual(len(encode_batch([operation])), MIN_BATCH)
                with self.assertRaises(ValueError):
                    make_operation(character * (count + 1), OPERATION_ID)

    def test_rejects_invalid_envelopes_ids_schemas_and_digests(self):
        operation = make_operation({"ok": True}, OPERATION_ID)
        invalid = [None, [], {**operation, "extra": True},
                   {key: value for key, value in operation.items() if key != "digest"},
                   *[{**operation, "id": value} for value in ("", "anything", OPERATION_ID.upper(), 42)],
                   *[{**operation, "schema": value} for value in (True, 1.0, "1", 2)],
                   *[{**operation, "digest": value} for value in ("0" * 64, "A" * 64, "short", None)],
                   {**operation, "payload": True}]
        for changed in invalid:
            with self.subTest(operation=changed), self.assertRaises(ValueError):
                validate_operation(changed)

    def test_matching_digest_does_not_make_noncanonical_payload_valid(self):
        operation = make_operation({"x": 1}, OPERATION_ID)
        for payload in ('{"x": 1}', '{"x":1,"x":1}', '{"x":1.0}'):
            invalid = {**operation, "payload": payload, "digest": digest_payload(payload)}
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_operation(invalid)


if __name__ == "__main__":
    unittest.main()
