# Runnable integration examples

These examples use synthetic inspection records, a loopback-only HTTP server and a
fixed public demo token. Use separate test vaults. The SDK is an upload-only research preview.

## Python: install, save offline, then synchronize

Install the examples with the package (Python 3.10+):

```sh
python -m pip install --upgrade lss-sync==0.1.2
python -m lss_sync.examples.client save
python -m lss_sync.examples.client status
```

Enter a demo passphrase of at least 12 characters. `save` writes an encrypted
record and a durable queue entry without contacting a server. `status` prints
metadata without unlocking or decrypting records. Keep using the same directory
so the commands open the same `data/example-client.sqlite3` vault.

In a second terminal, start the example server:

```sh
python -m lss_sync.examples.server
```

In the first terminal, send one queued batch with the same passphrase:

```sh
python -m lss_sync.examples.client sync
```

Expect `ACKNOWLEDGED` in `counts` to increase. Each sync command attempts one
bounded batch; repeat for larger queues. An unavailable server leaves the record
queued. In an actual application call `client.start()` to schedule retries while
the process is running, and `client.close()` on shutdown. Restarting a process
requires unlocking the original vault with its original passphrase.

Use `--help` for options, including alternate database paths and ports.

## Browser: run directly from the npm package

Install both packages in your project directory:

```sh
npm install lss-sync@0.1.2
python -m pip install lss-sync==0.1.2
python -m lss_sync.examples.server --browser-root node_modules/lss-sync
```

Open http://127.0.0.1:8766 in a current Chrome or Edge browser.

1. Enter a demo passphrase and create the vault.
2. Check **Simulate unavailable server**, then save the example JSON record.
3. Observe a pending queue entry. The payload is encrypted in IndexedDB.
4. Uncheck the simulation and wait for the scheduler's retry delay.
5. Observe `ACKNOWLEDGED` increase. Lock and unlock to see the vault lifecycle.

The simulation blocks only synchronization requests. It does not demonstrate
an offline page reload: your host app must supply its own service worker/cache.
Do not open the HTML through `file://`; the server supplies the same-origin API.
The demo deliberately retains pending records across page reloads.

## Run from a GitHub checkout

```sh
git clone https://github.com/Kingsum007/lss.git
cd lss/lss-sync
python -m pip install ./python
python examples/server.py
```

Open http://127.0.0.1:8766. The checkout wrapper serves the local browser source.

## Integrate into your own app

- Browser bundler import: `import { BrowserSyncEngine } from 'lss-sync'`.
  Copy the initialization/save/lock flow from `examples/browser/app.js`.
  Replace the demo transport with the default transport, use your application's
  access token, and use a distinct database name for each account.
- Python import: `from lss_sync import SyncClient`. Follow the packaged
  `lss_sync.examples.client` module; replace the demo endpoint/token and use HTTPS.
- Server: authenticate the request, derive the namespace from the authenticated
  account, and call `ReceiptStore.apply_batch(raw_body, namespace=account_id)`.
  Return the resulting receipt object as JSON. Preserve the body limit and error
  handling shown in `lss_sync.examples.server` when adapting to your framework.
- Data: JSON-safe integers, strings, booleans, arrays, objects and null; encode
  decimal quantities as strings. A complete encoded operation must fit 2 KiB.
- UI: show pending/acknowledged/error states from `snapshot()` and report errors
  without discarding queued data. Never claim delivery merely because save succeeded.

The included server's fixed token and namespace are for a single local demo only.
Production integrations need their own authentication, HTTPS, per-account
namespaces, access control, and deployment. Neither example provides key recovery
or background delivery after the application is closed.
