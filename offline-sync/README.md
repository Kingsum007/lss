# Lightweight Secure Synchronization

A working research prototype of the LSS algorithm in the thesis proposal. It encrypts site logs before local persistence, queues them in IndexedDB, and automatically sends bounded batches to a SQLite server while the application is open and unlocked.

## Run the demo

Requirements: Python 3.10 or newer and a current Chrome or Edge browser. The application and server have no third-party runtime dependencies.

```powershell
cd "C:\Users\sumir\Documents\ChatGPT\lss\offline-sync"
python server.py --demo
```

Open **http://127.0.0.1:8765**. Alternatively, double-click `start-demo.cmd` on Windows. Keep the terminal running while using the demo.

1. Create a local workspace with a passphrase of at least 12 characters.
2. Open **Experiment controls** and select **Pause connection for demo**.
3. Save a few synthetic NBCC construction site logs. They remain encrypted and queued on the device.
4. Resume the connection. Queued entries upload automatically and become **Acknowledged** after their server receipts are committed locally.
5. Lock the workspace. Reload and unlock with the same passphrase to continue.

The pause switch affects this tab's upload transport. To demonstrate a real offline reload, first wait for **Application ready for offline use**, then use the browser's offline network setting. Returning online resumes delivery after unlock. A browser's online indication is only a hint; a successful request establishes reachability.

The explicit demo uses loopback HTTP and a public demonstration token, `local-demo-only`. It binds only to the local computer. Use synthetic records. The server stores its demo database in `data/lss.sqlite3`; the browser vault belongs to the exact origin, including the port. Keep the same origin to reopen it.

## What is implemented

- **Encrypted local capture:** AES-256-GCM, a unique 96-bit IV per encryption, and authenticated record ID/schema. A unique IV store also reserves the key-check IV. Ciphertext, the IV reservation, and the outgoing queue entry commit atomically.
- **Session key handling:** PBKDF2-HMAC-SHA256 with 600,000 iterations on setup/unlock; a non-extractable key remains in memory. The passphrase and raw key are never persisted. Wrong passphrases fail the encrypted key check.
- **Adaptive batches:** start at 2 KiB; grow by 2 KiB after two full, completely acknowledged transfers of at most eight seconds; halve after a slower or failed transfer, within 2–16 KiB. The limit includes the entire serialized request body.
- **Persistent recovery:** `PENDING → IN_FLIGHT → ACKNOWLEDGED`; unfinished transfers return to `PENDING` on recovery. Damaged or permanently rejected records remain `BLOCKED`. No retry limit discards records.
- **Safe replay:** immutable UUIDs, SHA-256 payload digests, exact server payload comparisons, and one transaction for each entry and receipt. The server can commit part of a batch and safely accept replay after a lost response.
- **Bounded retries:** 30-second request timeout, exponential full jitter with a 30-second ceiling, debounced wakeups, and persisted `Retry-After` deadlines. Online hints do not disable retries.
- **One sender per vault:** a foreground asynchronous scheduler plus the browser Web Locks API prevents overlapping transfers across tabs sharing the same vault.
- **Offline application shell:** the service worker caches an explicit list of static assets. It never caches API responses or record payloads.
- **Comparison policies:** adaptive, fixed 2 KiB, and fixed 16 KiB share the same cryptography, queue, retry, and server implementation.

## Source map

| File | Responsibility |
|---|---|
| `public/lib/engine.js` | Save, select, synchronize, acknowledge, recover, and schedule |
| `public/lib/crypto.js` | Key derivation and authenticated encryption |
| `public/lib/store.js` | IndexedDB transactions, IV uniqueness, and indexed queue access |
| `public/lib/policy.js` | Adaptive batching, jitter, and Retry-After parsing |
| `public/lib/encoding.js` | Canonical payloads, byte accounting, and size admission |
| `server.py` | Static app server, authenticated API, and SQLite transactions |
| `public/app.js` | Site-log demonstration interface |
| `tests/` | Core, server, browser, and controlled-link checks |

The protocol and transaction boundaries are documented in `ALGORITHM.md`.

## Reuse the algorithm

Serve the modules from the same HTTPS origin as the API:

```javascript
import { SyncEngine } from './lib/engine.js';

const sync = new SyncEngine({
  dbName: 'my-offline-vault',
  endpoint: '/api/sync',
  token: accessToken,
  policy: 'adaptive'
});
const { configured } = await sync.init();
if (configured) await sync.unlock(passphrase);
else await sync.setup(passphrase);

await sync.save({
  siteCode: 'NBCC-01',
  occurredAt: new Date().toISOString(),
  activity: 'Synthetic example: foundation inspection completed.'
});

sync.addEventListener('change', async () => {
  const state = await sync.snapshot();
  // Render current queue state. Payloads are returned only while unlocked.
});
// sync.lock();  // Cancel active transport and release the in-memory key.
// sync.stop();  // Stop scheduling without changing persisted queue entries.
```

`setup()` and `unlock()` start scheduling. `save()` resolves only after local commit. `setToken()` resumes a paused authentication state; `kick()` requests a debounced early attempt and honors Retry-After. Keep one engine per vault in each tab. A locked or closed application cannot decrypt and upload its records.

## Run validation

Node.js 20.19+ is required for the JavaScript tests. Playwright and a Chromium-family browser are required only for browser tests and benchmarks, not for the app itself. The runner uses an installed `playwright` module, `PLAYWRIGHT_MODULE`, or the bundled runtime available in this workspace. `BROWSER_EXECUTABLE` and `PYTHON` can override test executables.

```powershell
node --test tests/core.test.mjs
python -m unittest discover -s tests -p test_server.py -v
node tests/browser.mjs
node tests/benchmark.mjs
```

The browser runner starts its own temporary server/database, exercises real Web Crypto and IndexedDB, and writes a JSON report and desktop/mobile screenshots into `test-results/`. It injects lost responses, wrong receipts, storage aborts, corrupted ciphertext, timeout, rate limiting, and a deliberately colliding IV. It also tests real offline reload and multiple workers sharing a vault.

The default benchmark runs **nine short engineering trials** with 12 synthetic 512-byte plaintext records each. It applies upload/download byte-rate delays and round-trip latency around real HTTP and SQLite operations. P1 uses 256 kbit/s and 200 ms RTT; P2 uses 32 kbit/s and 800 ms RTT. P3-smoke uses 16 kbit/s, 1,200 ms RTT, and two-second online/offline windows for 12 seconds before becoming stable. These are synthetic conditions.

For the full configured proposal experiment:

```powershell
node tests/benchmark.mjs --full
```

Full mode uses 100 records, ten repetitions, three policies and three profiles: **90 runs**. P3 uses 20-second online/offline windows for 180 seconds, then a stable link; each run has a 600-second observation limit. Incomplete runs retain a null completion time. This mode may take hours. Running the short benchmark does not establish the results of the full study.

The traffic report counts attempted encoded request bodies and generated response bodies, including generated responses lost by the emulator. It excludes HTTP headers, TLS, TCP retransmission and radio costs. Heap measurements include harness/garbage-collection effects. Asset gzip size is an estimate; the simple demo server sends uncompressed assets.

## HTTPS mode

For an isolated HTTPS evaluation, supply a browser-trusted certificate/key and set `LSS_API_TOKEN` to a private random secret of at least 32 characters. The app prompts for that token and retains it only in memory.

```powershell
# Set LSS_API_TOKEN securely in the process environment first.
python server.py --cert path/to/cert.pem --key path/to/key.pem --host 127.0.0.1
```

The normal server mode refuses to start without TLS and the token. Certificate provisioning is separate from the synchronization algorithm. The Python reference server is for research; production deployment needs an appropriate web server and operational controls.

## Research boundaries

This implements the proposed combination of established encryption, outbox, idempotency, and adaptation mechanisms. It does not establish a new cipher or a universal performance advantage. It supports small append-only site logs, one browser profile, and one server. It does not implement attachments, edits/merging, user accounts, key recovery/rotation, or production NBCC MIS integration.

Local encryption protects record payloads in copied storage while the passphrase/key is unavailable. IDs, sizes, queue states, and timing metadata remain visible. The authorized server receives readable records over HTTPS and stores readable payloads under its access controls. Malicious code running in an unlocked page or a compromised device is outside this protection.

Browser storage may be cleared or evicted. A lost passphrase can make unsynchronized data unrecoverable. Acknowledged encrypted records remain in the local vault; production retention/archival is future work. During complete disconnection, records stay queued until an adequate exchange becomes possible. Browser background throttling can delay attempts; closing the app stops them.

## Implementation references

- [MDN Web Crypto encryption](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/encrypt)
- [MDN IndexedDB transactions and usage](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Using_IndexedDB)
- [MDN Web Locks](https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API)
- The accompanying thesis proposal provides the broader narrative literature review and research design.
