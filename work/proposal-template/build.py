import zipfile, xml.etree.ElementTree as ET, re, os, hashlib, copy
from pathlib import Path
src=Path(r'C:\Users\sumir\Documents\ChatGPT\lss\MS Thesis Proposal Template.docx')
txt=Path(r'C:\Users\sumir\.codex\attachments\12785a42-d773-44cd-a909-1cec83c1c5c5\Pasted text.txt')
out=Path(r'C:\Users\sumir\Documents\ChatGPT\lss\outputs\MS Thesis Proposal.docx')
NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main'; ET.register_namespace('w',NS)
q=lambda x:f'{{{NS}}}{x}'
content=txt.read_text(encoding='utf-8-sig').strip()
if content.startswith('```'): content=content[3:]
if content.endswith('```'): content=content[:-3]
lines=content.splitlines()
# Remove decorative ASCII title borders only
lines=[l for l in lines if not re.fullmatch(r'\s*[=]{8,}\s*',l)]
with zipfile.ZipFile(src) as z:
    files={n:z.read(n) for n in z.namelist()}
root=ET.fromstring(files['word/document.xml']); body=root.find('w:body',{'w':NS})
sectPs=[copy.deepcopy(x) for x in body if x.tag==q('p') and x.find('.//w:sectPr',{'w':NS}) is not None]
finalSect=copy.deepcopy(body.find('w:sectPr',{'w':NS}))
# Paragraph/table builders
def para(text='',style=None,bold=False,italic=False,center=False):
    p=ET.Element(q('p'))
    if style:
        pp=ET.SubElement(p,q('pPr')); ET.SubElement(pp,q('pStyle'),{q('val'):style})
    if center:
        pp=p.find('w:pPr',{'w':NS})
        if pp is None: pp=ET.SubElement(p,q('pPr'))
        ET.SubElement(pp,q('jc'),{q('val'):'center'})
    # simple inline markdown emphasis/code
    for i,part in enumerate(re.split(r'(\*\*.*?\*\*|\*.*?\*|`.*?`)',text)):
        if not part: continue
        r=ET.SubElement(p,q('r')); rp=None
        if part.startswith('**') or part.startswith('*') or part.startswith('`'):
            rp=ET.SubElement(r,q('rPr'))
            if part.startswith('**'): ET.SubElement(rp,q('b')); val=part[2:-2]
            elif part.startswith('*'): ET.SubElement(rp,q('i')); val=part[1:-1]
            else: val=part[1:-1]
        else: val=part
        t=ET.SubElement(r,q('t')); t.text=val
        if val[:1].isspace() or val[-1:].isspace(): t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    return p
def table(rows):
    tbl=ET.Element(q('tbl')); pr=ET.SubElement(tbl,q('tblPr')); ET.SubElement(pr,q('tblStyle'),{q('val'):'TableGrid'})
    borders=ET.SubElement(pr,q('tblBorders'))
    for edge in ('top','left','bottom','right','insideH','insideV'): ET.SubElement(borders,q(edge),{q('val'):'single',q('sz'):'4',q('color'):'A6A6A6'})
    for row in rows:
        tr=ET.SubElement(tbl,q('tr'))
        for cell in row:
            tc=ET.SubElement(tr,q('tc')); p=para(re.sub(r'\*\*|\*|`','',cell).strip())
            tc.append(p)
    return tbl
# find 1st-level sections
first=next((i for i,l in enumerate(lines) if l.startswith('# CHAPTER 1')),len(lines))
# Build body content based on markdown blocks, partition by chapter to preserve section breaks
# Handle all content uniformly, put section breaks after title block and TOC.
def parse_block(s):
    s=s.strip()
    if not s: return []
    if s.startswith('```'): return [para(x,'Normal') for x in s.splitlines()[1:-1] if x.strip()]
    if s.startswith('|'):
        rows=[]
        for ln in s.splitlines():
            cells=[x.strip() for x in ln.strip().strip('|').split('|')]
            if all(re.fullmatch(r':?-{3,}:?',c) for c in cells): continue
            rows.append(cells)
        return [table(rows)] if rows else []
    if s.startswith('# '): return [para(s[2:].strip(),'Heading1')]
    if s.startswith('## '): return [para(s[3:].strip(),'Heading2')]
    if s.startswith('### '): return [para(s[4:].strip(),'Heading3')]
    if s.startswith('* ') or s.startswith('- '):
        return [para(re.sub(r'^\s*[*-]\s+','• ',x),'ListParagraph') for x in s.splitlines()]
    if re.match(r'^\d+\.\s',s): return [para(x,'ListParagraph') for x in s.splitlines()]
    if s.startswith('>'): return [para(x.lstrip('> ').strip()) for x in s.splitlines()]
    return [para(x.strip()) for x in re.split(r'\n\s*\n',s) if x.strip()]
# Strip first cover ASCII/informal presentation and generate cover from content values
alltext='\n'.join(lines)
title=next((l[2:].strip() for l in lines if l.startswith('## ') and 'Architecting Resilient' in l),'Thesis Proposal')
cover=[para('KABUL UNIVERSITY','Title',center=True),para('FACULTY OF COMPUTER SCIENCE','Subtitle',center=True),para('DEPARTMENT OF INFORMATION SYSTEMS','Subtitle',center=True),para('THESIS PROPOSAL','Title',center=True),para(title,'Subtitle',center=True),para('Student Name     [Insert Full Name]'),para('Student ID       [Insert ID Number]'),para('MS Program       Master of Science in Computer Science (Information Systems)'),para('Supervisor       [Insert Academic Title and Full Name]'),para('Co-Supervisor    [Insert Academic Title and Full Name, if applicable]'),para('Semester / Academic Year    Fall Semester / Academic Year 1403–1404 (2024–2025)'),para('Submission Date    15 November 2024'),para('Kabul, Afghanistan     Academic Year 1403 (2024)')]
# Build sections from lines: cover then break, then content beginning Approval Page through TOC and chapter material
approval=next((i for i,l in enumerate(lines) if '## Proposal Submission and Approval Page' in l),0)
chapter=next((i for i,l in enumerate(lines) if l.startswith('# CHAPTER 1')),len(lines))
# parse region from approval onward; remove duplicate main title, decorative fence remnants
mid='\n'.join(lines[approval:chapter]); tail='\n'.join(lines[chapter:])
def blocks(text):
    result=[]; cur=[]; incode=False
    for line in text.splitlines():
        if line.strip().startswith('```'):
            if cur: result += parse_block('\n'.join(cur)); cur=[]
            incode=not incode; cur.append(line); continue
        if incode: cur.append(line); continue
        if not line.strip():
            if cur: result += parse_block('\n'.join(cur)); cur=[]
        else: cur.append(line)
    if cur: result+=parse_block('\n'.join(cur))
    return result
newchildren=cover+[sectPs[0]]+blocks(mid)+[sectPs[1]]+blocks(tail)
body.clear()
for el in newchildren: body.append(el)
body.append(finalSect)
files['word/document.xml']=ET.tostring(root,encoding='utf-8',xml_declaration=True)
out.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for n,data in files.items(): z.writestr(n,data)
print(out, out.stat().st_size)
print('template sha256',hashlib.sha256(src.read_bytes()).hexdigest())
print('preserved package parts',len(files))
