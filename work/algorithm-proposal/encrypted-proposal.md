# Design and Evaluation of a Lightweight Secure Synchronization Algorithm for Offline First Applications
## A Database and Software Engineering Study for Intermittent Connectivity

## Proposal Submission and Approval

| Administrative item | Details |
| --- | --- |
| Proposed title | Design and Evaluation of a Lightweight Secure Synchronization Algorithm for Offline First Applications |
| Motivating application | Construction site logs at Nishat Brothers Construction Company (NBCC) |
| Student name and ID | [Insert full name and student ID] |
| Supervisor | [Insert name, signature, and date] |
| Department approval | [Complete according to university requirements] |
| Submission date | 15 November 2026 |

## Abstract

An application should let a user record work even when the internet is unavailable. It should also protect the saved information and send it to the main server when a usable connection returns. To address these needs, I propose a lightweight synchronization algorithm for offline-first applications operating with limited and intermittent connectivity.

My proposed algorithm combines encrypted local storage, a persistent outgoing queue, adaptive batch sizes, and safe retries. Each record will be encrypted before it is committed to IndexedDB. When the application is open and unlocked, a single synchronization worker will send small batches over HTTPS. It will increase the byte limit cautiously after successful transfers and reduce it after slow or failed transfers. Stable operation identifiers and transactional server acknowledgements will prevent repeated requests from creating duplicate logical records.

I will use a focused narrative literature review to guide the design. Drawing on my work on the NBCC management information system, I will build a prototype for one append-only construction site-log workflow using synthetic data. I will compare adaptive batching with two fixed batch limits under reproducible low-bandwidth and interruption profiles, measuring encrypted save latency, completion time, request volume, attempted application bytes, memory use, and record integrity.

My intended contribution is a precisely specified algorithmic adaptation and evidence about its tradeoffs. Lightweight operation, prompt synchronization, and confidentiality are design objectives with explicit evaluation criteria. I will evaluate where adaptation helps and where fixed batching performs better, within conditions that allow data transfer.

**Keywords:** offline-first applications; encrypted local storage; synchronization; adaptive batching; IndexedDB; database transactions; software engineering.

## Table of Contents

1. Chapter 1 Introduction
2. Chapter 2 Literature Review
3. Chapter 3 Research Methodology
4. References
5. Appendices

# CHAPTER 1: INTRODUCTION

## 1.1 Background of the Study

A weak connection should not prevent a worker from recording what happened during the day. A construction supervisor may need to enter a short activity report while a site is disconnected, close the application, and continue working. When connectivity returns, those entries should reach the central system without requiring the user to re-enter them or decide which records need resending.

Offline-first applications address this need by saving locally before contacting a server. Local-first research identifies continued access to local data as an important design goal [1]. Browser applications can support this behavior through IndexedDB for structured records and service workers for cached assets [2], [3]. Local availability also raises two practical questions: how should stored information be protected, and how should queued work be delivered over an unreliable connection?

My motivation for this study comes from my work on mis.nishatbrothers.com, my management information system project for Nishat Brothers Construction Company (NBCC). Afghanistan provides the application context, and intermittent connectivity is the engineering condition being addressed. I will use synthetic construction site logs and an isolated prototype. I will report the laboratory network settings as experimental conditions, without treating them as measurements of Afghan locations or NBCC's live system.

## 1.2 Problem Statement

Saving offline records as readable text can expose information if application storage is copied. Waiting for a server response before saving can instead interrupt work during an outage. A useful design must protect local records while allowing capture to remain responsive.

Synchronization creates another tradeoff. Many small requests spend time on repeated exchanges, while large batches can take longer to finish and involve more data when interrupted. A response may also be lost after the server commits. Retrying becomes necessary, but the server must recognize repeated operations and avoid duplicate application [4].

The problem I address is how to coordinate encrypted local persistence and reliable uploads without excessive client cost. My proposed algorithm will adjust a bounded batch limit using observed transfer outcomes. I will test its value against fixed limits under identical encryption, retry, and database rules.

## 1.3 Research Gap and Positioning

The main ingredients already exist. Transactional outboxes arrange later delivery, idempotent APIs handle retries, and standard cryptographic APIs support authenticated encryption [4]–[6]. Additive increase and multiplicative decrease are established control ideas [7]. Their combination does not itself demonstrate a new cryptographic invention.

The bounded research question is whether a simple byte-based adaptation rule gives encrypted browser records a useful balance between responsiveness, request overhead, and recovery cost. My contribution will be an explicit application-level algorithm, its correctness argument, and a reproducible comparison. I will use the narrative review to identify closely related approaches and refine the originality claim before implementation.

## 1.4 Research Aim

My aim is to design and evaluate a lightweight synchronization algorithm that encrypts records before local persistence and automatically transfers queued records over a usable connection, while controlling batch size and preserving integrity during retries.

## 1.5 Research Objectives

1. I will review encrypted local persistence, outgoing queues, idempotency, and adaptive transmission through a focused narrative literature review.
2. I will specify the algorithm's data model, key lifecycle, transaction boundaries, adaptation rules, and recovery behavior.
3. I will implement one small PWA with adaptive and fixed batching policies sharing the same storage and security mechanisms.
4. I will evaluate local responsiveness, synchronization cost, resource use, and correctness under controlled connectivity conditions.

## 1.6 Research Questions and Hypotheses

**RQ1.** Which database and software-engineering mechanisms support encrypted offline capture and reliable later synchronization within a small browser application?

**RQ2.** How can bounded adaptive batching preserve records and prevent duplicate logical inserts during disconnection, response loss, and application restart?

**RQ3.** Compared with fixed small and fixed larger batches, what tradeoffs does adaptation introduce in completion time, requests, retransmission work, and client resource use?

**H1.** Under the stated storage assumptions, each policy will retain locally committed valid records, reject altered ciphertext, and produce at most one server entry per operation ID in the defined tests.

**H2.** Adaptive batching will have condition-dependent benefits: increasing the limit can reduce request count on a stable link, while decreasing it after interruption can reduce the data carried in a retry. Its effect on completion time will be established experimentally.

I will test these propositions and acceptance criteria during the evaluation.

## 1.7 Significance and Expected Contributions

My practical goal is to let people enter information once, keep it protected, and allow the application to manage delivery. I will connect database transactions and application state with cryptographic storage and scheduling, producing a documented algorithm, an encrypted outbox design, a reproducible prototype, and measured comparisons that include unfavorable cases.

The working name **lightweight secure synchronization (LSS)** identifies my proposed algorithm. I will attribute its existing cryptographic and control mechanisms to their sources and assess its usefulness through measured behavior and clearly stated limits.

## 1.8 Scope and Delimitations

I will limit the prototype to one append-only site-log record type, one browser profile, one foreground worker, IndexedDB, and one relational server database. Records contain a synthetic site code, time, activity description, and optional quantity and unit. Attachments, edits, multi-device merging, peer-to-peer communication, and production MIS integration are excluded.

Automatic upload means an attempt when the application is running, unlocked, authenticated, and able to reach the server. An online event can wake the worker; an actual HTTPS exchange determines whether the path is usable. Closed-browser execution and delivery during complete disconnection are outside the guarantee. Local storage clearance, eviction, device loss, and operating-system failure also remain limits.

## 1.9 Operational Definitions

| Term | Meaning in this study |
| --- | --- |
| Offline capture | Committing an encrypted record without requiring a server response. |
| Outbox | Persistent IDs and synchronization states for saved records. |
| Batch limit | Maximum serialized request-body bytes for one upload attempt. |
| Idempotent application | Repeating an ID with matching content creates no additional logical entry. |
| Acknowledged | A committed server receipt has been verified and its local state update committed. |
| Lightweight | Bounded batch processing and memory, with measured latency and application size. |

# CHAPTER 2: LITERATURE REVIEW

## 2.1 Offline Availability and Browser Persistence

Kleppmann and colleagues identify continued local access as a central property of local-first software [1]. I apply that principle to one reporting workflow. IndexedDB provides transactions for structured local data [2]. In my prototype, an encrypted record and its queue entry will commit together, so every reported save has a corresponding delivery obligation.

A service worker will cache application assets separately [3]. Caching the form does not itself protect or synchronize business records. Browser storage can also be evicted or cleared, so local persistence must be interpreted within an explicit boundary [8].

## 2.2 Encryption and Key Handling

The Web Cryptography API provides standard cryptographic operations [6]. AES-GCM protects payload confidentiality and detects modification when used with correct keys and nonces. Its initialization vector must be unique for each encryption under the same key; 96 bits is the usual recommended IV size [9].

Key handling matters as much as the cipher choice. I will implement passphrase-based key derivation at unlock, keeping the key in memory for that session without persisting the passphrase or raw key. MDN documents browser key derivation [10]. I will measure the cost of unlocking separately from subsequent saves. A memory-only key also means that a reopened application must be unlocked before it can decrypt queued records for upload.

## 2.3 Queues, Transactions, and Safe Retries

The transactional-outbox pattern commits a business change with an outgoing message and delivers it later. Its delivery process may repeat messages after failure [5]. Here, encryption precedes the local transaction, and ciphertext and queue metadata commit together.

Featonby explains how stable request IDs make retries safe and why reuse of an ID with different intent needs explicit handling [4]. The server will enforce unique operation IDs, compare stored content, and return committed receipts. A repeated transfer must not create another logical site-log entry.

## 2.4 Batching and Connectivity

I base the proposed rule on additive increase and multiplicative decrease, concepts documented in TCP congestion control [7]. LSS changes application request-body limits; it does not replace TCP or inherit its fairness guarantees. The eight-second threshold and byte limits are design parameters to evaluate, not values established by that RFC.

Backoff with jitter helps control repeated attempts against an unavailable service [11]. I will use the same retry timing for each experimental policy. Browser online indicators can be unreliable [12], so actual request outcomes will guide processing. End-to-end completion time includes transmission, latency, and server work; the algorithm will not treat it as a direct bandwidth measurement.

## 2.5 Synthesis

| Mechanism | Established role | Design implication |
| --- | --- | --- |
| Local-first principles [1] | Access independent of continuous connectivity | Complete local capture before upload. |
| IndexedDB [2] | Atomic local changes | Commit encrypted record and queue together. |
| Web Crypto and AES-GCM [6], [9] | Authenticated encryption | Use standard primitives and unique IVs. |
| Outbox and idempotency [4], [5] | Reliable retries with controlled effects | Preserve IDs and require committed receipts. |
| Increase/decrease control [7] | Established adaptation concept | Evaluate a bounded application-level variation. |
| Retry guidance [11], [12] | Manage outages and uncertain connectivity | Use one worker and bounded retry delays. |

These sources motivate the components but do not establish this prototype's speed, memory cost, or effectiveness on a weak connection. I will investigate those questions through the prototype evaluation.

# CHAPTER 3: RESEARCH METHODOLOGY

## 3.1 Research Approach and Narrative Review

I will follow a design science approach: identify the problem, specify an artifact, implement it, and evaluate it against stated objectives [13]. I will use a focused narrative review with a documented selection rationale to inform the design [14]. My searches will target offline-first applications, encrypted browser storage, transactional outboxes, idempotent synchronization, adaptive batching, and interrupted uploads.

I will search Google Scholar, accessible publisher repositories, and official specifications. I will keep a log of each query, date, citation, mechanism, evidence type, and reason for inclusion. My synthesis will compare transaction boundaries, key management, retry identity, and evaluation methods. I will distinguish documented technical evidence from product advertising and keep the review focused on the research questions.

## 3.2 Prototype and Environment

I will implement a small JavaScript PWA using Web Crypto, IndexedDB, a single worker, and an HTTPS endpoint backed by SQLite. Before the pilot, I will select one available browser-capable device and use a workstation to host the server and controlled transport. I will record the hardware, browser, runtime, source revision, and settings, and limit performance conclusions to that configuration.

I will install and cache the application before the offline tests. The transport will apply reproducible throughput limits, round-trip delays, and availability windows. Synthetic site logs remove dependence on private company records or a field survey.

## 3.3 Encrypted Data Model and Key Lifecycle

| Store | Information | Purpose |
| --- | --- | --- |
| Local records | ID, ciphertext, IV, schema and key version | Encrypted immutable site-log payload. |
| Local outbox | ID, sequence, state, retries, due time, byte length | Indexed queue without readable activity descriptions. |
| Local configuration | Salt, KDF settings, encrypted key-check value | Derivation and verification after unlock. |
| Server entries and receipts | ID, canonical payload, digest, committed result | Unique entry and per-record acknowledgement. |

Setup creates a random salt. Unlock derives a non-extractable AES-256-GCM key with PBKDF2-HMAC-SHA-256 and verifies it using an authenticated encrypted check value. I will start with 600,000 iterations, informed by OWASP password-storage guidance [15], and benchmark the cost on the selected device. Derivation occurs once per unlocked session, not per record or retry; neither the passphrase nor raw key is persisted or logged.

Each encryption uses a fresh random 96-bit IV. A unique index on key version and IV prevents local reuse, including the key-check value; a detected collision requires a new IV and encryption attempt. The operation ID and schema version form authenticated additional data. Ciphertext and queue state commit in one transaction. IDs, sizes, and synchronization states remain visible metadata; the confidentiality claim concerns the record payload.

During upload, only a bounded batch is decrypted in memory. Plaintext reaches the main server through HTTPS and is stored under server access controls. This is client encryption at rest plus encrypted transport; the main server can read the data. The service worker caches assets only, and records are excluded from URLs, analytics, localStorage, and plaintext diagnostic logs.

**Figure 1. Proposed encrypted storage and synchronization architecture.**

[[FIG: architecture]]

## 3.4 Proposed Algorithm

I have specified three rules for LSS: encrypt before local commit, transmit a bounded batch, and retain the original identity until a committed acknowledgement is saved locally. It adjusts the batch limit using completed attempts and sends eligible records without waiting for a batch to fill.

### 3.4.1 States and Scheduling

PENDING records are eligible for transmission. A selected batch becomes IN_FLIGHT in one local transaction before dispatch. Verified committed receipts change the corresponding items to ACKNOWLEDGED. A timeout requeues unacknowledged IDs; restart recovery also restores unfinished IN_FLIGHT records to PENDING.

LOCKED is an application condition requiring unlock before encryption or upload. Permanent validation errors retain a BLOCKED record and explanation. Authentication expiry pauses the worker. A failed local state transaction also pauses processing and invokes recovery after storage becomes usable, including failure to persist an acknowledgement. Records are never deleted because a retry count is exceeded.

Online notifications, new saves, and application resume can wake the single worker. Bounded timed retries remain available while it runs unlocked, even if the online hint is wrong. Repeated online events are debounced. No second request starts while one is active.

**Figure 2. Queue states and synchronization control.**

[[FIG: states]]

### 3.4.2 Batch Rule and Pseudocode

I will set the initial and minimum body limit to 2 KiB and the maximum to 16 KiB. After two consecutive full successful batches taking at most eight seconds each, the limit increases by 2 KiB. A transient transfer failure or a successful transfer slower than eight seconds halves the next limit, down to the minimum, and resets the success counter. Slow but acknowledged records are not retried. A full batch means that another eligible record could not fit; small queue-tail batches do not cause growth.

The limit includes the encoded envelope, IDs, digests, and payloads. Validation ensures that a single operation fits the minimum limit; an oversized entry is rejected before local save is reported. The worker reads through a queue index and decrypts candidates incrementally, keeping only one batch plus the next candidate in memory. IDs stay unchanged when retries are regrouped.

After successful unlock, a record that fails authenticated decryption is preserved as BLOCKED with an error reason and skipped. Other eligible records can proceed. No output from failed decryption is uploaded; an incorrect passphrase instead fails the initial unlock before the worker starts.

```text
SAVE(payload)
  require unlocked session and valid bounded input
  id = new UUID; bytes = canonical_encode(payload)
  iv = fresh IV for this key version
  ciphertext = AES_GCM_ENCRYPT(key, iv, bytes, AAD=id+schema)
  atomically insert ciphertext, unique IV and PENDING outbox
  report local save only after commit

RECOVER()
  transactionally change IN_FLIGHT records to PENDING
  reset byte limit to 2 KiB and success counter to zero
```

```text
SYNC_STEP()
  require unlocked session, credentials and no active request
  select and decrypt due records within encoded byte limit B
  if none is due: wait for a trigger or next scheduled attempt
  persist selected IDs as IN_FLIGHT before dispatch
  response = HTTPS_SUBMIT(batch with original IDs and digests)
  verify each receipt against its sent ID and digest
  atomically ACK matching COMMITTED receipts
  retain permanent errors as BLOCKED; requeue other IDs
  if transient failure or duration > 8 seconds:
    B = max(2 KiB, floor(B/2)); successes = 0
  else if full batch and every selected ID was acknowledged:
    successes += 1
    if successes == 2: B = min(16 KiB, B+2 KiB); successes = 0
  else: successes = 0
  schedule retry for transient failures with capped backoff
```

```text
SERVER_APPLY(operation)
  validate authorization, schema and recomputed payload digest
  begin serialized write transaction
    if ID exists and stored payload differs:
      roll back; return identity error
    if ID exists with matching payload: read stored receipt
    else: insert entry and receipt under unique ID
  commit before returning the success receipt
```

The endpoint applies a separate atomic transaction to each operation, so an interrupted batch may be partly committed. A lost response causes replay under the original IDs; matching operations return stored receipts. The server retains these identities throughout the experiment. The client acknowledges only verified results and reports synchronization complete only after local commit.

Retries will use full jitter with a one-second initial ceiling and a 30-second maximum delay. An online or resume trigger may allow one prompt attempt, with a one-second minimum spacing between triggered requests. The request timeout will initially be 30 seconds, longer than the slow-transfer threshold. A server Retry-After instruction will take precedence where applicable. I will freeze the settings after the pilot and apply them consistently across all policies.

### 3.4.3 Interrupted Upload Example

Suppose four records are sent and the server commits the first two before the response is lost. All unacknowledged IDs remain queued. The worker reduces its batch limit and retries those same operations. The server acknowledges the first two without reinserting them, then processes the remaining entries. Persisted local copies remain encrypted; only the active batch is readable in memory.

**Figure 3. Offline capture and recovery from a lost response.**

[[FIG: sequence]]

## 3.5 Security and Correctness Properties

**Payload protection:** encrypted persisted records must reject changed ciphertext, incorrect additional data, or a wrong key. The threat model covers copied application storage while the key is unavailable. It excludes malicious code in an unlocked application, a compromised operating system, and an easily guessed passphrase. This is an application security design, not a new cipher.

**Retention:** ciphertext and queue metadata commit together. Aborted local transactions are not reported as saved. If persisting an acknowledgement fails, the worker pauses and recovers unfinished operations. Browser storage survival and access to the correct passphrase are necessary assumptions.

**Duplicate prevention:** a unique server ID and an atomic entry-receipt transaction allow at most one logical insertion per valid operation. Exact payload comparison distinguishes a retry from conflicting ID reuse. Network messages may still be sent repeatedly.

**Conditional progress:** valid records can eventually complete if the application runs unlocked, credentials work, and the connection allows complete exchanges for long enough. During total disconnection it preserves records until delivery becomes possible. A finite test can expose failures but cannot establish success for every network sequence.

## 3.6 Comparison and Experimental Profiles

I will compare three policies: adaptive 2–16 KiB batches, fixed 2 KiB batches, and fixed 16 KiB batches. All three will share the same encryption, database code, IDs, authentication, timeout, and retry rules, allowing me to test adaptation against both ends of its permitted range.

| Profile | Throughput and round-trip delay | Availability |
| --- | --- | --- |
| P1 Stable reference | 256 kbit/s each direction; 200 ms RTT | Continuously available. |
| P2 Weak stable link | 32 kbit/s each direction; 800 ms RTT | Continuously available. |
| P3 Weak intermittent link | 16 kbit/s each direction; 1,200 ms RTT | Alternating 20-second online/offline windows for 180 seconds, then stable. |

These are synthetic engineering conditions, not national or NBCC measurements. I will document how the transport enforces rates, models outages, and drops responses. Rate applies to the encoded stream rather than a fixed delay per batch.

Each run begins with 100 records saved offline, targeting 512 UTF-8 payload bytes each before encryption. I will record the actual encrypted and request sizes. Three policies, three profiles, and ten repetitions produce 90 main runs. I will use the same records and predetermined interruption and jitter seeds for paired runs and rotate the policy order. The observation window is 600 seconds from the start of the network trace. I will report incomplete runs explicitly and leave their completion times unassigned.

## 3.7 Boundary Tests and Measures

I will test restart after encrypted save; response loss after partial or complete server commit; duplicate requests; conflicting ID reuse; failed local acknowledgement commit; interrupted unlock; changed ciphertext; wrong passphrase; incorrect online hints; and aborted database transactions. These target the stated properties and do not constitute a complete security audit.

| Measure | Collection and interpretation |
| --- | --- |
| Encrypted save latency | Valid save action to committed local transaction; median and 95th percentile. |
| Unlock cost | Key derivation and verification time, measured once per session separately. |
| First-attempt delay | Usable-connection trigger to upload attempt, with unlock/authentication state recorded. |
| Completion time | Network-trace start until all valid IDs are acknowledged locally. |
| Communication cost | Request count and attempted encoded request/response body bytes. |
| Resource use | Compressed initial application assets and observed JavaScript heap growth during sync. |
| Integrity and protection | Retention, matching server payloads, duplicate effects, and rejection of altered ciphertext or wrong keys. |

The harness counts each issued request and generated response body once, including deliberately dropped messages. A request dropped before processing creates no response to count. This measures attempted application exchanges, excluding headers, TLS, TCP retransmissions, and radio energy. It does not estimate network bills or battery savings.

My proposed usability targets are encrypted-save 95th-percentile latency below 100 ms, compressed initial application assets below 150 KiB, and observed synchronization heap growth below 10 MiB on the selected device. These are targets to evaluate, not achieved results. I will report unlock time separately. Browser runtime memory is excluded from application asset size, and heap measurement will use a documented tool with garbage-collection variability reported.

## 3.8 Analysis and Interpretation

I will report counts, medians, ranges, and paired differences by profile, including failures. Correctness requires retained locally committed valid records, exact final payload matches, and zero duplicate logical effects after successful recovery. Tampered-ciphertext and wrong-key checks must fail authenticated decryption. I will use storage inspection as an implementation check, alongside authenticated-decryption tests.

I will explain unfavorable cases as carefully as favorable ones. Small batches limit the data associated with one interrupted attempt but can increase round trips. Larger batches may improve a stable transfer and require more replay after loss. Adaptation is useful only if its measured balance justifies its extra state.

Payload work per attempt scales with the batch's byte count. Indexed queue reads and one active request should bound working payload memory by one batch plus a candidate record, while persistent storage grows with the queue. I will measure whether the implementation meets these expectations, including the effect of browser overhead.

## 3.9 Validity, Ethics, and Limitations

One device, browser, record size, and synthetic transport limit generalization. Throttling cannot reproduce every cellular failure. I will state the tested conditions and report encryption and unlocking costs explicitly, so readers can judge where the findings apply.

I will use only synthetic records and keep the prototype isolated from my NBCC MIS project. I will exclude passphrases and plaintext from diagnostics. Losing the passphrase may make unsynchronized local records unrecoverable. Production key recovery, rotation, multi-user deployment, and broader security assessment remain separate future work.

## 3.10 Expected Outputs and Work Plan

I will produce a focused narrative review, the LSS specification, three design diagrams, a prototype with three batching policies, and a reproducible report. My security contribution will be the correct use and evaluation of standard mechanisms within the synchronization design.

| Period after approval | Activity | Deliverable |
| --- | --- | --- |
| Weeks 1–2 | Review and scope confirmation | Prior-art comparison and final questions. |
| Weeks 3–4 | Algorithm, threat model, and data design | Pseudocode, key lifecycle, and tests. |
| Weeks 5–7 | Prototype and shared baselines | Encrypted storage and controlled transport. |
| Weeks 8–9 | Pilot, freeze settings, and evaluate | Ninety run logs and boundary-test evidence. |
| Weeks 10–11 | Analyze and write | Comparisons, limitations, and design rationale. |
| Week 12 | Supervisor review and revision | Thesis and reproducibility package. |

I will carry out the work using an available test device, a workstation, and open-source tools, without requiring company deployment or a field survey. At my proposal defense, I will present the algorithm and research design. After approval, I will implement the prototype and collect the evaluation results.

# REFERENCES

[1] M. Kleppmann, A. Wiggins, P. van Hardenberg, and M. McGranaghan, “Local-first software: You own your data, in spite of the cloud,” in Proceedings of Onward! 2019, pp. 154–178, 2019. doi: 10.1145/3359591.3359737. https://www.inkandswitch.com/essay/local-first/.

[2] MDN Web Docs, “IndexedDB key characteristics and basic terminology.” https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Basic_Terminology. Accessed: Nov. 15, 2026.

[3] MDN Web Docs, “Offline and background operation.” https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation. Accessed: Nov. 15, 2026.

[4] M. Featonby, “Making retries safe with idempotent APIs,” Amazon Builders' Library. https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/. Accessed: Nov. 15, 2026.

[5] C. Richardson, “Pattern: Transactional outbox.” https://microservices.io/patterns/data/transactional-outbox.html. Accessed: Nov. 15, 2026.

[6] W3C, “Web Cryptography Level 2,” First Public Working Draft, Apr. 22, 2025. https://www.w3.org/TR/2025/WD-webcrypto-2-20250422/. Accessed: Nov. 15, 2026.

[7] M. Allman, V. Paxson, and E. Blanton, “TCP congestion control,” RFC 5681, Sept. 2009. https://www.rfc-editor.org/rfc/rfc5681. Cited as conceptual prior art for adaptation.

[8] MDN Web Docs, “Storage quotas and eviction criteria.” https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria. Accessed: Nov. 15, 2026.

[9] MDN Web Docs, “AesGcmParams.” https://developer.mozilla.org/en-US/docs/Web/API/AesGcmParams. Accessed: Nov. 15, 2026.

[10] MDN Web Docs, “SubtleCrypto: deriveKey() method.” https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/deriveKey. Accessed: Nov. 15, 2026.

[11] M. Brooker, “Timeouts, retries, and backoff with jitter,” Amazon Builders' Library, 2019. https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/. Accessed: Nov. 15, 2026.

[12] MDN Web Docs, “Navigator: onLine property.” https://developer.mozilla.org/en-US/docs/Web/API/Navigator/onLine. Accessed: Nov. 15, 2026.

[13] K. Peffers, T. Tuunanen, M. A. Rothenberger, and S. Chatterjee, “A design science research methodology for information systems research,” Journal of Management Information Systems, vol. 24, no. 3, pp. 45–77, 2007. doi: 10.2753/MIS0742-1222240302.

[14] H. Snyder, “Literature review as a research methodology: An overview and guidelines,” Journal of Business Research, vol. 104, pp. 333–339, 2019. doi: 10.1016/j.jbusres.2019.07.039.

[15] OWASP Foundation, “Password storage cheat sheet,” PBKDF2 guidance. https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html. Accessed: Nov. 15, 2026. Used to inform a starting work factor, not to validate the full encryption design.

# APPENDIX A: RESEARCH ALIGNMENT

| Question | Method | Output |
| --- | --- | --- |
| RQ1 Mechanisms | Focused narrative literature review | Prior-art comparison and design rationale. |
| RQ2 Integrity and recovery | Transaction/state reasoning and boundary checks | Algorithm and correctness assessment. |
| RQ3 Performance tradeoffs | Three policies under three profiles | Latency, byte, request, and memory comparisons. |

## APPENDIX B: DEFENSE EXPLANATION

My algorithm protects records before storing them on the device and keeps a persistent queue. When the unlocked application can reach the main server, it sends small batches automatically. It grows batches cautiously after successful transfers and reduces them when transfers become slow or fail. Stable identities allow retries without duplicate records.

I will evaluate whether adaptation gives a useful balance between speed, communication cost, and resource use. The underlying encryption and synchronization patterns are established. My contribution is the bounded algorithm, its integration, and controlled evaluation. During complete disconnection, it preserves protected data until transmission becomes possible.
