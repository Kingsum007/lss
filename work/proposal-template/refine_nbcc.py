import zipfile,xml.etree.ElementTree as ET
from pathlib import Path
p=Path(r'C:\Users\sumir\Documents\ChatGPT\lss\outputs\MS Thesis Proposal.docx'); tmp=p.with_suffix('.tmp.docx'); N='http://schemas.openxmlformats.org/wordprocessingml/2006/main'; ET.register_namespace('w',N); q=lambda x:f'{{{N}}}{x}'; ns={'w':N}
with zipfile.ZipFile(p) as z: parts={n:z.read(n) for n in z.namelist()}
r=ET.fromstring(parts['word/document.xml'])
def txt(e):return ''.join(t.text or '' for t in e.findall('.//w:t',ns))
def setp(p,s):
 pp=p.find('w:pPr',ns);p.clear();
 if pp is not None:p.append(pp)
 run=ET.SubElement(p,q('r'))
 for i,line in enumerate(s.split('\n')):
  if i:ET.SubElement(run,q('br'))
  if line:
   t=ET.SubElement(run,q('t'));t.text=line
# fix remaining unsupported sector-specific passages
for p0 in r.findall('.//w:p',ns):
 s=txt(p0)
 if s.startswith('However, studies note that when inventory deductions occur across multiple disconnected border terminals'):
  setp(p0,'Distributed enterprise systems can face reconciliation challenges when multiple sites update records during connectivity interruptions. The review will assess relevant evidence and avoid attributing a specific synchronization mechanism or outcome to NBCC without technical documentation.')
 elif s.startswith('Preserves border clearance throughput'):
  setp(p0,'Construction project operations; outcomes to be established')
 elif 'Local Serial I/O (Weighbridges/POS)' in s:
  setp(p0,s.replace('Local Serial I/O (Weighbridges/POS)','Project/site interfaces (to be verified)'))
 elif s.startswith('1. Problem Identification: Grounded in field realities across Afghan health, logistics, and retail systems.'):
  setp(p0,'1. Problem Identification: Grounded in documented evidence from Afghan health, construction project operations, and retail systems.')
# scrub technology assertions from the NBCC table row. Keep classification while marking unknowns.
for tr in r.findall('.//w:tr',ns):
 cells=tr.findall('w:tc',ns)
 if cells and 'NBCC company MIS (mis.nishatbrothers.com)' in txt(tr):
  vals=['NBCC company MIS (mis.nishatbrothers.com)','Construction project operations (specific scope to verify)','To be verified from owner-approved technical documentation','To be verified','To be verified','Outcomes to be established empirically','To be verified']
  for c,v in zip(cells,vals):
   ps=c.findall('w:p',ns)
   if ps:setp(ps[0],v)
   for extra in ps[1:]: c.remove(extra)
parts['word/document.xml']=ET.tostring(r,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
 for n,d in parts.items(): z.writestr(n,d)
tmp.replace(p);print('refined unsupported NBCC architecture details')
