from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

OUT = Path(__file__).parent / 'figures'
OUT.mkdir(exist_ok=True)
INK = '#203544'
BLUE = '#245875'
PALE = '#EEF4F8'
GREEN = '#EDF5EF'
AMBER = '#FAF3E7'

def font(n, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf', n)

def lines(draw, text, rect, size=34, bold=False, color=INK):
    x1,y1,x2,y2 = rect
    f=font(size,bold); rows=[]
    for para in text.split('\n'):
        row=''
        for w in para.split():
            test=(row+' '+w).strip()
            if draw.textlength(test,font=f)>x2-x1-28 and row:
                rows.append(row); row=w
            else: row=test
        rows.append(row)
    h=size+12; y=y1+(y2-y1-len(rows)*h)/2
    for row in rows:
        draw.text(((x1+x2-draw.textlength(row,font=f))/2,y),row,font=f,fill=color)
        y+=h

def box(draw,r,title,body='',fill=PALE):
    draw.rounded_rectangle(r,radius=14,fill=fill,outline=BLUE,width=3)
    x1,y1,x2,y2=r
    if body:
        lines(draw,title,(x1+10,y1+12,x2-10,y1+82),36,True)
        lines(draw,body,(x1+12,y1+84,x2-12,y2-10),33)
    else: lines(draw,title,(x1+12,y1+8,x2-12,y2-8),36,True)

def arrow(draw,pts,color=BLUE,width=4):
    draw.line(pts,fill=color,width=width,joint='curve')
    a,b=pts[-2:]; ang=math.atan2(b[1]-a[1],b[0]-a[0]); l=18
    draw.polygon([b,(b[0]-l*math.cos(ang-.48),b[1]-l*math.sin(ang-.48)),(b[0]-l*math.cos(ang+.48),b[1]-l*math.sin(ang+.48))],fill=color)

def canvas(h):
    im=Image.new('RGB',(1600,h),'white'); return im,ImageDraw.Draw(im)

im,d=canvas(1130)
lines(d,'Proposed architecture',(40,10,1560,80),40,True)
d.rounded_rectangle((45,110,960,940),radius=18,outline='#9BABB6',width=3)
lines(d,'BROWSER',(70,122,920,180),32,True)
box(d,(90,215,460,390),'PWA interface','Capture and view site logs')
box(d,(90,475,460,700),'IndexedDB','site_log + outbox\nOne local transaction')
box(d,(560,475,915,700),'Retry worker','One foreground worker\nSend or reconcile')
box(d,(560,215,915,390),'Service worker','Cache application shell')
arrow(d,[(560,300),(460,300)])
arrow(d,[(275,390),(275,475)])
lines(d,'save',(295,395,455,465),32)
arrow(d,[(460,585),(560,585)])
lines(d,'read queue',(490,715,940,775),32)
box(d,(1040,465,1545,745),'HTTP server','site_log + receipt\nOne SQL transaction\nUnique operation ID')
arrow(d,[(915,515),(975,515),(975,390),(1290,390),(1290,465)])
lines(d,'SUBMIT: ID + digest + full record',(945,240,1580,370),32)
arrow(d,[(915,645),(975,645),(975,830),(1290,830),(1290,745)])
lines(d,'STATUS: ID + digest',(1000,840,1570,910),32)
lines(d,'Receipt returns only after commit',(1015,950,1570,1040),32)
lines(d,'Application assets and business records have separate stores.',(60,955,950,1075),32)
im.save(OUT/'architecture.png',dpi=(300,300))

im,d=canvas(1340)
lines(d,'Client state transitions',(30,5,1570,80),40,True)
box(d,(50,145,440,300),'PENDING','Ready for submission')
box(d,(605,145,1000,300),'IN_FLIGHT','Saved before sending')
box(d,(1170,145,1550,300),'ACKNOWLEDGED','Matching receipt')
arrow(d,[(440,220),(605,220)])
lines(d,'send',(445,160,600,210),32)
arrow(d,[(1000,220),(1170,220)])
lines(d,'commit ACK',(1000,87,1170,195),31)
box(d,(605,440,1000,595),'UNCERTAIN','Outcome not confirmed',fill=AMBER)
arrow(d,[(800,300),(800,440)])
lines(d,'Timeout or restart',(830,315,1280,420),33)
box(d,(605,735,1000,895),'STATUS LOOKUP','Ask for stored receipt')
arrow(d,[(800,595),(800,735)])
lines(d,'When retry is due',(835,610,1290,720),33)
arrow(d,[(605,815),(370,815),(370,520),(605,520)])
lines(d,'Failed lookup:\nkeep UNCERTAIN\nand back off',(55,590,350,805),32)
box(d,(50,1090,480,1255),'PENDING','Receipt absent')
box(d,(585,1090,1015,1255),'ACKNOWLEDGED','Committed + digest match',fill=GREEN)
box(d,(1120,1090,1550,1255),'BLOCKED','Digest mismatch or\npermanent rejection',fill=AMBER)
arrow(d,[(690,895),(690,965),(265,965),(265,1090)])
arrow(d,[(800,895),(800,1090)])
arrow(d,[(910,895),(910,965),(1335,965),(1335,1090)])
lines(d,'Resume normal send',(50,1265,480,1325),30)
lines(d,'Retain local record',(585,1265,1015,1325),30)
lines(d,'Show reason to user',(1120,1265,1550,1325),30)
im.save(OUT/'states.png',dpi=(300,300))

im,d=canvas(1210)
lines(d,'Recovery after a lost acknowledgement',(30,5,1570,85),40,True)
box(d,(70,120,465,240),'Client + outbox')
box(d,(1135,120,1530,240),'Server + database')
for x in [270,1330]:
    for y in range(250,1090,24): d.line((x,y,x,y+12),fill='#A5AFB6',width=3)
arrow(d,[(270,330),(1330,330)])
lines(d,'SUBMIT operation ID, digest and record',(350,260,1250,325),34)
box(d,(1030,365,1560,505),'Atomic commit','Store record and receipt',fill=GREEN)
arrow(d,[(1330,560),(780,560)])
d.line((740,540,780,580),fill='#A14A37',width=6); d.line((740,580,780,540),fill='#A14A37',width=6)
lines(d,'Acknowledgement lost',(390,505,1030,555),34)
box(d,(35,595,520,740),'UNCERTAIN','Keep original operation ID',fill=AMBER)
arrow(d,[(270,825),(1330,825)])
lines(d,'STATUS operation ID + digest',(380,755,1220,815),34)
arrow(d,[(1330,945),(270,945)])
lines(d,'COMMITTED receipt + matching digest',(350,875,1250,935),34)
box(d,(35,1000,520,1160),'ACKNOWLEDGED','Local state updated',fill=GREEN)
lines(d,'The full record is not retransmitted in this recovery path.',(590,1020,1540,1150),34)
im.save(OUT/'sequence.png',dpi=(300,300))
print('Created architecture.png, states.png and sequence.png')
