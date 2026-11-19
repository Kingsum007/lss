from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

OUT=Path(__file__).parent/'figures'; OUT.mkdir(exist_ok=True)
INK='#203544'; BLUE='#245875'; PALE='#EEF4F8'; GREEN='#EDF5EF'; AMBER='#FAF3E7'
def font(n,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',n)
def text(d,s,r,size=33,bold=False):
    x1,y1,x2,y2=r; f=font(size,bold); rows=[]
    for para in s.split('\n'):
        row=''
        for w in para.split():
            t=(row+' '+w).strip()
            if d.textlength(t,font=f)>x2-x1-24 and row: rows.append(row);row=w
            else:row=t
        rows.append(row)
    h=size+9;y=y1+(y2-y1-len(rows)*h)/2
    for row in rows:
        d.text(((x1+x2-d.textlength(row,font=f))/2,y),row,font=f,fill=INK);y+=h
def box(d,r,title,body='',fill=PALE):
    d.rounded_rectangle(r,radius=12,fill=fill,outline=BLUE,width=3)
    x1,y1,x2,y2=r
    if body:
        text(d,title,(x1+8,y1+8,x2-8,y1+68),35,True)
        text(d,body,(x1+12,y1+72,x2-12,y2-8),32)
    else:text(d,title,(x1+10,y1+8,x2-10,y2-8),35,True)
def arrow(d,ps,color=BLUE):
    d.line(ps,fill=color,width=4,joint='curve');a,b=ps[-2:];ang=math.atan2(b[1]-a[1],b[0]-a[0]);l=17
    d.polygon([b,(b[0]-l*math.cos(ang-.48),b[1]-l*math.sin(ang-.48)),(b[0]-l*math.cos(ang+.48),b[1]-l*math.sin(ang+.48))],fill=color)
def canvas(h):
    im=Image.new('RGB',(1600,h),'white');return im,ImageDraw.Draw(im)

im,d=canvas(1020)
text(d,'Encrypted local storage and bounded synchronization',(30,5,1570,80),40,True)
box(d,(55,145,435,320),'PWA interface','Capture and view records')
box(d,(590,145,970,320),'Web Crypto','AES-GCM encryption')
box(d,(1120,145,1550,365),'IndexedDB','Ciphertext + outbox\nOne local transaction')
arrow(d,[(435,230),(590,230)]);arrow(d,[(970,230),(1120,230)])
box(d,(590,420,970,605),'Unlock key','Passphrase-derived\nMemory only',fill=AMBER)
arrow(d,[(780,420),(780,320)])
box(d,(55,420,435,605),'Service worker','Separate cache for\napplication assets')
arrow(d,[(245,420),(245,320)])
box(d,(1050,640,1550,885),'Sync worker','One foreground worker\nDecrypt one bounded batch\nPlaintext only in memory')
arrow(d,[(1330,365),(1330,640)])
text(d,'Queued\nciphertext',(1050,430,1310,540),32)
arrow(d,[(970,530),(1005,530),(1005,735),(1050,735)])
box(d,(55,700,590,920),'Main server','SQL records + receipts\nUnique operation IDs\nOne commit transaction')
arrow(d,[(1050,795),(590,795)])
text(d,'HTTPS submit',(615,710,1030,780),33)
arrow(d,[(590,875),(1020,875),(1020,850),(1050,850)])
text(d,'Committed receipts',(615,890,1030,955),32)
text(d,'Proposed prototype architecture',(35,952,1565,1010),30)
im.save(OUT/'architecture.png',dpi=(300,300))

im,d=canvas(1060)
text(d,'Local protection and synchronization states',(25,5,1575,80),40,True)
box(d,(60,135,435,285),'LOCKED','Ciphertext remains stored',fill=AMBER)
box(d,(600,135,1000,285),'UNLOCKED','Key available in memory',fill=GREEN)
arrow(d,[(435,210),(600,210)])
text(d,'unlock',(435,135,600,190),32)
text(d,'Only unlocked records can be submitted.',(1050,130,1550,290),32)
box(d,(60,410,435,575),'PENDING','Encrypted entry retained')
box(d,(600,410,1000,575),'IN_FLIGHT','State saved before send')
box(d,(1170,410,1550,575),'ACKNOWLEDGED','Committed receipts\nsaved locally',fill=GREEN)
arrow(d,[(800,285),(800,410)])
arrow(d,[(435,490),(600,490)])
text(d,'submit',(435,415,600,475),32)
arrow(d,[(1000,490),(1170,490)])
text(d,'valid ACK',(1005,410,1165,475),30)
arrow(d,[(800,575),(800,680),(245,680),(245,575)])
text(d,'Timeout or restart: retain original IDs',(80,690,990,770),33)
arrow(d,[(1000,535),(1080,535),(1080,860),(1170,860)])
box(d,(1170,770,1550,955),'PAUSED','Auth / validation block\nPreserve data',fill=AMBER)
box(d,(60,820,1020,980),'Bounded retry policy','Batch cap: 2–16 KiB\nRetry delay is bounded; pending records are retained')
im.save(OUT/'states.png',dpi=(300,300))

im,d=canvas(1100)
text(d,'Recovery when the server acknowledgement is lost',(25,5,1575,75),38,True)
box(d,(55,100,490,195),'Client + encrypted outbox')
box(d,(1090,100,1545,195),'Main server + SQL')
for x in [275,1315]:
    for y in range(210,1030,22):d.line((x,y,x,y+11),fill='#A5AFB6',width=3)
box(d,(40,225,510,365),'Offline save','Encrypt and commit locally')
arrow(d,[(275,420),(1315,420)])
text(d,'Usable connection: HTTPS batch with stable IDs',(365,365,1240,414),32)
box(d,(1050,455,1570,595),'Atomic SQL commit','Records + per-record receipts',fill=GREEN)
arrow(d,[(1315,640),(770,640)])
text(d,'ACK lost',(735,583,1035,635),32)
d.line((728,620,770,660),fill='#A14A37',width=6);d.line((728,660,770,620),fill='#A14A37',width=6)
box(d,(40,655,535,805),'Retain pending records','Keep IDs; halve batch cap\nWait before retry',fill=AMBER)
arrow(d,[(275,850),(1315,850)])
text(d,'HTTPS retry: same IDs; full records as needed',(360,805,1240,844),32)
arrow(d,[(1315,950),(275,950)])
text(d,'Stored receipts returned; no duplicate inserts',(360,897,1240,945),32)
box(d,(40,980,740,1080),'Commit local acknowledgement',fill=GREEN)
im.save(OUT/'sequence.png',dpi=(300,300))
print('Updated encrypted architecture, states and sequence diagrams')
