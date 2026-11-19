# Design and Evaluation of an Offline-First PWA for Construction Site Logs
## A Database and Software Engineering Study at Nishat Brothers Construction Company

**Master of Science in Computer Science (Information Systems)**

Student: [Insert full name]  
Student ID: [Insert student ID]  
Supervisor: [Insert academic title and full name]  
Co-supervisor: [If applicable]  
Kabul University, Faculty of Computer Science, Department of Information Systems  
Submission date: 6 November 2026

## Proposal Submission and Approval

| Administrative item | Details |
| --- | --- |
| Proposed title | Design and Evaluation of an Offline-First PWA for Construction Site Logs: A Database and Software Engineering Study at Nishat Brothers Construction Company |
| Student name and ID | [Complete before submission] |
| Supervisor | Name: ____________________ Signature: ____________________ Date: __________ |
| Co-supervisor | Name: ____________________ Signature: ____________________ Date: __________ |
| Department chair | Name: ____________________ Signature: ____________________ Date: __________ |
| Proposal decision | [ ] Approved  [ ] Approved with revisions  [ ] Revision required |

## Abstract

Construction teams need to record routine site updates even when connectivity is interrupted. This proposal focuses on one bounded software-engineering problem: how a small progressive web application (PWA) can save a construction site-log entry to browser-local storage and synchronize it safely when a connection returns. Afghanistan’s connectivity indicators provide context, but they do not describe any particular NBCC site [1], [2], [4].

The study will combine a focused narrative literature review with design science and a controlled prototype evaluation. Using publicly accessible NBCC project descriptions and the researcher’s project context, it will define a minimal site-log record with synthetic test data. It will implement one PWA with a service worker, IndexedDB local persistence, a durable synchronization outbox, and a small server endpoint. It will not inspect or modify NBCC’s production MIS. The technical stack will be confirmed during the feasibility stage.

The experiment will compare a server-first baseline with local-first capture in three scenarios: online entry, offline entry followed by application restart, and reconnection with a repeated synchronization request. Primary outcomes will be successful capture, record durability, duplicate effects, and synchronization completion time. The study will not attempt multi-user conflict merging, broad device comparisons, or a market-wide application census. The planned deliverables are a narrative synthesis, a documented prototype, a reproducible test procedure, and design recommendations for this single workflow.

**Keywords:** progressive web application; IndexedDB; offline-first; synchronization; construction site log; software engineering; design science.

## Table of Contents

1. Chapter 1 Introduction  
2. Chapter 2 Literature Review  
3. Chapter 3 Research Methodology  
4. References  
5. Appendices

# CHAPTER 1: INTRODUCTION

## 1.1 Background of the Study

Many information systems assume a reliable connection to a central server. That assumption affects whether a user can open a record, save a form, or complete a transaction. An offline-first design makes local persistence available during disconnection and treats synchronization as a later operation. Local-first principles add user control and continued access to local data as design goals [3]. These ideas are relevant where work takes place across sites with changing connectivity, including construction projects.

Afghanistan’s connectivity indicators are incomplete and do not agree exactly. Available Afghanistan-wide statistics describe broad connectivity context but cannot establish the network conditions of an NBCC construction site [1], [2], [4]. The prototype will therefore use explicitly described laboratory offline and reconnect scenarios; it will make no claim about site-level coverage.

The researcher identifies mis.nishatbrothers.com as the NBCC company MIS. NBCC is a construction company. The system is relevant as a potential case through which to study project-information requirements and the design constraints of construction operations. Technical features will be described only when confirmed by materials the company makes available for this study. The proposal does not infer a PWA, IndexedDB, offline synchronization, field equipment interface, or any specific project workflow from the domain name alone.

## 1.2 Problem Statement

When a construction information system depends on continuous server access, an interruption can prevent a worker from viewing or recording information until the connection returns. A system that accepts local work but lacks a defined synchronization policy can instead create delayed, duplicated, overwritten, or inconsistent records. The engineering problem is to keep approved tasks usable while disconnected and to reconcile changes predictably without compromising record integrity.

The specific problem is how to persist and later submit a routine construction site-log entry without requiring a live server at the moment of capture, while avoiding loss or duplicate application during retry. The study does not evaluate NBCC’s current MIS. It will design and test an isolated prototype using synthetic site-log records.

## 1.3 Research Gap

Prior work describes local-first design, browser storage, service workers, and synchronization, while operational systems such as DHIS2 document local capture and later synchronization [3], [5]. The bounded gap addressed here is the lack of a small, reproducible evaluation that connects PWA client-side persistence and retry-safe synchronization to one construction site-log workflow. The contribution is an engineering prototype and controlled test, not a new synchronization algorithm or an evaluation of NBCC’s live system.

## 1.4 Research Aim

To design and evaluate a PWA-based local-persistence and synchronization approach for one construction site-log workflow, grounded in the NBCC context and tested with synthetic data.

## 1.5 Research Objectives

1. Synthesize database and software-engineering literature on offline-capable PWAs, browser-local persistence, and retry-safe synchronization using a focused narrative review.
2. Define a minimal site-log data model and functional requirements from the NBCC construction context, without accessing or changing the production MIS.
3. Implement one PWA prototype with service-worker asset caching, IndexedDB persistence, a durable outbox, and an idempotent synchronization endpoint.
4. Evaluate record capture, restart durability, duplicate prevention, and synchronization completion in a small, repeatable laboratory experiment.

## 1.6 Research Questions and Hypotheses

**RQ1.** What database and software-engineering practices support local persistence and reliable synchronization in offline-capable PWAs?

**RQ2.** What minimal data and interaction requirements are needed for an offline-capable construction site-log entry in the NBCC context?

**RQ3.** In online, offline/restart, and reconnect/retry scenarios, how does the PWA prototype compare with a server-first baseline in successful capture, durable record retention, duplicate effects, and synchronization completion time?

**H1.** During network disconnection, the local-first prototype will accept and retain site-log entries after application restart, while the server-first baseline will not complete a server-dependent submission.

**H2.** Repeating synchronization for the same queued entry will not create a second logical server record when the endpoint enforces the entry’s stable identifier.

These hypotheses concern one append-only record type and the defined test environment. The study will not implement or claim general multi-user conflict resolution.

## 1.7 Significance of the Study

The study will give the student a tested method for evaluating offline-first behavior through database persistence and synchronization. NBCC provides the construction context for the selected site-log workflow, while the prototype and data remain isolated from company systems. The reusable contribution will be a documented test procedure and design rationale for the defined prototype and scenarios. Conclusions will be limited to this workflow and test environment.

## 1.8 Expected Contributions

- A focused narrative synthesis of PWA storage and synchronization design evidence.
- A minimal site-log data model and requirements traceable to publicly accessible NBCC project context.
- A small PWA prototype and reproducible test procedure for one local persistence and synchronization workflow.
- Measured performance and correctness results under clearly specified laboratory conditions.
- A reference architecture that labels empirically tested elements separately from recommendations.

These are planned outputs. They are not completed results or promises of production deployment.

## 1.9 Scope, Delimitations, and Assumptions

The study covers one browser-based PWA, one append-only site-log record type, one local database (IndexedDB), one test synchronization endpoint, and synthetic records. The baseline is a server-first submission path; the proposed design commits locally and synchronizes later. Evaluation is limited to online entry, offline entry with application restart, and reconnect with a repeated request. The prototype is isolated from NBCC’s production MIS and will not process real project, personal, financial, safety, or contractual data. Multi-user concurrent editing, CRDTs, BLE/Wi-Fi Direct, field deployment, user interviews, broad device benchmarking, and market-wide PWA discovery are out of scope.

## 1.10 Operational Definitions and Abbreviations

| Term | Definition for this study |
| --- | --- |
| Offline-first | A design in which specified user operations use local state as their normal execution path and can complete without a live server connection. |
| Local durable write | A record is committed to local persistent storage and remains available after the application is closed and reopened. |
| Synchronization | Exchange of pending local changes and remote changes after a connection becomes available. |
| NBCC | Nishat Brothers Construction Company. |
| MIS | Management information system. |
| PWA | Progressive web application. |
| IndexedDB | Browser API for persistent structured client-side data. |

# CHAPTER 2: LITERATURE REVIEW

## 2.1 Core Concepts and Technical Foundations

### 2.1.1 Offline-first and local-first design

Offline-first engineering separates the user’s immediate operation from the availability of a remote service. A local database or durable queue accepts work, and synchronization transfers changes when connectivity returns. Local-first principles further emphasize local data access and user ownership [3]. For this study, an application will not be called offline-first merely because it caches pages or can display previously downloaded content. The classification will ask which operations work offline, whether writes persist across restart, and how updates are synchronized.

### 2.1.2 Local persistence and retry-safe synchronization

The client-side database and the application cache serve different purposes. A service worker can make the application shell available offline, while IndexedDB stores structured records that the user creates. A durable outbox records which local entries still need transmission. Stable entry identifiers and server-side uniqueness checks make a repeated request safe to retry. These mechanisms are central to the proposed prototype and differ from caching pages or relying on an ephemeral in-memory queue [12], [13].

The study will implement one append-only entry type, so it does not require automatic merging of simultaneous edits. Concurrent editing and CRDT comparisons are outside the scope; keeping them out allows the experiment to focus on persistence and retry correctness.

### 2.1.3 Evidence from field systems

The DHIS2 Android documentation describes local capture and later synchronization [5]. Open Data Kit (ODK) is a field data-collection precedent [6]. These systems provide useful operational context, but their data models differ from the single site-log entry in this study. The narrative review will report source limitations and will not treat vendor claims as independent performance evidence.

### 2.1.4 Afghanistan connectivity context

World Bank / ITU series estimates indicate internet use at 16.10 per 100 people in 2024, while fixed-broadband subscriptions were reported at 0.08 per 100 people in 2023 [1], [2], [4]. The measures have different definitions and years and should not be treated as direct measures of network reliability. The 2025 Afghanistan digital-infrastructure report also cautions that internet-penetration estimates are scarce and sometimes contradictory [4]. Accordingly, the study will use controlled network conditions to answer its performance questions and will not claim that a chosen impairment profile represents every Afghan province or construction site.

## 2.2 Review of Related Empirical and Technical Studies

The literature base is organized around database persistence, service-worker caching, synchronization reliability, and a small number of field-system precedents. The focused narrative review in Section 3.3 will explain how selected technical sources inform the prototype; it is not exhaustive.

### 2.2.1 Local-first systems

Kleppmann et al. articulate local-first software principles and discuss collaboration, local availability, and data ownership [3]. Their work supplies a design vocabulary but is not an evaluation of construction systems in Afghanistan. The proposed study translates applicable principles into operational checks: write availability during disconnection, durability after restart, controlled synchronization, and visible handling of conflicts.

### 2.2.2 Field data collection

ODK demonstrates a modular approach to collecting and managing field data in developing-region contexts [6]. DHIS2 documentation provides operational guidance for offline capture, metadata synchronization, queued data, and error correction [5]. This evidence supports evaluating offline capability as a set of operations and synchronization rules, rather than a binary marketing attribute. The review will record whether each source presents empirical measurements, deployment experience, implementation documentation, or a conceptual proposal.

### 2.2.3 Afghanistan and NBCC case materials

The public connectivity indicators establish that internet use and fixed-broadband subscription levels are limited, but cannot establish the network conditions or software design at NBCC. NBCC’s project portfolio and MIS may provide a useful construction-sector case. The researcher identifies the MIS at mis.nishatbrothers.com as their own project. Before any case-specific claim is included, the researcher will preserve the relevant project-page URL or approved export, record the access date, and distinguish publicly visible project descriptions from private system documentation. No claim about NBCC’s offline operation, database, synchronization, or particular modules is treated as established by this proposal alone.

### 2.2.4 Afghan product examples as contextual evidence

Public-facing materials for Sava.af, Parastoo, Dokandar, and Daftarak describe offline or local-first behavior in Afghan business contexts [8]–[11]. These descriptions are useful examples of product requirements and terminology. They are vendor or store claims rather than independent technical evaluations, and they do not establish a PWA architecture. They will be used only as contextual examples; this study will not conduct a market census or reverse engineer these products.

## 2.3 Comparative Synthesis of Prior Work

| Evidence source | What it can support | What it cannot establish for this study |
| --- | --- | --- |
| Local-first principles [3] | Design goals for local availability and data ownership | Performance of NBCC’s MIS or any particular site |
| PWA platform documentation [13] | Service-worker caching and IndexedDB as implementation building blocks | Reliability of this prototype until tested on its target browser |
| DHIS2 technical documentation [5] | A deployed example of local capture, queueing, and sync limitations | NBCC’s architecture or construction data requirements |
| World Bank / ITU and Afghanistan infrastructure sources [1], [2], [4] | National indicators and their known measurement limits | Site-level latency, outage frequency, or field-device behavior |
| NBCC project materials (pending authorized review) | Project context and candidate requirements, to the extent documented | Technical architecture unless system documentation or tests verify it |

The review will connect browser storage choices to software-engineering properties that can be tested: durable local writes, an outbox that survives restart, stable operation identifiers, idempotent server handling, and visible synchronization status. Evidence types will remain distinct: published platform behavior, vendor claims, design decisions, and measured prototype results will not be conflated.

## 2.4 Research Gap and Positioning of the Proposed Study

The literature supports a focused engineering question: how should a PWA separate static app-shell caching from persistent business records, and how can a client outbox and idempotent endpoint preserve one record through offline entry and retry? The proposed contribution is a single-workflow implementation and evaluation grounded in the NBCC context. It does not claim to survey all Afghan applications or establish the internal design of Sava.af, Parastoo, or NBCC’s current MIS.

## 2.5 Conceptual and Analytical Framework

The framework links work context to measurable system behavior. The context supplies approved workflow requirements and synthetic records. A local-first prototype accepts and persists operations locally, queues changes, and synchronizes over a constrained connection. Evaluation compares observed output with the generated ground-truth event log. Results inform architecture recommendations only within the tested scope.

**Figure 1. Proposed PWA data and synchronization architecture.**

[[FIG: architecture]]

# CHAPTER 3: RESEARCH METHODOLOGY

## 3.1 Research Approach and Design

The study uses design science to produce and evaluate one software artifact and a focused narrative literature review to inform its design . The experimental unit is one site-log entry and its lifecycle through local persistence and synchronization. The review is explanatory rather than exhaustive: it synthesizes selected foundational research, official platform documentation, and directly relevant deployed-system documentation.

The sequence is: (1) conduct a focused narrative search and synthesis; (2) define the minimal site-log schema; (3) implement the isolated PWA and server-first comparator; (4) execute the three test scenarios; (5) analyze record integrity and timing; and (6) refine the design recommendations and report limitations.

**Figure 2. Research workflow.**

[[FIG: workflow]]

## 3.2 Research Context, Population, Data Source, and Study Environment

NBCC supplies the construction context, not a production-system evaluation. The requirements source will be its publicly accessible project descriptions and the researcher’s knowledge of the project context, clearly labeled as contextual input. No interviews, staff records, or non-public operational data are required for the planned experiment. The test environment is a current desktop or Android browser supporting service workers and IndexedDB, a local development server, and a small test endpoint. Exact browser and runtime versions will be recorded.

The experimental environment will consist of an Android device representative of the available low-cost test hardware, a workstation running the synchronization endpoint, a local database, and a network impairment gateway. Exact models, OS versions, database version, and test-server configuration will be recorded before data collection. If physical low-cost hardware cannot be obtained, emulator results will be reported separately and will not be represented as physical-device measurements.

## 3.3 Focused Narrative Literature Review

The narrative review will focus on three technical themes: browser persistence and the distinction between Cache Storage for app assets and IndexedDB for structured records; service-worker lifecycle and offline application-shell behavior; and reliable synchronization patterns, including durable outboxes, stable operation identifiers, retries, idempotency, and acknowledgment semantics. Foundational distributed-systems work will be included only where it clarifies these mechanisms. DHIS2 and ODK provide field-system context, while Sava.af, Parastoo, Dokandar, and Daftarak serve as examples of Afghan product claims [8]–[11].

Sources will be selected from relevant peer-reviewed software-engineering/database publications, official web-platform documentation, and directly relevant technical/product documentation. Search will use Google Scholar and the university library where accessible, with targeted searches for PWA, service worker, IndexedDB, offline-first, outbox, idempotency, and synchronization. The review will prioritize sources that explain implementation mechanisms or report a deployed system. It will not claim exhaustive coverage, use PRISMA counts, or attempt to identify every offline-capable application in Afghanistan. A short search log will record date, query, source, and why each central source informs the design.

Synthesis will compare the data each mechanism stores, its persistence guarantees and limits, the trigger for synchronization, retry behavior, and the evidence supporting the claim. Promotional product statements will be identified as vendor claims rather than technical validation. The review will produce a concise architecture rationale and a traceability table connecting each design choice to a source or test requirement.

## 3.4 Variables, Constructs, and Operationalization

| Construct | Operational measure | Collection method |
| --- | --- | --- |
| Capture completion | Whether the baseline or PWA accepts the site-log entry in each scenario | Automated scenario result |
| Local durability | Whether an acknowledged local entry remains after application restart | IndexedDB readback and event log |
| Duplicate effect | Number of logical server rows created after the same entry is submitted repeatedly | Server database check by stable entry ID |
| Synchronization completion | Elapsed time from reconnection to server acknowledgment of queued entries | Monotonic timer and client/server log |
| Data integrity | Equality of expected and persisted entry IDs and field values | Deterministic comparison script |

## 3.5 Data Collection Instruments and Procedures

The narrative source log will capture citation, technical theme, mechanism, and evidence type. The prototype will use a small fixed synthetic dataset of append-only site-log entries with stable IDs and timestamps. No real company, employee, project-confidential, or personal data will be used. Each test scenario will start from a clean database, run the same prepared entries, and compare client and server state with an expected list. Browser, server, and code versions plus test logs will be retained.

## 3.6 Data Preparation and Preprocessing

Narrative sources will be grouped by technical theme and evidence type; overlapping sources will be consolidated in the synthesis. Test logs will be checked for missing entries, timestamp anomalies, malformed records, and environment deviations. Reruns and exclusions will be recorded.

## 3.7 Proposed Prototype and Synchronization Method

The prototype will support one append-only site-log entry with fields for project/site identifier, date-time, short work description, and quantity/unit where applicable. The PWA shell will be cached by a service worker; structured entries and the pending outbox will be stored in IndexedDB. Saving an entry and adding its outbox item will occur in one local transaction. Each entry will receive a stable identifier. On reconnection the client will submit queued IDs; the endpoint will enforce uniqueness and return an acknowledgment so a repeated request cannot create another logical row. Concurrent editing and merge conflicts are avoided by the append-only one-record scope and are not part of the prototype.

**Figure 3. Local persistence and retry-safe synchronization sequence.**

[[FIG: sync]]

## 3.8 Baseline and Test Scenarios

The comparator is a server-first form submission that requires an HTTP response before the entry is considered saved. The PWA uses local-first capture and foreground retry after reconnection. Three scenarios will be run: (1) connected capture; (2) disconnected capture, close/reopen, then inspect local durability; and (3) reconnect and submit the same outbox item twice. These scenarios isolate the intended database and synchronization behavior without an expansive network impairment matrix.

## 3.9 Evaluation Metrics and Success Criteria

The correctness criteria are: every locally acknowledged entry remains readable after restart; reconnecting transfers it to the server; a repeated submission does not create a duplicate server row; and client/server fields match the expected values. For each scenario, the test will record successful entries, failures, duplicates, and elapsed synchronization time. These are prototype acceptance criteria, not universal PWA standards.

## 3.10 Data Analysis

The same fixed dataset will be run 10 times per scenario after one pilot run; if time permits, repetitions may be increased before analysis. Results will be summarized with counts, medians, ranges, and simple scenario-to-scenario comparisons. The design does not depend on inferential tests or broad statistical generalization. Narrative findings will be organized by storage, app-shell caching, and retry-safe synchronization, then linked to implementation decisions and test outcomes.

## 3.11 Validity and Limitations

Synthetic entries may not reflect all field reporting needs; the study addresses persistence mechanics rather than user acceptance. Browser storage can be cleared or evicted, and browser behavior may vary; the target browser/version and storage state will be recorded. The lab scenario cannot establish reliability on every Android device or under real Afghan network conditions. Repeatable data, explicit scenario scripts, and logs will support reproducibility.

## 3.12 Ethics, Privacy, and Data Management

The prototype uses synthetic records and a test endpoint only. No interviews, personal data, credentials, or NBCC production data are required. Public NBCC project descriptions will be cited as context. The prototype will not connect to or modify the company MIS.

## 3.13 Reproducibility

The project will retain a narrative source log, synthetic test data, scenario script, software versions, test logs, and analysis file. Any shared artifact will contain no company or personal data.

## 3.14 Proposed Technical Design

### 3.14.1 System Architecture

The reference design has five components: PWA interface, service-worker app-shell cache, IndexedDB site-log and outbox, retrying synchronization client, and a test endpoint with a unique constraint on entry ID. The app exposes pending/synchronized status. It contains no general conflict-merging subsystem.

### 3.14.2 Major Components and Interfaces

- **PWA interface:** creates and displays append-only synthetic site-log entries.
- **Service worker:** caches the small application shell so the interface can reopen offline after an initial load.
- **IndexedDB:** stores entries and a pending outbox transactionally.
- **Sync client:** retries pending entries after connectivity returns and records acknowledgments.
- **Test endpoint:** inserts each stable entry ID once and returns the stored result.
- **Measurement script:** records scenario completion, durability, duplicate count, and synchronization time.

### 3.14.3 Implementation Plan and Technology Stack

The target is a standards-based PWA using a service worker and IndexedDB, with a small HTTP endpoint and relational server-side table enforcing a unique site-log ID. A lightweight frontend framework may be used if the feasibility pilot supports it. The evaluation will focus on the data lifecycle rather than framework comparison. Exact tools, versions, and licenses will be recorded before implementation. The project will use localhost or a university test host and will not deploy to NBCC infrastructure.

## 3.15 Expected Results and Research Outputs

The study will deliver a concise narrative review, one PWA site-log prototype, the three-scenario evaluation results, and a database/synchronization design rationale. No measured outcome is asserted in advance.

## 3.16 Anticipated Limitations, Risks, and Mitigation

| Risk or limitation | Mitigation |
| --- | --- |
| PWA scope grows beyond the time available | Implement one append-only record and three scenarios; defer all secondary features. |
| Browser clears or evicts local data | Record browser/version, use a clean controlled profile, and report storage limitations. |
| NBCC context is not representative of every contractor | Limit conclusions to the tested workflow and synthetic prototype. |
| Limited device/browser coverage | Test one primary browser/device configuration and state this as a boundary. |
| Test success may be confused with field readiness | Do not claim production suitability or site-level performance. |

## 3.17 Work Plan and Timeline

| Activity | Weeks 1–2 | Weeks 3–4 | Weeks 5–7 | Weeks 8–9 | Weeks 10–11 | Week 12 |
| --- | --- | --- | --- | --- | --- | --- |
| Narrative review and freeze scope | ■ |  |  |  |  |  |
| Site-log schema and test scenarios | ■ | ■ |  |  |  |  |
| PWA and server endpoint implementation |  | ■ | ■ |  |  |  |
| Pilot and three-scenario evaluation |  |  |  | ■ |  |  |
| Results analysis and design refinement |  |  |  |  | ■ |  |
| Thesis writing and supervisor revisions |  |  |  |  | ■ | ■ |

Weeks are relative to approval of the research plan. Scope is limited to the listed workflow and scenarios; extensions require supervisor approval and available time.

## 3.18 Resources and Budget

| Resource | Purpose | Availability / status | Cost |
| --- | --- | --- | --- |
| Browser-capable phone or workstation | PWA scenario testing | Existing device availability to confirm | Quote required only if unavailable |
| Workstation | Endpoint, test scripts, and analysis | Student/dept. availability to confirm | Quote required if unavailable |
| Test database and development tools | Prototype and log analysis | Open-source options planned | Verify licenses |

## REFERENCES

[1] Federal Reserve Bank of St. Louis, “Internet users for the Islamic Republic of Afghanistan,” FRED series ITNETUSERP2AFG, World Bank source via ITU. [Online]. Available: https://fred.stlouisfed.org/series/ITNETUSERP2AFG. Accessed: Nov. 6, 2026.

[2] World Bank, “Individuals using the Internet (% of population) – Afghanistan,” World Development Indicators, indicator IT.NET.USER.ZS. [Online]. Available: https://data.worldbank.org/indicator/IT.NET.USER.ZS?locations=AF. Accessed: Nov. 6, 2026.

[3] M. Kleppmann, A. Wiggins, P. van Hardenberg, and M. McGranaghan, “Local-first software: You own your data, in spite of the cloud,” in *Proc. ACM SIGPLAN Int. Symp. New Ideas, New Paradigms, and Reflections on Programming and Software (Onward! ’19)*, 2019, pp. 154–178, doi: 10.1145/3359591.3359737.

[4] International Media Support, *Digital Infrastructures in Afghanistan*, 2025. [Online]. Available: https://www.mediasupport.org/wp-content/uploads/2025/03/Digital_Infrastructres_Afghanistan_IMS.pdf. Accessed: Nov. 6, 2026.

[5] DHIS2, “DHIS2 Android App: Sync mechanism and offline-first design,” official documentation. [Online]. Available: https://docs.dhis2.org/en/full/use/dhis2-android-app.html. Accessed: Nov. 6, 2026.

[6] C. Hartung, Y. Anokwa, W. Brunette, A. Lerer, C. Tseng, and G. Borriello, “Open Data Kit: Tools to build information services for developing regions,” in *Proc. 4th ACM/IEEE Int. Conf. Information and Communication Technologies and Development*, 2010, pp. 1–12.

[7] K. Peffers, T. Tuunanen, M. A. Rothenberger, and S. Chatterjee, “A design science research methodology for information systems research,” *Journal of Management Information Systems*, vol. 24, no. 3, pp. 45–77, 2007, doi: 10.2753/MIS0742-1222240302.

[8] Sava.af, “Features and offline operation,” product documentation. [Online]. Available: https://sava.af/features/. Accessed: Nov. 6, 2026. Claims are vendor-reported and not independently tested in this proposal.

[9] Sayed K. Asghari, “Parastoo: Shop & Delivery,” Apple App Store product listing. [Online]. Available: https://apps.apple.com/gb/app/parastoo-shop-delivery/id6799033028. Accessed: Nov. 6, 2026. Offline-first details are developer-submitted listing claims.

[10] Karan Technology, “Frequently asked questions,” Dokandar. [Online]. Available: https://www.dokandar.af/en/faq. Accessed: Nov. 6, 2026.

[11] Karan, “Daftarak,” product page and support documentation. [Online]. Available: https://karan.af/en/products/daftarak and https://daftarak.app/en/support/. Accessed: Nov. 6, 2026.

[12] Mozilla Developer Network, “Offline and background operation,” *Progressive Web Apps*. [Online]. Available: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation. Accessed: Nov. 6, 2026.

[13] Mozilla Developer Network, “Progressive Web Apps reference,” including Cache Storage and IndexedDB. [Online]. Available: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Reference. Accessed: Nov. 6, 2026.

## APPENDIX A: Research Alignment Matrix

| Research question | Objective | Evidence | Method | Analysis | Output |
| --- | --- | --- | --- | --- | --- |
| RQ1: What practices support PWA persistence and synchronization? | 1 | Selected research and official technical documentation | Focused narrative literature review | Synthesis by storage, caching, retry, and acknowledgment | Design rationale |
| RQ2: What does one site-log workflow require? | 2 | NBCC public project context; synthetic record model | Requirements definition | Field and interaction mapping | Minimal schema |
| RQ3: How does local-first capture compare with server-first? | 3–4 | Prototype and deterministic test dataset | Three-scenario lab experiment | Capture, durability, duplicates, sync time | Prototype evaluation |

## APPENDIX B: Data Integrity and Evidence Rules

1. A national statistic is not a site-level network measurement.  
2. A product or company description is not independent performance evidence.  
3. A planned sample, test, or result is not reported as completed.  
4. A system component is attributed to NBCC only when an authorized source or direct test supports it.  
5. No feature is attributed to NBCC’s MIS unless an authorized source or direct test supports it.
