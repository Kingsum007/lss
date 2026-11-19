import zipfile, xml.etree.ElementTree as ET
p=r'C:\Users\sumir\Documents\ChatGPT\lss\outputs\MS Thesis Proposal.docx'
z=zipfile.ZipFile(p)
for n in z.namelist():
 if n.endswith('.xml') or n.endswith('.rels'): ET.fromstring(z.read(n))
r=ET.fromstring(z.read('word/document.xml')); ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
a=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in r.findall('.//w:p',ns)]
print('NBCC and construction evidence:')
print('\n'.join(x for x in a if 'NBCC' in x or 'Nishat Brothers' in x))
print('false leftovers:',[(k,sum(k in x.lower() for x in a)) for k in ['petroleum transport','fuel imports','weighbridge','border customs','tanker','axle-weight']])
print('sections:',len(r.findall('.//w:sectPr',ns)),'paragraphs:',len(a))
