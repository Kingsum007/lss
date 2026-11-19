# LSS implementation specification

## Local save

1. Require an unlocked session and validate the small site-log schema.
2. Serialize its string fields in a fixed order; create a UUID and hash the UTF-8 payload.
3. Encode a single-operation request and reject it before saving if the complete body exceeds 2,048 bytes.
4. Generate a 96-bit random IV and encrypt with AES-256-GCM. Authenticated additional data is the encoded pair `[operationId, schema]`.
5. In one IndexedDB transaction, reserve `(keyVersion, IV)`, insert ciphertext, and insert a `PENDING` outbox item. A uniqueness failure rolls back and triggers fresh encryption; other storage errors are returned to the caller.
6. Report success after the transaction completes. Wake the sender if running and unlocked.

The key-check IV is reserved in the same nonce store during vault creation. Setup stores a random salt, derivation parameters, and an encrypted check value; no passphrase or raw key is stored.

## Upload step

Acquire the browser's exclusive `lss-sync:<database-name>` lock. If recovering, return unfinished `IN_FLIGHT` records to `PENDING`. Read the persisted server retry deadline before selecting records.

Scan the state/sequence index. Decrypt records one at a time and add eligible operations while the actual request-body encoding fits the current byte limit. One candidate may sit beyond the active batch. Corrupt or invalid local records are retained as `BLOCKED`; remaining valid records can proceed. Send partial queue-tail batches without waiting for more records.

Persist all selected IDs as `IN_FLIGHT` before dispatch. The foreground scheduler allows one request at a time; the browser lock extends that rule across tabs. Use the original IDs and payload digests for every replay. The response body is bounded to 64 KiB as a defensive implementation limit.

For each receipt, verify that its ID belongs to the attempted batch, its digest matches, and its status is `COMMITTED`. Atomically store acknowledged states, retain known permanent errors as `BLOCKED`, and requeue unconfirmed IDs with due times. A failed local acknowledgement transaction leaves recoverable in-flight records. Do not remove entries after a retry count.

## Batch controller

Let `B` be the maximum serialized request body in bytes and `s` the count of consecutive full, fast, completely acknowledged batches.

```text
initial B = 2048; s = 0

if an attempt fails transiently OR duration > 8000 ms:
    B = max(2048, floor(B / 2)); s = 0
else if full AND every selected operation was acknowledged:
    s = s + 1
    if s == 2:
        B = min(16384, B + 2048); s = 0
else:
    s = 0
```

“Full” means the next eligible record would not fit. A smaller queue-tail transfer does not increase `B`. Slow acknowledged records remain acknowledged. The fixed comparison policies keep `B=2048` or `B=16384` while sharing every other mechanism.

The full-jitter delay is a uniform sample from zero up to `min(30000, 1000 × 2^(retryCount−1))` milliseconds. A timer has a small scheduling floor of 10 ms to avoid a zero-delay spin. A new-save, online, or resume event may prompt an earlier retry, with at least one second between triggered requests. A server Retry-After deadline always takes precedence and persists across recovery. The default request timeout is 30 seconds.

## Protocol and server commit

```json
{
  "operations": [
    {
      "id": "b1c64479-d242-426a-b069-2aca0c8e083e",
      "schema": 1,
      "payload": "{\"activity\":\"Synthetic log\",\"occurredAt\":\"2026-11-17T00:00:00.000Z\",\"siteCode\":\"NBCC-01\"}",
      "digest": "<SHA-256 hex of the UTF-8 payload string>"
    }
  ]
}
```

The payload is a JSON **string**, allowing the server to hash and compare the exact client serialization without cross-language floating-point canonicalization. All business fields in this prototype are strings.

The server checks authentication, request size, operation schema, payload schema and recomputed digest. For each operation independently:

1. Start `BEGIN IMMEDIATE` in SQLite.
2. If the ID exists, compare its stored schema, exact payload and digest. A matching replay reads the existing receipt; a different operation returns `ID_CONFLICT` without altering the original.
3. Otherwise, insert the entry and receipt in the same transaction.
4. Commit before returning the receipt.

The response is `{receipts: [...], errors: [...]}`. Receipts contain `id`, `digest`, `status: "COMMITTED"`, and `committedAt`. Permanent per-operation errors contain `id`, `code`, and `permanent: true`.

Network delivery can repeat. The database enforces at most one logical entry per operation ID, assuming its retained identity/receipt tables remain intact. This is not a claim that network messages are delivered exactly once.

## Lifecycle

`lock()` invalidates in-progress unlock/save sessions, aborts active transport, releases the engine's key reference and removes payloads from snapshots. In-flight data stays recoverable. Unlock derives and verifies the key once and resets the adaptive policy to its initial limit. Authentication failures pause uploads until a new token is supplied. Storage failures pause the sender and retry recovery after five seconds.

Web Crypto runs cryptographic operations asynchronously. The synchronization worker is a foreground JavaScript scheduler, not a dedicated Web Worker or an always-running background service. JavaScript cannot promise immediate erasure of every temporary string or native buffer; the key and plaintext are not intentionally persisted by this implementation.
