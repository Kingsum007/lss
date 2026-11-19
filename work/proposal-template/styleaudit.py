from docx import Document
p=r'C:\Users\sumir\Documents\ChatGPT\lss\MS Thesis Proposal Template.docx';d=Document(p)
for n in ['Normal','Proposal Body','Heading 1','Heading 2','Heading 3','Title','Subtitle','Caption','List Paragraph']:
 s=d.styles[n]; print(n,'font',s.font.name,s.font.size.pt if s.font.size else None,'bold',s.font.bold,'align',s.paragraph_format.alignment,'line',s.paragraph_format.line_spacing,'first',s.paragraph_format.first_line_indent)
print('tables', [x.name for x in d.styles if x.type==3][:30])
