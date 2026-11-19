from docx import Document
p=r'C:\Users\sumir\Documents\ChatGPT\lss\MS Thesis Proposal Template.docx'; d=Document(p)
print([s.name for s in d.styles if s.type==1][:50])
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','List Paragraph','Table Grid']:
 try: print(name,'OK',d.styles[name].style_id)
 except KeyError: print(name,'missing')
