"""Save offline, inspect metadata, or upload one batch to the loopback demo."""
import argparse
import getpass
import json
from lss_sync import SyncClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["save", "status", "sync"])
    parser.add_argument("--db", default="data/example-client.sqlite3")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--payload", default='{"kind":"inspection","passed":true,"quantity":"12.50"}')
    args = parser.parse_args()
    client = SyncClient(args.db, endpoint=f"http://127.0.0.1:{args.port}/api/sync",
                        token="local-demo-only", allow_insecure_localhost=True)
    try:
        if args.action != "status":
            passphrase = getpass.getpass("Vault passphrase (12+ characters): ")
            if client.configured:
                client.unlock(passphrase)
            elif args.action == "save":
                client.setup(passphrase)
            else:
                parser.error("Save a record first to create this vault.")
            if args.action == "save":
                client.save(json.loads(args.payload))
            else:
                client.sync_once(force=True)
        state = client.snapshot()
        print(json.dumps({k: state[k] for k in ("counts", "phase", "last_error")}, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
