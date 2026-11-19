# LSS synchronization SDK

Reusable encrypted offline synchronization for JavaScript/TypeScript browser applications and Python applications. This is a research preview. Source: [GitHub](https://github.com/Kingsum007/lss). Packages: [npm](https://www.npmjs.com/package/lss-sync) and [PyPI](https://pypi.org/project/lss-sync/). Licensed under the MIT License. Copyright (c) 2026 Safi Ullah Mirzai.

See [راهنمای دری](docs/README.fa.md), [protocol](docs/PROTOCOL.md), [security boundaries](docs/SECURITY.md), and [release instructions](docs/RELEASING.md).

## Install

```sh
npm install lss-sync
python -m pip install lss-sync
```

The browser package has no runtime JavaScript dependencies and includes TypeScript declarations. Python uses the maintained `cryptography` library and SQLite. Use Python 3.10+ and a current browser supporting Web Crypto, IndexedDB and Web Locks.

## Browser integration

```javascript
import { BrowserSyncEngine } from 'lss-sync';

const sync = new BrowserSyncEngine({
  dbName: 'my-app-account-123',
  endpoint: '/api/sync',
  token: accessToken
});
const { configured } = await sync.init();
if (configured) await sync.unlock(passphrase);
else await sync.setup(passphrase);
await sync.save({ kind: 'inspection', passed: true, quantity: '12.50' });
sync.addEventListener('change', async () => render(await sync.snapshot()));
// await sync.close();
```

Supply your application's `accessToken`, `passphrase`, and `render` function. Setup/unlock starts the browser scheduler. Serve the app and API on the same HTTPS origin. The package does not install a service worker: the host app must cache its own shell for offline reload. Distinct accounts should use distinct vault names.

## Python integration

```python
from lss_sync import SyncClient

client = SyncClient('account-123.sqlite3', endpoint=endpoint, token=access_token)
if client.configured:
    client.unlock(passphrase)
else:
    client.setup(passphrase)
client.save({'kind': 'inspection', 'passed': True, 'quantity': '12.50'})
client.start()
# Keep your application running. On shutdown:
# client.close()
```

See [Python API details](python/README.md). The Python worker starts explicitly; browser and Python lifecycle APIs differ while sharing the wire protocol and algorithm.

## Server integration

```python
from lss_sync.backend import ReceiptStore

receipts = ReceiptStore('server.sqlite3')
# Authenticate in your web framework first. Derive account_id on the server.
result = receipts.apply_batch(request_body_bytes, namespace=account_id)
```

Return `result` as JSON. Each operation and its receipt commit atomically. The namespace must come from authenticated server context, never from an untrusted payload field. The SDK supplies neither account management nor a production web server.

## Supported data and behavior

Payloads are generic JSON: objects, arrays, strings, booleans, null and safe integers. Decimal quantities use strings. Both SDKs reject floats, cycles, invalid Unicode and nesting beyond 32 levels. Each complete encoded operation must fit 2 KiB. These restrictions keep serialization deterministic and retries bounded.

AES-256-GCM protects persisted payloads. A passphrase-derived key is retained in memory during the unlocked session. Adaptive batches start at 2 KiB, grow after two fast full acknowledgements, and halve after failure or slow transfer, up to 16 KiB. Fixed 2 KiB and 16 KiB policies remain available for comparison. Stable IDs, verified receipts, persistent queues and safe replay handle interruptions.

This is an upload-only append-only protocol. No attachments, edits/merging, key recovery or background operation after the application closes are included. The authorized server receives readable payloads over HTTPS. Offline encryption does not hide data from malicious code in an unlocked application.

## Install from source

Install from the GitHub repository (the SDK is in the lss-sync subdirectory):

```sh
git clone https://github.com/Kingsum007/lss.git
npm install ./lss/lss-sync
python -m pip install 'git+https://github.com/Kingsum007/lss.git#subdirectory=lss-sync/python'
```

The MIT License permits reuse under its terms. Preserve the copyright and license notice in redistributed copies.

## Validation

Run these commands from the `lss-sync/` SDK directory, not the Git repository root.

```sh
npm install
npm test
npm run typecheck
python -m pip install ./python
python -m unittest discover -s python/tests -v
npm run test:interop
```

The prior NBCC demo's benchmark results describe that earlier application, not this SDK. Re-run device and network measurements before making performance claims for integrations.

## Author and license

**Safi Ullah Mirzai**  
MSc Computer Science, Kabul University; Instructor at the National Institute of Management and Administration (NIMA).

Copyright (c) 2026 Safi Ullah Mirzai. Licensed under [MIT](LICENSE).

## Runnable integration examples

See the [step-by-step integration guide](https://github.com/Kingsum007/lss/blob/v0.1.2/lss-sync/examples/README.md) for an offline-save walkthrough, browser demo, Python client, and authenticated server adapter.

```sh
python -m lss_sync.examples.server
# In a second terminal:
python -m lss_sync.examples.client save
python -m lss_sync.examples.client sync
```
