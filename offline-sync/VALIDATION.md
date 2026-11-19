# Validation record

Validated on **17 November 2026** using synthetic records. The implementation is a working research prototype. The complete 90-run thesis evaluation has not been executed.

## Functional checks

| Suite | Passed | Failed |
|---|---:|---:|
| JavaScript policy, encoding, and cryptography | 7 | 0 |
| SQLite and HTTP server | 16 | 0 |
| Real-browser integration | 16 | 0 |
| **Total** | **39** | **0** |

The browser checks use real Web Crypto, IndexedDB and service-worker caching in Microsoft Edge. They cover encrypted persistence, wrong passphrases, local transaction aborts, response loss after server commit, restart recovery, tampered ciphertext, invalid receipts, failed local acknowledgement commits, authentication pauses, overlapping triggers, real offline reload, desktop/mobile UI, shared-vault worker exclusion, persisted Retry-After, cancelled unlock, encryption-IV collision recovery, and request timeout with an incorrect online hint.

The server suite additionally checks partial-batch commit followed by response loss, concurrent duplicate operations, conflicting ID reuse, bad digests, atomic entry/receipt rollback, malformed JSON, request limits, traversal, and refusal to run external plaintext demo mode.

## Short network trials

Environment: Intel Core i7-9850H at 2.60 GHz, Windows x64, Edge 157.0.4341.46, Node v26.7.0. One repetition per policy/profile, **12 records per run**, each targeting 512 UTF-8 plaintext bytes. Completion time is sampled at approximately 100 ms intervals.

| Synthetic profile | Adaptive | Fixed 2 KiB | Fixed 16 KiB |
|---|---:|---:|---:|
| P1: 256 kbit/s, 200 ms RTT | 1.19 s / 3 attempts | 1.43 s / 4 attempts | 0.68 s / 1 attempt |
| P2: 32 kbit/s, 800 ms RTT | 5.23 s / 3 attempts | 6.16 s / 4 attempts | 3.54 s / 1 attempt |
| P3-smoke: 16 kbit/s, 1,200 ms RTT, short outages | 24.73 s / 12 attempts | 38.42 s / 16 attempts | 24.30 s / 14 attempts |

All nine runs ended with all 12 entries acknowledged. P3-smoke alternates two-second online/offline windows for 12 seconds, then becomes stable; it is a shortened engineering check, not the proposal's full P3 trace. The emulator delays actual serialized upload/download bodies and can drop a generated response after the real server has committed.

The adaptive policy's P3-smoke run experienced three lost generated responses and six failures before server processing. Attempted application-body bytes were 30,381 for adaptive, 33,945 for fixed 2 KiB, and 45,506 for fixed 16 KiB. These counts include retry attempts and generated response bodies, not TCP/TLS/radio traffic.

Encrypted-save p95 ranged from **1.0 to 1.9 ms** across these runs. Vault creation, including key derivation, ranged from **243 to 258 ms** and was measured separately. Observed heap growth ranged from approximately **0.43 to 1.29 MiB**, including measurement-harness allocations and garbage-collection effects. These desktop results do not predict low-end phone performance.

The static application files total **59,796 bytes uncompressed**, or **19,690 bytes estimated gzip** when compressed individually. The reference server sends them uncompressed. No external libraries, fonts, or CDNs are required at runtime.

## Interpretation

Adaptive batching completed these trials faster than fixed-small batches. Fixed-large batches were fastest in this small workload. Adaptive batching used fewer attempted application bytes than fixed-large batches in the intermittent smoke trace. These observations support keeping both fixed baselines in the research design; they do not establish general superiority or statistical significance.

The machine-readable reports and screenshots in `evidence/` preserve the observed results. The benchmark contains a `--full` mode for the configured 90-run study. Further evaluation should use the selected target device, frozen parameters, and repeated trials before thesis performance conclusions are drawn.
