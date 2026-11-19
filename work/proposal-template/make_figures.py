from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap, math
D=Path(r'C:\Users\sumir\Documents\ChatGPT\lss\work\proposal-template\figures'); D.mkdir(parents=True,exist_ok=True)
FONT=r'C:\Windows\Fonts\times.ttf'; BOLD=r'C:\Windows\Fonts\timesbd.ttf'
def font(size,bold=False):
 try:return ImageFont.truetype(BOLD if bold else FONT,size)
 except:return ImageFont.load_default()
def wrap_draw(draw, text, box, f, color=(20,30,40), max_lines=None, center=True):
 x1,y1,x2,y2=box; words=text.split(); lines=[]; cur=''
 for w in words:
  test=(cur+' '+w).strip()
  if draw.textbbox((0,0),test,font=f)[2] <= x2-x1-24: cur=test
  else:
   if cur: lines.append(cur)
   cur=w
 if cur:lines.append(cur)
 if max_lines and len(lines)>max_lines: lines=lines[:max_lines]; lines[-1]+='…'
 line_h=f.size+7; total=len(lines)*line_h; y=y1+(y2-y1-total)/2
 for line in lines:
  tw=draw.textbbox((0,0),line,font=f)[2]; x=x1+(x2-x1-tw)/2 if center else x1+8
  draw.text((x,y),line,font=f,fill=color); y+=line_h
def box(draw,rect,title,sub='',fill=(239,245,250),outline=(36,80,112)):
 draw.rounded_rectangle(rect,radius=18,fill=fill,outline=outline,width=3)
 x1,y1,x2,y2=rect
 if sub:
  wrap_draw(draw,title,(x1+8,y1+8,x2-8,(y1+y2)//2+5),font(27,True),max_lines=2)
  wrap_draw(draw,sub,(x1+12,(y1+y2)//2-3,x2-12,y2-8),font(20),max_lines=3)
 else:wrap_draw(draw,title,(x1+10,y1+8,x2-10,y2-8),font(25,True),max_lines=3)
def arrow(draw,a,b,color=(65,83,99),width=5):
 draw.line([a,b],fill=color,width=width); ang=math.atan2(b[1]-a[1],b[0]-a[0]); L=16
 p1=(b[0]-L*math.cos(ang-0.55),b[1]-L*math.sin(ang-0.55));p2=(b[0]-L*math.cos(ang+0.55),b[1]-L*math.sin(ang+0.55));draw.polygon([b,p1,p2],fill=color)
# Figure 1: official WDI/ITU data series
im=Image.new('RGB',(1200,700),'white');g=ImageDraw.Draw(im);g.text((90,28),'Individuals using the Internet in Afghanistan',font=font(34,True),fill=(20,30,40));g.text((90,75),'World Bank / ITU estimate, percent of population',font=font(23),fill=(60,70,80))
vals=[(2020,17.0485),(2021,16.5143),(2022,15.8663),(2023,15.9284),(2024,16.095)]
x0,y0,x1,y1=120,150,1060,565
for yv in [0,5,10,15,20]:
 y=y1-(yv/20)*(y1-y0);g.line((x0,y,x1,y),fill=(215,222,228),width=2);g.text((65,y-13),str(yv),font=font(20),fill=(70,80,90))
pts=[]
for i,(yr,v) in enumerate(vals):
 x=x0+i*(x1-x0)/(len(vals)-1);y=y1-(v/20)*(y1-y0);pts.append((x,y));g.text((x-25,y1+20),str(yr),font=font(22),fill=(40,50,60));g.text((x-33,y-42),f'{v:.2f}',font=font(21,True),fill=(30,78,112))
g.line(pts,fill=(32,107,151),width=6)
for x,y in pts:g.ellipse((x-9,y-9,x+9,y+9),fill=(32,107,151),outline='white',width=2)
g.text((90,625),'Source: World Bank WDI indicator IT.NET.USER.ZS (ITU-sourced series); downloaded 6 Nov 2026.',font=font(18),fill=(70,70,70))
im.save(D/'internet-use.png',dpi=(180,180))
# Figure 2 architecture
im=Image.new('RGB',(1500,760),'white');g=ImageDraw.Draw(im);g.text((60,24),'Proposed offline-first reference architecture',font=font(34,True),fill=(20,30,40))
box(g,(60,190,320,440),'User interface','Selected construction project records')
box(g,(390,160,680,470),'Local database','Durable records and transaction log')
box(g,(750,160,1040,470),'Sync outbox','IDs, versions, retries, acknowledgements')
box(g,(1110,195,1410,435),'Server endpoint','Validate, deduplicate, authorize')
arrow(g,(320,315),(390,315));arrow(g,(680,315),(750,315));arrow(g,(1040,315),(1110,315))
g.text((340,275),'local write',font=font(18),fill=(50,60,70));g.text((690,275),'enqueue',font=font(18),fill=(50,60,70));g.text((1050,275),'when online',font=font(18),fill=(50,60,70))
box(g,(480,555,900,680),'Conflict policy','Merge only defined operations; flag semantic conflicts',fill=(250,247,236),outline=(160,120,40))
arrow(g,(895,470),(740,555));arrow(g,(1260,435),(860,555))
g.text((65,710),'Proposed design only; it does not describe NBCC current implementation.',font=font(18),fill=(75,75,75));im.save(D/'architecture.png',dpi=(180,180))
# Figure 3 study workflow
im=Image.new('RGB',(1600,440),'white');g=ImageDraw.Draw(im);g.text((60,20),'Research workflow',font=font(34,True),fill=(20,30,40))
labels=[('Narrative review','Targeted search + synthesis'),('Workflow scope','One append-only site-log'),('Prototype','IndexedDB + outbox'),('Three scenarios','Online, restart, retry'),('Analysis','Integrity + sync time'),('Recommendations','Bounded to tested design')]
xs=[45,305,565,825,1085,1345]
for i,(t,s) in enumerate(labels):
 rect=(xs[i],140,xs[i]+215,320);box(g,rect,t,s)
 if i<len(labels)-1:arrow(g,(xs[i]+215,230),(xs[i+1]-10,230))
g.text((55,365),'Evidence sources remain distinct: literature, approved case material, and laboratory measurements.',font=font(21),fill=(60,70,80));im.save(D/'workflow.png',dpi=(180,180))
# Figure 5 sync
im=Image.new('RGB',(1450,650),'white');g=ImageDraw.Draw(im);g.text((55,24),'Local commit and synchronization lifecycle',font=font(34,True),fill=(20,30,40))
box(g,(50,160,330,355),'1. User operation','Create or edit a project record')
box(g,(390,160,670,355),'2. Atomic local commit','Persist record + outbox event')
box(g,(730,160,1010,355),'3. Connection available?','No: keep queued. Yes: send batch')
box(g,(1070,160,1370,355),'4. Server response','Validate, de-duplicate, acknowledge')
for a,b in [((330,255),(390,255)),((670,255),(730,255)),((1010,255),(1070,255))]:arrow(g,a,b)
box(g,(430,440,740,580),'Compatible updates','Apply documented deterministic merge')
box(g,(850,440,1180,580),'Semantic conflict','Keep both versions; request review',fill=(250,247,236),outline=(160,120,40))
arrow(g,(1210,355),(590,440));arrow(g,(1210,355),(1010,440))
g.text((55,605),'Acknowledgement follows durable local storage; unresolved conflicts remain visible and auditable.',font=font(20),fill=(60,70,80));im.save(D/'sync.png',dpi=(180,180))
print('created figures',len(list(D.glob('*.png'))))
