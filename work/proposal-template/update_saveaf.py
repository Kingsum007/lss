import zipfile, xml.etree.ElementTree as ET, hashlib
from pathlib import Path
p=Path(r'C:\Users\sumir\Documents\ChatGPT\lss\outputs\MS Thesis Proposal.docx')
tmp=p.with_suffix('.tmp.docx'); NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main'; ET.register_namespace('w',NS); q=lambda x:f'{{{NS}}}{x}'
with zipfile.ZipFile(p,'r') as z:
    parts={n:z.read(n) for n in z.namelist()}
r=ET.fromstring(parts['word/document.xml']); body=r.find('w:body',{'w':NS})
def txt(el): return ''.join(x.text or '' for x in el.findall('.//w:t',{'w':NS}))
def mkpara(text,style):
    x=ET.Element(q('p')); pp=ET.SubElement(x,q('pPr')); ET.SubElement(pp,q('pStyle'),{q('val'):style}); run=ET.SubElement(x,q('r')); t=ET.SubElement(run,q('t')); t.text=text; return x
idx=next(i for i,x in enumerate(list(body)) if txt(x).startswith('2.3 Comparative Synthesis of Prior Work'))
new=[
 mkpara('2.2.1 Save.af as a Candidate Offline-First Case','Heading3'),
 mkpara('A targeted scoping search was conducted on 6 November 2026 for the exact domain and product name using the queries “save.af”, “save.af offline-first”, and “Save.af Afghanistan app”. Direct access to https://save.af failed because the domain could not be resolved during this check, and the exact-name web searches returned no indexed results. No peer-reviewed study, technical documentation, or independently verifiable product description for Save.af was identified in this search.', 'Normal'),
 mkpara('This is a search outcome, not evidence that Save.af does not exist or that its offline-first claim is false. Because no primary source could be retrieved, the claim cannot yet be coded as verified offline-first behavior, and Save.af is not counted as an empirical deployment in the synthesis. It is retained as a candidate gray-literature case pending an exact product link, archived page, application listing, technical documentation, or access to the system.', 'Normal'),
 mkpara('If documentation becomes available, the review will extract whether offline operation includes local durable writes, which functions remain usable without connectivity, how synchronization resumes, how concurrent edits are reconciled, and whether the claims have been tested under partitions or low-bandwidth conditions. Marketing language alone will be coded as a vendor claim, not as empirical validation.', 'Normal')]
for x in reversed(new): body.insert(idx,x)
parts['word/document.xml']=ET.tostring(r,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
    for n,d in parts.items(): z.writestr(n,d)
tmp.replace(p)
print('updated',p,'bytes',p.stat().st_size)
