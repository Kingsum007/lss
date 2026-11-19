# LSS Python SDK

Encrypted offline persistence and adaptive upload batches for Python applications. This is a research preview, not a hosted service or a production authentication system. Licensed under the MIT License. Copyright (c) 2026 Safi Ullah Mirzai.

Install from this repository root with `python -m pip install ./python`, or install the built wheel. Python 3.10+ and `cryptography` are required.

```python
from lss_sync import SyncClient

client = SyncClient("queue.sqlite3", endpoint="https://your-domain.example/api/sync", token=access_token)
if client.configured:
    client.unlock(passphrase)
else:
    client.setup(passphrase)

client.save({"kind": "inspection", "project": "A1", "passed": True, "quantity": "12.50"})
client.start()  # Background uploads while this Python process runs and the vault is unlocked.
state = client.snapshot()
# client.lock()  # Prevent future dispatch and release the client's key reference.
# client.close()
```

`save()` returns `{"id": ..., "save_ms": ...}` only after ciphertext, IV reservation and outbox commit in one SQLite transaction. `setup()` and `unlock()` do not start a thread; call `start()` explicitly. `sync_once()` performs one bounded attempt without a background thread. `sync_once(force=True)` may bypass retry jitter, with a one-second triggered-attempt debounce, but always honors a stored Retry-After deadline.

Payloads can be objects, arrays, strings, booleans, null, or integers in JavaScript's safe integer range. Floating-point values are rejected; use decimal strings for money and measurements. Dictionary keys are sorted by Unicode code point; string values are preserved. Cycles, unsupported types, lone surrogates, nesting beyond 32, and single-operation requests larger than 2 KiB are rejected before saving. An optional `validator(payload)` can raise or return `False` to reject application-specific data.

The supplied server adapter must authenticate requests and derive the owner namespace from trusted session/account context. The package does not infer account ownership from client-supplied record fields.

Custom transports implement `transport(body: bytes, headers: dict, timeout: float) -> TransportResponse`. They must enforce the timeout and must not persist or log plaintext bodies or tokens. The default transport verifies HTTPS certificates and does not follow redirects. HTTP is permitted only for an explicit local demo using `allow_insecure_localhost=True` and a loopback hostname.

`snapshot(include_payloads=True)` decrypts at most the latest 50 records while unlocked; its default returns metadata only. `set_token()` resumes authentication-paused delivery. `set_policy()` selects `adaptive`, `fixed-small`, or `fixed-large` between attempts. `stop()` stops scheduling. `close()` stops scheduling and locks the client. An already-dispatched synchronous HTTP request may finish after `lock()` or `stop()`; later dispatch is prevented. Python holds raw key bytes in process memory and cannot guarantee immediate zeroization. The key is never intentionally persisted.

The SQLite path identifies a vault. Use distinct paths per account/device context. OS file locking excludes multiple senders using the same local vault and is released on process exit; use a local filesystem with functioning OS locks. Unsynchronized data requires the original vault and passphrase. This package does not provide key recovery, key rotation, multi-device merge, or a protection guarantee against malicious code in an unlocked process.

Run tests from the repository root with `python -m unittest discover -s python/tests -v` after installing the package. See the repository's shared protocol and security documentation for the cross-language contract.

## Author and license

**Safi Ullah Mirzai**  
MSc Computer Science, Kabul University; Instructor at the National Institute of Management and Administration (NIMA).

Copyright (c) 2026 Safi Ullah Mirzai. Licensed under [MIT](LICENSE).
