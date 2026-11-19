import zipfile, xml.etree.ElementTree as ET
from pathlib import Path
p=Path(r'C:\Users\sumir\Documents\ChatGPT\lss\outputs\MS Thesis Proposal.docx'); tmp=p.with_suffix('.tmp.docx')
NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main'; ET.register_namespace('w',NS); q=lambda x:f'{{{NS}}}{x}'
with zipfile.ZipFile(p) as z: parts={n:z.read(n) for n in z.namelist()}
r=ET.fromstring(parts['word/document.xml']); ns={'w':NS}
def get(p): return ''.join(t.text or '' for t in p.findall('.//w:t',ns))
def setp(p,s):
    pp=p.find('w:pPr',ns); p.clear()
    if pp is not None: p.append(pp)
    run=ET.SubElement(p,q('r'))
    # preserve paragraph line breaks as Word breaks
    for i,line in enumerate(s.split('\n')):
        if i: ET.SubElement(run,q('br'))
        if line:
            t=ET.SubElement(run,q('t')); t.text=line
            if line[:1].isspace() or line[-1:].isspace(): t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
updates={
'AAlthough individual systems': '',
}
# replacements keyed by unique leading phrases; rewrites remove unsupported prior descriptions.
repls=[
('Although individual systems in Afghanistan', 'Although individual systems in Afghanistan—such as the national health management information system (DHIS2), the Nishat Brothers Construction Company (NBCC) management information system (mis.nishatbrothers.com), and retail point-of-sale applications (parastoo.app)—have been identified as possible examples of offline-capable information systems, their architectures and offline behavior require source-based verification. There remains a need for an empirically validated architectural framework for offline-first information systems in low-resource environments.'),
('In Afghanistan, various organizations have developed ad-hoc solutions', 'In Afghanistan, organizations use information systems to support work in settings where connectivity may be unreliable. The Ministry of Public Health (MoPH) uses the District Health Information Software 2 (DHIS2) Android Capture application for health data collection. Nishat Brothers Construction Company (NBCC) operates the company management information system at mis.nishatbrothers.com. NBCC is a construction company, and this proposal treats its MIS as a construction-sector case. The system’s modules, local data storage, and synchronization behavior will be documented from the company’s project materials and technical evidence before being characterized. In local commerce, Afghan retailers also use point-of-sale and inventory applications such as Parastoo (parastoo.app); their offline features likewise require verification from product documentation.'),
('These failures produce severe real-world consequences:', 'Network interruptions can delay access to operational records and reporting. In health services, delayed data submission may affect timely monitoring. In construction project operations, connectivity loss may disrupt access to project information or reporting, but the effects and any offline procedures at NBCC will be established through company-approved project documentation rather than assumed. Retail operations provide a further comparison case whose offline behavior will be checked against product evidence.'),
('1.5 Research Objectives', '1.5 Research Objectives\n1. Analyze and Classify Existing Deployments (SLR): Systematically review and classify technical architectures, edge persistence mechanisms, and conflict-resolution strategies in production offline systems, including DHIS2 and, subject to evidence access, the NBCC company MIS and Parastoo.\n2. Formulate the ROFRA Architectural Model: Design a formal, five-layer software reference architecture that integrates embedded edge persistence, join-semilattice CvRDTs, logical clocks, and transport-agnostic synchronization abstractions.\n3. Develop a Functional Prototype Artifact: Implement an open-source, lightweight reference synchronization and storage engine using web and mobile primitives such as TypeScript, SQLite/IndexedDB, and Bluetooth Low Energy.\n4. Empirically Benchmark Performance: Evaluate the prototype against cloud-first and store-and-forward baselines across a testbed simulating degraded Afghan network conditions, including packet loss, variable latency, and multi-day partitions, using low-tier Android hardware.\n5. Formulate Technical Recommendations: Derive software engineering guidelines and deployment patterns tailored to public health, construction project operations, and commercial retail, with organization-specific recommendations limited to verified evidence.'),
('1.7 Significance of the Study', '1.7 Significance of the Study\nThis study has technical and practical value. It will evaluate consistency, replication overhead, and causal ordering under constrained connectivity. For Afghan enterprises and software teams, including construction organizations such as NBCC, the work may provide a reference architecture for resilient project information systems; recommendations about NBCC’s current system will depend on verified project and technical materials. For public health and humanitarian services, the study will examine how offline data capture can support work during connectivity interruptions, subject to reliable sources.'),
('#### Commercial Enterprise and Industrial Supply Chains', '#### Construction and Project-Based Enterprise Systems\nConstruction organizations coordinate information across offices and project sites, where connectivity conditions can vary. The proposed review will examine how project information systems preserve access to records and synchronize updates during interruptions, where technical or operational evidence is available.'),
('In Afghanistan, the proprietary portal mis.nishatbrothers.com', 'The user identifies mis.nishatbrothers.com as the NBCC company MIS. It is a relevant construction-sector case for this research. Its software architecture, offline functionality, storage mechanisms, and synchronization design have not been independently verified in the materials currently available; these characteristics will be established from the company’s project-section material and technical documentation before inclusion as empirical findings.'),
('Nishat Brothers MIS (2023)', 'NBCC company MIS (mis.nishatbrothers.com)'),
('Petroleum Logistics (Border Ports)', 'Construction project operations (specific modules to be verified)'),
('4. Demonstration: Implementing simulated scenarios derived from DHIS2, mis.nishatbrothers.com, and parastoo.app.', '4. Demonstration: Implementing synthetic scenarios based on published or owner-approved materials for DHIS2, the NBCC company MIS (mis.nishatbrothers.com), and retail systems; exclude confidential company data.'),
('3.2 Research Context, Population, Data Source, or Study Environment', '3.2 Research Context, Population, Data Source, or Study Environment\nThe experimental environment will represent low-resource mobile devices and, where relevant to NBCC’s documented workflows, construction project-office or site workstations. No system configuration or site workflow will be attributed to NBCC until confirmed from approved project materials.'),
('3.3 Sampling Strategy and Dataset Synthesis', '3.3 Sampling Strategy and Dataset Synthesis\nTo evaluate concurrency, transaction scale, and synchronization workloads, synthetic datasets will be generated. Health and retail datasets will follow their cited data models where sources permit. A construction-project dataset will be defined only after review of NBCC’s project-section materials and an owner-approved description of relevant record types. It will contain synthetic records only; no private operational or personal data will be used.'),
('3.11 Validity, Reliability, Robustness, and Threats to Validity', '3.11 Validity, Reliability, Robustness, and Threats to Validity\nConstruct validity: Metrics such as latency, throughput, and convergence will be captured using system timers and state comparisons. Internal validity: Potential confounders, including OS background tasks and device thermal throttling, will be controlled where feasible. External validity: Synthetic datasets will be based on documented source schemas; NBCC workflows and system behavior will not be generalized until company-approved evidence is reviewed. Performance may vary across device and operating-system configurations.'),
('Interfaces directly with weighbridges and thermal receipt printers.', 'Interfaces with construction project-office or site systems only where those interfaces are documented and included in the approved research scope.'),
('11. Nishat Brothers Group of Companies, "Management Information System (MIS) border point ingestion specifications," NBGC Technical Documentation, Kabul, Afghanistan, 2023.', '11. Nishat Brothers Construction Company (NBCC), company MIS and project-section materials for mis.nishatbrothers.com. Owner-provided source details and access date to be completed after verification; no technical claim is based on this entry until the source is reviewed.'),
]
# Fix accidental entry if ignored; apply startswith matching and update only first matching paragraph.
for old,new in repls:
    if not old: continue
    matches=[x for x in r.findall('.//w:p',ns) if get(x).startswith(old)]
    if matches: setp(matches[0],new)
# Generic reference to NBCC under significance, if embedded in another reflowed paragraph, handled above.
# Update named logistics dataset row in alignment matrix.
for x in r.findall('.//w:tc',ns):
    s=get(x)
    if 'Synthetic Health, Logistics, and Retail Datasets' in s:
        for p0 in x.findall('.//w:p',ns): setp(p0,'Synthetic health, construction-project (pending source review), and retail datasets')
# swap old bogus exact descriptive tokens anywhere still remaining in paragraphs to safe neutral wording
for x in r.findall('.//w:p',ns):
    s=get(x)
    if 'Nishat Brothers' in s and any(k in s.lower() for k in ['petroleum','weighbridge','customs','border port','fuel import']):
        s=s.replace('Petroleum Logistics (Border Ports)','Construction project operations (specific modules to be verified)')
        s=s.replace('petroleum logistics','construction project operations').replace('Petroleum Logistics','Construction Project Operations')
        s=s.replace('weighbridges','construction project systems').replace('Weighbridges','Construction project systems')
        s=s.replace('customs fiber cuts','connectivity interruptions').replace('border customs ports','construction project offices or sites')
        s=s.replace('fuel diversion and billing discrepancies','project-record synchronization errors')
        setp(x,s)
parts['word/document.xml']=ET.tostring(r,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
    for n,d in parts.items(): z.writestr(n,d)
tmp.replace(p)
print('updated',p)
