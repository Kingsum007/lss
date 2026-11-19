from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.section import WD_SECTION
from PIL import Image
import re, copy, zipfile, hashlib
BASE=Path(r'C:\Users\sumir\Documents\ChatGPT\lss')
WORK=BASE/'work'/'algorithm-proposal'; REF=BASE/'MS Thesis Proposal Template.docx'
OUT=BASE/'outputs'/'MS Thesis Proposal - Lightweight Secure Offline Sync.docx'; MD=WORK/'encrypted-proposal.md'; FIG=WORK/'figures'
content=MD.read_text(encoding='utf-8-sig'); lines=content.splitlines()
chapter1=next(i for i,l in enumerate(lines) if l.startswith('# CHAPTER 1:'))
front=lines[:chapter1]; main=lines[chapter1:]
# source document includes three sections and institutional page furniture
D=Document(str(REF)); body=D._element.body
breaks=[copy.deepcopy(el) for el in list(body) if el.tag==qn('w:p') and el.find('.//'+qn('w:sectPr')) is not None]
finalsect=copy.deepcopy(body.find(qn('w:sectPr')))
for el in list(body): body.remove(el)
body.append(finalsect)
# helpers
NAVY='244C66'; BLUE='DCEAF2'; LIGHT='F3F6F8'; WHITE='FFFFFF'; GRAY='666666'
def set_repeat_table_header(row):
 trPr=row._tr.get_or_add_trPr(); rep=OxmlElement('w:tblHeader'); rep.set(qn('w:val'),'true'); trPr.append(rep)
def set_cell_shading(cell, fill):
 tcPr=cell._tc.get_or_add_tcPr(); shd=OxmlElement('w:shd'); shd.set(qn('w:fill'),fill); tcPr.append(shd)
def set_cell_margins(cell,top=70,start=90,bottom=70,end=90):
 tc=cell._tc; tcPr=tc.get_or_add_tcPr(); m=OxmlElement('w:tcMar')
 for side,val in [('top',top),('start',start),('bottom',bottom),('end',end)]:
  e=OxmlElement('w:'+side); e.set(qn('w:w'),str(val));e.set(qn('w:type'),'dxa');m.append(e)
 tcPr.append(m)
def format_run(run,size=None,bold=None,italic=None,color=None,font='Times New Roman'):
 run.font.name=font; run._element.get_or_add_rPr().rFonts.set(qn('w:ascii'),font);run._element.get_or_add_rPr().rFonts.set(qn('w:hAnsi'),font)
 if size:run.font.size=Pt(size)
 if bold is not None:run.bold=bold
 if italic is not None:run.italic=italic
 if color:run.font.color.rgb=__import__('docx').shared.RGBColor.from_string(color)
def add_rich(p,text,size=None):
 parts=re.split(r'(\*\*.*?\*\*|\*.*?\*|`.*?`)',text)
 for part in parts:
  if not part:continue
  bold=part.startswith('**') and part.endswith('**'); ital=part.startswith('*') and part.endswith('*') and not bold; code=part.startswith('`') and part.endswith('`')
  val=part[2:-2] if bold else part[1:-1] if (ital or code) else part
  r=p.add_run(val);format_run(r,size=size,bold=True if bold else None,italic=True if ital else None,font='Consolas' if code else 'Times New Roman')
 return p
def add_body(text,style='Proposal Body',align=None):
 p=D.add_paragraph(style=style);add_rich(p,text)
 if align is not None:p.alignment=align
 p.paragraph_format.keep_together=True
 return p
def add_caption(text):
 p=D.add_paragraph(style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;add_rich(p,text,size=9);p.paragraph_format.keep_with_next=True;return p
def add_table(rows):
 if not rows:return
 tab=D.add_table(rows=1,cols=len(rows[0]));tab.style='Table Grid';tab.alignment=WD_TABLE_ALIGNMENT.CENTER;tab.autofit=False
 maxw=6.0; colw=maxw/len(rows[0])
 for ri,row in enumerate(rows):
  cells=tab.rows[0].cells if ri==0 else tab.add_row().cells
  trPr=cells[0]._tc.getparent().get_or_add_trPr(); no_split=OxmlElement('w:cantSplit'); trPr.append(no_split)
  if ri==0:set_repeat_table_header(tab.rows[0])
  for ci,val in enumerate(row):
   c=cells[ci];c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;set_cell_margins(c)
   if ri==0:set_cell_shading(c,NAVY)
   elif ri%2==0:set_cell_shading(c,LIGHT)
   p=c.paragraphs[0];p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=1.0
   p.alignment=WD_ALIGN_PARAGRAPH.LEFT
   p.paragraph_format.keep_with_next=(ri==0 or (len(rows)<=7 and ri<len(rows)-1))
   add_rich(p,val,size=10)
   for r in p.runs:
    format_run(r,size=10,bold=(ri==0),color=WHITE if ri==0 else None)
   c.width=Inches(colw)
  for c in cells:c.width=Inches(colw)
 D.add_paragraph().paragraph_format.space_after=Pt(0)
 return tab
def add_figure(which):
 path=FIG/(which+'.png')
 p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=False;p.paragraph_format.keep_together=True
 run=p.add_run();run.add_picture(str(path),width=Inches(5.95))
def add_toc_field():
 p=D.add_paragraph();p.paragraph_format.space_after=Pt(6)
 r=OxmlElement('w:r');b=OxmlElement('w:fldChar');b.set(qn('w:fldCharType'),'begin');r.append(b);p._p.append(r)
 r=OxmlElement('w:r');instr=OxmlElement('w:instrText');instr.set(qn('xml:space'),'preserve');instr.text=' TOC \\o "1-2" \\h \\z \\u ';r.append(instr);p._p.append(r)
 r=OxmlElement('w:r');b=OxmlElement('w:fldChar');b.set(qn('w:fldCharType'),'separate');r.append(b);p._p.append(r)
 r=OxmlElement('w:r');t=OxmlElement('w:t');t.text='Right-click and update field in Word if the contents do not refresh automatically.';r.append(t);p._p.append(r)
 r=OxmlElement('w:r');b=OxmlElement('w:fldChar');b.set(qn('w:fldCharType'),'end');r.append(b);p._p.append(r)
def insert_break(node):
 body.insert(len(body)-1,node)
def table_lines(block):
 rows=[]
 for line in block.splitlines():
  vals=[x.strip() for x in line.strip().strip('|').split('|')]
  if all(re.fullmatch(r':?-{3,}:?',v) for v in vals):continue
  rows.append(vals)
 return rows
def parse_content(src,prelim=False):
 cur=[];table=[];in_toc=False
 def flush():
  nonlocal cur
  if cur:
   text=' '.join(x.strip() for x in cur).strip();cur=[]
   if text:add_body(text)
 i=0
 while i<len(src):
  line=src[i]
  if line.startswith('```'):
   flush();i+=1;code=[]
   while i<len(src) and not src[i].startswith('```'):code.append(src[i]);i+=1
   p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.LEFT;p.paragraph_format.line_spacing=1.0;p.paragraph_format.first_line_indent=Inches(0);p.paragraph_format.left_indent=Inches(0);p.paragraph_format.keep_together=True;p.paragraph_format.space_after=Pt(10)
   if code and code[0].startswith('SAVE('):p.paragraph_format.page_break_before=True
   r=p.add_run('\n'.join(code));format_run(r,size=9,font='Consolas');i+=1;continue
  if line.startswith('|'):
   flush();tb=[]
   while i<len(src) and src[i].startswith('|'):tb.append(src[i]);i+=1
   add_table(table_lines('\n'.join(tb)));continue
  if line.startswith('[[FIG:'):
   flush(); key=line[6:-2].strip();add_figure(key);i+=1;continue
  if line.startswith('# '):
   flush(); title=line[2:].strip()
   if title.startswith('CHAPTER'):
    if not prelim and not title.startswith('CHAPTER 1'):D.add_page_break()
    p=D.add_paragraph(style='Heading 1');add_rich(p,title);p.paragraph_format.keep_with_next=True
   else:
    if not prelim:D.add_page_break()
    p=D.add_paragraph(style='Heading 1');add_rich(p,title);p.paragraph_format.keep_with_next=True
   i+=1;continue
  if line.startswith('## '):
   flush();title=line[3:].strip()
   if prelim and title in ['Abstract','Table of Contents']:D.add_page_break()
   if title=='Table of Contents':
    p=D.add_paragraph(style='Heading 2');add_rich(p,title);add_toc_field();in_toc=True
   else:
    p=D.add_paragraph(style='Heading 2');add_rich(p,title);p.paragraph_format.keep_with_next=True
   i+=1;continue
  if line.startswith('### '):
   flush();p=D.add_paragraph(style='Heading 3');add_rich(p,line[4:].strip());p.paragraph_format.keep_with_next=True
   if line.startswith('### 3.4.2'):p.paragraph_format.page_break_before=True
   i+=1;continue
  if not line.strip():flush();i+=1;continue
  if re.match(r'^\[\d+\]',line):
   flush();p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.LEFT;p.paragraph_format.line_spacing=1.0;p.paragraph_format.left_indent=Inches(.25);p.paragraph_format.first_line_indent=Inches(-.25);p.paragraph_format.space_after=Pt(8);p.paragraph_format.keep_together=True;add_rich(p,line,size=10.5);i+=1;continue
  if in_toc and (re.match(r'^\d+\.',line.strip()) or line.startswith('4.') or line.startswith('5.')):i+=1;continue
  if line.startswith('**Figure'):
   flush();add_caption(line.strip('* '));i+=1;continue
  if line.startswith('- '):
   flush();p=D.add_paragraph(style='List Bullet');add_rich(p,line[2:].strip());i+=1;continue
  if re.match(r'^\d+\.\s',line):
   flush();p=D.add_paragraph(style='Normal');p.paragraph_format.left_indent=Cm(0.7);p.paragraph_format.first_line_indent=Cm(-0.55);p.add_run(re.match(r'^(\d+)\.',line).group(1)+'.  ');add_rich(p,re.sub(r'^\d+\.\s*','',line));i+=1;continue
  if line.startswith('`') and line.endswith('`'):
   flush();p=D.add_paragraph(style='macro');p.paragraph_format.left_indent=Cm(0.4);p.paragraph_format.right_indent=Cm(0.25);p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(6);add_rich(p,line[1:-1]);
   for r in p.runs:format_run(r,size=8.5,font='Consolas')
   i+=1;continue
  cur.append(line);i+=1
 flush()
# cover page with original university emblem from template
logo=BASE/'work'/'proposal-template'/'template-image.png';p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(8);p.add_run().add_picture(str(logo),width=Inches(1.25))
for txt,sty in [('KABUL UNIVERSITY','Title'),('FACULTY OF COMPUTER SCIENCE','Subtitle'),('DEPARTMENT OF INFORMATION SYSTEMS','Subtitle'),('THESIS PROPOSAL','Title')]:
 p=D.add_paragraph(style=sty);p.alignment=WD_ALIGN_PARAGRAPH.CENTER;add_rich(p,txt);p.paragraph_format.space_after=Pt(2)
p=D.add_paragraph(style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(12);p.paragraph_format.space_after=Pt(6);add_rich(p,'Design and Evaluation of a Lightweight Secure Synchronization Algorithm for Offline First Applications',size=16)
p=D.add_paragraph(style='Subtitle');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;add_rich(p,'A Database and Software Engineering Study for Intermittent Connectivity',size=12)
p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;add_rich(p,'Master of Science in Computer Science (Information Systems)',size=12)
D.add_paragraph()
meta=[('Student','[Insert full name]'),('Student ID','[Insert student ID]'),('Supervisor','[Insert academic title and full name]'),('Co-supervisor','[If applicable]'),('Submission date','15 November 2026')]
t=D.add_table(rows=0,cols=2);t.style='Table Grid';t.alignment=WD_TABLE_ALIGNMENT.CENTER
for a,b in meta:
 c=t.add_row().cells;c[0].text=a;c[1].text=b
 for cell in c:
  for pp in cell.paragraphs:
   pp.paragraph_format.space_after=Pt(0);pp.paragraph_format.line_spacing=1.0
   for rr in pp.runs:format_run(rr,size=10,bold=(cell==c[0]))
p=D.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;add_rich(p,'Kabul, Afghanistan',size=11)
if breaks:insert_break(breaks[0])
# preliminary submission/abstract/contents
appr=next(i for i,l in enumerate(front) if l.startswith('## Proposal Submission and Approval'))
parse_content(front[appr:],prelim=True)
if len(breaks)>1:insert_break(breaks[1])
parse_content(main,prelim=False)
# enable field refresh in Word
settings=D.settings._element
upd=settings.find(qn('w:updateFields'))
if upd is None:upd=OxmlElement('w:updateFields');settings.append(upd)
upd.set(qn('w:val'),'true')
# Set document metadata
D.core_properties.title='Design and Evaluation of a Lightweight Secure Synchronization Algorithm for Offline First Applications'
D.core_properties.subject='MS Thesis Proposal - Information Systems'
D.core_properties.author='[Student name]'
OUT.parent.mkdir(parents=True,exist_ok=True)
D.save(str(OUT))
# final package XML validation + summary
with zipfile.ZipFile(OUT) as z:
 for n in z.namelist():
  if n.endswith('.xml') or n.endswith('.rels'):
   import xml.etree.ElementTree as ET;ET.fromstring(z.read(n))
print('created',OUT,'bytes',OUT.stat().st_size,'sections',len(Document(str(OUT)).sections),'paragraphs',len(Document(str(OUT)).paragraphs),'tables',len(Document(str(OUT)).tables))

