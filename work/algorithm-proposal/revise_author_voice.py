from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import json
import shutil

ROOT = Path(r'C:\Users\sumir\Documents\ChatGPT\lss')
WORK = ROOT / 'work' / 'algorithm-proposal'
SOURCE = WORK / 'encrypted-proposal.md'
DOCX = ROOT / 'outputs' / 'MS Thesis Proposal - Lightweight Secure Offline Sync.docx'
OUTPUT = ROOT / 'outputs' / 'MS Thesis Proposal - Lightweight Secure Offline Sync - Revised.docx'

replacements = [
('These needs motivate this proposal, which focuses on a lightweight synchronization algorithm for offline-first applications operating with limited and intermittent connectivity.', 'To address these needs, I propose a lightweight synchronization algorithm for offline-first applications operating with limited and intermittent connectivity.'),
('The proposed algorithm combines encrypted local storage, a persistent outgoing queue, adaptive batch sizes, and safe retries.', 'My proposed algorithm combines encrypted local storage, a persistent outgoing queue, adaptive batch sizes, and safe retries.'),
("A focused narrative literature review will guide the design. The prototype will support one append-only construction site-log workflow, motivated by the researcher's NBCC project context, using synthetic data. Evaluation will compare adaptive batching with two fixed batch limits under reproducible low-bandwidth and interruption profiles. It will measure encrypted save latency, completion time, request volume, attempted application bytes, memory use, and record integrity.", 'I will use a focused narrative literature review to guide the design. Drawing on my work on the NBCC management information system, I will build a prototype for one append-only construction site-log workflow using synthetic data. I will compare adaptive batching with two fixed batch limits under reproducible low-bandwidth and interruption profiles, measuring encrypted save latency, completion time, request volume, attempted application bytes, memory use, and record integrity.'),
('The intended contribution is a precisely specified algorithmic adaptation and evidence about its tradeoffs.', 'My intended contribution is a precisely specified algorithmic adaptation and evidence about its tradeoffs.'),
('The proposal does not assume that every connection can carry data or that adaptation will outperform fixed batching in every condition.', 'I will evaluate where adaptation helps and where fixed batching performs better, within conditions that allow data transfer.'),
('The study is motivated by my work on mis.nishatbrothers.com, the management information system for Nishat Brothers Construction Company (NBCC).', 'My motivation for this study comes from my work on mis.nishatbrothers.com, my management information system project for Nishat Brothers Construction Company (NBCC).'),
("The experiment will use synthetic construction site logs and an isolated prototype. Laboratory network settings will not be presented as measurements of every Afghan location or of NBCC's live system.", "I will use synthetic construction site logs and an isolated prototype. I will report the laboratory network settings as experimental conditions, without treating them as measurements of Afghan locations or NBCC's live system."),
('The research problem is to coordinate encrypted local persistence and reliable uploads without excessive client cost. The proposed algorithm will adjust a bounded batch limit using observed transfer outcomes. Its value will be tested against fixed limits under identical encryption, retry, and database rules.', 'The problem I address is how to coordinate encrypted local persistence and reliable uploads without excessive client cost. My proposed algorithm will adjust a bounded batch limit using observed transfer outcomes. I will test its value against fixed limits under identical encryption, retry, and database rules.'),
('The contribution will be an explicit application-level algorithm, its correctness argument, and a reproducible comparison. The narrative review will identify closely related approaches and refine the originality claim before implementation.', 'My contribution will be an explicit application-level algorithm, its correctness argument, and a reproducible comparison. I will use the narrative review to identify closely related approaches and refine the originality claim before implementation.'),
('To design and evaluate a lightweight synchronization algorithm that encrypts records before local persistence and automatically transfers queued records over a usable connection, while controlling batch size and preserving integrity during retries.', 'My aim is to design and evaluate a lightweight synchronization algorithm that encrypts records before local persistence and automatically transfers queued records over a usable connection, while controlling batch size and preserving integrity during retries.'),
('Review encrypted local persistence, outgoing queues, idempotency, and adaptive transmission through a focused narrative literature review.', 'I will review encrypted local persistence, outgoing queues, idempotency, and adaptive transmission through a focused narrative literature review.'),
("Specify the algorithm's data model, key lifecycle, transaction boundaries, adaptation rules, and recovery behavior.", "I will specify the algorithm's data model, key lifecycle, transaction boundaries, adaptation rules, and recovery behavior."),
('Implement one small PWA with adaptive and fixed batching policies sharing the same storage and security mechanisms.', 'I will implement one small PWA with adaptive and fixed batching policies sharing the same storage and security mechanisms.'),
('Evaluate local responsiveness, synchronization cost, resource use, and correctness under controlled connectivity conditions.', 'I will evaluate local responsiveness, synchronization cost, resource use, and correctness under controlled connectivity conditions.'),
('These are planned propositions and acceptance checks, not results already obtained.', 'I will test these propositions and acceptance criteria during the evaluation.'),
('The practical goal is to let people enter information once, keep it protected, and allow the application to manage delivery. The work connects database transactions and application state with cryptographic storage and scheduling. It will provide a documented algorithm, an encrypted outbox design, a reproducible prototype, and measured comparisons that include unfavorable cases.', 'My practical goal is to let people enter information once, keep it protected, and allow the application to manage delivery. I will connect database transactions and application state with cryptographic storage and scheduling, producing a documented algorithm, an encrypted outbox design, a reproducible prototype, and measured comparisons that include unfavorable cases.'),
('identifies the proposed algorithm in this study. Its existing cryptographic and control mechanisms will be attributed to their sources. Usefulness will be judged by measured behavior and clearly stated limits.', 'identifies my proposed algorithm. I will attribute its existing cryptographic and control mechanisms to their sources and assess its usefulness through measured behavior and clearly stated limits.'),
('The prototype includes one append-only site-log record type, one browser profile, one foreground worker, IndexedDB, and one relational server database.', 'I will limit the prototype to one append-only site-log record type, one browser profile, one foreground worker, IndexedDB, and one relational server database.'),
('The present study narrows that principle to one reporting workflow.', 'I apply that principle to one reporting workflow.'),
('The prototype will commit an encrypted record and its queue entry together, so every reported save has a corresponding delivery obligation.', 'In my prototype, an encrypted record and its queue entry will commit together, so every reported save has a corresponding delivery obligation.'),
('The prototype will derive a key from a passphrase at unlock, retain it in memory for that session, and avoid persisting the passphrase or raw key.', 'I will implement passphrase-based key derivation at unlock, keeping the key in memory for that session without persisting the passphrase or raw key.'),
('Unlocking has a cost that will be measured separately from subsequent saves.', 'I will measure the cost of unlocking separately from subsequent saves.'),
('The proposed rule is inspired by additive increase and multiplicative decrease, concepts documented in TCP congestion control [7].', 'I base the proposed rule on additive increase and multiplicative decrease, concepts documented in TCP congestion control [7].'),
('Each experimental policy will use the same retry timing.', 'I will use the same retry timing for each experimental policy.'),
("Those are the empirical questions of the study.", 'I will investigate those questions through the prototype evaluation.'),
('The study will follow design science: identify a problem, specify an artifact, implement it, and evaluate it against stated objectives [13]. A focused narrative review will inform the design using a documented selection rationale [14]. Searches will target offline-first applications, encrypted browser storage, transactional outboxes, idempotent synchronization, adaptive batching, and interrupted uploads.', 'I will follow a design science approach: identify the problem, specify an artifact, implement it, and evaluate it against stated objectives [13]. I will use a focused narrative review with a documented selection rationale to inform the design [14]. My searches will target offline-first applications, encrypted browser storage, transactional outboxes, idempotent synchronization, adaptive batching, and interrupted uploads.'),
('Google Scholar, accessible publisher repositories, and official specifications will provide the main sources. A log will record query, date, citation, mechanism, evidence type, and reason for inclusion. The synthesis will compare transaction boundaries, key management, retry identity, and evaluation methods. The review will not claim exhaustive coverage of the Afghan application market or treat product advertising as security evidence.', 'I will search Google Scholar, accessible publisher repositories, and official specifications. I will keep a log of each query, date, citation, mechanism, evidence type, and reason for inclusion. My synthesis will compare transaction boundaries, key management, retry identity, and evaluation methods. I will distinguish documented technical evidence from product advertising and keep the review focused on the research questions.'),
('The implementation will use a small JavaScript PWA, Web Crypto, IndexedDB, a single worker, and an HTTPS endpoint backed by SQLite. One available browser-capable device will be selected before the pilot; a workstation will host the server and controlled transport. Hardware, browser, runtime, source revision, and settings will be recorded. Performance conclusions will apply to that configuration.', 'I will implement a small JavaScript PWA using Web Crypto, IndexedDB, a single worker, and an HTTPS endpoint backed by SQLite. Before the pilot, I will select one available browser-capable device and use a workstation to host the server and controlled transport. I will record the hardware, browser, runtime, source revision, and settings, and limit performance conclusions to that configuration.'),
('The application will be installed and cached before offline tests.', 'I will install and cache the application before the offline tests.'),
('A starting setting of 600,000 iterations is informed by OWASP password-storage guidance [15], rather than a Web Crypto performance guarantee. Its cost will be benchmarked.', 'I will start with 600,000 iterations, informed by OWASP password-storage guidance [15], and benchmark the cost on the selected device.'),
('LSS follows three rules:', 'I have specified three rules for LSS:'),
('The initial and minimum body limit will be 2 KiB and the maximum 16 KiB.', 'I will set the initial and minimum body limit to 2 KiB and the maximum to 16 KiB.'),
('Settings will be frozen after the pilot and shared by all policies.', 'I will freeze the settings after the pilot and apply them consistently across all policies.'),
('Three policies will share the same encryption, database code, IDs, authentication, timeout, and retry rules: adaptive 2–16 KiB batches, fixed 2 KiB batches, and fixed 16 KiB batches. This tests adaptation against both ends of its permitted range without weakening either baseline.', 'I will compare three policies: adaptive 2–16 KiB batches, fixed 2 KiB batches, and fixed 16 KiB batches. All three will share the same encryption, database code, IDs, authentication, timeout, and retry rules, allowing me to test adaptation against both ends of its permitted range.'),
('The transport will document rate enforcement, outage behavior, and response-drop boundaries.', 'I will document how the transport enforces rates, models outages, and drops responses.'),
('Actual encrypted and request sizes will be recorded.', 'I will record the actual encrypted and request sizes.'),
('Paired runs share records and predetermined interruption and jitter seeds; policy order rotates.', 'I will use the same records and predetermined interruption and jitter seeds for paired runs and rotate the policy order.'),
('Incomplete runs remain reported as incomplete rather than receiving an invented completion time.', 'I will report incomplete runs explicitly and leave their completion times unassigned.'),
('Boundary tests cover restart after encrypted save;', 'I will test restart after encrypted save;'),
('Proposed usability targets are encrypted-save 95th-percentile latency below 100 ms, compressed initial application assets below 150 KiB, and observed synchronization heap growth below 10 MiB on the selected device.', 'My proposed usability targets are encrypted-save 95th-percentile latency below 100 ms, compressed initial application assets below 150 KiB, and observed synchronization heap growth below 10 MiB on the selected device.'),
('Unlock time is reported separately.', 'I will report unlock time separately.'),
('The study will report counts, medians, ranges, and paired differences by profile, including failures.', 'I will report counts, medians, ranges, and paired differences by profile, including failures.'),
('Storage inspection alone will not be described as a cryptographic proof.', 'I will use storage inspection as an implementation check, alongside authenticated-decryption tests.'),
('The analysis will explain unfavorable cases as carefully as favorable ones.', 'I will explain unfavorable cases as carefully as favorable ones.'),
('Measurements will check these design expectations rather than assume browser overhead is negligible.', 'I will measure whether the implementation meets these expectations, including the effect of browser overhead.'),
('The results will identify tested conditions rather than promise problem-free operation on the weakest possible internet. Encryption and unlocking costs will be reported explicitly.', 'I will state the tested conditions and report encryption and unlocking costs explicitly, so readers can judge where the findings apply.'),
("All records are synthetic and the prototype is isolated from NBCC's production MIS. Passphrases and plaintext are excluded from diagnostics.", "I will use only synthetic records and keep the prototype isolated from my NBCC MIS project. I will exclude passphrases and plaintext from diagnostics."),
('The outputs will be a focused narrative review, the LSS specification, three design diagrams, a prototype with three batching policies, and a reproducible report. The security contribution is correct use and evaluation of standard mechanisms within the synchronization design.', 'I will produce a focused narrative review, the LSS specification, three design diagrams, a prototype with three batching policies, and a reproducible report. My security contribution will be the correct use and evaluation of standard mechanisms within the synchronization design.'),
('The plan uses an available test device, a workstation, and open-source tools. It requires no company deployment or field survey. The defense presents the algorithm and research design; measured results follow implementation after approval.', 'I will carry out the work using an available test device, a workstation, and open-source tools, without requiring company deployment or a field survey. At my proposal defense, I will present the algorithm and research design. After approval, I will implement the prototype and collect the evaluation results.'),
('The research will determine whether adaptation gives a useful balance between speed, communication cost, and resource use.', 'I will evaluate whether adaptation gives a useful balance between speed, communication cost, and resource use.'),
]

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
xml_space = '{http://www.w3.org/XML/1998/namespace}space'
text = SOURCE.read_text(encoding='utf-8-sig')
with ZipFile(DOCX) as src:
    tree = etree.fromstring(src.read('word/document.xml'))
    paragraphs = tree.xpath('.//w:p', namespaces=ns)
    counts = []
    for old, new in replacements:
        assert text.count(old) == 1, ('source occurrence mismatch', old, text.count(old))
        found = 0
        for p in paragraphs:
            nodes = p.xpath('.//w:t', namespaces=ns)
            joined = ''.join(n.text or '' for n in nodes)
            start = joined.find(old)
            if start < 0:
                continue
            assert joined.count(old) == 1
            end = start + len(old)
            offset = 0
            inserted = False
            for node in nodes:
                value = node.text or ''
                node_end = offset + len(value)
                if node_end > start and offset < end:
                    left = max(0, start - offset)
                    right = min(len(value), end - offset)
                    node.text = value[:left] + (new if not inserted else '') + value[right:]
                    node.set(xml_space, 'preserve')
                    inserted = True
                offset = node_end
            found += 1
        assert found == 1, ('DOCX occurrence mismatch', old, found)
        text = text.replace(old, new)
        counts.append({'before': old, 'after': new})
    assert "researcher's" not in text.lower()
    with ZipFile(OUTPUT, 'w') as out:
        for info in src.infolist():
            value = src.read(info.filename)
            if info.filename == 'word/document.xml':
                value = etree.tostring(tree, encoding='UTF-8', xml_declaration=True, standalone=True)
            out.writestr(info, value)

backup = WORK / 'encrypted-proposal-before-author-voice.md'
if not backup.exists():
    shutil.copy2(SOURCE, backup)
SOURCE.write_text(text, encoding='utf-8')
(WORK / 'author-voice-changes.json').write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Applied {len(counts)} targeted revisions; preserved original DOCX structure and formatting.')
print(OUTPUT)
