from docx import Document
from docx.oxml.ns import qn
p=r'C:\Users\sumir\Documents\ChatGPT\lss\MS Thesis Proposal Template.docx';d=Document(p);b=d._element.body
print('children',len(b));print('section break paras',[(i, e.tag.split('}')[-1]) for i,e in enumerate(b) if e.tag.endswith('}p') and e.find('.//'+qn('w:sectPr')) is not None]);print('sections',len(d.sections))
