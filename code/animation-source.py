"""Generate original decorative GIFs for Kunal's GitHub profile.
Requires Pillow and numpy. All diagrams are illustrative, not live telemetry.
"""
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
ASSETS.mkdir(exist_ok=True)
W, S, N, DURATION = 850, 2, 64, 80
BG = (13, 17, 23)
BLUE = (88, 166, 255)
PURPLE = (163, 113, 247)
GREEN = (63, 185, 80)
CYAN = (57, 208, 202)
ORANGE = (247, 129, 102)
WHITE = (230, 237, 243)
MUTED = (139, 148, 158)
FONT_ROOT = Path('/usr/share/fonts/truetype/dejavu')
FONTS = {}
BACKGROUND_CACHE = {}


def font(size, bold=False, mono=False):
    name = 'DejaVuSansMono.ttf' if mono else ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    key = (size, name)
    if key not in FONTS:
        path = FONT_ROOT / name
        FONTS[key] = ImageFont.truetype(str(path), round(size * S)) if path.exists() else ImageFont.load_default()
    return FONTS[key]


def mix(a, b, t):
    t = min(1, max(0, t))
    return tuple(round(x * (1 - t) + y * t) for x, y in zip(a, b))


def xy(p):
    return tuple(round(x * S) for x in p)


def base(h):
    if h not in BACKGROUND_CACHE:
        yy, xx = np.mgrid[0:h*S, 0:W*S]
        x, y = xx/(W*S), yy/(h*S)
        a = np.exp(-(((x-.18)/.30)**2 + ((y-.50)/.8)**2))
        b = np.exp(-(((x-.88)/.28)**2 + ((y-.40)/.8)**2))
        rgb = np.zeros((h*S, W*S, 3), dtype=np.uint8)
        for k in range(3):
            rgb[:,:,k] = np.clip(BG[k] + a * [1,5,11][k] + b * [5,1,9][k], 0, 255)
        BACKGROUND_CACHE[h] = Image.fromarray(rgb)
    return BACKGROUND_CACHE[h].copy()


def text(im, x, y, value, size=13, color=WHITE, bold=False, mono=False, anchor='la'):
    ImageDraw.Draw(im).text(xy((x,y)), value, font=font(size,bold,mono), fill=color, anchor=anchor)


def line(im, points, color, width=1):
    ImageDraw.Draw(im).line([xy(p) for p in points], fill=color, width=max(1,round(width*S)), joint='curve')


def box(im, bounds, fill=(14,22,33), outline=(38,53,72), radius=9, width=1):
    ImageDraw.Draw(im).rounded_rectangle(xy(bounds), radius=round(radius*S), fill=fill, outline=outline, width=max(1,round(width*S)))


def ellipse(im, bounds, fill=None, outline=None, width=1):
    ImageDraw.Draw(im).ellipse(xy(bounds), fill=fill, outline=outline, width=max(1,round(width*S)))


class Glow:
    def __init__(self, im):
        self.im = im
        self.layer = Image.new('RGBA', im.size, (0,0,0,0))
        self.draw = ImageDraw.Draw(self.layer)
        self.core = []

    def dot(self, x, y, radius, color, strength=150):
        self.draw.ellipse(xy((x-radius*1.9,y-radius*1.9,x+radius*1.9,y+radius*1.9)), fill=(*color,strength))
        self.core.append(('dot',(x,y,radius),color,1))

    def path(self, points, color, width=2, strength=100):
        self.draw.line([xy(p) for p in points], fill=(*color,strength), width=round((width+5)*S), joint='curve')
        self.core.append(('line',points,color,width))

    def apply(self):
        layer = self.layer.filter(ImageFilter.GaussianBlur(4*S))
        self.im.paste(layer,(0,0),layer)
        for kind, data, color, width in self.core:
            if kind == 'dot':
                x,y,r = data
                ellipse(self.im,(x-r,y-r,x+r,y+r),fill=color)
            else:
                line(self.im,data,color,width)


def finish(im, h):
    return im.resize((W,h),Image.Resampling.LANCZOS)


def icon(im, kind, cx, cy, color, phase):
    d = ImageDraw.Draw(im)
    if kind == 'quest':
        line(im,[(cx-13,cy+13),(cx+13,cy-13)],color,3)
        line(im,[(cx-12,cy+4),(cx-3,cy+13)],color,2)
        d.polygon([xy((cx+8,cy-14)),xy((cx+16,cy-16)),xy((cx+14,cy-8))],fill=color)
    elif kind in ('check','shield'):
        points=[(cx-15,cy-15),(cx+15,cy-15),(cx+13,cy+5),(cx,cy+17),(cx-13,cy+5),(cx-15,cy-15)]
        line(im,points,color,2)
        line(im,[(cx-7,cy),(cx-1,cy+6),(cx+9,cy-6)],color,2.5)
    elif kind == 'reward':
        points=[]
        for j in range(10):
            a=-math.pi/2+j*math.pi/5
            r=17 if j%2==0 else 7
            points.append((cx+r*math.cos(a),cy+r*math.sin(a)))
        line(im,points+[points[0]],color,2)
        ellipse(im,(cx-3,cy-3,cx+3,cy+3),fill=color)
    elif kind in ('store','restore'):
        ellipse(im,(cx-17,cy-15,cx+17,cy-3),outline=color,width=2)
        line(im,[(cx-17,cy-9),(cx-17,cy+12)],color,2)
        line(im,[(cx+17,cy-9),(cx+17,cy+12)],color,2)
        for y in (cy+1,cy+12):
            d.arc(xy((cx-17,y-6,cx+17,y+6)),0,180,fill=color,width=round(2*S))
    elif kind in ('infer','model'):
        ellipse(im,(cx-9,cy-9,cx+9,cy+9),outline=color,width=2)
        for j in range(6):
            a=j*math.tau/6+phase*math.tau/6
            p=(cx+23*math.cos(a),cy+23*math.sin(a))
            q=(cx+10*math.cos(a),cy+10*math.sin(a))
            line(im,[q,p],color,1)
            ellipse(im,(p[0]-3,p[1]-3,p[0]+3,p[1]+3),fill=color)
    elif kind == 'track':
        line(im,[(cx-19,cy-17),(cx-19,cy+16),(cx+21,cy+16)],color,1.5)
        line(im,[(cx-15,cy+10),(cx-7,cy+1),(cx,cy+5),(cx+8,cy-10),(cx+16,cy-15)],color,2.5)
    elif kind in ('source','stt'):
        box(im,(cx-14,cy-18,cx+14,cy+17),fill=None,outline=color,radius=3,width=2)
        for y,w in [(cy-8,15),(cy,19),(cy+8,12)]:
            line(im,[(cx-9,y),(cx-9+w,y)],color,1.5)
    elif kind == 'clock':
        ellipse(im,(cx-17,cy-17,cx+17,cy+17),outline=color,width=2)
        a=phase*math.tau-math.pi/2
        line(im,[(cx,cy),(cx+12*math.cos(a),cy+12*math.sin(a))],color,2)
        line(im,[(cx,cy),(cx-6,cy-6)],color,2)
    elif kind == 'mic':
        box(im,(cx-7,cy-18,cx+7,cy+3),fill=None,outline=color,radius=6,width=2)
        d.arc(xy((cx-14,cy-10,cx+14,cy+13)),0,180,fill=color,width=round(2*S))
        line(im,[(cx,cy+12),(cx,cy+19)],color,2)
        line(im,[(cx-9,cy+19),(cx+9,cy+19)],color,2)
    else:
        points=[]
        for j in range(45):
            x=cx-22+j
            y=cy+math.sin(j*.38+phase*math.tau*2)*(7+4*math.cos(j*.13))
            points.append((x,y))
        line(im,points,color,2)


def pipeline(phase, title, labels, kinds, colors, footer, voice=False):
    h=174 if voice else 152
    im=base(h)
    box(im,(1,1,W-1,h-1),fill=None,outline=(35,49,67),radius=12)
    text(im,20,13,title,12,MUTED,bold=True)
    n=len(labels)
    centers=np.linspace(125 if n==4 else 155, W-125 if n==4 else W-155, n)
    cw=162 if n==4 else 220
    cy=70 if voice else 78
    top=36 if voice else 43
    bottom=105 if voice else 119
    hot=phase*n
    glow=Glow(im)
    for i in range(n-1):
        a,b=centers[i]+cw/2+4,centers[i+1]-cw/2-5
        line(im,[(a,cy),(b,cy)],(42,66,87),2)
        ImageDraw.Draw(im).polygon([xy((b-5,cy-4)),xy((b+1,cy)),xy((b-5,cy+4))],fill=(59,85,105))
        u=(hot-i)%n
        if u<1:
            for trail in range(5):
                q=u-trail*.065
                if q>=0:
                    x=a+(b-a)*q
                    glow.dot(x,cy,2.3+(.3 if trail==0 else 0),mix(BG,colors[i],1-trail*.16),130-trail*16)
    for i,cx in enumerate(centers):
        delta=min(abs(hot-i),n-abs(hot-i))
        activity=math.exp(-delta*delta/.30)
        col=mix((52,70,90),colors[i],.30+.70*activity)
        box(im,(cx-cw/2,top,cx+cw/2,bottom),fill=mix((15,24,35),colors[i],.018+.035*activity),outline=col,radius=9,width=1.2)
        if activity>.35:
            glow.path([(cx-cw/2+13,bottom),(cx+cw/2-13,bottom)],mix(BG,colors[i],activity),1.2,90)
        icon(im,kinds[i],cx,top+25,colors[i],phase)
        text(im,cx,bottom-14,labels[i],12,WHITE,bold=True,anchor='mm')
    if voice:
        points=[]
        for j in range(220):
            x=23+j*(W-46)/219
            envelope=max(0.0,math.sin(math.pi*j/219))**.75
            wave=(math.sin(j*.34+phase*math.tau*3)+.5*math.sin(j*.83-phase*math.tau*2))
            y=140+15*envelope*wave
            points.append((x,y))
        for j in range(len(points)-1):
            col=mix(CYAN,PURPLE,j/(len(points)-1))
            line(im,[points[j],points[j+1]],col,1.6)
        glow.path(points,CYAN,.8,55)
    glow.apply()
    if footer:
        text(im,20,h-18,footer,9,MUTED,mono=True)
    return finish(im,h)


def orbit(phase):
    h=238
    im=base(h)
    box(im,(1,1,W-1,h-1),fill=None,outline=(36,51,70),radius=13)
    d=ImageDraw.Draw(im)
    for x in range(20,335,23):
        line(im,[(x,34),(x,h-18)],(20,35,48),.6)
    for y in range(35,h-12,23):
        line(im,[(16,y),(331,y)],(20,35,48),.6)
    text(im,20,13,'SYSTEMS IN MOTION',12,MUTED,bold=True)
    cx,cy=184,133
    glow=Glow(im)
    for r in (46,76,99):
        ellipse(im,(cx-r,cy-r,cx+r,cy+r),outline=(35,54,75),width=.8)
    for r,c,speed in [(46,CYAN,-1),(76,BLUE,1),(99,PURPLE,-1)]:
        a=phase*360*speed
        for k in range(3):
            d.arc(xy((cx-r,cy-r,cx+r,cy+r)),a+k*120,a+k*120+36,fill=mix(BG,c,.55),width=round(2*S))
        angle=math.radians(a)
        for j in range(6):
            q=angle-j*.08
            glow.dot(cx+r*math.cos(q),cy+r*math.sin(q),2.8-j*.25,mix(BG,c,1-j*.12),140-j*15)
    labels=['BACKEND','DATA','LLM','VOICE','ML','UI']
    for k,label in enumerate(labels):
        a=k*math.tau/6-math.pi/2
        x,y=cx+76*math.cos(a),cy+76*math.sin(a)
        col=[BLUE,PURPLE,CYAN,GREEN,ORANGE,BLUE][k]
        glow.dot(x,y,4.2+.7*math.sin(phase*math.tau+k),col,140)
        tx,ty=cx+108*math.cos(a),cy+88*math.sin(a)
        text(im,tx,ty,label,8,MUTED,mono=True,anchor='mm')
    hexagon=[(cx+35*math.cos(k*math.tau/6+math.pi/6),cy+35*math.sin(k*math.tau/6+math.pi/6)) for k in range(6)]
    d.polygon([xy(p) for p in hexagon],fill=(15,28,44))
    glow.path(hexagon+[hexagon[0]],mix(BLUE,PURPLE,.5+.5*math.sin(phase*math.tau)),1.7,110)
    glow.apply()
    text(im,cx,cy-4,'AI',23,WHITE,bold=True,anchor='mm')
    text(im,cx,cy+18,'BUILD',8,MUTED,mono=True,anchor='mm')
    box(im,(354,39,825,213),fill=(10,18,28),outline=(40,58,79),radius=10)
    text(im,372,52,'kunal.profile',11,MUTED,mono=True)
    for j,c in enumerate([(247,129,102),(227,179,65),(63,185,80)]):
        ellipse(im,(774+j*14,53,780+j*14,59),fill=c)
    line(im,[(354,74),(825,74)],(36,51,70),1)
    rows=[
        ('focus = ["backend", "AI", "data"]',BLUE),
        ('loop  = build -> measure -> learn',CYAN),
        ('goal  = "AI infrastructure"',PURPLE),
        ('state = "learning + building"',GREEN)
    ]
    for j,(value,col) in enumerate(rows):
        text(im,373,88+j*27,value,12,col,mono=True)
    cursor=mix((26,54,67),CYAN,.4+.4*math.sin(phase*math.tau*2))
    line(im,[(684,191),(692,191)],cursor,2)
    return finish(im,h)


def divider(phase):
    h=16
    im=Image.new('RGB',(W*S,h*S),BG)
    line(im,[(8,8),(W-8,8)],(25,47,67),1)
    glow=Glow(im)
    for k,col in enumerate([BLUE,PURPLE,CYAN]):
        center=(phase*W+k*W/3)%W
        for trail in range(23):
            x=(center-trail*3)%W
            c=mix(BG,col,(1-trail/24)**1.6)
            glow.dot(x,8,1.25,c,round(95*(1-trail/24)))
        glow.dot(center,8,1.6,WHITE,120)
    glow.apply()
    return finish(im,h)


def save(name, painter):
    frames=[painter(i/N) for i in range(N)]
    # Use a shared palette so the GIFs do not shimmer from palette changes.
    sample=Image.new('RGB',(W,frames[0].height*4))
    for j,k in enumerate([0,N//4,N//2,3*N//4]):
        sample.paste(frames[k],(0,j*frames[0].height))
    palette=sample.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    pframes=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
    path=ASSETS/name
    pframes[0].save(path,save_all=True,append_images=pframes[1:],duration=DURATION,loop=0,disposal=2,optimize=False,comment=b'Original illustrative UI animation; not live telemetry.')
    with Image.open(path) as gif:
        assert gif.n_frames==N
        assert gif.info.get('loop')==0
        gif.seek(0); a=gif.convert('RGB')
        gif.seek(N//4); b=gif.convert('RGB')
        assert ImageChops.difference(a,b).getbbox() is not None
    cache=Path.home()/'.cache'/'profile-frames'
    cache.mkdir(parents=True,exist_ok=True)
    frames[N//4].save(cache/(name.replace('.gif','.png')))
    print(name,path.stat().st_size,'bytes',N,'frames',flush=True)


if __name__=='__main__':
    save('system-orbit.gif',orbit)
    save('quest-flow.gif',lambda t:pipeline(t,'QUESTBOUND / PROGRESSION LOOP',['QUEST','VALIDATE','REWARD'],['quest','shield','reward'],[BLUE,PURPLE,GREEN],'ILLUSTRATIVE FLOW  |  DETERMINISTIC RULES + SERVER-SIDE STATE'))
    save('datavortex-flow.gif',lambda t:pipeline(t,'DATAVORTEX / PIPELINE',['RESTORE','MODEL','TRACK'],['restore','model','track'],[GREEN,PURPLE,BLUE],'ILLUSTRATIVE FLOW  |  DATA INTEGRITY -> EVALUATION -> SIGNALS'))
    save('anaya-wave.gif',lambda t:pipeline(t,'ANAYA / ILLUSTRATIVE VOICE PIPELINE',['VOICE','STT','LLM','TTS'],['mic','stt','infer','respond'],[CYAN,BLUE,PURPLE,GREEN],'',voice=True))
    save('flowcare-provenance.gif',lambda t:pipeline(t,'FLOWCARE / PROVENANCE',['SOURCE','VERIFY','FRESHNESS'],['source','check','clock'],[BLUE,GREEN,PURPLE],'ILLUSTRATIVE FLOW  |  SOURCES + VERIFICATION + FRESHNESS'))
    save('system-pipeline.gif',lambda t:pipeline(t,'ENGINEERING / SYSTEM BOUNDARIES',['VALIDATE','STORE','INFER','RESPOND'],['check','store','infer','respond'],[BLUE,GREEN,PURPLE,CYAN],'ILLUSTRATIVE ARCHITECTURE  |  NOT LIVE SYSTEM TELEMETRY'))
    save('neon-divider.gif',divider)
