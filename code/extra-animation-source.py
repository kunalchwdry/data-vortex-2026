"""All-in additions: original decorative GIFs and a factual calendar snake.
The snake uses contribution intensity levels from the public GitHub calendar.
Its motion is decorative; the calendar is a dated snapshot, not a live feed.
"""
from pathlib import Path
from datetime import date, timedelta
import importlib.util
import argparse
import json
import math
import html
import re
from xml.etree import ElementTree
from PIL import ImageDraw

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'assets'
spec=importlib.util.spec_from_file_location('profile_animation_core',ROOT/'animation-source.py')
a=importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def cyberpunk(t):
    h=238
    im=a.base(h)
    a.box(im,(1,1,a.W-1,h-1),fill=None,outline=(35,52,73),radius=12)
    symbols='01{}<>[]'
    for col in range(39):
        x=14+col*22
        head=(t*h+col*37)%h
        for j in range(9):
            y=(head-j*19)%h
            strength=.48*(1-j/10)
            color=a.mix(a.BG,a.mix(a.BLUE,a.CYAN,(col%7)/6),strength)
            a.text(im,x,y,symbols[(col*3+j*5)%len(symbols)],10,color,mono=True)
    # A slow scan beam and orbiting edge particles add motion without flashing.
    g=a.Glow(im)
    scan=27+(h-54)*t
    g.path([(16,scan),(a.W-16,scan)],(35,76,106),.8,45)
    for k in range(8):
        theta=t*math.tau+k*math.tau/8
        x=660+148*math.cos(theta)
        y=119+83*math.sin(theta)
        g.dot(x,y,2,a.mix(a.BLUE,a.PURPLE,k/7),95)
    g.apply()
    a.text(im,43,51,'KUNAL',34,a.WHITE,bold=True)
    a.text(im,43,97,'CHOUDHARY',28,a.PURPLE,bold=True)
    a.text(im,46,145,'MISSION 2030',13,a.CYAN,mono=True)
    a.text(im,46,177,'AI  /  BACKEND  /  DATA',12,a.MUTED,mono=True)
    labels=['LEARN','BUILD','ITERATE']
    colors=[a.CYAN,a.BLUE,a.PURPLE]
    for i,label in enumerate(labels):
        top=36+i*57
        intensity=.35+.65*(.5+.5*math.cos(t*math.tau-i*math.tau/3))
        col=a.mix((38,55,73),colors[i],intensity)
        a.box(im,(484,top,806,top+43),fill=(12,23,35),outline=col,radius=8,width=1.2)
        a.ellipse(im,(504,top+17,512,top+25),fill=colors[i])
        a.text(im,529,top+13,label,12,a.WHITE,bold=True)
        x=719+61*((t*2+i/3)%1)
        a.line(im,[(704,top+23),(786,top+23)],(38,59,78),1)
        a.ellipse(im,(x-2,top+21,x+2,top+25),fill=colors[i])
    return a.finish(im,h)


def mascot(t):
    h=238
    im=a.base(h)
    a.box(im,(1,1,a.W-1,h-1),fill=None,outline=(35,52,73),radius=12)
    a.text(im,20,12,'BUILD MODE / GENERIC CODING MASCOT',12,a.MUTED,bold=True)
    bob=3*math.sin(t*math.tau)
    cx,cy=188,82+bob
    g=a.Glow(im)
    # Body, antenna, rounded head and blinking eyes.
    a.box(im,(143,119+bob,233,174+bob),fill=(19,34,51),outline=a.BLUE,radius=15,width=1.8)
    a.line(im,[(cx,cy-32),(cx,cy-46)],a.CYAN,2)
    g.dot(cx,cy-48,3.2,a.CYAN,105)
    a.box(im,(cx-58,cy-30,cx+58,cy+31),fill=(18,33,48),outline=a.CYAN,radius=17,width=1.8)
    blink=min(1,math.exp(-((t-.26)/.022)**2)+math.exp(-((t-.76)/.022)**2))
    eye_h=10*(1-.92*blink)
    for ex in (cx-24,cx+24):
        a.ellipse(im,(ex-10,cy-eye_h,ex+10,cy+eye_h),fill=a.BLUE)
    a.line(im,[(cx-12,cy+20),(cx+12,cy+20)],a.PURPLE,2)
    a.box(im,(164,138+bob,212,158+bob),fill=(11,24,36),outline=(41,72,92),radius=5)
    a.text(im,cx,149+bob,'{ }',12,a.GREEN,mono=True,anchor='mm')
    # Keyboard and alternating typing hands.
    a.box(im,(71,176,309,214),fill=(10,20,31),outline=(53,73,95),radius=8)
    for r in range(2):
        for c in range(13):
            x=81+c*17
            col=a.mix((30,52,70),a.BLUE,.12+.2*(.5+.5*math.sin(t*math.tau*3+c*.7+r)))
            a.box(im,(x,182+r*13,x+11,189+r*13),fill=col,outline=None,radius=2)
    for side in (-1,1):
        start=(cx+side*45,139+bob)
        elbow=(cx+side*72,155)
        hand=(cx+side*48,179+3*math.sin(t*math.tau*4+side*math.pi/2))
        a.line(im,[start,elbow,hand],a.BLUE,5)
        a.ellipse(im,(hand[0]-8,hand[1]-4,hand[0]+8,hand[1]+4),fill=a.CYAN)
    # Floating technology tags: labels, not proficiency ratings.
    for i,(label,x,y,col) in enumerate([('PY',55,82,a.GREEN),('TS',309,59,a.BLUE),('SQL',328,127,a.PURPLE)]):
        y+=5*math.sin(t*math.tau+i*1.2)
        a.box(im,(x-22,y-12,x+22,y+12),fill=(13,24,37),outline=col,radius=6)
        a.text(im,x,y,label,10,col,bold=True,anchor='mm')
    g.apply()
    a.box(im,(397,38,820,211),fill=(10,18,29),outline=(39,57,78),radius=10)
    a.text(im,414,51,'ideas.py',11,a.MUTED,mono=True)
    a.line(im,[(397,74),(820,74)],(35,51,71),1)
    code=[('def build_idea():',a.PURPLE),('    validate_inputs()',a.BLUE),('    measure_outcomes()',a.CYAN),('    iterate()',a.GREEN)]
    active=int(t*4)%4
    for i,(value,col) in enumerate(code):
        y=90+i*26
        if i==active:
            a.box(im,(407,y-5,805,y+20),fill=(17,30,45),outline=None,radius=4)
        a.text(im,416,y,value,12,col,mono=True)
    return a.finish(im,h)


def achievement(t):
    h=190
    im=a.base(h)
    gold=(255,209,102)
    a.box(im,(1,1,a.W-1,h-1),fill=None,outline=(65,58,42),radius=12)
    g=a.Glow(im)
    # Slow drifting confetti around a generic trophy, not an official seal.
    for i in range(26):
        x=25+(i*97)%795+9*math.sin(t*math.tau+i)
        y=(i*53+t*h)%h
        col=[gold,a.BLUE,a.PURPLE,a.GREEN][i%4]
        strength=.15+.15*(.5+.5*math.sin(t*math.tau+i))
        a.line(im,[(x,y),(x+3,y+5)],a.mix(a.BG,col,strength),1.2)
    cx,cy=164,79
    d=ImageDraw.Draw(im)
    d.arc(a.xy((cx-53,cy-28,cx-18,cy+12)),50,285,fill=gold,width=round(3*a.S))
    d.arc(a.xy((cx+18,cy-28,cx+53,cy+12)),255,490,fill=gold,width=round(3*a.S))
    cup=[(cx-33,cy-31),(cx+33,cy-31),(cx+26,cy+9),(cx+11,cy+28),(cx-11,cy+28),(cx-26,cy+9)]
    d.polygon([a.xy(p) for p in cup],fill=(138,101,36))
    g.path(cup+[cup[0]],gold,2,110)
    a.ellipse(im,(cx-33,cy-39,cx+33,cy-25),fill=(51,41,24),outline=gold,width=2)
    g.path([(cx,cy+27),(cx,cy+47)],gold,5,100)
    a.box(im,(cx-36,cy+47,cx+36,cy+61),fill=(70,55,26),outline=gold,radius=4,width=1.5)
    a.icon(im,'reward',cx,cy-2,gold,t)
    angle=t*math.tau
    for k in range(7):
        q=angle+k*math.tau/7
        g.dot(cx+76*math.cos(q),cy+65*math.sin(q),1.7,gold,70)
    g.apply()
    a.text(im,286,30,'ACHIEVEMENT UNLOCKED',12,gold,mono=True)
    a.text(im,286,58,'QUESTBOUND',25,a.WHITE,bold=True)
    a.text(im,286,101,'Grand Finale Finalist',20,gold,bold=True)
    a.text(im,286,140,'Tech Zephyr 4.0  /  IIT Bhubaneswar',12,a.MUTED)
    return a.finish(im,h)


def fetch_calendar(as_of):
    if as_of > date.today():
        raise ValueError('The export date cannot be in the future for your computer\'s local date.')
    import requests
    from bs4 import BeautifulSoup
    start=as_of-timedelta(days=364)
    cells={};sources=[]
    for year in range(start.year,as_of.year+1):
        url='https://github.com/users/kunalchwdry/contributions'
        response=requests.get(url,params={'from':f'{year}-01-01','to':min(as_of,date(year,12,31)).isoformat()},timeout=30)
        response.raise_for_status();sources.append(response.url)
        soup=BeautifulSoup(response.text,'html.parser')
        for cell in soup.select('[data-date][data-level]'):
            day=cell.get('data-date','');level=cell.get('data-level','')
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}',day) and level.isdigit():
                value=int(level)
                if 0<=value<=4 and start.isoformat()<=day<=as_of.isoformat():
                    cells[day]=value
    items=[{'date':day,'level':cells[day]} for day in sorted(cells)]
    if len(items)!=365:
        raise RuntimeError(f'Public calendar returned {len(items)} of 365 days; no missing values were fabricated.')
    data={'username':'kunalchwdry','sources':sources,'exported_at':as_of.isoformat(),'first_date':items[0]['date'],'last_date':items[-1]['date'],'cells':items}
    (ASSETS/'contribution-calendar.json').write_text(json.dumps(data,indent=2))
    return data


def snake_svg(data):
    assert len(data['cells'])==365
    dates={date.fromisoformat(x['date']):int(x['level']) for x in data['cells']}
    assert all(0<=level<=4 for level in dates.values())
    start=min(dates);end=max(dates)
    assert (end-start).days==364
    # Sunday-aligned weeks. Padding dates are dim outlines, not fake activity.
    origin=start-timedelta(days=(start.weekday()+1)%7)
    columns=((end-origin).days//7)+1
    pitch=(850-48)/columns
    cell=min(11,pitch-3)
    x0,y0=24,72
    colors=['#161b22','#0e4429','#006d32','#26a641','#39d353']
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="850" height="216" viewBox="0 0 850 216" role="img" aria-labelledby="title desc">']
    svg+=['<title id="title">Kunalchwdry contribution snake</title>',f'<desc id="desc">Public calendar from {start} to {end}, exported {html.escape(data["exported_at"])}. The moving snake is decorative; contribution levels are a static snapshot.</desc>']
    svg+=['<defs><filter id="snake-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>']
    svg+=['<rect x="1" y="1" width="848" height="214" rx="12" fill="#0d1117" stroke="#233349"/>','<text x="20" y="28" fill="#8b949e" font-family="DejaVu Sans, sans-serif" font-size="12" font-weight="700">KUNALCHWDRY / CONTRIBUTION SNAKE</text>','<text x="827" y="28" text-anchor="end" fill="#58a6ff" font-family="monospace" font-size="10">PUBLIC CALENDAR SNAPSHOT</text>']
    labeled=set()
    for column in range(columns):
        for row in range(7):
            day=origin+timedelta(days=column*7+row)
            x,y=x0+column*pitch,y0+row*16
            if day in dates:
                level=dates[day]
                svg.append(f'<rect x="{x:.2f}" y="{y}" width="{cell:.2f}" height="{cell:.2f}" rx="2" fill="{colors[level]}"><title>{day}: GitHub contribution intensity level {level}</title></rect>')
                if day.day==1 and (day.year,day.month) not in labeled:
                    labeled.add((day.year,day.month))
                    svg.append(f'<text x="{x:.2f}" y="57" fill="#8b949e" font-family="monospace" font-size="10">{day:%b}</text>')
            else:
                svg.append(f'<rect x="{x:.2f}" y="{y}" width="{cell:.2f}" height="{cell:.2f}" rx="2" fill="none" stroke="#233349" opacity=".2"/>')
    # A closed route traverses rows, then returns outside the calendar grid.
    centers=[]
    for row in range(7):
        order=range(columns) if row%2==0 else range(columns-1,-1,-1)
        centers.extend((x0+column*pitch+cell/2,y0+row*16+cell/2) for column in order)
    centers.extend([(824,184),(15,184),(15,centers[0][1]),centers[0]])
    path='M '+' L '.join(f'{x:.2f},{y:.2f}' for x,y in centers)+' Z'
    # Negative start times keep the body behind the head on the closed route.
    for k in range(15,0,-1):
        begin=-2+k*.025
        radius=3.9*(1-.035*k)
        opacity=.92-.035*k
        fill='#a371f7' if k<8 else '#58a6ff'
        svg.append(f'<circle r="{radius:.2f}" fill="{fill}" opacity="{opacity:.2f}" filter="url(#snake-glow)"><animateMotion dur="22s" begin="{begin:.3f}s" repeatCount="indefinite" calcMode="paced" path="{path}"/></circle>')
    svg.append(f'<g filter="url(#snake-glow)"><circle r="4.5" fill="#e6edf3"/><circle cx="1.8" cy="-1.5" r=".7" fill="#0d1117"/><circle cx="1.8" cy="1.5" r=".7" fill="#0d1117"/><animateMotion dur="22s" begin="-2s" repeatCount="indefinite" calcMode="paced" rotate="auto" path="{path}"/></g>')
    svg.append(f'<text x="20" y="201" fill="#8b949e" font-family="monospace" font-size="10">{start} to {end} | Exported {html.escape(data["exported_at"])} | Decorative motion, factual calendar levels</text>')
    svg.append('</svg>')
    content='\n'.join(svg)
    ElementTree.fromstring(content)
    p=ASSETS/'contribution-snake.svg'
    p.write_text(content)
    print(p.name,len(content.encode()),'bytes',len(data['cells']),'verified public-calendar days',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh-snake',action='store_true',help='Fetch the public calendar and regenerate only the snake')
    parser.add_argument('--as-of',default=date.today().isoformat())
    args=parser.parse_args()
    if args.refresh_snake:
        data=fetch_calendar(date.fromisoformat(args.as_of))
        snake_svg(data)
    else:
        a.save('cyberpunk-console.gif',cyberpunk)
        a.save('coding-mascot.gif',mascot)
        a.save('achievement-unlock.gif',achievement)
        data=json.loads((ASSETS/'contribution-calendar.json').read_text())
        snake_svg(data)
