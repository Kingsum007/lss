from html.parser import HTMLParser
from pathlib import Path
class P(HTMLParser):
 def __init__(self):super().__init__();self.intext=False
 def handle_starttag(self,t,a):
  d=dict(a)
  if t in ['img','picture','source']:print('ASSET',t,d)
  if t in ['h1','h2','h3','p','li']:self.intext=True
 def handle_endtag(self,t):
  if t in ['h1','h2','h3','p','li']:self.intext=False;print()
 def handle_data(self,d):
  if self.intext and d.strip():
   s=d.strip()
   if any(k in s.lower() for k in ['offline','local','database','sync','همگام','آفلاین','sava','ساوا']):print('TEXT',s[:400])
html=Path(r'C:\Users\sumir\Documents\ChatGPT\lss\work\proposal-template\sava-home.html').read_text(encoding='utf-8',errors='ignore')
P().feed(html)
