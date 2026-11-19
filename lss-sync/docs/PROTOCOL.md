# LSS protocol version 1

This specification describes the common behavior of the JavaScript/TypeScript and Python packages. A compatible implementation uses the same wire format, byte limits, encryption parameters, receipt checks, and batch-control rules. Local storage can differ: the browser package uses IndexedDB and Web Crypto; the Python package uses SQLite and `cryptography`.

Protocol compatibility means that either client can submit operations to the same compatible server. It does not make an IndexedDB database interchangeable with a SQLite file. Fixed cryptographic fixtures verify byte-level compatibility; they are test data, never production keys or IVs.

## Supported application data

A payload can contain:

- `null`, booleans, or Unicode strings without unpaired surrogates;
- integers from −9,007,199,254,740,991 through 9,007,199,254,740,991;
- arrays of supported values;
- objects with Unicode string keys and supported values.

Fractional numbers, Python `float` values, non-finite numbers, binary values, cyclic structures, and nesting deeper than 32 levels are rejected. Represent decimal quantities as strings, such as `"1250.75"`. Dates are application-defined strings, normally an ISO 8601 value. The SDK does not assume construction logs, inventory records, or any other business schema. An optional application validator can restrict what a particular project accepts.

Canonical serialization follows these rules:

1. Sort object keys by Unicode code-point order, recursively. Array order stays unchanged.
2. Use compact JSON, without insignificant whitespace.
3. Preserve Unicode text. Escape quotes, backslashes, and JSON control characters as required.
4. Do not trim strings or normalize Unicode. Two differently encoded strings remain different payloads.
5. Encode the result as UTF-8 for hashing and encryption.

Use the shared fixtures in `spec/` to check another language port. Matching an example visually is insufficient: serialized bytes, SHA-256 digests, and AES-GCM outputs must agree.

## Operation envelope

```json
{
  "operations": [
    {
      "id": "b1c64479-d242-426a-b069-2aca0c8e083e",
      "schema": 1,
      "payload": "{\"item\":\"cement\",\"quantity\":24}",
      "digest": "<64 lowercase hexadecimal SHA-256 characters>"
    }
  ]
}
```

The example digest is a placeholder. A real client computes SHA-256 over the exact UTF-8 bytes of the `payload` string.

| Field | Meaning |
|---|---|
| `id` | Stable, lowercase UUID assigned once to an immutable operation |
| `schema` | Protocol payload schema version, currently the integer `1` |
| `payload` | Canonical application JSON represented as a JSON **string** |
| `digest` | SHA-256 of the payload's UTF-8 bytes, in lowercase hexadecimal |

Wrapping the payload as a string allows the receiver to compare the exact client serialization without reformatting numbers or strings. The server still parses and validates the contained application JSON.

`POST /api/sync` in the examples accepts this envelope and returns JSON. The path and authentication mechanism belong to the host application; production transport must use HTTPS. Do not put credentials or payloads in query strings.

The complete encoded request body must fit the active batch limit. That count includes the envelope, IDs, schema fields, digests, JSON punctuation, and escaping of the nested payload string. Every individual operation must fit a 2,048-byte batch before it can be reported as saved. A server accepts at most 16,384 body bytes per batch.

## Local encryption and persistence

Each vault uses the following parameters:

| Parameter | Value |
|---|---|
| Cipher | AES-256-GCM |
| Authentication tag | 128 bits, appended to ciphertext |
| Record IV | Fresh random 12-byte value |
| Passphrase derivation | PBKDF2-HMAC-SHA256, 600,000 iterations |
| Salt | Random 16-byte value created with the vault |
| Record additional authenticated data | UTF-8 compact JSON `[operationId, 1]` |
| Key-check plaintext | `LSS vault verification v1` |
| Key-check additional authenticated data | UTF-8 `LSS key-check v1` |

The stored vault configuration includes `version`, `keyVersion`, `iterations`, and base64 values for `salt`, `checkIv`, and `check`. The encrypted key check verifies a derived key at unlock. The passphrase and raw key are not intentionally persisted.

Reserve the key-check IV and every record IV in a uniqueness store keyed by `(keyVersion, IV)`. A local save performs encryption first, then commits the IV reservation, ciphertext, and outgoing queue item in one transaction. A conflicting IV requires fresh encryption with a new IV. An aborted transaction must never be reported as a completed save.

Only bounded batches are decrypted for synchronization. Decryption failure retains the record as `BLOCKED`; other valid records can proceed. IDs, sizes, queue states, and timing metadata are not covered by the payload-confidentiality claim.

## Queue states and recovery

| State | Meaning |
|---|---|
| `PENDING` | Stored locally and eligible for an attempt when due |
| `IN_FLIGHT` | Selection committed locally before request dispatch |
| `ACKNOWLEDGED` | Matching committed receipt verified and the local state update committed |
| `BLOCKED` | Retained record requiring attention because of corruption or a permanent rejection |

Recover unfinished `IN_FLIGHT` items as `PENDING` before a new worker processes the queue. A timeout or missing receipt requeues the same operation IDs. Do not discard a record because a retry count has been exceeded.

The browser uses Web Locks to serialize senders sharing a vault. Python uses a local synchronization lock around a step. Other ports must provide equivalent exclusion for their persistence adapter. The network can still deliver the same operation more than once; server idempotency is required.

## Receipts and independent server commits

```json
{
  "receipts": [
    {
      "id": "b1c64479-d242-426a-b069-2aca0c8e083e",
      "digest": "<matching payload digest>",
      "status": "COMMITTED",
      "committedAt": "2026-11-17T00:00:00.000Z"
    }
  ],
  "errors": []
}
```

Before acknowledging a record, the client checks that the receipt ID belongs to the attempted batch, its digest matches that operation, and its status is `COMMITTED`. Missing or invalid receipts leave records eligible for replay. A permanent per-operation error has `id`, `code`, and `permanent: true`; the record remains stored as `BLOCKED`.

A compatible server applies each operation independently:

1. Authenticate the request and derive its namespace from trusted server-side identity.
2. Validate the envelope, schema, canonical payload, size, and recomputed digest.
3. Begin a database transaction and look up `(namespace, operationId)`.
4. If it exists with the same schema, exact payload, and digest, return its stored receipt. If the content differs, reject it as `ID_CONFLICT` without changing the original.
5. Otherwise insert the entry and its receipt atomically.
6. Commit before including the receipt in the response.

The client does not choose an authoritative namespace in the wire envelope. The host server maps its authenticated account or tenant to that namespace. Namespace separation is not a replacement for authentication or business authorization.

Earlier records in a batch may be committed before a later failure. A lost response therefore causes replay under the same IDs. This produces at most one logical entry per retained ID and namespace; it does not promise exactly-once network delivery.

## Batch adaptation

Let `B` be the maximum encoded request-body bytes, initially 2,048. Let `s` be the count of consecutive full, fast batches in which every selected operation was acknowledged.

```text
if an attempt fails transiently or duration > 8,000 ms:
    B = max(2,048, floor(B / 2))
    s = 0
else if full and every selected operation was acknowledged:
    s = s + 1
    if s == 2:
        B = min(16,384, B + 2,048)
        s = 0
else:
    s = 0
```

A batch is full when the next eligible record would not fit. A queue-tail batch is sent immediately and does not cause growth merely because it succeeds. A slow acknowledged operation remains acknowledged; only the next limit shrinks. The fixed comparison modes keep the limit at 2,048 or 16,384 bytes while retaining all other mechanisms.

The timeout is 30 seconds. Retry delay uses full jitter with a ceiling of `min(30,000, 1,000 × 2^(retryCount−1))` milliseconds. A scheduled retry may have a small implementation scheduling floor. Prompt connection/resume notifications are debounced; a persisted server `Retry-After` deadline always takes precedence.

The browser must remain open and unlocked. The Python sender must remain running and unlocked. Total disconnection cannot carry data: valid queued records remain until a complete exchange becomes possible. Each implementation exposes its lifecycle explicitly so the host application can resume it after startup.
