# Security model

LSS protects persisted client payloads and coordinates replay-safe delivery. The SDK uses established cryptographic primitives; it is not a new encryption algorithm or a complete account/security system.

## What the SDK protects

AES-256-GCM encrypts each payload before the local save transaction. The record ID and schema are authenticated additional data. A changed ciphertext, mismatched ID/schema, or incorrect key fails authenticated decryption. Unique IV reservations include the vault key-check IV and commit atomically with record data.

A copied locked vault does not intentionally contain its passphrase or raw key. PBKDF2-HMAC-SHA256 derives the key from a passphrase and random salt. Password guessing remains possible against copied encrypted storage; users need a strong passphrase. The fixed initial work factor must be evaluated on target devices.

An operation keeps its ID on replay. The server's atomic entry/receipt transaction and exact payload comparison prevent duplicate logical inserts within an authenticated namespace, assuming the server retains its identity records. The SHA-256 digest identifies payload bytes; it is not a substitute for server authentication, TLS, or a cryptographic message signature.

## Boundaries

The authorized main server receives readable application data over HTTPS. This is client encryption at rest plus encrypted transport, not end-to-end encryption that hides the data from the server. Server storage, access policies, backups, and log handling belong to the host application.

Identifiers, record lengths, queue states, and timestamps remain visible local metadata. Malicious JavaScript executing in an unlocked page, a compromised operating system, or an attacker controlling the host process can access readable data. The SDK cannot protect against those conditions.

The browser uses a non-extractable Web Crypto key. Python holds key bytes in process memory. Neither JavaScript garbage collection nor ordinary Python objects provide a guarantee that every temporary key/plaintext buffer is immediately erased. Locking releases the SDK's key reference and prevents later dispatch. It cannot recall a request already transmitted; an in-progress Python HTTP request may complete within its timeout. Recovery handles a server commit whose receipt was not saved locally.

## Host application responsibilities

- Authenticate requests and derive server namespaces from that trusted identity. Never accept an arbitrary client namespace as authorization.
- Apply project-specific authorization and payload validation before accepting business records. The generic JSON schema validates structure, not permissions or business meaning.
- Serve the browser application and API over HTTPS. Protect against injected scripts and avoid logging passphrases, bearer tokens, readable payloads, or decrypted snapshots.
- Define how users handle lost passphrases, browser eviction, disk loss, backups, and acknowledged-record retention. This preview does not provide key recovery or rotation.

The browser vault is scoped to its origin and database name. A multi-account app must choose separate vault identities and a clear sign-out policy, while retaining any unsynchronized records that still need delivery. Browser persistence can be cleared or evicted.

## Examples and reporting

The included loopback server and sample token demonstrate the protocol with synthetic records. They are not a public account service. Keep reference HTTP servers isolated; use a production deployment and abuse controls before accepting public real-world traffic.

No project security-contact address is configured yet. Before public release, the maintainer should enable a private vulnerability-reporting channel in the repository and document it here. Reports should include a minimal reproduction and synthetic data; do not publish tokens, real records, or private vaults in an issue.

The test suite demonstrates selected failure cases. Passing tests is not a comprehensive security audit or a guarantee of confidentiality on a compromised device.
